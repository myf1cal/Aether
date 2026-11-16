import math
import tkinter as tk
import customtkinter as ctk
from config import BG, SIDE, CARD, LINE, TEXT, DIM, OK, WARN, CRIT, GREEN, FONT, HIST, tr, get_accent


def level_color(v):
    return CRIT if v >= 90 else WARN if v >= 75 else OK


def _hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def _rgb_to_hex(rgb):
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(c))) for c in rgb)


def blend_color(c1, c2, t):
    r1, g1, b1 = _hex_to_rgb(c1)
    r2, g2, b2 = _hex_to_rgb(c2)
    return _rgb_to_hex((r1 + (r2 - r1) * t, g1 + (g2 - g1) * t, b1 + (b2 - b1) * t))


class _FadeManager:
    def __init__(self):
        self.tasks = {}
        self._running = False
        self._root = None

    def add(self, widget, start_hex, end_hex, delay_ms=0, duration_ms=180):
        if not widget.winfo_exists():
            return
        if self._root is None:
            self._root = widget.winfo_toplevel()
        widget.configure(text_color=start_hex)
        self.tasks[widget] = (_hex_to_rgb(start_hex), _hex_to_rgb(end_hex), 0, delay_ms, max(16, duration_ms))
        if not self._running:
            self._running = True
            self._root.after(16, self._tick)

    def _tick(self):
        if not self.tasks:
            self._running = False
            return

        done = []
        for w, (s_rgb, e_rgb, elapsed, delay, dur) in list(self.tasks.items()):
            if not w.winfo_exists():
                done.append(w)
                continue

            elapsed += 16
            if elapsed <= delay:
                self.tasks[w] = (s_rgb, e_rgb, elapsed, delay, dur)
                continue

            t = min(1.0, (elapsed - delay) / dur)
            eased = 1.0 - (1.0 - t) ** 3
            col = _rgb_to_hex((
                s_rgb[0] + (e_rgb[0] - s_rgb[0]) * eased,
                s_rgb[1] + (e_rgb[1] - s_rgb[1]) * eased,
                s_rgb[2] + (e_rgb[2] - s_rgb[2]) * eased,
            ))
            w.configure(text_color=col)

            if t >= 1.0:
                done.append(w)
            else:
                self.tasks[w] = (s_rgb, e_rgb, elapsed, delay, dur)

        for w in done:
            self.tasks.pop(w, None)

        if self.tasks and self._root and self._root.winfo_exists():
            self._root.after(16, self._tick)
        else:
            self._running = False


class _BarManager:
    def __init__(self):
        self.bars = {}
        self._running = False
        self._root = None

    def add(self, bar_row, delay_ms=0):
        if not bar_row.winfo_exists():
            return
        if self._root is None:
            self._root = bar_row.winfo_toplevel()
        self.bars[bar_row] = delay_ms
        if not self._running:
            self._running = True
            self._root.after(16, self._tick)

    def _tick(self):
        if not self.bars:
            self._running = False
            return

        done = []
        for row, delay in list(self.bars.items()):
            if not row.winfo_exists():
                done.append(row)
                continue

            if delay > 0:
                self.bars[row] = delay - 16
                continue

            diff = row._target_pct - row._cur_pct
            if abs(diff) < 0.08:
                row._cur_pct = row._target_pct
                done.append(row)
            else:
                row._cur_pct += diff * 0.24

            row._apply_visual()

        for row in done:
            self.bars.pop(row, None)

        if self.bars and self._root and self._root.winfo_exists():
            self._root.after(16, self._tick)
        else:
            self._running = False


_FADER = _FadeManager()
_BAR_ANIM = _BarManager()


def fade_text(widget, start_hex, end_hex, steps=10, delay_ms=16, step=0):
    _FADER.add(widget, start_hex, end_hex, delay_ms=0, duration_ms=steps * delay_ms)


def fade_delayed(widget, start_hex, end_hex, delay_ms=0, duration_ms=180):
    _FADER.add(widget, start_hex, end_hex, delay_ms=delay_ms, duration_ms=duration_ms)


