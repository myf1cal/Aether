import datetime
import platform
import socket
import threading
import time
import psutil
import customtkinter as ctk
from config import (
    BG, CARD, LINE, TEXT, DIM, OK, WARN, CRIT, GREEN, FONT,
    tr, get_lang, get_accent, get_auto_game_mode, set_auto_game_mode
)
from sensors import (
    safe, hb, hr, fmt_up_sec, cpu_name, best_cpu_temp,
    get_hardware_specs, clean_ram_cache, scan_disk_junk, clean_disk_junk
)
from benchmark import load_bench_history, clear_bench_history, run_full_benchmark, analyze_bench_history
from widgets import Panel, Table, BarRow, ToolTip, fade_text


class Page(ctk.CTkScrollableFrame):
    def __init__(self, app):
        super().__init__(
            app.content, fg_color="transparent",
            scrollbar_button_color=LINE, scrollbar_button_hover_color=DIM
        )
        self.grid_columnconfigure(0, weight=1)
        self._n = 0
        self._headers = []

    def put(self, w):
        w.grid(row=self._n, column=0, sticky="ew", pady=6, padx=4)
        self._n += 1
        return w

    def head(self, text_key):
        lbl = ctk.CTkLabel(self, text=tr(text_key).upper(), font=(FONT, 11, "bold"), text_color=DIM, anchor="w")
        self.put(lbl)
        self._headers.append(lbl)
        return lbl

    def card(self):
        f = ctk.CTkFrame(self, fg_color=CARD, corner_radius=12)
        f.grid_columnconfigure(0, weight=1)
        return self.put(f)

    def refresh(self, d, h):
        pass

    def on_show(self):
        for idx, h in enumerate(self._headers):
            h.configure(text_color=BG)
            self.after(idx * 40, fade_text, h, BG, DIM, 8, 16, 0)

        panels = [
            getattr(self, attr) for attr in ("panel", "cpu", "mem", "net", "dio")
            if isinstance(getattr(self, attr, None), Panel)
        ]
        for idx, p in enumerate(panels):
            p.animate_in(delay_ms=idx * 55)

        bars = []
        for attr in ("ram", "swap"):
            b = getattr(self, attr, None)
            if isinstance(b, BarRow):
                bars.append(b)
        if hasattr(self, "cores"):
            bars.extend(self.cores)
        if hasattr(self, "vols"):
            bars.extend(self.vols.values())

        for idx, b in enumerate(bars):
            b.animate_in(delay_ms=60 + idx * 22)

        base_tbl_delay = 80 if panels else 40
        for attr in ("info", "t", "t_os", "nics", "temps", "misc"):
            tbl = getattr(self, attr, None)
            if isinstance(tbl, Table):
                tbl.animate_rows(base_delay=base_tbl_delay)
                base_tbl_delay += 70

    def on_theme_change(self):
        for attr in ("info", "t", "t_os", "nics", "temps", "misc"):
            tbl = getattr(self, attr, None)
            if isinstance(tbl, Table):
                tbl.update_theme()

    def on_lang_change(self):
        pass


