import ctypes
from ctypes import wintypes
import os
import platform
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from collections import deque
import psutil
from config import CPU_SMOOTH, SENSOR_SMOOTH, HIST, get_auto_game_mode

_lhm_computer = None

_GAME_EXES = {
    "eldenring.exe", "risk of rain 2.exe", "sekiro.exe", "darksoulsiii.exe",
    "terraria.exe", "tmodloader.exe", "dota2.exe", "rustclient.exe",
    "projectzomboid64.exe", "valheim.exe", "javaw.exe", "osu!.exe",
    "cs2.exe", "valorant-win64-shipping.exe", "cyberpunk2077.exe",
    "witcher3.exe", "gtav.exe", "rdr2.exe", "bg3.exe", "bg3_dx11.exe",
    "helldivers2.exe", "apex_legends.exe", "r5apex.exe", "fortniteclient-win64-shipping.exe",
    "robloxplayerbeta.exe", "hollow_knight.exe", "celeste.exe", "hades.exe", "hades2.exe"
}

_GAME_PATH_MARKERS = ("\\steamapps\\common\\", "\\epic games\\", "\\riot games\\", "\\gog games\\")
_NON_GAME_EXES = {
    "steam.exe", "steamwebhelper.exe", "epicgameslauncher.exe", "wallpaper32.exe",
    "wallpaper64.exe", "obs64.exe", "discord.exe", "code.exe", "python.exe", "pythonw.exe"
}


def detect_running_game():
    if not get_auto_game_mode():
        return None
    try:
        for proc in psutil.process_iter(["name", "exe"]):
            pname = (proc.info.get("name") or "").lower()
            if not pname or pname in _NON_GAME_EXES:
                continue
            if pname in _GAME_EXES:
                clean = os.path.splitext(proc.info["name"])[0]
                return clean[:20]

            exe_path = (proc.info.get("exe") or "").lower()
            if exe_path and any(m in exe_path for m in _GAME_PATH_MARKERS):
                if "crash" not in pname and "helper" not in pname and "redist" not in pname and "launcher" not in pname:
                    clean = os.path.splitext(proc.info["name"])[0]
                    return clean[:20]
    except Exception:
        pass
    return None


def safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def hb(n):
    n = float(n)
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or u == "TB":
            return f"{n:.0f} {u}" if u == "B" else f"{n:.2f} {u}"
        n /= 1024


def hr(n):
    return "--" if n is None else hb(n) + "/s"


def fmt_up_sec(s):
    d, r = divmod(int(s), 86400)
    h, r = divmod(r, 3600)
    m, sec = divmod(r, 60)
    if d:
        return f"{d}d {h}h {m:02d}m {sec:02d}s"
    return f"{h}h {m:02d}m {sec:02d}s"


def clean_ram_cache():
    before = psutil.virtual_memory().available
    if sys.platform == "win32":
        try:
            kernel32 = ctypes.windll.kernel32
            psapi = ctypes.windll.psapi
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            PROCESS_SET_QUOTA = 0x0100

            for proc in psutil.process_iter(["pid"]):
                pid = proc.info["pid"]
                if pid <= 4:
                    continue
                handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_SET_QUOTA, False, pid)
                if handle:
                    try:
                        psapi.EmptyWorkingSet(handle)
                    except Exception:
                        pass
                    finally:
                        kernel32.CloseHandle(handle)
        except Exception:
            pass
    after = psutil.virtual_memory().available
    return max(0, after - before)


def _dir_size(folder, skip_aether=True):
    total = 0
    if not folder or not os.path.isdir(folder):
        return 0
    try:
        for entry in os.scandir(folder):
            if skip_aether and entry.name.startswith("aether_"):
                continue
            try:
                if entry.is_file(follow_symlinks=False) or entry.is_symlink():
                    total += entry.stat(follow_symlinks=False).st_size
                elif entry.is_dir(follow_symlinks=False):
                    for root, _, files in os.walk(entry.path):
                        for fn in files:
                            try:
                                total += os.path.getsize(os.path.join(root, fn))
                            except Exception:
                                pass
            except Exception:
                pass
    except Exception:
        pass
    return total


