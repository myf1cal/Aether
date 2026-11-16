
import os
import sys
import tempfile
import threading
import time
import traceback

try:
    import psutil
    import customtkinter as ctk
except ImportError as e:
    sys.exit(f"Не хватает модуля '{e.name}'. Установи: pip install psutil customtkinter")

from config import (
    BG, SIDE, CARD, LINE, TEXT, DIM, GREEN, FONT, INTERVAL_MS, GAME_INTERVAL_MS,
    THEMES, tr, get_lang, set_lang, get_accent, get_theme, set_theme
)
from sensors import TelemetryCollector, fmt_up_sec
from pages import Overview, CpuPage, MemPage, DiskPage, NetPage, SensorPage, BenchPage, SysPage
from widgets import HeartbeatMonitor, fade_delayed

ctk.set_appearance_mode("dark")


def _darken(hex_col, factor=0.55):
    h = hex_col.lstrip("#")
    r, g, b = (int(h[i:i+2], 16) for i in (0, 2, 4))
    return (int(r * factor), int(g * factor), int(b * factor), 255)


def _hex_rgba(hex_col):
    h = hex_col.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4)) + (255,)


def create_app_icon(accent_hex="#6366f1"):
    try:
        from PIL import Image, ImageDraw
        size = 512
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        pad = 28
        top_col = _hex_rgba(accent_hex)
        bot_col = _darken(accent_hex, 0.52)

        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).rounded_rectangle([pad, pad, size - pad, size - pad], radius=128, fill=255)

        grad = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        g_draw = ImageDraw.Draw(grad)
        for y in range(pad, size - pad):
            t = (y - pad) / max(1, (size - 2 * pad))
            r = int(top_col[0] + (bot_col[0] - top_col[0]) * t)
            g = int(top_col[1] + (bot_col[1] - top_col[1]) * t)
            b = int(top_col[2] + (bot_col[2] - top_col[2]) * t)
            g_draw.line([(pad, y), (size - pad, y)], fill=(r, g, b, 255))

        img.paste(grad, (0, 0), mask)

        cx = size // 2
        top_y = 136
        bot_y = 376
        span = 106
        stroke = 42
        white = (255, 255, 255, 255)

        draw.line([(cx, top_y), (cx - span, bot_y)], fill=white, width=stroke)
        draw.line([(cx, top_y), (cx + span, bot_y)], fill=white, width=stroke)

        r_cap = stroke // 2
        for px, py in ((cx, top_y), (cx - span, bot_y), (cx + span, bot_y)):
            draw.ellipse([px - r_cap, py - r_cap, px + r_cap, py + r_cap], fill=white)

        bar_y = 296
        bar_x = 64
        bar_w = 36
        r_bar = bar_w // 2
        draw.line([(cx - bar_x, bar_y), (cx + bar_x, bar_y)], fill=white, width=bar_w)
        for px in (cx - bar_x, cx + bar_x):
            draw.ellipse([px - r_bar, bar_y - r_bar, px + r_bar, bar_y + r_bar], fill=white)

        return img.resize((256, 256), Image.Resampling.LANCZOS)
    except Exception:
        return None