class Overview(Page):
    def __init__(self, app):
        super().__init__(app)
        self.h_lbl = self.head("sys_overview")
        box = self.put(ctk.CTkFrame(self, fg_color="transparent"))
        for c in (0, 1):
            box.grid_columnconfigure(c, weight=1, uniform="p")
        self.cpu = Panel(box, tr("card_cpu"), [get_accent()], 100)
        self.mem = Panel(box, tr("card_ram"), [GREEN], 100)
        self.net = Panel(box, tr("card_net"), [OK, GREEN])
        self.dio = Panel(box, tr("card_dio"), [WARN, CRIT])
        for i, p in enumerate((self.cpu, self.mem, self.net, self.dio)):
            p.grid(row=i // 2, column=i % 2, padx=4, pady=4, sticky="nsew")
        self.info = self.put(Table(self))

    def refresh(self, d, h):
        cpu, mem, mem_pct, f_smooth = d.get("cpu"), d.get("mem"), d.get("mem_pct"), d.get("freq_smooth")
        sub = f"{len(d.get('per') or [])} threads" + (f" · {f_smooth / 1000:.2f} GHz" if f_smooth else "")
        self.cpu.set(f"{cpu:.2f}%" if cpu is not None else "N/A", [h["cpu"]], sub)
        self.mem.set(f"{mem_pct:.2f}%" if mem_pct is not None else "N/A", [h["mem"]],
                     f"{hb(mem.used)} / {hb(mem.total)}" if mem else " ")
        self.net.set("↓ " + hr(d.get("down")), [h["down"], h["up"]], "↑ " + hr(d.get("up")))
        self.dio.set("R " + hr(d.get("dr")), [h["dr"], h["dw"]], "W " + hr(d.get("dw")))

        t = safe(lambda: best_cpu_temp(d.get("temps")))
        t_str = f"{t:.2f} °C" if t is not None else ("N/A (Run LibreHardwareMonitor)" if get_lang() == "EN" else "Н/Д (Запустите LibreHardwareMonitor)")
        self.info.set("temp", tr("cpu_temp"), t_str, "cpu_temp_tip")

        gpu_t = d.get("gpu_temps") or {}
        if gpu_t:
            g_name, g_val = next(iter(gpu_t.items()))
            self.info.set("gpu_temp", tr("gpu_temp"), f"{g_val:.2f} °C ({g_name})", "gpu_temp_tip")

        peaks = d.get("peaks") or {}
        p_cpu = peaks.get("cpu", 0.0)
        p_gpu = peaks.get("gpu_temp", 0.0)
        peak_str = f"CPU {p_cpu:.2f}%" + (f"  ·  GPU {p_gpu:.2f} °C" if p_gpu > 0 else "")
        self.info.set("peaks", tr("session_peaks"), peak_str, "session_peaks_tip")

        sw, sw_pct = d.get("swap"), d.get("swap_pct")
        sw_str = f"{sw_pct:.2f}%  ({hb(sw.used)} / {hb(sw.total)})" if (sw and sw_pct is not None) else "N/A"
        self.info.set("swap", tr("swap_page"), sw_str, "swap_tip")
        self.info.set("procs", tr("active_procs"), str(d.get("procs") or "N/A"), "active_procs_tip")
        self.info.set("uptime", tr("sys_uptime"), fmt_up_sec(time.time() - psutil.boot_time()), "sys_uptime_tip")

    def on_theme_change(self):
        super().on_theme_change()
        self.cpu.graph.colors = [get_accent()]
        self.cpu.graph.redraw()

    def on_lang_change(self):
        self.h_lbl.configure(text=tr("sys_overview").upper())
        for p, key in ((self.cpu, "card_cpu"), (self.mem, "card_ram"), (self.net, "card_net"), (self.dio, "card_dio")):
            p.title_lbl.configure(text=tr(key))
            fade_text(p.title_lbl, CARD, DIM, steps=8, delay_ms=16)
        self.info.clear()


class CpuPage(Page):
    def __init__(self, app):
        super().__init__(app)
        self.h1 = self.head("proc_perf")
        self.panel = self.put(Panel(self, tr("total_cpu"), [get_accent()], 100))
        self.t = self.put(Table(self))
        self._init_static()

        self.h2 = self.head("core_threads")
        card = self.card()
        n = psutil.cpu_count() or 1
        cols = 2 if n > 8 else 1
        rows = -(-n // cols)
        for c in range(cols):
            card.grid_columnconfigure(c, weight=1, uniform="c")
        self.cores = []
        for i in range(n):
            r = BarRow(card, f"Thread {i:2d}", label_w=70)
            r.grid(row=i % rows, column=i // rows, sticky="ew", padx=6, pady=2)
            self.cores.append(r)

    def _init_static(self):
        self.t.set("model", tr("cpu_model"), cpu_name())
        self.t.set("cores", tr("phys_cores"), f"{safe(lambda: psutil.cpu_count(logical=False)) or '?'}")

    def refresh(self, d, h):
        cpu, f, f_smooth, t = d.get("cpu"), d.get("freq"), d.get("freq_smooth"), self.t
        self.panel.set(f"{cpu:.2f}%" if cpu is not None else "N/A", [h["cpu"]],
                       f"{f_smooth / 1000:.2f} GHz" if f_smooth else " ")
        t.set("freq", tr("curr_freq"), (f"{f_smooth:.2f} MHz" + (f"  (Max: {f.max:.2f} MHz)" if (f and f.max) else "")) if f_smooth else "N/A", "curr_freq_tip")
        if d.get("ctx") is not None:
            t.set("ctx", tr("ctx_switches"), f"{d['ctx']:,.2f} /s", "ctx_switches_tip")
            t.set("irq", tr("interrupts"), f"{d['irq']:,.2f} /s", "interrupts_tip")
        for row, v in zip(self.cores, d.get("per") or []):
            row.set(v)

    def on_theme_change(self):
        super().on_theme_change()
        self.panel.graph.colors = [get_accent()]
        self.panel.graph.redraw()

    def on_lang_change(self):
        self.h1.configure(text=tr("proc_perf").upper())
        self.h2.configure(text=tr("core_threads").upper())
        self.panel.title_lbl.configure(text=tr("total_cpu"))
        fade_text(self.panel.title_lbl, CARD, DIM, steps=8, delay_ms=16)
        self.t.clear()
        self._init_static()


class MemPage(Page):
    def __init__(self, app):
        super().__init__(app)
        self.h1 = self.head("mem_mgmt")
        self.panel = self.put(Panel(self, tr("ram_consumption"), [GREEN], 100))
        card = self.card()
        self.ram, self.swap = BarRow(card, "RAM", 60), BarRow(card, "SWAP", 60)
        self.ram.grid(row=0, column=0, sticky="ew", padx=6, pady=4)
        self.swap.grid(row=1, column=0, sticky="ew", padx=6, pady=4)
        self.t = self.put(Table(self))

    def refresh(self, d, h):
        m, mem_pct, s, sw_pct, t = d.get("mem"), d.get("mem_pct"), d.get("swap"), d.get("swap_pct"), self.t
        if m and mem_pct is not None:
            self.panel.set(f"{mem_pct:.2f}%", [h["mem"]], f"{hb(m.used)} / {hb(m.total)}")
            self.ram.set(mem_pct, sub=f"{hb(m.used)} / {hb(m.total)}")
            t.set("tot", tr("total_phys"), hb(m.total), "total_phys_tip")
            t.set("used", tr("used_mem"), hb(m.used), "used_mem_tip")
            t.set("avail", tr("avail_ram"), hb(m.available), "avail_ram_tip")
        if s and sw_pct is not None:
            self.swap.set(sw_pct, sub=f"{hb(s.used)} / {hb(s.total)}")
            t.set("sw_tot", tr("swap_tot"), hb(s.total), "swap_tot_tip")
            t.set("sw_used", tr("swap_used"), hb(s.used), "swap_used_tip")

    def on_lang_change(self):
        self.h1.configure(text=tr("mem_mgmt").upper())
        self.panel.title_lbl.configure(text=tr("ram_consumption"))
        fade_text(self.panel.title_lbl, CARD, DIM, steps=8, delay_ms=16)
        self.t.clear()


class DiskPage(Page):
    def __init__(self, app):
        super().__init__(app)
        self.h1 = self.head("disk_act")
        self.panel = self.put(Panel(self, tr("read_write"), [WARN, CRIT]))
        self.t = self.put(Table(self))
        self.h2 = self.head("mounted_vols")
        self.vcard = self.card()
        self.vols = {}

    def refresh(self, d, h):
        self.panel.set("R " + hr(d.get("dr")), [h["dr"], h["dw"]], "W " + hr(d.get("dw")))
        io = d.get("io")
        if io:
            self.t.set("t_read", tr("tot_read"), hb(io.read_bytes), "tot_read_tip")
            self.t.set("t_write", tr("tot_write"), hb(io.write_bytes), "tot_write_tip")
            self.t.set("r_ops", tr("read_ops"), f"{io.read_count:,}", "read_ops_tip")
            self.t.set("w_ops", tr("write_ops"), f"{io.write_count:,}", "write_ops_tip")
        for mount, fs, u in d.get("parts") or []:
            if mount not in self.vols:
                r = BarRow(self.vcard, mount, 70)
                r.grid(row=len(self.vols), column=0, sticky="ew", padx=6, pady=3)
                self.vols[mount] = r
            self.vols[mount].set(u.percent, sub=f"{fs} · {hb(u.used)} / {hb(u.total)}")

    def on_lang_change(self):
        self.h1.configure(text=tr("disk_act").upper())
        self.h2.configure(text=tr("mounted_vols").upper())
        self.panel.title_lbl.configure(text=tr("read_write"))
        fade_text(self.panel.title_lbl, CARD, DIM, steps=8, delay_ms=16)
        self.t.clear()


class NetPage(Page):
    def __init__(self, app):
        super().__init__(app)
        self.h1 = self.head("net_overview")
        self.panel = self.put(Panel(self, tr("net_band"), [OK, GREEN]))
        self.t = self.put(Table(self))
        self.t.set("host", tr("hostname"), socket.gethostname())
        self.h2 = self.head("active_interfaces")
        self.nics = self.put(Table(self))

    def refresh(self, d, h):
        self.panel.set("↓ " + hr(d.get("down")), [h["down"], h["up"]], "↑ " + hr(d.get("up")))
        n, t = d.get("net"), self.t
        if n:
            t.set("rec", tr("tot_rec"), hb(n.bytes_recv))
            t.set("sent", tr("tot_sent"), hb(n.bytes_sent))
            t.set("pkts", tr("pkts_io"), f"{n.packets_recv:,} / {n.packets_sent:,}")
        rates = d.get("nic_rates") or {}
        for name, (ip, _) in (d.get("nic_info") or {}).items():
            dn, up = rates.get(name, (None, None))
            self.nics.set(name, name, f"IP: {ip}  |  ↓ {hr(dn)}  ↑ {hr(up)}")

    def on_lang_change(self):
        self.h1.configure(text=tr("net_overview").upper())
        self.h2.configure(text=tr("active_interfaces").upper())
        self.panel.title_lbl.configure(text=tr("net_band"))
        fade_text(self.panel.title_lbl, CARD, DIM, steps=8, delay_ms=16)
        self.t.clear()
        self.t.set("host", tr("hostname"), socket.gethostname())
        self.nics.clear()


class SensorPage(Page):
    def __init__(self, app):
        super().__init__(app)
        self.h1 = self.head("hw_temps")
        self.temps = self.put(Table(self))
        self.h2 = self.head("fans_power")
        self.misc = self.put(Table(self))

    def refresh(self, d, h):
        temps = d.get("temps") or {}
        if not temps:
            self.temps.set("status", tr("sensors_status"), tr("sensors_inactive"))
        else:
            if "status" in self.temps.rows:
                self.temps.clear()
            for chip, val in temps.items():
                self.temps.set(chip, chip, f"{val:.2f} °C")

        fans = d.get("fans") or {}
        gpu_fans = d.get("gpu_fans") or {}
        power = d.get("power") or {}

        if not fans and not gpu_fans:
            self.misc.set("fans", "Fans" if get_lang() == "EN" else "Вентиляторы", tr("fans_inactive"))
        else:
            if "fans" in self.misc.rows:
                self.misc.clear()
            for fan_name, rpm in fans.items():
                self.misc.set(f"fan_{fan_name}", fan_name, f"{rpm:.2f} RPM")
            for gfan_name, pct in gpu_fans.items():
                self.misc.set(f"gfan_{gfan_name}", gfan_name, f"{pct:.2f} %")

        for pwr_name, watts in power.items():
            self.misc.set(f"pwr_{pwr_name}", pwr_name, f"{watts:.2f} W")

        b = d.get("bat")
        if b:
            status_text = f"{b.percent:.2f}% ({tr('charging') if b.power_plugged else tr('discharging')})"
            self.misc.set("bat", tr("battery_status"), status_text)
        else:
            self.misc.set("bat", tr("battery_status"), tr("no_battery"))

    def on_lang_change(self):
        self.h1.configure(text=tr("hw_temps").upper())
        self.h2.configure(text=tr("fans_power").upper())
        self.temps.clear()
        self.misc.clear()


class BenchPage(Page):
    def __init__(self, app):
        super().__init__(app)
        self._running = False
        self._status_key = "bench_ready"
        self._cur_prog = 0.0
        self._target_prog = 0.0
        self._start_time = 0.0
        self._est_total = 6.8

        self.h_top = self.head("bench_title")
        ctrl = self.card()
        ctrl.grid_columnconfigure(0, weight=1)

        top_row = ctk.CTkFrame(ctrl, fg_color="transparent")
        top_row.grid(row=0, column=0, padx=14, pady=(14, 6), sticky="ew")
        top_row.grid_columnconfigure(0, weight=1)

        self.status_lbl = ctk.CTkLabel(top_row, text=tr("bench_ready"), font=(FONT, 12, "bold"), text_color=TEXT, anchor="w")
        self.status_lbl.grid(row=0, column=0, sticky="w")

        score_box = ctk.CTkFrame(top_row, fg_color="transparent")
        score_box.grid(row=0, column=1, sticky="e")

        self.overall_lbl = ctk.CTkLabel(score_box, text="", font=(FONT, 18, "bold"), text_color=get_accent())
        self.overall_lbl.pack(side="left")

        self.overall_diff_lbl = ctk.CTkLabel(score_box, text="", font=(FONT, 12, "bold"), text_color=GREEN)
        self.overall_diff_lbl.pack(side="left", padx=(6, 0))

        self.pbar = ctk.CTkProgressBar(ctrl, height=8, corner_radius=4, fg_color=LINE, progress_color=get_accent())
        self.pbar.grid(row=1, column=0, padx=14, pady=(2, 10), sticky="ew")
        self.pbar.set(0)

        btn_row = ctk.CTkFrame(ctrl, fg_color="transparent")
        btn_row.grid(row=2, column=0, padx=14, pady=(0, 14), sticky="ew")
        btn_row.grid_columnconfigure(0, weight=1)

        self.btn_run = ctk.CTkButton(
            btn_row, text=tr("btn_run_bench"), height=38, corner_radius=10,
            font=(FONT, 13, "bold"), fg_color=get_accent(), hover_color=LINE,
            text_color=TEXT, command=self._start_bench
        )
        self.btn_run.grid(row=0, column=0, padx=(0, 8), sticky="ew")

        self.btn_clear = ctk.CTkButton(
            btn_row, text=tr("btn_clear_bench"), height=38, width=140, corner_radius=10,
            font=(FONT, 12, "bold"), fg_color=LINE, hover_color=CRIT,
            text_color=DIM, command=self._clear_hist
        )
        self.btn_clear.grid(row=0, column=1)

        self.h_res = self.head("bench_results")
        self.res_card = self.card()
        self.res_card.grid_columnconfigure(1, weight=1)

        self.h_avg = self.head("bench_avg_summary")
        self.avg_card = self.card()
        self.avg_card.grid_columnconfigure(1, weight=1)

        self.h_hist = self.head("bench_history")
        self.hist_card = self.card()
        self.hist_card.grid_columnconfigure(1, weight=1)

        self._render_history(load_bench_history())

    def _start_bench(self):
        if self._running:
            return
        self._running = True
        self._cur_prog = 0.02
        self._target_prog = 0.25
        self._start_time = time.perf_counter()
        self._status_key = "bench_step_cpu"
        self.pbar.set(0.02)
        self.btn_run.configure(state="disabled")
        self.btn_clear.configure(state="disabled")
        self._tick_bench_anim()
        run_full_benchmark(self._on_progress, self._on_finished)

    def _tick_bench_anim(self):
        if not self._running or not self.winfo_exists():
            return

        elapsed = time.perf_counter() - self._start_time
        rem = max(0.2, self._est_total - elapsed)

        if self._cur_prog < self._target_prog:
            self._cur_prog += (self._target_prog - self._cur_prog) * 0.08 + 0.0012
        else:
            self._cur_prog = min(0.99, self._cur_prog + 0.0008)

        self.pbar.set(min(0.99, self._cur_prog))

        sec_word = "с" if get_lang() == "RU" else "s"
        left_word = "осталось" if get_lang() == "RU" else "left"
        self.status_lbl.configure(text=f"{tr(self._status_key)}  ·  ~{rem:.1f}{sec_word} {left_word}")
        self.btn_run.configure(text=f"{tr('btn_running_bench')} ({rem:.1f}{sec_word})")

        self.after(16, self._tick_bench_anim)

    def _on_progress(self, pct, step_key):
        self.after(0, self._apply_progress, pct, step_key)

    def _apply_progress(self, pct, step_key):
        if not self.winfo_exists():
            return
        self._status_key = step_key
        self._target_prog = pct

    def _on_finished(self, result, hist, err):
        self.after(0, self._apply_finished, result, hist, err)

    def _apply_finished(self, result, hist, err):
        if not self.winfo_exists():
            return
        self._running = False
        self._cur_prog = 1.0
        self.pbar.set(1.0)
        self.btn_run.configure(state="normal", text=tr("btn_run_bench"))
        self.btn_clear.configure(state="normal")
        if err:
            self.status_lbl.configure(text=f"Error: {err}")
            return
        self._status_key = "bench_done"
        self.status_lbl.configure(text=tr("bench_done"))
        self._render_history(hist)

    def _clear_hist(self):
        if self._running:
            return
        clear_bench_history()
        self.overall_lbl.configure(text="")
        self.overall_diff_lbl.configure(text="")
        self.pbar.set(0)
        self._status_key = "bench_ready"
        self.status_lbl.configure(text=tr("bench_ready"))
        self._render_history([])

    def _calc_diff(self, cur, baseline):
        if not baseline or baseline <= 0:
            return "", DIM
        diff_pct = ((cur - baseline) / baseline) * 100.0
        if abs(diff_pct) < 0.2:
            return "0.0%", DIM
        if diff_pct > 0:
            return f"+{diff_pct:.1f}%", GREEN
        return f"{diff_pct:.1f}%", CRIT

    def _render_history(self, hist):
        for card in (self.res_card, self.avg_card, self.hist_card):
            for w in card.winfo_children():
                w.destroy()

        if not hist:
            lbl = ctk.CTkLabel(self.hist_card, text=tr("bench_no_history"), font=(FONT, 12), text_color=DIM, anchor="w")
            lbl.grid(row=0, column=0, padx=16, pady=14, sticky="w")
            return

        stats = analyze_bench_history(hist)
        avgs = stats["avgs"]
        maxs = stats["maxs"]
        avg_metrics = stats["avg_metrics"]
        count = stats["count"]

        latest = hist[0]
        is_ru = (get_lang() == "RU")
        avg_word = "ср." if is_ru else "avg"
        best_word = "рекорд" if is_ru else "best"
        runs_word = f"по {count} тестам" if is_ru else f"across {count} runs"

        ov_txt, ov_col = self._calc_diff(latest["overall"], avgs["overall"])
        self.overall_lbl.configure(text=f"{latest['overall']:,} pts")
        self.overall_diff_lbl.configure(
            text=f"[{ov_txt} vs {avg_word}]" if ov_txt else "",
            text_color=ov_col
        )

        metrics = [
            ("score_overall", "overall", f"{avg_word}: {int(round(avgs['overall'])):,} pts"),
            ("score_cpu", "cpu", f"{latest.get('cpu_detail', '')} · {avg_word}: {int(round(avgs['cpu'])):,}"),
            ("score_ram", "ram", f"{latest.get('ram_detail', '')} · {avg_word}: {int(round(avgs['ram'])):,}"),
            ("score_disk", "disk", f"{latest.get('disk_detail', '')} · {avg_word}: {int(round(avgs['disk'])):,}"),
            ("score_gpu", "gpu", f"{latest.get('gpu_detail', '')} · {avg_word}: {int(round(avgs['gpu'])):,}"),
        ]

        for r, (title_key, key, summary_text) in enumerate(metrics):
            pad_y = (12, 6) if r == 0 else ((6, 12) if r == len(metrics) - 1 else 6)

            ctk.CTkLabel(
                self.res_card, text=tr(title_key), font=(FONT, 12), text_color=DIM, anchor="w"
            ).grid(row=r, column=0, padx=(16, 12), pady=pad_y, sticky="w")

            val_box = ctk.CTkFrame(self.res_card, fg_color="transparent")
            val_box.grid(row=r, column=1, padx=(0, 16), pady=pad_y, sticky="w")

            ctk.CTkLabel(
                val_box, text=f"{latest[key]:,} pts", font=(FONT, 12, "bold"), text_color=TEXT
            ).pack(side="left")

            ctk.CTkLabel(
                val_box, text=f"  ({summary_text})", font=(FONT, 11), text_color=DIM
            ).pack(side="left")

            diff_txt, diff_col = self._calc_diff(latest[key], avgs[key])
            if diff_txt:
                ctk.CTkLabel(
                    val_box, text=f"  [{diff_txt}]", font=(FONT, 12, "bold"), text_color=diff_col
                ).pack(side="left")

        avg_rows = [
            ("score_overall", "overall", runs_word),
            ("score_cpu", "cpu", avg_metrics.get("cpu", "")),
            ("score_ram", "ram", avg_metrics.get("ram", "")),
            ("score_disk", "disk", avg_metrics.get("disk", "")),
            ("score_gpu", "gpu", avg_metrics.get("gpu", "")),
        ]

        for r, (title_key, key, speed_avg) in enumerate(avg_rows):
            pad_y = (12, 6) if r == 0 else ((6, 12) if r == len(avg_rows) - 1 else 6)

            ctk.CTkLabel(
                self.avg_card, text=tr(title_key), font=(FONT, 12), text_color=DIM, anchor="w"
            ).grid(row=r, column=0, padx=(16, 12), pady=pad_y, sticky="w")

            abox = ctk.CTkFrame(self.avg_card, fg_color="transparent")
            abox.grid(row=r, column=1, padx=(0, 16), pady=pad_y, sticky="w")

            ctk.CTkLabel(
                abox, text=f"{int(round(avgs[key])):,} pts", font=(FONT, 12, "bold"), text_color=OK
            ).pack(side="left")

            extra_parts = []
            if speed_avg:
                extra_parts.append(speed_avg)
            extra_parts.append(f"{best_word}: {int(round(maxs[key])):,} pts")

            ctk.CTkLabel(
                abox, text="  (" + "  ·  ".join(extra_parts) + ")", font=(FONT, 11), text_color=DIM
            ).pack(side="left")

        for idx, item in enumerate(hist):
            pad_y = (12, 6) if idx == 0 else ((6, 12) if idx == len(hist) - 1 else 6)

            ctk.CTkLabel(
                self.hist_card, text=item.get("date", f"#{idx + 1}"),
                font=(FONT, 12), text_color=DIM, anchor="nw"
            ).grid(row=idx, column=0, padx=(16, 14), pady=pad_y, sticky="nw")

            item_box = ctk.CTkFrame(self.hist_card, fg_color="transparent")
            item_box.grid(row=idx, column=1, padx=(0, 16), pady=pad_y, sticky="w")

            top_line = ctk.CTkFrame(item_box, fg_color="transparent")
            top_line.pack(anchor="w")

            scores_str = (
                f"Overall: {item['overall']:,}  |  CPU: {item['cpu']:,}  |  "
                f"GPU: {item['gpu']:,}  |  RAM: {item['ram']:,}  |  Disk: {item['disk']:,}"
            )
            ctk.CTkLabel(top_line, text=scores_str, font=(FONT, 12, "bold"), text_color=TEXT).pack(side="left")

            d_txt, d_col = self._calc_diff(item["overall"], avgs["overall"])
            if d_txt:
                ctk.CTkLabel(
                    top_line, text=f"  [{d_txt} vs {avg_word}]", font=(FONT, 11, "bold"), text_color=d_col
                ).pack(side="left")

            ctk.CTkLabel(
                item_box, text=item.get("hardware", ""), font=(FONT, 11), text_color=DIM, anchor="w"
            ).pack(anchor="w")

    def on_theme_change(self):
        super().on_theme_change()
        acc = get_accent()
        self.overall_lbl.configure(text_color=acc)
        self.pbar.configure(progress_color=acc)
        self.btn_run.configure(fg_color=acc)

    def on_lang_change(self):
        self.h_top.configure(text=tr("bench_title").upper())
        self.h_res.configure(text=tr("bench_results").upper())
        self.h_avg.configure(text=tr("bench_avg_summary").upper())
        self.h_hist.configure(text=tr("bench_history").upper())
        if not self._running:
            self.status_lbl.configure(text=tr(self._status_key))
            self.btn_run.configure(text=tr("btn_run_bench"))
        self.btn_clear.configure(text=tr("btn_clear_bench"))
        self._render_history(load_bench_history())


class DiskCleanupDialog(ctk.CTkToplevel):
    def __init__(self, parent, on_confirm):
        super().__init__(parent, fg_color=BG)
        self._on_confirm = on_confirm
        self._sizes = {"temp": 0, "cache": 0, "recycle": 0, "downloads": 0}
        self._vars = {
            "temp": ctk.BooleanVar(value=True),
            "cache": ctk.BooleanVar(value=True),
            "recycle": ctk.BooleanVar(value=False),
            "downloads": ctk.BooleanVar(value=False),
        }

        self.title("Aether")
        self.geometry("460x325")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.update_idletasks()
        px = parent.winfo_rootx() + (parent.winfo_width() - 460) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - 325) // 2
        self.geometry(f"+{max(0, px)}+{max(0, py)}")

        box = ctk.CTkFrame(self, fg_color=CARD, corner_radius=14, border_width=1, border_color=LINE)
        box.pack(fill="both", expand=True, padx=14, pady=14)
        box.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            box, text=tr("clean_modal_title"), font=(FONT, 15, "bold"), text_color=TEXT, anchor="w"
        ).grid(row=0, column=0, padx=18, pady=(16, 2), sticky="w")

        self.sub_lbl = ctk.CTkLabel(
            box, text=tr("clean_modal_sub"), font=(FONT, 11), text_color=DIM, anchor="w"
        )
        self.sub_lbl.grid(row=1, column=0, padx=18, pady=(0, 10), sticky="w")

        cats = [
            ("temp", "clean_cat_temp", TEXT),
            ("cache", "clean_cat_cache", TEXT),
            ("recycle", "clean_cat_recycle", WARN),
            ("downloads", "clean_cat_downloads", CRIT),
        ]

        self._size_lbls = {}
        for idx, (key, title_key, col) in enumerate(cats, start=2):
            row_f = ctk.CTkFrame(box, fg_color="transparent")
            row_f.grid(row=idx, column=0, padx=18, pady=4, sticky="ew")
            row_f.grid_columnconfigure(0, weight=1)

            cb = ctk.CTkCheckBox(
                row_f, text=tr(title_key), variable=self._vars[key],
                font=(FONT, 12), text_color=col, fg_color=get_accent(),
                hover_color=get_accent(), border_color=LINE,
                command=self._update_total_btn
            )
            cb.grid(row=0, column=0, sticky="w")

            sz_lbl = ctk.CTkLabel(row_f, text="...", font=(FONT, 11, "bold"), text_color=DIM)
            sz_lbl.grid(row=0, column=1, sticky="e")
            self._size_lbls[key] = sz_lbl

        btn_row = ctk.CTkFrame(box, fg_color="transparent")
        btn_row.grid(row=6, column=0, padx=18, pady=(14, 16), sticky="ew")
        btn_row.grid_columnconfigure(0, weight=1)

        self.confirm_btn = ctk.CTkButton(
            btn_row, text=tr("clean_btn_confirm"), height=36, corner_radius=10,
            font=(FONT, 12, "bold"), fg_color=get_accent(), hover_color=LINE,
            text_color=TEXT, command=self._submit
        )
        self.confirm_btn.grid(row=0, column=0, padx=(0, 8), sticky="ew")

        ctk.CTkButton(
            btn_row, text=tr("clean_btn_cancel"), height=36, width=100, corner_radius=10,
            font=(FONT, 12, "bold"), fg_color=LINE, hover_color=CRIT,
            text_color=DIM, command=self.destroy
        ).grid(row=0, column=1)

        threading.Thread(target=self._scan_worker, daemon=True).start()

    def _scan_worker(self):
        sizes = scan_disk_junk()
        self.after(0, self._apply_sizes, sizes)

    def _apply_sizes(self, sizes):
        if not self.winfo_exists():
            return
        self._sizes = sizes
        self.sub_lbl.configure(text=tr("clean_modal_ready"))
        for key, lbl in self._size_lbls.items():
            lbl.configure(text=hb(sizes.get(key, 0)))
        self._update_total_btn()

    def _update_total_btn(self):
        selected = [k for k, var in self._vars.items() if var.get()]
        total_bytes = sum(self._sizes.get(k, 0) for k in selected)
        if not selected:
            self.confirm_btn.configure(state="disabled", text=tr("clean_btn_confirm"))
        else:
            self.confirm_btn.configure(
                state="normal",
                text=f"{tr('clean_btn_confirm')} ({hb(total_bytes)})"
            )

    def _submit(self):
        selected = [k for k, var in self._vars.items() if var.get()]
        self.destroy()
        if selected:
            self._on_confirm(selected)


class SysPage(Page):
    def __init__(self, app):
        super().__init__(app)
        self._app = app
        self._specs = get_hardware_specs()
        self._trim_cooldown = False
        self._disk_cleaning = False

        self.h_tools = self.head("quick_tools")
        tools_card = self.card()
        tools_card.grid_columnconfigure((0, 1, 2), weight=1, uniform="tools")

        self.btn_trim = ctk.CTkButton(
            tools_card, text=f"{tr('btn_trim_ram')}  ⓘ", height=36, corner_radius=10,
            font=(FONT, 12, "bold"), fg_color=get_accent(), hover_color=LINE,
            text_color=TEXT, command=self._do_trim_ram
        )
        self.btn_trim.grid(row=0, column=0, padx=(12, 5), pady=(12, 8), sticky="ew")
        ToolTip(self.btn_trim, "btn_trim_tip")

        self.btn_disk = ctk.CTkButton(
            tools_card, text=f"{tr('btn_clean_disk')}  ⓘ", height=36, corner_radius=10,
            font=(FONT, 12, "bold"), fg_color=LINE, hover_color=get_accent(),
            text_color=TEXT, command=self._open_disk_dialog
        )
        self.btn_disk.grid(row=0, column=1, padx=5, pady=(12, 8), sticky="ew")
        ToolTip(self.btn_disk, "btn_clean_disk_tip")

        self.btn_reset = ctk.CTkButton(
            tools_card, text=tr("btn_reset_graphs"), height=36, corner_radius=10,
            font=(FONT, 12, "bold"), fg_color=LINE, hover_color=get_accent(),
            text_color=TEXT, command=self._do_reset_graphs
        )
        self.btn_reset.grid(row=0, column=2, padx=(5, 12), pady=(12, 8), sticky="ew")

        self.gm_switch = ctk.CTkSwitch(
            tools_card, text=tr("auto_gm_label"), font=(FONT, 12), text_color=TEXT,
            progress_color=get_accent(), command=self._toggle_gm
        )
        if get_auto_game_mode():
            self.gm_switch.select()
        self.gm_switch.grid(row=1, column=0, columnspan=3, padx=14, pady=(2, 12), sticky="w")

        self.h1 = self.head("sys_specs")
        self.t = self.put(Table(self))

        self.h2 = self.head("os_specs")
        self.t_os = self.put(Table(self))

        self._init_static()

    def _toggle_gm(self):
        set_auto_game_mode(bool(self.gm_switch.get()))

    def _do_trim_ram(self):
        if self._trim_cooldown:
            return
        self._trim_cooldown = True
        freed = clean_ram_cache()
        self.btn_trim.configure(state="disabled", text=f"✓ {tr('btn_trim_done')}: {hb(freed)}")
        self.after(5000, self._reset_trim_btn)

    def _reset_trim_btn(self):
        self._trim_cooldown = False
        if self.btn_trim.winfo_exists():
            self.btn_trim.configure(state="normal", text=f"{tr('btn_trim_ram')}  ⓘ")

    def _open_disk_dialog(self):
        if self._disk_cleaning:
            return
        DiskCleanupDialog(self._app, self._run_disk_cleanup)

    def _run_disk_cleanup(self, selected_categories):
        self._disk_cleaning = True
        self.btn_disk.configure(state="disabled", text=tr("btn_cleaning_disk"))

        def _worker():
            freed = clean_disk_junk(selected_categories)
            self.after(0, self._on_disk_cleaned, freed)

        threading.Thread(target=_worker, daemon=True).start()

    def _on_disk_cleaned(self, freed):
        if not self.btn_disk.winfo_exists():
            self._disk_cleaning = False
            return
        self.btn_disk.configure(text=f"✓ {tr('btn_trim_done')}: {hb(freed)}")
        self.after(4000, self._reset_disk_btn)

    def _reset_disk_btn(self):
        self._disk_cleaning = False
        if self.btn_disk.winfo_exists():
            self.btn_disk.configure(state="normal", text=f"{tr('btn_clean_disk')}  ⓘ")

    def _do_reset_graphs(self):
        self._app.telemetry.reset_history()
        self.btn_reset.configure(text=f"✓ {tr('btn_reset_done')}")
        self.after(1800, lambda: self.btn_reset.configure(text=tr("btn_reset_graphs")) if self.btn_reset.winfo_exists() else None)

    def _init_static(self):
        t, t_os, sp = self.t, self.t_os, self._specs

        phys = safe(lambda: psutil.cpu_count(logical=False)) or "?"
        logi = psutil.cpu_count() or "?"
        t.set("cpu", tr("cpu_model"), cpu_name())
        t.set("threads", tr("logical_threads"), f"{phys} / {logi}")
        t.set("gpu", tr("gpu_model"), sp.get("gpu", "Unknown"))
        t.set("mobo", tr("mobo_model"), sp.get("mobo", "Unknown"))
        t.set("bios", tr("bios_ver"), sp.get("bios", "Unknown"))

        ram_total = safe(lambda: hb(psutil.virtual_memory().total), "?")
        ram_spd = sp.get("ram_speed")
        t.set("mem", tr("tot_mem"), f"{ram_total}" + (f" · {ram_spd}" if ram_spd else ""))

        if sp.get("drives"):
            t.set("drives", tr("storage_list"), sp["drives"])

        sw = safe(lambda: self._app.winfo_screenwidth(), 0)
        sh = safe(lambda: self._app.winfo_screenheight(), 0)
        if sw and sh:
            t.set("disp", tr("display_res"), f"{sw} × {sh}")

        t_os.set("host", tr("hostname"), safe(socket.gethostname, "?"))
        t_os.set("os", tr("os_name"), f"{platform.system()} {platform.release()} (Build {platform.version().split('.')[-1]})")
        t_os.set("arch", tr("arch"), platform.machine())
        t_os.set("boot", tr("boot_time"), safe(lambda: datetime.datetime.fromtimestamp(psutil.boot_time()).strftime("%Y-%m-%d %H:%M:%S"), "?"))

    def refresh(self, d, h):
        self.t_os.set("up", tr("sys_uptime"), fmt_up_sec(time.time() - psutil.boot_time()), "sys_uptime_tip")

    def on_theme_change(self):
        super().on_theme_change()
        acc = get_accent()
        self.btn_trim.configure(fg_color=acc)
        self.btn_disk.configure(hover_color=acc)
        self.btn_reset.configure(hover_color=acc)
        self.gm_switch.configure(progress_color=acc)

    def on_lang_change(self):
        self.h_tools.configure(text=tr("quick_tools").upper())
        self.h1.configure(text=tr("sys_specs").upper())
        self.h2.configure(text=tr("os_specs").upper())
        if not self._trim_cooldown:
            self.btn_trim.configure(text=f"{tr('btn_trim_ram')}  ⓘ")
        if not self._disk_cleaning:
            self.btn_disk.configure(text=f"{tr('btn_clean_disk')}  ⓘ")
        self.btn_reset.configure(text=tr("btn_reset_graphs"))
        self.gm_switch.configure(text=tr("auto_gm_label"))
        self.t.clear()
        self.t_os.clear()
        self._init_static()