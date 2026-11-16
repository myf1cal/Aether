<p align="center">
  <img src="assets/banner.jpg" width="100%" alt="Aether Banner">
</p>

<div align="center">

![GitHub release](https://img.shields.io/github/v/release/myf1cal/Aether?color=6366f1&include_prereleases&style=flat-square)
![License](https://img.shields.io/github/license/myf1cal/Aether?color=34d399&style=flat-square)
![Python](https://img.shields.io/badge/Python-3.10%2B-38bdf8?style=flat-square)
![Platform](https://img.shields.io/badge/Platform-Windows%2011%2F10-71717a?style=flat-square)

</div>

---

# Aether — PC Monitor & Benchmark

**Aether** is a lightweight, modern dark-themed desktop utility for Windows designed to monitor hardware telemetry in real-time, run built-in synthetic benchmarks, and safely clean system junk.

## ✨ Features
- **Real-time Telemetry:** Smooth 60 FPS graphs for CPU, RAM, Network, and Disk I/O with a live heartbeat pulse indicator.
- **Auto Game Mode:** Automatically detects running games, frees up unused RAM cache on launch, and minimizes background polling overhead.
- **Built-in Benchmark:** Multi-core CPU, RAM bandwidth, Disk Read/Write, and OpenGL GPU tests with persistent history and all-time average comparisons.
- **Quick Tools:** One-click RAM cache cleaner and a selective Disk Cleanup modal (Temp files, update caches, Recycle Bin, and Downloads).
- **Customizable & Bilingual:** Instant `EN ⇄ RU` language switcher, 4 accent color themes, and system tray integration with live stats on hover.

---

## 📥 Download Executable (No Python required)

You don't need to install Python or set up the source code if you just want to run the app:
1. Go to the 👉 **[Releases](../../releases)** page on the right side of the repository.
2. Download the latest **`Aether.exe`** binary from the newest release.
3. Run it — all configurations and benchmark history will automatically be saved next to the executable.

---

## 🛠 Run from Source (For Developers)

If you prefer to run the project via the Python interpreter or modify the source code:

1. Clone the repository or download the source:
   ```bash
   git clone [https://github.com/myf1cal/Aether.git](https://github.com/myf1cal/Aether.git)
   cd Aether

1. Install the required dependencies:
pip install -r requirements.txt



2. Run the application:
python Aether.py 




## 📥 Building from Source (.exe)
To bundle the application into a single standalone executable using PyInstaller:

python -m pip install pyinstaller

python -m PyInstaller --noconsole --onefile --name "Aether" --icon="aether.ico" --collect-all customtkinter Aether.py

The compiled file will be located in the dist/Aether.exe directory 



## 📄 License
This project is licensed under the MIT License. You are free to use, modify, and distribute it.