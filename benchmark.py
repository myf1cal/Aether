import ctypes
import hashlib
import json
import math
import os
import re
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
import psutil
from sensors import cpu_name, get_hardware_specs, hb

_BASE_DIR = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.abspath(".")
BENCH_HISTORY_PATH = os.path.join(_BASE_DIR, "benchmarks.json")


def load_bench_history():
    try:
        with open(BENCH_HISTORY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def save_bench_result(entry):
    hist = load_bench_history()
    hist.insert(0, entry)
    hist = hist[:20] 
    try:
        with open(BENCH_HISTORY_PATH, "w", encoding="utf-8") as f:
            json.dump(hist, f, indent=2, ensure_ascii=False)
    except Exception:
        pass
    return hist


def clear_bench_history():
    try:
        if os.path.exists(BENCH_HISTORY_PATH):
            os.remove(BENCH_HISTORY_PATH)
    except Exception:
        pass


def analyze_bench_history(hist):
    if not hist:
        return None

    n = len(hist)
    avgs = {}
    maxs = {}
    for k in ("overall", "cpu", "ram", "disk", "gpu"):
        vals = [float(item.get(k, 0)) for item in hist]
        avgs[k] = sum(vals) / n
        maxs[k] = max(vals) if vals else 0.0

    cpu_kops = []
    ram_gbs = []
    disk_r = []
    disk_w = []
    gpu_fps = []

    for item in hist:
        if "cpu_kops" in item:
            cpu_kops.append(float(item["cpu_kops"]))
        else:
            m = re.search(r"([\d.]+)\s*kOps/s", item.get("cpu_detail", ""))
            if m:
                cpu_kops.append(float(m.group(1)))

        if "ram_gbs" in item:
            ram_gbs.append(float(item["ram_gbs"]))
        else:
            m = re.search(r"([\d.]+)\s*GB/s", item.get("ram_detail", ""))
            if m:
                ram_gbs.append(float(m.group(1)))

        if "disk_read" in item and "disk_write" in item:
            disk_r.append(float(item["disk_read"]))
            disk_w.append(float(item["disk_write"]))
        else:
            mr = re.search(r"R:\s*([\d.]+)\s*MB/s", item.get("disk_detail", ""))
            mw = re.search(r"W:\s*([\d.]+)\s*MB/s", item.get("disk_detail", ""))
            if mr:
                disk_r.append(float(mr.group(1)))
            if mw:
                disk_w.append(float(mw.group(1)))

        if "gpu_fps" in item:
            gpu_fps.append(float(item["gpu_fps"]))
        else:
            m = re.search(r"([\d.]+)\s*FPS", item.get("gpu_detail", ""))
            if m:
                gpu_fps.append(float(m.group(1)))

    avg_metrics = {
        "cpu": f"{sum(cpu_kops) / len(cpu_kops):.1f} kOps/s" if cpu_kops else "",
        "ram": f"{sum(ram_gbs) / len(ram_gbs):.2f} GB/s" if ram_gbs else "",
        "disk": (
            f"R: {sum(disk_r) / len(disk_r):.0f} MB/s · W: {sum(disk_w) / len(disk_w):.0f} MB/s"
            if (disk_r and disk_w) else ""
        ),
        "gpu": f"{sum(gpu_fps) / len(gpu_fps):.0f} FPS" if gpu_fps else "",
    }

    return {
        "count": n,
        "avgs": avgs,
        "maxs": maxs,
        "avg_metrics": avg_metrics
    }


def _cpu_worker(duration_sec=1.6):
    end_t = time.perf_counter() + duration_sec
    data = b"AetherBenchmarkPayload_2026_x86_64" * 64
    ops = 0
    acc = 1.0001
    while time.perf_counter() < end_t:
        for _ in range(40):
            data = hashlib.sha256(data).digest()
            acc = math.sin(acc) + math.cos(acc * 1.1) + 1.5
        ops += 40
    return ops


def run_cpu_bench():
    threads = psutil.cpu_count(logical=True) or 4
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=threads) as pool:
        futures = [pool.submit(_cpu_worker, 1.6) for _ in range(threads)]
        total_ops = sum(f.result() for f in futures)
    elapsed = max(0.1, time.perf_counter() - t0)
    ops_per_sec = total_ops / elapsed
    kops = ops_per_sec / 1000.0
    score = int(round(ops_per_sec / 18.0))
    return score, f"{kops:.1f} kOps/s ({threads}T)", round(kops, 2)