class HeartbeatMonitor(ctk.CTkFrame):

    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self.w = 176
        self.h = 26
        self.canvas = tk.Canvas(self, width=self.w, height=self.h, bg=SIDE, highlightthickness=0)
        self.canvas.pack(fill="x")
        self._phase = 0.0
        self._load = 10.0  
        self._samples = [0.0] * 48
        self._animate()

    def set_load(self, cpu_pct):
        if cpu_pct is not None:
            self._load = max(0.0, min(100.0, float(cpu_pct)))

    def _ecg_wave(self, t):
        if 0.12 <= t < 0.20:
            return 0.18 * math.sin((t - 0.12) / 0.08 * math.pi)
        if 0.28 <= t < 0.32:
            return -0.22 * math.sin((t - 0.28) / 0.04 * math.pi)
        if 0.32 <= t < 0.38:
            return 1.0 * math.sin((t - 0.32) / 0.06 * math.pi)
        if 0.38 <= t < 0.43:
            return -0.35 * math.sin((t - 0.38) / 0.05 * math.pi)
        if 0.55 <= t < 0.70:
            return 0.26 * math.sin((t - 0.55) / 0.15 * math.pi)
        return 0.0

    def _animate(self):
        if not self.winfo_exists():
            return

        speed = 0.022 + (self._load / 100.0) * 0.042
        self._phase = (self._phase + speed) % 1.0

        amp = 0.55 + (self._load / 100.0) * 0.45
        val = self._ecg_wave(self._phase) * amp

        self._samples.pop(0)
        self._samples.append(val)

        self.canvas.delete("all")
        col = get_accent()
        mid_y = self.h * 0.62
        scale_y = self.h * 0.48
        step_x = self.w / (len(self._samples) - 1)

        self.canvas.create_line(0, mid_y, self.w, mid_y, fill=LINE, dash=(2, 3))

        n = len(self._samples)
        for i in range(n - 1):
            alpha = (i / n) ** 1.4
            seg_col = blend_color(SIDE, col, max(0.12, alpha))
            x1, y1 = i * step_x, mid_y - self._samples[i] * scale_y
            x2, y2 = (i + 1) * step_x, mid_y - self._samples[i + 1] * scale_y
            self.canvas.create_line(x1, y1, x2, y2, fill=seg_col, width=1.8, capstyle=tk.ROUND)

        lx = self.w - 3
        ly = mid_y - self._samples[-1] * scale_y
        halo = blend_color(SIDE, col, 0.4)
        self.canvas.create_oval(lx - 4, ly - 4, lx + 4, ly + 4, fill=halo, outline="")
        self.canvas.create_oval(lx - 2, ly - 2, lx + 2, ly + 2, fill="#ffffff", outline=col)

        self.after(33, self._animate)


class ToolTip:
    def __init__(self, widget, text_key):
        self.widget = widget
        self.text_key = text_key
        self.tipwindow = None
        self.widget.bind("<Enter>", self.show_tip)
        self.widget.bind("<Leave>", self.hide_tip)

    def show_tip(self, event=None):
        if self.tipwindow:
            return
        tip_text = tr(self.text_key)
        if not tip_text:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")

        label = tk.Label(
            tw, text=tip_text, justify=tk.LEFT,
            background="#202128", foreground="#f4f4f5",
            relief=tk.SOLID, borderwidth=1,
            font=(FONT, 10), padx=8, pady=4
        )
        label.pack(ipadx=1)

    def hide_tip(self, event=None):
        if self.tipwindow:
            self.tipwindow.destroy()
            self.tipwindow = None


