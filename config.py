import json
import os
import sys
import tkinter as tk
from tkinter import font as tkfont


def pick_rounded_font():
    preferred = ["Century Gothic", "Bahnschrift", "Trebuchet MS", "Verdana", "Segoe UI"]
    try:
        r = tk.Tk()
        r.withdraw()
        available = set(tkfont.families(r))
        r.destroy()
        for name in preferred:
            if name in available:
                return name
    except Exception:
        pass
    return "Century Gothic"


FONT = pick_rounded_font()

# Цветовая палитра (Modern Dark UI)
BG = "#0d0e12"
SIDE = "#121318"
CARD = "#17181e"
LINE = "#272832"
TEXT = "#f4f4f5"
DIM = "#71717a"

OK = "#38bdf8"
WARN = "#fbbf24"
CRIT = "#f43f5e"
GREEN = "#34d399"

THEMES = {
    "Indigo": "#6366f1",
    "Emerald": "#10b981",
    "Rose": "#f43f5e",
    "Mono": "#a1a1aa"
}

INTERVAL_MS = 1000
GAME_INTERVAL_MS = 2000
CPU_SMOOTH = 0.25
SENSOR_SMOOTH = 0.25
HIST = 60

_BASE_DIR = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.abspath(".")
SETTINGS_PATH = os.path.join(_BASE_DIR, "settings.json")


def _load_settings():
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


_SETTINGS = _load_settings()
CURRENT_LANG = _SETTINGS.get("lang", "EN") if _SETTINGS.get("lang") in ("EN", "RU") else "EN"
CURRENT_THEME = _SETTINGS.get("theme", "Indigo") if _SETTINGS.get("theme") in THEMES else "Indigo"
AUTO_GAME_MODE = bool(_SETTINGS.get("auto_game_mode", True))
ACCENT = THEMES[CURRENT_THEME]


def save_settings():
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump({
                "lang": CURRENT_LANG,
                "theme": CURRENT_THEME,
                "auto_game_mode": AUTO_GAME_MODE
            }, f, indent=2)
    except Exception:
        pass


def get_accent():
    return ACCENT


def get_theme():
    return CURRENT_THEME


def set_theme(theme_name):
    global CURRENT_THEME, ACCENT
    if theme_name in THEMES:
        CURRENT_THEME = theme_name
        ACCENT = THEMES[theme_name]
        save_settings()


def get_auto_game_mode():
    return AUTO_GAME_MODE


def set_auto_game_mode(enabled):
    global AUTO_GAME_MODE
    AUTO_GAME_MODE = bool(enabled)
    save_settings()