def run_ram_bench():
    block_mb = 64
    size = block_mb * 1024 * 1024
    src = ctypes.create_string_buffer(size)
    dst = ctypes.create_string_buffer(size)
    ctypes.memset(src, 0xAB, size)

    ctypes.memmove(dst, src, size)

    passes = 16
    t0 = time.perf_counter()
    for _ in range(passes):
        ctypes.memmove(dst, src, size)
    elapsed = max(0.01, time.perf_counter() - t0)

    total_gb = (size * passes) / (1024 ** 3)
    gb_per_sec = total_gb / elapsed
    score = int(round(gb_per_sec * 165))
    return score, f"{gb_per_sec:.2f} GB/s", round(gb_per_sec, 2)


def run_disk_bench():
    chunk = os.urandom(4 * 1024 * 1024)
    chunks_count = 64
    tmp_path = os.path.join(tempfile.gettempdir(), "aether_bench_io.tmp")

    write_mb_s = 0.0
    read_mb_s = 0.0
    try:
        t0 = time.perf_counter()
        with open(tmp_path, "wb", buffering=0) as f:
            for _ in range(chunks_count):
                f.write(chunk)
            f.flush()
            os.fsync(f.fileno())
        w_time = max(0.01, time.perf_counter() - t0)
        write_mb_s = 256.0 / w_time

        t1 = time.perf_counter()
        with open(tmp_path, "rb", buffering=0) as f:
            while f.read(4 * 1024 * 1024):
                pass
        r_time = max(0.01, time.perf_counter() - t1)
        read_mb_s = 256.0 / r_time
    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass

    avg_speed = (write_mb_s + read_mb_s) / 2.0
    score = int(round(avg_speed * 2.2))
    return score, f"R: {read_mb_s:.0f} MB/s · W: {write_mb_s:.0f} MB/s", round(read_mb_s, 1), round(write_mb_s, 1)