def _clean_folder_contents(folder, skip_aether=True):
    freed = 0
    if not folder or not os.path.isdir(folder):
        return 0
    try:
        for entry in os.scandir(folder):
            if skip_aether and entry.name.startswith("aether_"):
                continue
            try:
                if entry.is_file(follow_symlinks=False) or entry.is_symlink():
                    sz = entry.stat(follow_symlinks=False).st_size
                    os.unlink(entry.path)
                    freed += sz
                elif entry.is_dir(follow_symlinks=False):
                    dir_sz = _dir_size(entry.path, skip_aether=False)
                    shutil.rmtree(entry.path, ignore_errors=False)
                    freed += dir_sz
            except Exception:
                continue
    except Exception:
        pass
    return freed


def _get_recycle_bin_size():
    if sys.platform != "win32":
        return 0
    try:
        class SHQUERYRBINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("i64Size", ctypes.c_int64),
                ("i64NumItems", ctypes.c_int64),
            ]

        info = SHQUERYRBINFO()
        info.cbSize = ctypes.sizeof(SHQUERYRBINFO)
        res = ctypes.windll.shell32.SHQueryRecycleBinW(None, ctypes.byref(info))
        if res == 0 and info.i64Size > 0:
            return int(info.i64Size)
    except Exception:
        pass
    return 0


def _empty_recycle_bin():
    if sys.platform != "win32":
        return 0
    sz = _get_recycle_bin_size()
    try:
        # SHERB_NOCONFIRMATION (1) | SHERB_NOPROGRESSUI (2) | SHERB_NOSOUND (4) = 7
        ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 7)
        return sz
    except Exception:
        return 0


def _get_cleanup_paths():
    win_dir = os.environ.get("SystemRoot", r"C:\Windows")
    local_app = os.environ.get("LOCALAPPDATA", "")
    user_temp = tempfile.gettempdir()

    temp_dirs = []
    if user_temp and os.path.isdir(user_temp):
        temp_dirs.append(user_temp)
    win_temp = os.path.join(win_dir, "Temp")
    if os.path.isdir(win_temp) and win_temp not in temp_dirs:
        temp_dirs.append(win_temp)

    cache_dirs = []
    for sub in (r"SoftwareDistribution\Download", "Prefetch"):
        p = os.path.join(win_dir, sub)
        if os.path.isdir(p):
            cache_dirs.append(p)

    explorer_cache = os.path.join(local_app, r"Microsoft\Windows\Explorer")
    downloads_dir = os.path.join(os.path.expanduser("~"), "Downloads")

    return temp_dirs, cache_dirs, explorer_cache, downloads_dir


def scan_disk_junk():
    temp_dirs, cache_dirs, explorer_cache, downloads_dir = _get_cleanup_paths()

    temp_sz = sum(_dir_size(d, skip_aether=True) for d in temp_dirs)

    cache_sz = sum(_dir_size(d, skip_aether=False) for d in cache_dirs)
    if os.path.isdir(explorer_cache):
        try:
            for entry in os.scandir(explorer_cache):
                if entry.is_file() and entry.name.lower().startswith(("thumbcache_", "iconcache_")):
                    try:
                        cache_sz += entry.stat().st_size
                    except Exception:
                        pass
        except Exception:
            pass

    recycle_sz = _get_recycle_bin_size()
    downloads_sz = _dir_size(downloads_dir, skip_aether=False)

    return {
        "temp": temp_sz,
        "cache": cache_sz,
        "recycle": recycle_sz,
        "downloads": downloads_sz,
    }


