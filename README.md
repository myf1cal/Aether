# Aether — PC Monitor & Benchmark

Lightweight, modern dark-themed desktop utility for Windows to monitor hardware telemetry, run synthetic benchmarks, and clean system junk.

## Features
- **Real-time Telemetry:** Smooth 60 FPS graphs for CPU, RAM, Network, and Disk I/O with live heartbeat pulse.
- **Auto Game Mode:** Automatically detects running games, trims unused RAM cache on launch, and lowers background polling overhead.
- **Built-in Benchmark:** Multi-core CPU, RAM bandwidth, Disk Read/Write, and OpenGL GPU tests with saved run history and all-time average comparisons.
- **Quick Tools:** One-click RAM cache cleaner and selective Disk Cleanup (Temp files, system caches, Recycle Bin, Downloads).
- **Bilingual & Customizable:** Instant `EN ⇄ RU` language switch, 4 accent color themes, and system tray integration with live hover stats.

## Run from Source
```bash
pip install -r requirements.txt
python Aether.py