class Graph(tk.Canvas):
    def __init__(self, master, colors, fixed_max=None, height=95):
        super().__init__(master, width=10, height=height, bg=CARD, highlightthickness=0)
        self.colors = colors
        self.fixed_max = fixed_max
        self.series = []
        self.hover_x = None
        self._reveal = 1.0
        self._reveal_id = None
        self.bind("<Motion>", self.on_motion)
        self.bind("<Leave>", self.on_leave)

    def reveal(self):
        if self._reveal_id:
            self.after_cancel(self._reveal_id)
            self._reveal_id = None
        self._reveal = 0.0
        self.redraw()
        self._step_reveal(1, 14)

    def _step_reveal(self, step, total):
        if not self.winfo_exists():
            return
        t = step / max(1, total)
        self._reveal = 1.0 - (1.0 - t) ** 3
        self.redraw()
        if step < total:
            self._reveal_id = self.after(16, self._step_reveal, step + 1, total)
        else:
            self._reveal_id = None

    def draw(self, series):
        self.series = series
        self.redraw()

    def redraw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 20 or not self.series:
            return

        top = self.fixed_max or max(1.0, max((max(s) for s in self.series if s), default=1.0) * 1.15)
        for i in (1, 2, 3):
            self.create_line(0, h * i / 4, w, h * i / 4, fill=LINE, dash=(2, 2))

        step = w / max(1, (HIST - 1))
        for s, col in zip(self.series, self.colors):
            if len(s) < 2:
                continue

            vis_count = max(2, int(round(len(s) * self._reveal)))
            sub_s = list(s)[:vis_count]

            pts = []
            for i, v in enumerate(sub_s):
                x = w - (len(s) - 1 - i) * step
                y = h - 5 - min(v / top, 1.0) * (h - 10)
                pts.extend([x, y])

            if len(pts) >= 4:
                fill_col = blend_color(CARD, col, 0.14 * self._reveal)
                poly_pts = [pts[0], h] + pts + [pts[-2], h]
                self.create_polygon(*poly_pts, fill=fill_col, outline="")
                self.create_line(*pts, fill=col, width=2, smooth=True)

                lx, ly = pts[-2], pts[-1]
                halo_col = blend_color(CARD, col, 0.35)
                self.create_oval(lx - 5, ly - 5, lx + 5, ly + 5, fill=halo_col, outline="")
                self.create_oval(lx - 2.5, ly - 2.5, lx + 2.5, ly + 2.5, fill="#ffffff", outline=col, width=1.5)

        if self.hover_x is not None and self._reveal >= 0.99:
            idx = int(round((self.hover_x / w) * (HIST - 1)))
            idx = max(0, min(HIST - 1, idx))
            cx = idx * step
            self.create_line(cx, 0, cx, h, fill=TEXT, dash=(1, 1))
            vals_str = [f"{s[idx]:.2f}" for s in self.series if idx < len(s)]
            if vals_str:
                txt = " / ".join(vals_str)
                self.create_text(min(cx + 5, w - 65), 12, text=txt, fill=TEXT, font=(FONT, 9, "bold"), anchor="nw")

    def on_motion(self, event):
        self.hover_x = event.x
        self.redraw()

    def on_leave(self, event):
        self.hover_x = None
        self.redraw()


class Panel(ctk.CTkFrame):
    def __init__(self, master, title, colors, fixed_max=None):
        super().__init__(master, fg_color=CARD, corner_radius=12)
        self.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=16, pady=(12, 0))
        header.grid_columnconfigure(0, weight=1)

        self.title_lbl = ctk.CTkLabel(header, text=title, font=(FONT, 12, "bold"), text_color=DIM)
        self.title_lbl.grid(row=0, column=0, sticky="w")
        self.value = ctk.CTkLabel(header, text="--", font=(FONT, 18, "bold"), text_color=TEXT)
        self.value.grid(row=0, column=1, sticky="e")

        self.graph = Graph(self, colors, fixed_max)
        self.graph.grid(row=1, column=0, columnspan=2, padx=12, pady=8, sticky="ew")

        self.sub = ctk.CTkLabel(self, text=" ", font=(FONT, 11), text_color=DIM, anchor="w")
        self.sub.grid(row=2, column=0, columnspan=2, padx=16, pady=(0, 12), sticky="w")

    def animate_in(self, delay_ms=0):
        fade_delayed(self.title_lbl, CARD, DIM, delay_ms=delay_ms, duration_ms=180)
        fade_delayed(self.value, CARD, TEXT, delay_ms=delay_ms + 30, duration_ms=180)
        fade_delayed(self.sub, CARD, DIM, delay_ms=delay_ms + 60, duration_ms=180)
        if delay_ms > 0:
            self.after(delay_ms, self.graph.reveal)
        else:
            self.graph.reveal()

    def set(self, value, series, sub=" "):
        self.value.configure(text=value)
        self.sub.configure(text=sub)
        self.graph.draw(series)