def clean_disk_junk(categories=None):
    if categories is None:
        categories = {"temp", "cache"}
    else:
        categories = set(categories)

    freed_bytes = 0
    temp_dirs, cache_dirs, explorer_cache, downloads_dir = _get_cleanup_paths()

    if "temp" in categories:
        for d in temp_dirs:
            freed_bytes += _clean_folder_contents(d, skip_aether=True)

    if "cache" in categories:
        for d in cache_dirs:
            freed_bytes += _clean_folder_contents(d, skip_aether=False)
        if os.path.isdir(explorer_cache):
            try:
                for entry in os.scandir(explorer_cache):
                    if entry.is_file() and entry.name.lower().startswith(("thumbcache_", "iconcache_")):
                        try:
                            sz = entry.stat().st_size
                            os.unlink(entry.path)
                            freed_bytes += sz
                        except Exception:
                            pass
            except Exception:
                pass

    if "recycle" in categories:
        freed_bytes += _empty_recycle_bin()

    if "downloads" in categories:
        freed_bytes += _clean_folder_contents(downloads_dir, skip_aether=False)

    return freed_bytes


def cpu_name():
    try:
        if sys.platform == "win32":
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as k:
                return winreg.QueryValueEx(k, "ProcessorNameString")[0].strip()
        if sys.platform.startswith("linux"):
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if line.startswith("model name"):
                        return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return platform.processor() or "Unknown CPU"


def get_hardware_specs():
    specs = {
        "mobo": "Unknown",
        "bios": "Unknown",
        "gpu": "Unknown",
        "ram_speed": "",
        "drives": ""
    }

    if sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\BIOS") as k:
                manuf = safe(lambda: winreg.QueryValueEx(k, "BaseBoardManufacturer")[0].strip(), "")
                prod = safe(lambda: winreg.QueryValueEx(k, "BaseBoardProduct")[0].strip(), "")
                bios_v = safe(lambda: winreg.QueryValueEx(k, "BIOSVersion")[0].strip(), "")
                bios_d = safe(lambda: winreg.QueryValueEx(k, "BIOSReleaseDate")[0].strip(), "")
                if manuf or prod:
                    specs["mobo"] = f"{manuf} {prod}".strip()
                if bios_v:
                    specs["bios"] = f"{bios_v}" + (f" ({bios_d})" if bios_d else "")
        except Exception:
            pass

    gpu_found = False
    try:
        import pynvml  # type: ignore
        pynvml.nvmlInit()
        if pynvml.nvmlDeviceGetCount() > 0:
            h = pynvml.nvmlDeviceGetHandleByIndex(0)
            name = pynvml.nvmlDeviceGetName(h)
            if isinstance(name, bytes):
                name = name.decode("utf-8")
            mem_info = pynvml.nvmlDeviceGetMemoryInfo(h)
            vram_gb = mem_info.total / (1024 ** 3)
            specs["gpu"] = f"{name} ({vram_gb:.0f} GB VRAM)"
            gpu_found = True
        pynvml.nvmlShutdown()
    except Exception:
        pass

    if not gpu_found and sys.platform == "win32":
        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            out = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                startupinfo=startupinfo, stderr=subprocess.DEVNULL, timeout=2
            ).decode().strip()
            if out:
                g_name, g_mem = [x.strip() for x in out.splitlines()[0].split(",", 1)]
                specs["gpu"] = f"{g_name} ({int(g_mem) / 1024:.0f} GB VRAM)"
                gpu_found = True
        except Exception:
            pass

    if not gpu_found and sys.platform == "win32":
        try:
            import winreg
            key_path = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}\0000"
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as k:
                desc = winreg.QueryValueEx(k, "DriverDesc")[0].strip()
                if desc:
                    specs["gpu"] = desc
        except Exception:
            pass

    if sys.platform == "win32":
        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            out = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_PhysicalMemory | Select-Object -First 1 -ExpandProperty ConfiguredClockSpeed)"],
                startupinfo=startupinfo, stderr=subprocess.DEVNULL, timeout=3
            ).decode().strip()
            if out.isdigit() and int(out) > 0:
                specs["ram_speed"] = f"{out} MHz"
        except Exception:
            pass

    drives = []
    for p in safe(lambda: psutil.disk_partitions(all=False), []):
        if not p.fstype or "cdrom" in p.opts:
            continue
        u = safe(lambda: psutil.disk_usage(p.mountpoint))
        if u:
            letter = p.mountpoint.rstrip("\\/")
            drives.append(f"{letter} ({u.total / (1024 ** 3):.0f} GB)")
    if drives:
        specs["drives"] = "  ·  ".join(drives)

    return specs