LANG = {
    "EN": {
        "Overview": "Home",
        "CPU": "Processor",
        "Memory": "Memory",
        "Disks": "Storage",
        "Network": "Internet",
        "Sensors": "Temps & Fans",
        "Benchmark": "Benchmark",
        "System": "My PC",
        "always_on_top": "Pin on Top",
        "uptime": "Running",
        "lang_label": "Language:",
        "theme_label": "Accent:",
        "tray_show": "Open Aether",
        "tray_quit": "Quit",
        "game_mode_active": "game mode",
        "auto_gm_label": "Auto Game Mode (clean RAM & low-overhead polling in games)",
        # Заголовки секций
        "sys_overview": "Quick Summary",
        "proc_perf": "Processor Load",
        "total_cpu": "TOTAL CPU LOAD",
        "core_threads": "Load by Thread",
        "mem_mgmt": "Memory (RAM)",
        "ram_consumption": "MEMORY USED",
        "disk_act": "Drives & Speed",
        "read_write": "READ / WRITE SPEED",
        "mounted_vols": "Your Drives",
        "net_overview": "Internet & Network",
        "net_band": "DOWNLOAD / UPLOAD",
        "active_interfaces": "Connections",
        "hw_temps": "Temperatures",
        "fans_power": "Fans & Power",
        "sys_specs": "Hardware & System",
        "os_specs": "Windows & Session",
        "quick_tools": "Quick Tools",
        # Benchmark
        "bench_title": "PC Performance Test",
        "bench_results": "Latest Results",
        "bench_avg_summary": "All-Time Averages & Peaks",
        "bench_history": "Saved Runs (Compare Upgrades)",
        "btn_run_bench": "Run Full Benchmark (~7 sec)",
        "btn_running_bench": "Testing...",
        "btn_clear_bench": "Clear History",
        "bench_ready": "Ready to test CPU, RAM, Disk & GPU",
        "bench_step_cpu": "Testing CPU multi-core speed...",
        "bench_step_ram": "Testing RAM bandwidth...",
        "bench_step_disk": "Testing Disk Read / Write speed...",
        "bench_step_gpu": "Testing GPU rendering pipeline...",
        "bench_done": "Benchmark complete!",
        "score_overall": "Overall PC Score",
        "score_cpu": "CPU Benchmark",
        "score_ram": "RAM Speed Test",
        "score_disk": "Disk Read/Write Test",
        "score_gpu": "GPU Benchmark",
        "bench_no_history": "No runs yet. Click Run Full Benchmark to save your baseline!",
        # Быстрые действия и модальное окно очистки диска
        "btn_trim_ram": "Clean RAM Cache",
        "btn_trim_done": "Freed",
        "btn_trim_tip": "Unloads unused background app memory.\nDon't spam it — best used once before launching a heavy game (frequent clicks can cause brief stutters).",
        "btn_clean_disk": "Clean Disk...",
        "btn_cleaning_disk": "Cleaning...",
        "btn_clean_disk_tip": "Choose what to delete: Windows Temp files, system caches, Recycle Bin, or Downloads.",
        "clean_modal_title": "Disk Cleanup — Choose Categories",
        "clean_modal_sub": "Scanning folder sizes...",
        "clean_modal_ready": "Select items you want to permanently remove:",
        "clean_cat_temp": "Windows & User Temp Files",
        "clean_cat_cache": "Update & Thumbnail Caches",
        "clean_cat_recycle": "Recycle Bin",
        "clean_cat_downloads": "Downloads Folder (All files inside)",
        "clean_btn_confirm": "Clean Selected",
        "clean_btn_cancel": "Cancel",
        "btn_reset_graphs": "Reset Graphs & Peaks",
        "btn_reset_done": "Cleared!",
        # Карточки на главной
        "card_cpu": "PROCESSOR",
        "card_ram": "MEMORY",
        "card_net": "INTERNET",
        "card_dio": "DRIVE SPEED",
        # Таблицы и простые подсказки
        "cpu_temp": "CPU Temp",
        "cpu_temp_tip": "How hot your processor is. 35–50°C is chill, 60–85°C under games/load is normal.",
        "gpu_temp": "Graphics Temp",
        "gpu_temp_tip": "How hot your graphics card is right now.",
        "session_peaks": "Session Peaks",
        "session_peaks_tip": "Highest CPU load and GPU temperature recorded since you opened Aether (or since game start).",
        "swap_page": "Extra Memory (Swap)",
        "swap_tip": "Backup space on your drive that Windows uses when regular RAM gets full.",
        "active_procs": "Running Programs",
        "active_procs_tip": "How many apps and background tasks are open right now.",
        "sys_uptime": "Time Since Boot",
        "sys_uptime_tip": "How long your PC has been on without a restart.",
        "phys_cores": "Real Cores",
        "curr_freq": "Clock Speed",
        "curr_freq_tip": "How fast your processor is ticking right now (higher = faster).",
        "ctx_switches": "Task Switches",
        "ctx_switches_tip": "How many times per second the CPU jumps between open apps.",
        "interrupts": "Device Signals",
        "interrupts_tip": "Signals per second from your mouse, keyboard, drive, and GPU.",
        "total_phys": "Total RAM",
        "total_phys_tip": "Total memory installed inside your PC.",
        "used_mem": "In Use",
        "used_mem_tip": "Memory currently taken by Windows and your open apps.",
        "avail_ram": "Free to Use",
        "avail_ram_tip": "Memory ready for new apps and games.",
        "swap_tot": "Total Swap",
        "swap_tot_tip": "Max size of backup virtual memory on your drive.",
        "swap_used": "Swap In Use",
        "swap_used_tip": "How much backup drive memory is currently being used.",
        "tot_read": "Total Read",
        "tot_read_tip": "Everything read from your drives since you turned the PC on.",
        "tot_write": "Total Written",
        "tot_write_tip": "Everything saved to your drives since you turned the PC on.",
        "read_ops": "Read Count",
        "read_ops_tip": "How many times Windows read files from your drives.",
        "write_ops": "Write Count",
        "write_ops_tip": "How many times Windows saved files to your drives.",
        "tot_rec": "Downloaded",
        "tot_sent": "Uploaded",
        "pkts_io": "Packets In / Out",
        # Вкладка My PC
        "hostname": "PC Name",
        "os_name": "Windows Version",
        "arch": "System Type",
        "cpu_model": "Processor",
        "gpu_model": "Graphics Card",
        "mobo_model": "Motherboard",
        "bios_ver": "BIOS Version",
        "logical_threads": "Cores / Threads",
        "tot_mem": "Installed RAM",
        "storage_list": "Storage Drives",
        "display_res": "Display",
        "boot_time": "Turned On At",
        "battery_status": "Battery",
        "no_battery": "Desktop PC (no battery)",
        "charging": "Charging",
        "discharging": "On battery",
        "sensors_status": "Status",
        "sensors_inactive": "Open LibreHardwareMonitor in the background to see CPU & motherboard temps.",
        "fans_inactive": "No fan speed sensors found."
    },
    "RU": {
        "Overview": "Главная",
        "CPU": "Процессор",
        "Memory": "Память",
        "Disks": "Диски",
        "Network": "Интернет",
        "Sensors": "Температуры",
        "Benchmark": "Тест ПК",
        "System": "Мой ПК",
        "always_on_top": "Поверх окон",
        "uptime": "Работает",
        "lang_label": "Язык:",
        "theme_label": "Цвет:",
        "tray_show": "Открыть Aether",
        "tray_quit": "Выход",
        "game_mode_active": "игровой режим",
        "auto_gm_label": "Авто Game Mode (чистит кэш RAM и снижает нагрузку в играх)",
        # заголовки секций
        "sys_overview": "Краткая сводка",
        "proc_perf": "Нагрузка на процессор",
        "total_cpu": "ОБЩАЯ НАГРУЗКА",
        "core_threads": "По каждому потоку",
        "mem_mgmt": "Оперативная память",
        "ram_consumption": "ЗАНЯТО ПАМЯТИ",
        "disk_act": "Диски и скорость",
        "read_write": "ЧТЕНИЕ / ЗАПИСЬ",
        "mounted_vols": "Твои диски",
        "net_overview": "Интернет и сеть",
        "net_band": "СКАЧИВАНИЕ / ОТДАЧА",
        "active_interfaces": "Подключения",
        "hw_temps": "Температуры",
        "fans_power": "Кулеры и питание",
        "sys_specs": "Железо компьютера",
        "os_specs": "Система и сеанс",
        "quick_tools": "Быстрые действия",
        # Benchmark
        "bench_title": "Тест производительности ПК",
        "bench_results": "Результаты прогона",
        "bench_avg_summary": "Средние значения и рекорды (анализ всех тестов)",
        "bench_history": "История тестов (сравнение до и после апгрейда)",
        "btn_run_bench": "Запустить полный тест (~7 сек)",
        "btn_running_bench": "Тестируем...",
        "btn_clear_bench": "Очистить историю",
        "bench_ready": "Готов протестировать CPU, RAM, Диск и Видеокарту",
        "bench_step_cpu": "Тестируем многопоточность процессора...",
        "bench_step_ram": "Замеряем скорость оперативной памяти...",
        "bench_step_disk": "Проверяем скорость чтения/записи диска...",
        "bench_step_gpu": "Тестируем графический конвейер видеокарты...",
        "bench_done": "Тест завершён!",
        "score_overall": "Общий балл ПК (Overall Score)",
        "score_cpu": "CPU Benchmark",
        "score_ram": "RAM Speed Test",
        "score_disk": "Disk Read/Write Test",
        "score_gpu": "GPU Benchmark",
        "bench_no_history": "История пуста. Нажми «Запустить полный тест», чтобы сохранить первый результат!",
        # Быстрые действия
        "btn_trim_ram": "Очистить кэш памяти",
        "btn_trim_done": "Освобождено",
        "btn_trim_tip": "Выгружает неиспользуемую память фоновых программ.\nНе спамь кнопкой — лучше нажимать один раз перед запуском тяжёлой игры (частое нажатие может вызвать микрофризы).",
        "btn_clean_disk": "Очистить диск...",
        "btn_cleaning_disk": "Чистим диск...",
        "btn_clean_disk_tip": "Открывает выбор категорий: временные файлы Temp, кэш системы, Корзина или папка «Загрузки».",
        "clean_modal_title": "Очистка диска — выбор категорий",
        "clean_modal_sub": "Подсчитываем размер файлов...",
        "clean_modal_ready": "Отметь категории, которые хочешь удалить безвозвратно:",
        "clean_cat_temp": "Временные файлы (Windows & User Temp)",
        "clean_cat_cache": "Кэш обновлений, Prefetch и эскизов",
        "clean_cat_recycle": "Корзина (Recycle Bin)",
        "clean_cat_downloads": "Папка «Загрузки» (Downloads)",
        "clean_btn_confirm": "Очистить выбранное",
        "clean_btn_cancel": "Отмена",
        "btn_reset_graphs": "Сбросить графики и пики",
        "btn_reset_done": "Сброшено!",
        # карточки на главной
        "card_cpu": "ПРОЦЕССОР",
        "card_ram": "ПАМЯТЬ",
        "card_net": "ИНТЕРНЕТ",
        "card_dio": "СКОРОСТЬ ДИСКОВ",
        # таблицы
        "cpu_temp": "Температура CPU",
        "cpu_temp_tip": "Нагрев процессора. 35–50°C в покое и 60–85°C в играх — это нормально.",
        "gpu_temp": "Температура видеокарты",
        "gpu_temp_tip": "Нагрев видеокарты прямо сейчас.",
        "session_peaks": "Пики за сессию",
        "session_peaks_tip": "Максимальная нагрузка на процессор и нагрев видеокарты с момента запуска Aether (или старта игры).",
        "swap_page": "Запасная память (Swap)",
        "swap_tip": "Место на диске, которое Windows берёт как запасную память, если обычная оперативка забита.",
        "active_procs": "Открыто процессов",
        "active_procs_tip": "Сколько программ и фоновых служб сейчас запущено.",
        "sys_uptime": "Работает без перезагрузки",
        "sys_uptime_tip": "Сколько времени прошло с момента включения компьютера.",
        "phys_cores": "Физических ядер",
        "curr_freq": "Текущая частота",
        "curr_freq_tip": "На какой скорости сейчас работает процессор (чем выше — тем быстрее).",
        "ctx_switches": "Переключения задач",
        "ctx_switches_tip": "Сколько раз в секунду процессор переключается между открытыми программами.",
        "interrupts": "Сигналы устройств",
        "interrupts_tip": "Сигналы в секунду от мышки, клавиатуры, дисков и видеокарты.",
        "total_phys": "Всего оперативки",
        "total_phys_tip": "Сколько всего оперативной памяти стоит в компьютере.",
        "used_mem": "Занято",
        "used_mem_tip": "Сколько памяти прямо сейчас используют Windows и открытые программы.",
        "avail_ram": "Свободно",
        "avail_ram_tip": "Сколько памяти свободно для новых игр и программ.",
        "swap_tot": "Всего запаса (Swap)",
        "swap_tot_tip": "Максимальный размер файла подкачки на диске.",
        "swap_used": "Занято из запаса",
        "swap_used_tip": "Сколько запасной памяти на диске сейчас используется.",
        "tot_read": "Прочитано с дисков",
        "tot_read_tip": "Сколько гигабайт система прочитала с дисков с момента включения.",
        "tot_write": "Записано на диски",
        "tot_write_tip": "Сколько гигабайт система записала на диски с момента включения.",
        "read_ops": "Операций чтения",
        "read_ops_tip": "Сколько раз Windows считывала данные с накопителей.",
        "write_ops": "Операций записи",
        "write_ops_tip": "Сколько раз Windows сохраняла данные на накопители.",
        "tot_rec": "Скачано",
        "tot_sent": "Отдано",
        "pkts_io": "Пакеты Вх / Вых",
        # Вкладка Мой ПК
        "hostname": "Имя компьютера",
        "os_name": "Версия Windows",
        "arch": "Разрядность",
        "cpu_model": "Процессор",
        "gpu_model": "Видеокарта",
        "mobo_model": "Материнская плата",
        "bios_ver": "Версия BIOS",
        "logical_threads": "Ядра / Потоки",
        "tot_mem": "Оперативная память",
        "storage_list": "Накопители",
        "display_res": "Экран",
        "boot_time": "Включён в",
        "battery_status": "Батарея",
        "no_battery": "Стационарный ПК (без батареи)",
        "charging": "Заряжается",
        "discharging": "От батареи",
        "sensors_status": "Статус",
        "sensors_inactive": "Запусти LibreHardwareMonitor в фоне, чтобы видеть температуру процессора и кулеры.",
        "fans_inactive": "Датчики кулеров не найдены."
    }
}


def tr(key):
    return LANG[CURRENT_LANG].get(key, key)


def set_lang(lang_code):
    global CURRENT_LANG
    CURRENT_LANG = lang_code
    save_settings()


def get_lang():
    return CURRENT_LANG