class Table(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=CARD, corner_radius=12)
        self.grid_columnconfigure(1, weight=1)
        self.rows = {}

    def clear(self):
        for lbl_frame, _, val_widget, _ in self.rows.values():
            lbl_frame.destroy()
            val_widget.destroy()
        self.rows.clear()

    def update_theme(self):
        col = get_accent()
        for _, _, _, icon in self.rows.values():
            if icon is not None:
                icon.configure(text_color=col)

    def animate_rows(self, base_delay=0):
        for idx, (_, lbl, v, _) in enumerate(self.rows.values()):
            delay = base_delay + idx * 30
            fade_delayed(lbl, CARD, DIM, delay_ms=delay, duration_ms=160)
            fade_delayed(v, CARD, TEXT, delay_ms=delay, duration_ms=160)

    def set(self, row_id, key, value, tip_key=None):
        if row_id not in self.rows:
            r = len(self.rows)
            pad = (10, 5) if r == 0 else 5

            lbl_frame = ctk.CTkFrame(self, fg_color="transparent")
            lbl_frame.grid(row=r, column=0, padx=(16, 12), pady=pad, sticky="w")

            lbl = ctk.CTkLabel(lbl_frame, text=key, font=(FONT, 12), text_color=DIM, anchor="w")
            lbl.pack(side="left")

            info_icon = None
            if tip_key:
                info_icon = ctk.CTkLabel(lbl_frame, text=" ⓘ", font=(FONT, 10), text_color=get_accent())
                info_icon.pack(side="left")
                ToolTip(lbl_frame, tip_key)
                ToolTip(lbl, tip_key)
                ToolTip(info_icon, tip_key)

            v = ctk.CTkLabel(self, text="", font=(FONT, 12, "bold"), text_color=TEXT, anchor="w")
            v.grid(row=r, column=1, padx=(0, 16), pady=pad, sticky="w")
            self.rows[row_id] = (lbl_frame, lbl, v, info_icon)

            delay = r * 30
            fade_delayed(lbl, CARD, DIM, delay_ms=delay, duration_ms=160)
            fade_delayed(v, CARD, TEXT, delay_ms=delay, duration_ms=160)

        _, lbl, v, _ = self.rows[row_id]
        lbl.configure(text=key)
        v.configure(text=str(value))


class BarRow(ctk.CTkFrame):
    def __init__(self, master, label, label_w=50):
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(1, weight=1)
        self.lbl = ctk.CTkLabel(self, text=label, width=label_w, anchor="w", font=(FONT, 11, "bold"), text_color=DIM)
        self.lbl.grid(row=0, column=0, padx=(10, 6), pady=4)

        self.bar = ctk.CTkProgressBar(self, height=8, corner_radius=4, fg_color=LINE, progress_color=OK)
        self.bar.grid(row=0, column=1, sticky="ew", pady=4)
        self.bar.set(0)

        self.val = ctk.CTkLabel(self, text="--", width=75, anchor="e", font=(FONT, 11, "bold"), text_color=TEXT)
        self.val.grid(row=0, column=2, padx=(6, 10))
        self.sub = None

        self._cur_pct = 0.0
        self._target_pct = 0.0
        self._last_col = OK

    def animate_in(self, delay_ms=0):
        self._cur_pct = 0.0
        self.bar.set(0)
        fade_delayed(self.lbl, CARD, DIM, delay_ms=delay_ms, duration_ms=160)
        fade_delayed(self.val, CARD, TEXT, delay_ms=delay_ms, duration_ms=160)
        if self.sub is not None:
            fade_delayed(self.sub, CARD, DIM, delay_ms=delay_ms + 30, duration_ms=160)
        _BAR_ANIM.add(self, delay_ms=delay_ms)

    def set(self, pct, text=None, sub=None):
        self._target_pct = max(0.0, min(100.0, pct or 0.0))
        self.val.configure(text=text if text is not None else f"{self._target_pct:.2f}%")
        if sub is not None:
            if self.sub is None:
                self.sub = ctk.CTkLabel(self, text="", font=(FONT, 10), text_color=DIM, anchor="w")
                self.sub.grid(row=1, column=1, columnspan=2, sticky="w", pady=(0, 4))
            self.sub.configure(text=sub)
        _BAR_ANIM.add(self, delay_ms=0)

    def _apply_visual(self):
        col = level_color(self._cur_pct)
        if col != self._last_col:
            self._last_col = col
            self.bar.configure(progress_color=col)
        self.bar.set(self._cur_pct / 100.0)