def get_resource_path(relative_path):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


def get_nvidia_sensors():
    temps, fans, power = {}, {}, {}
    try:
        import pynvml  # type: ignore
        pynvml.nvmlInit()
        count = pynvml.nvmlDeviceGetCount()
        for i in range(count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            name = pynvml.nvmlDeviceGetName(handle)
            if isinstance(name, bytes):
                name = name.decode("utf-8")

            temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
            temps[name] = float(temp)

            try:
                fan_pct = pynvml.nvmlDeviceGetFanSpeed(handle)
                fans[f"{name} Fan"] = float(fan_pct)
            except Exception:
                pass

            try:
                pwr_mw = pynvml.nvmlDeviceGetPowerUsage(handle)
                power[f"{name} Power"] = float(pwr_mw) / 1000.0
            except Exception:
                pass

        pynvml.nvmlShutdown()
        if temps or fans or power:
            return temps, fans, power
    except Exception:
        pass

    try:
        startupinfo = None
        if sys.platform == "win32":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,temperature.gpu,fan.speed,power.draw", "--format=csv,noheader,nounits"],
            startupinfo=startupinfo, stderr=subprocess.DEVNULL, timeout=3
        ).decode().strip()
        if out:
            parts = [p.strip() for p in out.splitlines()[0].split(",")]
            if len(parts) >= 2:
                temps[parts[0]] = float(parts[1])
            if len(parts) >= 3:
                try:
                    fans[f"{parts[0]} Fan"] = float(parts[2])
                except ValueError:
                    pass
            if len(parts) >= 4:
                try:
                    power[f"{parts[0]} Power"] = float(parts[3])
                except ValueError:
                    pass
    except Exception:
        pass
    return temps, fans, power


def get_windows_hwm():
    global _lhm_computer
    temps, fans, power = {}, {}, {}
    if sys.platform != "win32":
        return temps, fans, power

    try:
        import clr  # type: ignore
        dll_path = get_resource_path("LibreHardwareMonitorLib.dll")
        if os.path.exists(dll_path):
            if _lhm_computer is None:
                clr.AddReference(dll_path)
                from LibreHardwareMonitor import Hardware  # type: ignore
                _lhm_computer = Hardware.Computer()
                _lhm_computer.IsCpuEnabled = True
                _lhm_computer.IsGpuEnabled = True
                _lhm_computer.IsMotherboardEnabled = True
                _lhm_computer.IsStorageEnabled = True
                _lhm_computer.Open()

            for hardware in _lhm_computer.Hardware:
                hardware.Update()
                all_sensors = list(hardware.Sensors)
                for subhardware in hardware.SubHardware:
                    subhardware.Update()
                    all_sensors.extend(subhardware.Sensors)

                for sensor in all_sensors:
                    if sensor.Value is not None:
                        stype = str(sensor.SensorType)
                        label = f"{hardware.Name} - {sensor.Name}"
                        if stype == "Temperature":
                            temps[label] = float(sensor.Value)
                        elif stype == "Fan":
                            fans[label] = float(sensor.Value)
                        elif stype == "Power":
                            power[label] = float(sensor.Value)

            if temps or fans or power:
                return temps, fans, power
    except Exception:
        pass

    try:
        import wmi  # type: ignore
        for ns in ("root\\LibreHardwareMonitor", "root\\OpenHardwareMonitor"):
            try:
                w = wmi.WMI(namespace=ns)
                sensors = w.Sensor()
                if sensors:
                    for s in sensors:
                        if s.SensorType == "Temperature":
                            temps[str(s.Name)] = float(s.Value)
                        elif s.SensorType == "Fan":
                            fans[str(s.Name)] = float(s.Value)
                        elif s.SensorType == "Power":
                            power[str(s.Name)] = float(s.Value)
                    break
            except Exception:
                continue
    except ImportError:
        pass

    return temps, fans, power