class Aether(ctk.CTk):
    def __init__(self):
        super().__init__(fg_color=BG)
        self.title("Aether")
        self.geometry("980x680")
        self.minsize(860, 580)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.telemetry = TelemetryCollector()
        self._tray_icon = None
        self._tk_icons = []

        self._apply_window_icon()
        self.after(250, self._apply_window_icon)

        self.protocol("WM_DELETE_WINDOW", self.hide_to_tray)

        # Боковая панель
        side = ctk.CTkFrame(self, fg_color=SIDE, corner_radius=0, width=210)
        side.grid(row=0, column=0, sticky="ns")
        side.pack_propagate(False)

        logo_frame = ctk.CTkFrame(side, fg_color="transparent")
        logo_frame.pack(pady=(20, 2), padx=16, fill="x")
        ctk.CTkLabel(logo_frame, text="Aether", font=(FONT, 24, "bold"), text_color=TEXT).pack(anchor="w")

        # Живой сердечный ритм (кардиограмма)
        self.heartbeat = HeartbeatMonitor(side)
        self.heartbeat.pack(pady=(2, 2), padx=16, fill="x")

        # Плашка статуса Game Mode
        self.gm_badge = ctk.CTkLabel(side, text="", font=(FONT, 10, "bold"), text_color=GREEN, anchor="w")
        self.gm_badge.pack(pady=(0, 8), padx=16, fill="x")

        # Переключатель языка
        lang_frame = ctk.CTkFrame(side, fg_color="transparent")
        lang_frame.pack(pady=(2, 6), padx=14, fill="x")
        self.lang_lbl = ctk.CTkLabel(lang_frame, text=tr("lang_label"), font=(FONT, 11), text_color=DIM)
        self.lang_lbl.pack(side="left")

        self.lang_btn = ctk.CTkButton(
            lang_frame, text="EN ⇄ RU", width=72, height=26, corner_radius=8,
            font=(FONT, 10, "bold"), fg_color=LINE, hover_color=get_accent(), command=self.toggle_lang
        )
        self.lang_btn.pack(side="right")

        # Выбор цветовой темы
        theme_frame = ctk.CTkFrame(side, fg_color="transparent")
        theme_frame.pack(pady=(2, 12), padx=14, fill="x")
        self.theme_lbl = ctk.CTkLabel(theme_frame, text=tr("theme_label"), font=(FONT, 11), text_color=DIM)
        self.theme_lbl.pack(side="left")

        dots_box = ctk.CTkFrame(theme_frame, fg_color="transparent")
        dots_box.pack(side="right")
        self.theme_btns = {}
        for t_name, t_hex in THEMES.items():
            is_active = (t_name == get_theme())
            btn = ctk.CTkButton(
                dots_box, text="", width=16, height=16, corner_radius=8,
                fg_color=t_hex, hover_color=t_hex,
                border_width=2 if is_active else 0,
                border_color=TEXT,
                command=lambda n=t_name: self.change_theme(n)
            )
            btn.pack(side="left", padx=3)
            self.theme_btns[t_name] = btn

        # Контейнер страниц
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.grid(row=0, column=1, sticky="nsew", padx=16, pady=16)
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

        self.pages = {
            "Overview": Overview(self),
            "CPU": CpuPage(self),
            "Memory": MemPage(self),
            "Disks": DiskPage(self),
            "Network": NetPage(self),
            "Sensors": SensorPage(self),
            "Benchmark": BenchPage(self),
            "System": SysPage(self)
        }

        self.btns = {}
        self.current = None
        for name in self.pages:
            b = ctk.CTkButton(
                side, text="  " + tr(name), anchor="w", height=34, corner_radius=10,
                fg_color="transparent", hover_color=CARD, text_color=DIM,
                font=(FONT, 13, "bold"), command=lambda n=name: self.show(n)
            )
            b.pack(fill="x", padx=12, pady=2)
            self.btns[name] = b

        self.up = ctk.CTkLabel(side, text="", font=(FONT, 11), text_color=DIM)
        self.up.pack(side="bottom", pady=(0, 12))

        self.pin = ctk.CTkSwitch(
            side, text=tr("always_on_top"), font=(FONT, 11), text_color=DIM,
            progress_color=get_accent(),
            command=lambda: self.attributes("-topmost", bool(self.pin.get()))
        )
        self.pin.pack(side="bottom", pady=8)

        self._start_tray()
        self.show("Overview")
        self.tick()

    def _apply_window_icon(self):
        img = create_app_icon(get_accent())
        if img is None:
            return
        try:
            from PIL import Image, ImageTk
            if sys.platform == "win32":
                tmp = os.path.join(tempfile.gettempdir(), f"aether_v3_{get_theme().lower()}.ico")
                sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
                imgs = [img.resize(s, Image.Resampling.LANCZOS) for s in sizes]
                imgs[0].save(tmp, format="ICO", append_images=imgs[1:])
                self.iconbitmap(default=tmp)
            self._tk_icons = [
                ImageTk.PhotoImage(img),
                ImageTk.PhotoImage(img.resize((64, 64), Image.Resampling.LANCZOS)),
                ImageTk.PhotoImage(img.resize((32, 32), Image.Resampling.LANCZOS)),
            ]
            self.wm_iconphoto(True, *self._tk_icons)
        except Exception:
            pass

    def _start_tray(self):
        try:
            import pystray
            img = create_app_icon(get_accent())
            if img is None:
                return

            menu = pystray.Menu(
                pystray.MenuItem(lambda item: tr("tray_show"), self._on_tray_show, default=True),
                pystray.MenuItem(lambda item: tr("tray_quit"), self._on_tray_quit)
            )
            self._tray_icon = pystray.Icon("Aether", img, "Aether", menu)
            threading.Thread(target=self._tray_icon.run, daemon=True).start()
        except Exception:
            self._tray_icon = None

    def _update_tray_tooltip(self):
        if self._tray_icon is None:
            return
        try:
            d = self.telemetry.data
            cpu = d.get("cpu")
            mem = d.get("mem_pct")
            gpu_t = d.get("gpu_temps") or {}

            parts = ["Aether"]
            if cpu is not None:
                parts.append(f"CPU {cpu:.0f}%")
            if mem is not None:
                parts.append(f"RAM {mem:.0f}%")
            if gpu_t:
                g_val = next(iter(gpu_t.values()))
                parts.append(f"GPU {g_val:.0f}°C")
            if d.get("active_game"):
                parts.append("[Game Mode]")

            self._tray_icon.title = " · ".join(parts)[:127]
        except Exception:
            pass

    def hide_to_tray(self):
        if self._tray_icon is not None:
            self.withdraw()
        else:
            self.destroy()

    def _on_tray_show(self, icon=None, item=None):
        self.after(0, self._restore_window)

    def _restore_window(self):
        self.deiconify()
        self.lift()
        self.focus_force()
        self.after(50, self._apply_window_icon)

    def _on_tray_quit(self, icon=None, item=None):
        if self._tray_icon:
            self._tray_icon.stop()
        self.after(0, self.destroy)

    def change_theme(self, theme_name):
        set_theme(theme_name)
        acc = get_accent()

        for name, btn in self.theme_btns.items():
            btn.configure(border_width=2 if name == theme_name else 0)

        self.lang_btn.configure(hover_color=acc)
        self.pin.configure(progress_color=acc)
        self._apply_window_icon()

        if self._tray_icon is not None:
            new_img = create_app_icon(acc)
            if new_img is not None:
                self._tray_icon.icon = new_img

        for page in self.pages.values():
            page.on_theme_change()

        self.refresh_page()

    def toggle_lang(self):
        set_lang("RU" if get_lang() == "EN" else "EN")

        self.lang_lbl.configure(text=tr("lang_label"))
        fade_delayed(self.lang_lbl, SIDE, DIM, duration_ms=180)

        self.theme_lbl.configure(text=tr("theme_label"))
        fade_delayed(self.theme_lbl, SIDE, DIM, duration_ms=180)

        self.pin.configure(text=tr("always_on_top"))
        fade_delayed(self.pin, SIDE, DIM, duration_ms=180)

        for idx, (name, b) in enumerate(self.btns.items()):
            target_col = TEXT if name == self.current else DIM
            start_col = CARD if name == self.current else SIDE
            b.configure(text="  " + tr(name))
            fade_delayed(b, start_col, target_col, delay_ms=idx * 25, duration_ms=180)

        for page in self.pages.values():
            page.on_lang_change()

        self.refresh_page()
        self.after(35, self.pages[self.current].on_show)

    def show(self, name):
        if self.current == name:
            return
        if self.current:
            self.pages[self.current].grid_forget()
        self.current = name
        self.pages[name].grid(row=0, column=0, sticky="nsew")
        for n, b in self.btns.items():
            b.configure(
                fg_color=CARD if n == name else "transparent",
                text_color=TEXT if n == name else DIM
            )
        self.refresh_page()
        self.after(35, self.pages[name].on_show)

    def refresh_page(self):
        try:
            self.pages[self.current].refresh(self.telemetry.data, self.telemetry.hist)
        except Exception:
            traceback.print_exc()

    def tick(self):
        interval = INTERVAL_MS
        try:
            self.telemetry.collect()
            game = self.telemetry.data.get("active_game")
            if game:
                interval = GAME_INTERVAL_MS
                self.gm_badge.configure(text=f"● {tr('game_mode_active')} · {game}")
            else:
                self.gm_badge.configure(text="")

            self._update_tray_tooltip()

            if self.state() != "withdrawn":
                self.heartbeat.set_load(self.telemetry.data.get("cpu"))
                self.refresh_page()
                self.up.configure(text=f"{tr('uptime')}: " + fmt_up_sec(time.time() - psutil.boot_time()))
        except Exception:
            traceback.print_exc()
        finally:
            self.after(interval, self.tick)


if __name__ == "__main__":
    Aether().mainloop()