def run_gpu_bench():
    if sys.platform == "win32":
        try:
            user32 = ctypes.windll.user32
            gdi32 = ctypes.windll.gdi32
            opengl32 = ctypes.windll.opengl32

            hwnd = user32.CreateWindowExW(
                0, "STATIC", "AetherGL", 0, 0, 0, 640, 480, 0, 0, 0, 0
            )
            hdc = user32.GetDC(hwnd)

            class PIXELFORMATDESCRIPTOR(ctypes.Structure):
                _fields_ = [
                    ("nSize", ctypes.c_ushort), ("nVersion", ctypes.c_ushort),
                    ("dwFlags", ctypes.c_ulong), ("iPixelType", ctypes.c_ubyte),
                    ("cColorBits", ctypes.c_ubyte), ("cRedBits", ctypes.c_ubyte),
                    ("cRedShift", ctypes.c_ubyte), ("cGreenBits", ctypes.c_ubyte),
                    ("cGreenShift", ctypes.c_ubyte), ("cBlueBits", ctypes.c_ubyte),
                    ("cBlueShift", ctypes.c_ubyte), ("cAlphaBits", ctypes.c_ubyte),
                    ("cAlphaShift", ctypes.c_ubyte), ("cAccumBits", ctypes.c_ubyte),
                    ("cAccumRedBits", ctypes.c_ubyte), ("cAccumGreenBits", ctypes.c_ubyte),
                    ("cAccumBlueBits", ctypes.c_ubyte), ("cAccumAlphaBits", ctypes.c_ubyte),
                    ("cDepthBits", ctypes.c_ubyte), ("cStencilBits", ctypes.c_ubyte),
                    ("cAuxBuffers", ctypes.c_ubyte), ("iLayerType", ctypes.c_ubyte),
                    ("bReserved", ctypes.c_ubyte), ("dwLayerMask", ctypes.c_ulong),
                    ("dwVisibleMask", ctypes.c_ulong), ("dwDamageMask", ctypes.c_ulong),
                ]

            pfd = PIXELFORMATDESCRIPTOR()
            pfd.nSize = ctypes.sizeof(PIXELFORMATDESCRIPTOR)
            pfd.nVersion = 1
            pfd.dwFlags = 0x00000020 | 0x00000004 | 0x00000001
            pfd.iPixelType = 0
            pfd.cColorBits = 32
            pfd.cDepthBits = 24

            pf = gdi32.ChoosePixelFormat(hdc, ctypes.byref(pfd))
            gdi32.SetPixelFormat(hdc, pf, ctypes.byref(pfd))
            hglrc = opengl32.wglCreateContext(hdc)
            opengl32.wglMakeCurrent(hdc, hglrc)

            GL_TRIANGLES = 0x0004
            GL_COLOR_BUFFER_BIT = 0x00004000
            GL_DEPTH_BUFFER_BIT = 0x00000100

            glClear = opengl32.glClear
            glBegin = opengl32.glBegin
            glEnd = opengl32.glEnd
            glVertex3f = opengl32.glVertex3f
            glColor3f = opengl32.glColor3f
            glFinish = opengl32.glFinish

            glVertex3f.argtypes = [ctypes.c_float, ctypes.c_float, ctypes.c_float]
            glColor3f.argtypes = [ctypes.c_float, ctypes.c_float, ctypes.c_float]

            frames = 0
            t0 = time.perf_counter()
            end_t = t0 + 1.6
            while time.perf_counter() < end_t:
                glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
                glBegin(GL_TRIANGLES)
                for i in range(600):
                    v = (i % 100) * 0.01 - 0.5
                    glColor3f(0.4, 0.5, 0.9)
                    glVertex3f(v, 0.5, 0.0)
                    glVertex3f(-0.5, v, 0.0)
                    glVertex3f(0.5, -v, 0.0)
                glEnd()
                gdi32.SwapBuffers(hdc)
                frames += 1
            glFinish()
            elapsed = max(0.1, time.perf_counter() - t0)

            opengl32.wglMakeCurrent(0, 0)
            opengl32.wglDeleteContext(hglrc)
            user32.ReleaseDC(hwnd, hdc)
            user32.DestroyWindow(hwnd)

            fps = frames / elapsed
            score = int(round(fps * 12.5))
            return score, f"{fps:.0f} FPS (OpenGL)", round(fps, 1)
        except Exception:
            pass

    t0 = time.perf_counter()
    iters = 0
    while time.perf_counter() - t0 < 1.5:
        for i in range(5000):
            _ = (i * 0.1234) ** 0.5
        iters += 5000
    fps_eq = iters / 1000.0
    score = int(round(iters / 1200))
    return score, f"{fps_eq:.0f} kTris/s", round(fps_eq, 1)


def run_full_benchmark(progress_cb, done_cb):
    def _worker():
        try:
            progress_cb(0.25, "bench_step_cpu")
            cpu_score, cpu_detail, cpu_kops = run_cpu_bench()

            progress_cb(0.50, "bench_step_ram")
            ram_score, ram_detail, ram_gbs = run_ram_bench()

            progress_cb(0.75, "bench_step_disk")
            disk_score, disk_detail, disk_r, disk_w = run_disk_bench()

            progress_cb(0.98, "bench_step_gpu")
            gpu_score, gpu_detail, gpu_fps = run_gpu_bench()

            overall = int(round(
                cpu_score * 0.35 +
                gpu_score * 0.35 +
                ram_score * 0.15 +
                disk_score * 0.15
            ))

            specs = get_hardware_specs()
            ram_gb = hb(psutil.virtual_memory().total)
            hw_summary = f"{cpu_name()} · {specs.get('gpu', 'GPU')} · {ram_gb}"

            result = {
                "date": time.strftime("%Y-%m-%d %H:%M"),
                "overall": overall,
                "cpu": cpu_score,
                "cpu_detail": cpu_detail,
                "cpu_kops": cpu_kops,
                "ram": ram_score,
                "ram_detail": ram_detail,
                "ram_gbs": ram_gbs,
                "disk": disk_score,
                "disk_detail": disk_detail,
                "disk_read": disk_r,
                "disk_write": disk_w,
                "gpu": gpu_score,
                "gpu_detail": gpu_detail,
                "gpu_fps": gpu_fps,
                "hardware": hw_summary
            }
            hist = save_bench_result(result)
            progress_cb(1.0, "bench_done")
            done_cb(result, hist, None)
        except Exception as e:
            done_cb(None, load_bench_history(), str(e))

    threading.Thread(target=_worker, daemon=True).start()