def best_cpu_temp(temps):
    if not temps:
        return None
    for k, v in temps.items():
        if any(word in k.lower() for word in ("cpu", "package", "core", "tctl", "tdie")):
            return v
    return next(iter(temps.values()))


class TelemetryCollector:
    def __init__(self):
        self.data = {}
        self.tick_count = 0
        self.t_prev = time.time()
        self.hist = {k: deque([0.0] * HIST, maxlen=HIST) for k in ("cpu", "mem", "down", "up", "dr", "dw")}
        self.peaks = {"cpu": 0.0, "gpu_temp": 0.0}
        self.active_game = None
        self.per_avg = None
        self.io_prev = None
        self.net_prev = None
        self.st_prev = None
        self.nic_prev = {}
        self._ema = {}
        safe(lambda: psutil.cpu_percent(percpu=True))

    def reset_history(self):
        for k in self.hist:
            self.hist[k].clear()
            self.hist[k].extend([0.0] * HIST)
        self.peaks = {"cpu": self.data.get("cpu") or 0.0, "gpu_temp": 0.0}

    def smooth(self, key, val, alpha=SENSOR_SMOOTH):
        if val is None:
            return None
        val = float(val)
        if key not in self._ema:
            self._ema[key] = val
        else:
            self._ema[key] = alpha * val + (1.0 - alpha) * self._ema[key]
        return self._ema[key]

    def collect(self):
        self.tick_count += 1
        d, now = self.data, time.time()
        dt = max(now - self.t_prev, 1e-3)
        self.t_prev = now

        if self.tick_count % 5 == 1:
            detected = detect_running_game()
            if detected and self.active_game != detected:
                clean_ram_cache()
                self.peaks = {"cpu": 0.0, "gpu_temp": 0.0}
            self.active_game = detected
        d["active_game"] = self.active_game

        per = safe(lambda: psutil.cpu_percent(percpu=True))
        if per:
            if not self.per_avg or len(self.per_avg) != len(per):
                self.per_avg = [float(x) for x in per]
            else:
                self.per_avg = [CPU_SMOOTH * r + (1.0 - CPU_SMOOTH) * a for r, a in zip(per, self.per_avg)]
            d["per"] = self.per_avg
            cpu_val = sum(self.per_avg) / len(self.per_avg)
            d["cpu"] = cpu_val
            if cpu_val > self.peaks["cpu"]:
                self.peaks["cpu"] = cpu_val

        f = safe(psutil.cpu_freq)
        d["freq"] = f
        d["freq_smooth"] = self.smooth("freq", f.current) if f else None

        m = safe(psutil.virtual_memory)
        d["mem"] = m
        d["mem_pct"] = self.smooth("mem_pct", m.percent) if m else None

        sw = safe(psutil.swap_memory)
        d["swap"] = sw
        d["swap_pct"] = self.smooth("swap_pct", sw.percent) if sw else None

        d["procs"] = safe(lambda: len(psutil.pids()))

        st = safe(psutil.cpu_stats)
        if st and self.st_prev:
            d["ctx"] = self.smooth("ctx", (st.ctx_switches - self.st_prev.ctx_switches) / dt)
            d["irq"] = self.smooth("irq", (st.interrupts - self.st_prev.interrupts) / dt)
        self.st_prev = st

        io = d["io"] = safe(psutil.disk_io_counters)
        if io and self.io_prev:
            d["dr"] = self.smooth("dr", (io.read_bytes - self.io_prev.read_bytes) / dt)
            d["dw"] = self.smooth("dw", (io.write_bytes - self.io_prev.write_bytes) / dt)
        self.io_prev = io

        net = d["net"] = safe(psutil.net_io_counters)
        if net and self.net_prev:
            d["down"] = self.smooth("down", (net.bytes_recv - self.net_prev.bytes_recv) / dt)
            d["up"] = self.smooth("up", (net.bytes_sent - self.net_prev.bytes_sent) / dt)
        self.net_prev = net

        nic = safe(lambda: psutil.net_io_counters(pernic=True), {})
        nic_rates = {}
        for k, v in nic.items():
            if k in self.nic_prev:
                r_dn = (v.bytes_recv - self.nic_prev[k].bytes_recv) / dt
                r_up = (v.bytes_sent - self.nic_prev[k].bytes_sent) / dt
                nic_rates[k] = (self.smooth(f"nic_dn_{k}", r_dn), self.smooth(f"nic_up_{k}", r_up))
        d["nic_rates"] = nic_rates
        self.nic_prev = nic

        raw_temps = safe(lambda: {e.label or 'Sensor': e.current for t in psutil.sensors_temperatures().values() for e in t}, {})
        raw_fans = safe(lambda: {e.label or 'Fan': e.current for f in psutil.sensors_fans().values() for e in f}, {})
        raw_power = {}

        wmi_t, wmi_f, wmi_p = get_windows_hwm()
        raw_temps.update(wmi_t)
        raw_fans.update(wmi_f)
        raw_power.update(wmi_p)

        gpu_t, gpu_f, gpu_p = get_nvidia_sensors()
        raw_temps.update(gpu_t)
        raw_power.update(gpu_p)

        smoothed_gpu_t = {k: self.smooth(f"gpu_{k}", v) for k, v in gpu_t.items()}
        d["gpu_temps"] = smoothed_gpu_t
        if smoothed_gpu_t:
            cur_g = next(iter(smoothed_gpu_t.values()))
            if cur_g and cur_g > self.peaks["gpu_temp"]:
                self.peaks["gpu_temp"] = cur_g

        d["temps"] = {k: self.smooth(f"temp_{k}", v) for k, v in raw_temps.items()}
        d["fans"] = {k: self.smooth(f"fan_{k}", v) for k, v in raw_fans.items()}
        d["gpu_fans"] = {k: self.smooth(f"gfan_{k}", v) for k, v in gpu_f.items()}
        d["power"] = {k: self.smooth(f"pwr_{k}", v) for k, v in raw_power.items()}
        d["bat"] = safe(lambda: psutil.sensors_battery())
        d["peaks"] = self.peaks

        if self.tick_count % 5 == 1:
            parts = []
            for p in safe(lambda: psutil.disk_partitions(all=False), []):
                if not p.fstype or "cdrom" in p.opts:
                    continue
                u = safe(lambda: psutil.disk_usage(p.mountpoint))
                if u:
                    parts.append((p.mountpoint, p.fstype, u))
            d["parts"] = parts

            addrs, stats = safe(psutil.net_if_addrs, {}), safe(psutil.net_if_stats, {})
            info = {}
            for name, s in stats.items():
                if not s.isup:
                    continue
                ip = next((a.address for a in addrs.get(name, []) if a.family == socket.AF_INET), None)
                if ip and not ip.startswith("127."):
                    info[name] = (ip, s.speed)
            d["nic_info"] = info

        for k, v in (
            ("cpu", d.get("cpu")),
            ("mem", d.get("mem_pct")),
            ("down", d.get("down")),
            ("up", d.get("up")),
            ("dr", d.get("dr")),
            ("dw", d.get("dw")),
        ):
            self.hist[k].append(v or 0.0)