# -*- coding: utf-8 -*-
"""
app.py - Elegant GUI for NetEase Music VIP Song Decryptor & Universal Converter
Modern Step-by-Step Tabbed Workflow UI with Crisp High-DPI Microsoft YaHei UI Rendering.
"""

import os
import sys
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# 1. Enable Windows Per-Monitor V2 High-DPI Awareness BEFORE Tk is initialized
try:
    import ctypes
    # Shcore.dll SetProcessDpiAwareness: 2 = PROCESS_PER_MONITOR_DPI_AWARE_V2
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

# 2. Set AppUserModelID for Windows taskbar icon grouping
try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("studioj2y.163musicconverter.v100")
except Exception:
    pass

import customtkinter as ctk
import tkinterdnd2

from config import load_config, save_config
from task_manager import ConversionTaskManager, TaskStatus
from ffmpeg_engine import find_ffmpeg, get_ffmpeg_version

# Ensure UTF-8 output if terminal attached
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass


def get_resource_path(relative_path: str) -> str:
    """Get absolute path to resource, works for dev and for PyInstaller --onefile"""
    if getattr(sys, 'frozen', False):
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    res = os.path.join(base_path, relative_path)
    if os.path.exists(res):
        return res
    if getattr(sys, 'frozen', False):
        exe_res = os.path.join(os.path.dirname(sys.executable), relative_path)
        if os.path.exists(exe_res):
            return exe_res
    return res


# Standard High-Clarity Font Family for Windows
FONT_FAMILY = "Microsoft YaHei UI"


class ElegantSegmentedButton(ctk.CTkSegmentedButton):
    """
    Enhanced CTkSegmentedButton with active text inversion (pure white on active color).
    """
    def __init__(self, *args, selected_text_color="#ffffff", unselected_text_color="#334155", **kwargs):
        super().__init__(*args, **kwargs)
        self._custom_selected_text_color = selected_text_color
        self._custom_unselected_text_color = unselected_text_color
        self.after(50, self._refresh_button_colors)

    def _refresh_button_colors(self):
        curr = self.get()
        for val, btn in self._buttons_dict.items():
            if val == curr:
                btn.configure(text_color=self._custom_selected_text_color)
            else:
                btn.configure(text_color=self._custom_unselected_text_color)

    def _select_button_by_value(self, value: str):
        super()._select_button_by_value(value)
        if value in self._buttons_dict:
            self._buttons_dict[value].configure(text_color=self._custom_selected_text_color)

    def _unselect_button_by_value(self, value: str):
        super()._unselect_button_by_value(value)
        if value in self._buttons_dict:
            self._buttons_dict[value].configure(text_color=self._custom_unselected_text_color)

    def set(self, value: str, *args, **kwargs):
        super().set(value, *args, **kwargs)
        self._refresh_button_colors()

    def update_theme(self, selected_tc: str, unselected_tc: str):
        self._custom_selected_text_color = selected_tc
        self._custom_unselected_text_color = unselected_tc
        self._refresh_button_colors()


class CloudMusicConverterApp(ctk.CTk, tkinterdnd2.TkinterDnD.DnDWrapper):
    """
    Main Application Window with Modern Step-by-Step Tabbed Workflow:
      Step 1: 📥 选歌清单 (Queue & Import)
      Step 2: ⚙️ 格式与设置 (Format & Audio Engineering)
      Step 3: 🚀 转换与结果 (Progress & Converted Tracks)
    """

    def __init__(self):
        super().__init__()
        self.TkdndVersion = tkinterdnd2.TkinterDnD._require(self)

        # Load persisted settings
        self.cfg = load_config()
        self.default_vip_dir = r"D:\CloudMusic\VipSongsDownload"

        # Initialize Task Manager & Queue
        self.task_manager = ConversionTaskManager()
        self.queue = []

        self.current_mode = self.cfg.get("appearance_mode", "light")
        ctk.set_appearance_mode(self.current_mode)
        ctk.set_default_color_theme("blue")

        self.title("网易云音乐 VIP 歌曲解密 & 全能转换工具")
        self.geometry("1160x820")
        self.minsize(980, 700)

        # Multi-resolution Window & Taskbar Icon
        icon_path = get_resource_path("app_icon.ico")
        if os.path.exists(icon_path):
            try:
                self.iconbitmap(icon_path)
            except Exception:
                pass

        # Center on screen
        self.update_idletasks()
        w = 1160
        h = 820
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = max(0, (sw - w) // 2)
        y = max(0, (sh - h) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

        # Current active step
        self.active_step = 1

        # Real-time conversion counters
        self.count_success = 0
        self.count_skipped = 0
        self.count_failed = 0
        self.count_total = 0

        # Build UI Components
        self._apply_canvas_bg(self.current_mode)
        self._init_styles(self.current_mode)
        self._build_header()
        self._build_steps_container()
        self._setup_dnd()
        self._apply_initial_config()

        # Check FFmpeg asynchronously
        threading.Thread(target=self._check_ffmpeg_status, daemon=True).start()

        # Handle clean exit
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # =========================================================================
    # THEME & STYLES
    # =========================================================================

    def _apply_canvas_bg(self, mode: str):
        bg = "#f8fafc" if mode == "light" else "#0f172a"
        self.configure(fg_color=bg)

    def _init_styles(self, mode: str):
        self.tree_style = ttk.Style(self)
        self.tree_style.theme_use("clam")

        if mode == "light":
            table_bg = "#ffffff"
            text_color = "#0f172a"
            header_bg = "#f1f5f9"
            header_fg = "#334155"
            selected_bg = "#dbeafe"
            selected_fg = "#1e3a8a"
            hover_bg = "#f8fafc"
        else:
            table_bg = "#1e293b"
            text_color = "#f8fafc"
            header_bg = "#0f172a"
            header_fg = "#cbd5e1"
            selected_bg = "#1e3a8a"
            selected_fg = "#ffffff"
            hover_bg = "#334155"

        # Step 1 Queue Treeview Style
        self.tree_style.configure(
            "Queue.Treeview",
            background=table_bg,
            foreground=text_color,
            fieldbackground=table_bg,
            borderwidth=0,
            font=(FONT_FAMILY, 10),
            rowheight=32
        )
        self.tree_style.configure(
            "Queue.Treeview.Heading",
            background=header_bg,
            foreground=header_fg,
            relief="flat",
            borderwidth=0,
            font=(FONT_FAMILY, 10, "bold")
        )
        self.tree_style.map(
            "Queue.Treeview",
            background=[("selected", selected_bg)],
            foreground=[("selected", selected_fg)]
        )
        self.tree_style.map(
            "Queue.Treeview.Heading",
            background=[("active", hover_bg)]
        )

        # Step 3 Results Treeview Style
        self.tree_style.configure(
            "Result.Treeview",
            background=table_bg,
            foreground=text_color,
            fieldbackground=table_bg,
            borderwidth=0,
            font=(FONT_FAMILY, 10),
            rowheight=32
        )
        self.tree_style.configure(
            "Result.Treeview.Heading",
            background=header_bg,
            foreground=header_fg,
            relief="flat",
            borderwidth=0,
            font=(FONT_FAMILY, 10, "bold")
        )
        self.tree_style.map(
            "Result.Treeview",
            background=[("selected", selected_bg)],
            foreground=[("selected", selected_fg)]
        )

    # =========================================================================
    # HEADER & STEP NAVIGATION BAR
    # =========================================================================

    def _build_header(self):
        self.top_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.top_frame.pack(side="top", fill="x", padx=24, pady=(16, 12))

        # Brand Logo + Title
        brand_box = ctk.CTkFrame(self.top_frame, fg_color="transparent")
        brand_box.pack(side="left")

        icon_box = ctk.CTkFrame(
            brand_box,
            width=46,
            height=46,
            corner_radius=12,
            fg_color="#eff6ff" if self.current_mode == "light" else "#1e293b",
            border_width=1,
            border_color="#bfdbfe" if self.current_mode == "light" else "#334155"
        )
        icon_box.pack(side="left", padx=(0, 12))
        icon_box.pack_propagate(False)

        png_icon_path = get_resource_path("app_icon.png")
        if os.path.exists(png_icon_path):
            try:
                from PIL import Image
                pil_img = Image.open(png_icon_path).resize((36, 36), Image.Resampling.LANCZOS)
                self.brand_icon = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(36, 36))
                lbl_icon = ctk.CTkLabel(icon_box, text="", image=self.brand_icon)
                lbl_icon.place(relx=0.5, rely=0.5, anchor="center")
            except Exception:
                lbl_icon = ctk.CTkLabel(icon_box, text="🎧", font=ctk.CTkFont(family=FONT_FAMILY, size=22))
                lbl_icon.place(relx=0.5, rely=0.5, anchor="center")
        else:
            lbl_icon = ctk.CTkLabel(icon_box, text="🎧", font=ctk.CTkFont(family=FONT_FAMILY, size=22))
            lbl_icon.place(relx=0.5, rely=0.5, anchor="center")

        title_text_box = ctk.CTkFrame(brand_box, fg_color="transparent")
        title_text_box.pack(side="left")

        self.title_label = ctk.CTkLabel(
            title_text_box,
            text="网易云音乐 VIP 歌曲全能转换",
            font=ctk.CTkFont(family=FONT_FAMILY, size=18, weight="bold"),
            text_color="#0f172a" if self.current_mode == "light" else "#f8fafc"
        )
        self.title_label.pack(anchor="w")

        self.subtitle_label = ctk.CTkLabel(
            title_text_box,
            text="批量解密 NCM · 提取原始无损音质 · 智能转码 MP3 / AAC",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color="#64748b"
        )
        self.subtitle_label.pack(anchor="w")

        # Top Right Actions: FFmpeg Status & Theme Toggle
        top_right_box = ctk.CTkFrame(self.top_frame, fg_color="transparent")
        top_right_box.pack(side="right", pady=4)

        theme_txt = "🌙 深色" if self.current_mode == "light" else "☀️ 浅色"
        self.btn_theme = ctk.CTkButton(
            top_right_box,
            text=theme_txt,
            width=76,
            height=30,
            corner_radius=15,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            fg_color="#f1f5f9" if self.current_mode == "light" else "#334155",
            text_color="#334155" if self.current_mode == "light" else "#f1f5f9",
            hover_color="#e2e8f0" if self.current_mode == "light" else "#475569",
            command=self._on_toggle_theme
        )
        self.btn_theme.pack(side="right", padx=(8, 0))

        self.ffmpeg_badge_btn = ctk.CTkButton(
            top_right_box,
            text="● 正在检测 FFmpeg...",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            height=30,
            corner_radius=15,
            fg_color="#ecfdf5",
            text_color="#065f46",
            border_width=1,
            border_color="#a7f3d0",
            hover_color="#d1fae5",
            command=self._on_ffmpeg_settings
        )
        self.ffmpeg_badge_btn.pack(side="right")

        # =====================================================================
        # Step Navigation Tabs Bar (步骤向导标签条)
        # =====================================================================
        self.step_nav_bar = ctk.CTkFrame(
            self,
            corner_radius=12,
            border_width=1,
            fg_color="#ffffff" if self.current_mode == "light" else "#1e293b",
            border_color="#e2e8f0" if self.current_mode == "light" else "#334155",
            height=46
        )
        self.step_nav_bar.pack(side="top", fill="x", padx=24, pady=(0, 14))
        self.step_nav_bar.pack_propagate(False)

        step_nav_inner = ctk.CTkFrame(self.step_nav_bar, fg_color="transparent")
        step_nav_inner.place(relx=0.5, rely=0.5, anchor="center")

        # Step 1 Button
        self.btn_nav_step1 = ctk.CTkButton(
            step_nav_inner,
            text="① 选歌清单 (0 首)",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            width=210,
            height=34,
            corner_radius=8,
            fg_color="#2563eb",
            text_color="#ffffff",
            hover_color="#1d4ed8",
            command=lambda: self.switch_to_step(1)
        )
        self.btn_nav_step1.pack(side="left", padx=6)

        # Arrow indicator 1
        self.lbl_arrow1 = ctk.CTkLabel(
            step_nav_inner,
            text="➔",
            font=ctk.CTkFont(family=FONT_FAMILY, size=14, weight="bold"),
            text_color="#94a3b8"
        )
        self.lbl_arrow1.pack(side="left", padx=4)

        # Step 2 Button
        self.btn_nav_step2 = ctk.CTkButton(
            step_nav_inner,
            text="② 格式与参数配置",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13),
            width=210,
            height=34,
            corner_radius=8,
            fg_color="transparent",
            text_color="#64748b" if self.current_mode == "light" else "#94a3b8",
            hover_color="#f1f5f9" if self.current_mode == "light" else "#334155",
            command=lambda: self.switch_to_step(2)
        )
        self.btn_nav_step2.pack(side="left", padx=6)

        # Arrow indicator 2
        self.lbl_arrow2 = ctk.CTkLabel(
            step_nav_inner,
            text="➔",
            font=ctk.CTkFont(family=FONT_FAMILY, size=14, weight="bold"),
            text_color="#94a3b8"
        )
        self.lbl_arrow2.pack(side="left", padx=4)

        # Step 3 Button
        self.btn_nav_step3 = ctk.CTkButton(
            step_nav_inner,
            text="③ 转换进度与结果",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13),
            width=210,
            height=34,
            corner_radius=8,
            fg_color="transparent",
            text_color="#64748b" if self.current_mode == "light" else "#94a3b8",
            hover_color="#f1f5f9" if self.current_mode == "light" else "#334155",
            command=lambda: self.switch_to_step(3)
        )
        self.btn_nav_step3.pack(side="left", padx=6)

    # =========================================================================
    # STEPS CONTAINER & SWITCHER
    # =========================================================================

    def _build_steps_container(self):
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True, padx=24, pady=(0, 16))

        # Build individual step views
        self._build_step1_view()
        self._build_step2_view()
        self._build_step3_view()

        # Display Step 1 initially
        self.switch_to_step(1)

    def switch_to_step(self, step: int):
        self.active_step = step

        # Update step tabs appearance
        active_fg = "#2563eb"
        active_tc = "#ffffff"
        inactive_fg = "transparent"
        inactive_tc = "#64748b" if self.current_mode == "light" else "#94a3b8"
        hover_bg = "#f1f5f9" if self.current_mode == "light" else "#334155"

        # Step 1 tab
        self.btn_nav_step1.configure(
            fg_color=active_fg if step == 1 else inactive_fg,
            text_color=active_tc if step == 1 else inactive_tc,
            hover_color="#1d4ed8" if step == 1 else hover_bg,
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold" if step == 1 else "normal")
        )
        # Step 2 tab
        self.btn_nav_step2.configure(
            fg_color=active_fg if step == 2 else inactive_fg,
            text_color=active_tc if step == 2 else inactive_tc,
            hover_color="#1d4ed8" if step == 2 else hover_bg,
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold" if step == 2 else "normal")
        )
        # Step 3 tab
        self.btn_nav_step3.configure(
            fg_color=active_fg if step == 3 else inactive_fg,
            text_color=active_tc if step == 3 else inactive_tc,
            hover_color="#1d4ed8" if step == 3 else hover_bg,
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold" if step == 3 else "normal")
        )

        # Show active step frame
        if step == 1:
            self.step2_frame.pack_forget()
            self.step3_frame.pack_forget()
            self.step1_frame.pack(fill="both", expand=True)
        elif step == 2:
            self.step1_frame.pack_forget()
            self.step3_frame.pack_forget()
            self.step2_frame.pack(fill="both", expand=True)
        elif step == 3:
            self.step1_frame.pack_forget()
            self.step2_frame.pack_forget()
            self.step3_frame.pack(fill="both", expand=True)

    # =========================================================================
    # STEP 1 VIEW: 选歌清单 (IMPORT & QUEUE MANAGEMENT)
    # =========================================================================

    def _build_step1_view(self):
        self.step1_frame = ctk.CTkFrame(self.container, fg_color="transparent")

        # 1. Action Toolbar
        self.toolbar_frame = ctk.CTkFrame(
            self.step1_frame,
            corner_radius=12,
            border_width=1,
            fg_color="#ffffff" if self.current_mode == "light" else "#1e293b",
            border_color="#e2e8f0" if self.current_mode == "light" else "#334155"
        )
        self.toolbar_frame.pack(side="top", fill="x", pady=(0, 10))

        # Add Files button
        btn_add_files = ctk.CTkButton(
            self.toolbar_frame,
            text="➕ 添加文件...",
            width=115,
            height=34,
            corner_radius=8,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            fg_color="#f8fafc" if self.current_mode == "light" else "#334155",
            text_color="#1e293b" if self.current_mode == "light" else "#f8fafc",
            border_width=1,
            border_color="#cbd5e1" if self.current_mode == "light" else "#475569",
            hover_color="#e2e8f0" if self.current_mode == "light" else "#475569",
            command=self._on_add_files
        )
        btn_add_files.pack(side="left", padx=(12, 8), pady=8)

        # Add Folder button
        btn_add_folder = ctk.CTkButton(
            self.toolbar_frame,
            text="📁 添加文件夹...",
            width=115,
            height=34,
            corner_radius=8,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            fg_color="#f8fafc" if self.current_mode == "light" else "#334155",
            text_color="#1e293b" if self.current_mode == "light" else "#f8fafc",
            border_width=1,
            border_color="#cbd5e1" if self.current_mode == "light" else "#475569",
            hover_color="#e2e8f0" if self.current_mode == "light" else "#475569",
            command=self._on_add_folder
        )
        btn_add_folder.pack(side="left", padx=4, pady=8)

        # One-click import VIP dir
        btn_import_vip = ctk.CTkButton(
            self.toolbar_frame,
            text="⚡ 一键导入网易云目录",
            width=175,
            height=34,
            corner_radius=8,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            fg_color="#10b981",
            hover_color="#059669",
            text_color="#ffffff",
            command=self._on_import_vip_dir
        )
        btn_import_vip.pack(side="left", padx=6, pady=8)

        # Filter unconverted
        btn_filter = ctk.CTkButton(
            self.toolbar_frame,
            text="🔍 筛选未转换 (剔除已存在)",
            width=180,
            height=34,
            corner_radius=8,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            fg_color="#6366f1",
            hover_color="#4f46e5",
            text_color="#ffffff",
            command=self._on_filter_unconverted
        )
        btn_filter.pack(side="left", padx=6, pady=8)

        # Separator line
        sep = ctk.CTkFrame(
            self.toolbar_frame,
            width=1,
            height=20,
            fg_color="#e2e8f0" if self.current_mode == "light" else "#334155"
        )
        sep.pack(side="left", padx=6, pady=8)

        # Remove Selected
        btn_remove = ctk.CTkButton(
            self.toolbar_frame,
            text="移除选中",
            width=80,
            height=34,
            corner_radius=8,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            fg_color="transparent",
            text_color="#64748b",
            hover_color="#f1f5f9" if self.current_mode == "light" else "#334155",
            command=self._on_remove_selected
        )
        btn_remove.pack(side="left", padx=4, pady=8)

        # Clear List
        btn_clear = ctk.CTkButton(
            self.toolbar_frame,
            text="清空列表",
            width=80,
            height=34,
            corner_radius=8,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            fg_color="transparent",
            text_color="#ef4444",
            hover_color="#fee2e2" if self.current_mode == "light" else "#451a1a",
            command=self._on_clear_list
        )
        btn_clear.pack(side="left", padx=4, pady=8)

        # Right queue count badge
        self.lbl_queue_count = ctk.CTkLabel(
            self.toolbar_frame,
            text="共 0 首歌曲",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            text_color="#2563eb" if self.current_mode == "light" else "#60a5fa"
        )
        self.lbl_queue_count.pack(side="right", padx=16, pady=8)

        # 2. Main High-Resolution Treeview Queue Table (Full Space!)
        self.queue_frame = ctk.CTkFrame(
            self.step1_frame,
            corner_radius=12,
            border_width=1,
            fg_color="#ffffff" if self.current_mode == "light" else "#1e293b",
            border_color="#e2e8f0" if self.current_mode == "light" else "#334155"
        )
        self.queue_frame.pack(side="top", fill="both", expand=True, pady=(0, 10))

        cols = ("idx", "name", "size", "source_type", "compare_status", "target_fmt", "path")
        self.tree = ttk.Treeview(
            self.queue_frame,
            columns=cols,
            show="headings",
            selectmode="extended",
            style="Queue.Treeview"
        )

        self.tree.heading("idx", text="#", anchor="center")
        self.tree.heading("name", text="歌曲文件名", anchor="w")
        self.tree.heading("size", text="文件大小", anchor="e")
        self.tree.heading("source_type", text="源类型", anchor="center")
        self.tree.heading("compare_status", text="比对状态", anchor="center")
        self.tree.heading("target_fmt", text="目标格式", anchor="center")
        self.tree.heading("path", text="源文件完整路径", anchor="w")

        self.tree.column("idx", width=50, minwidth=40, anchor="center")
        self.tree.column("name", width=360, minwidth=240, anchor="w")
        self.tree.column("size", width=100, minwidth=80, anchor="e")
        self.tree.column("source_type", width=90, minwidth=80, anchor="center")
        self.tree.column("compare_status", width=140, minwidth=110, anchor="center")
        self.tree.column("target_fmt", width=120, minwidth=100, anchor="center")
        self.tree.column("path", width=320, minwidth=180, anchor="w")

        scroll_y = ttk.Scrollbar(self.queue_frame, orient="vertical", command=self.tree.yview)
        scroll_x = ttk.Scrollbar(self.queue_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

        scroll_y.pack(side="right", fill="y", pady=4, padx=(0, 4))
        scroll_x.pack(side="bottom", fill="x", padx=4, pady=(0, 4))
        self.tree.pack(side="left", fill="both", expand=True, padx=4, pady=4)

        # Empty State Placeholder
        self.lbl_empty_state = ctk.CTkLabel(
            self.tree,
            text="🎵 拖拽 .ncm 文件或文件夹到此窗口\n或点击上方「⚡ 一键导入网易云目录」快速载入",
            font=ctk.CTkFont(family=FONT_FAMILY, size=14),
            text_color="#94a3b8",
            justify="center"
        )
        self.lbl_empty_state.place(relx=0.5, rely=0.5, anchor="center")

        # Context Menu & Double Click
        self._setup_step1_tree_events()

        # 3. Bottom Action Bar for Step 1
        self.step1_bottom = ctk.CTkFrame(
            self.step1_frame,
            corner_radius=12,
            border_width=1,
            fg_color="#ffffff" if self.current_mode == "light" else "#1e293b",
            border_color="#e2e8f0" if self.current_mode == "light" else "#334155",
            height=54
        )
        self.step1_bottom.pack(side="bottom", fill="x")
        self.step1_bottom.pack_propagate(False)

        # Left Info & Auto Filter Checkbox
        left_box = ctk.CTkFrame(self.step1_bottom, fg_color="transparent")
        left_box.pack(side="left", padx=16, fill="y")

        self.auto_filter_var = tk.BooleanVar(value=self.cfg.get("auto_filter_existing", False))
        chk_auto_filter = ctk.CTkCheckBox(
            left_box,
            text="导入时自动排除已转换歌曲",
            variable=self.auto_filter_var,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color="#475569" if self.current_mode == "light" else "#cbd5e1",
            checkbox_width=18,
            checkbox_height=18,
            corner_radius=4,
            command=self._on_toggle_auto_filter
        )
        chk_auto_filter.pack(side="left", pady=16)

        # Right Action Buttons: "Next: Settings" & "Direct Start"
        right_box = ctk.CTkFrame(self.step1_bottom, fg_color="transparent")
        right_box.pack(side="right", padx=16, fill="y")

        btn_go_step2 = ctk.CTkButton(
            right_box,
            text="下一步：格式与参数配置 ➔",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            width=190,
            height=38,
            corner_radius=8,
            fg_color="#f1f5f9" if self.current_mode == "light" else "#334155",
            text_color="#1e293b" if self.current_mode == "light" else "#f8fafc",
            border_width=1,
            border_color="#cbd5e1" if self.current_mode == "light" else "#475569",
            hover_color="#e2e8f0" if self.current_mode == "light" else "#475569",
            command=lambda: self.switch_to_step(2)
        )
        btn_go_step2.pack(side="left", padx=(0, 8), pady=8)

        self.btn_step1_start = ctk.CTkButton(
            right_box,
            text="🚀 直接开始转换 (Alt+S)",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            width=180,
            height=38,
            corner_radius=8,
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            text_color="#ffffff",
            command=self._on_start_stop_clicked
        )
        self.btn_step1_start.pack(side="left", pady=8)

    # =========================================================================
    # STEP 2 VIEW: 格式与设置 (FORMAT & AUDIO ENGINEERING)
    # =========================================================================

    def _build_step2_view(self):
        self.step2_frame = ctk.CTkFrame(self.container, fg_color="transparent")

        # Main Scrollable Settings Container
        settings_box = ctk.CTkScrollableFrame(
            self.step2_frame,
            corner_radius=12,
            border_width=1,
            fg_color="#ffffff" if self.current_mode == "light" else "#1e293b",
            border_color="#e2e8f0" if self.current_mode == "light" else "#334155"
        )
        settings_box.pack(side="top", fill="both", expand=True, pady=(0, 10))

        # CARD 1: 🎯 音频输出格式与质量
        card1 = ctk.CTkFrame(
            settings_box,
            corner_radius=10,
            border_width=1,
            fg_color="#f8fafc" if self.current_mode == "light" else "#0f172a",
            border_color="#e2e8f0" if self.current_mode == "light" else "#334155"
        )
        card1.pack(fill="x", padx=16, pady=(16, 12))

        c1_head = ctk.CTkFrame(card1, fg_color="transparent")
        c1_head.pack(fill="x", padx=16, pady=(14, 8))

        lbl_c1_title = ctk.CTkLabel(
            c1_head,
            text="🎯 目标音频格式与转码策略",
            font=ctk.CTkFont(family=FONT_FAMILY, size=14, weight="bold"),
            text_color="#0f172a" if self.current_mode == "light" else "#f8fafc"
        )
        lbl_c1_title.pack(side="left")

        # Format Selector Segmented Button
        fmt_row = ctk.CTkFrame(card1, fg_color="transparent")
        fmt_row.pack(fill="x", padx=16, pady=(0, 10))

        self.segmented_format = ElegantSegmentedButton(
            fmt_row,
            values=["源文件 (仅解密)", "MP3 通用音频", "AAC / M4A (全兼容)"],
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            height=36,
            corner_radius=8,
            selected_color="#2563eb",
            selected_hover_color="#1d4ed8",
            unselected_color="#ffffff" if self.current_mode == "light" else "#1e293b",
            unselected_hover_color="#e2e8f0" if self.current_mode == "light" else "#334155",
            selected_text_color="#ffffff",
            unselected_text_color="#334155" if self.current_mode == "light" else "#cbd5e1",
            command=self._on_format_changed
        )
        self.segmented_format.pack(side="left", padx=(0, 20))

        # Bitrate row
        bitrate_row = ctk.CTkFrame(card1, fg_color="transparent")
        bitrate_row.pack(fill="x", padx=16, pady=(0, 12))

        self.lbl_bitrate_title = ctk.CTkLabel(
            bitrate_row,
            text="音质码率规格:",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            text_color="#334155" if self.current_mode == "light" else "#e2e8f0",
            width=90,
            anchor="w"
        )
        self.lbl_bitrate_title.pack(side="left")

        self.bitrate_combo = ctk.CTkComboBox(
            bitrate_row,
            width=420,
            height=34,
            corner_radius=8,
            state="readonly",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            values=[],
            command=self._on_bitrate_changed
        )
        self.bitrate_combo.pack(side="left", padx=4)

        # Callout Notice Box
        self.callout_frame = ctk.CTkFrame(
            card1,
            corner_radius=8,
            border_width=1,
            fg_color="#eff6ff" if self.current_mode == "light" else "#1e3a8a",
            border_color="#bfdbfe" if self.current_mode == "light" else "#2563eb"
        )
        self.callout_frame.pack(fill="x", padx=16, pady=(0, 16))

        self.lbl_encoding_hint = ctk.CTkLabel(
            self.callout_frame,
            text="",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color="#1e40af" if self.current_mode == "light" else "#bfdbfe",
            anchor="w",
            justify="left"
        )
        self.lbl_encoding_hint.pack(fill="both", expand=True, padx=12, pady=10)

        # CARD 2: 📂 输出保存路径与增量规则
        card2 = ctk.CTkFrame(
            settings_box,
            corner_radius=10,
            border_width=1,
            fg_color="#f8fafc" if self.current_mode == "light" else "#0f172a",
            border_color="#e2e8f0" if self.current_mode == "light" else "#334155"
        )
        card2.pack(fill="x", padx=16, pady=(0, 12))

        c2_head = ctk.CTkFrame(card2, fg_color="transparent")
        c2_head.pack(fill="x", padx=16, pady=(14, 8))

        lbl_c2_title = ctk.CTkLabel(
            c2_head,
            text="📂 输出保存目录与增量规则",
            font=ctk.CTkFont(family=FONT_FAMILY, size=14, weight="bold"),
            text_color="#0f172a" if self.current_mode == "light" else "#f8fafc"
        )
        lbl_c2_title.pack(side="left")

        # Output dir input
        out_row = ctk.CTkFrame(card2, fg_color="transparent")
        out_row.pack(fill="x", padx=16, pady=(0, 10))

        self.output_dir_var = tk.StringVar(value=self.cfg.get("output_dir", self.default_vip_dir + r"\decrypted"))
        self.entry_output_dir = ctk.CTkEntry(
            out_row,
            textvariable=self.output_dir_var,
            height=34,
            corner_radius=8,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12)
        )
        self.entry_output_dir.pack(side="left", fill="x", expand=True, padx=(0, 8))

        btn_browse_out = ctk.CTkButton(
            out_row,
            text="浏览...",
            width=76,
            height=34,
            corner_radius=8,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            fg_color="#ffffff" if self.current_mode == "light" else "#334155",
            text_color="#1e293b" if self.current_mode == "light" else "#f8fafc",
            border_width=1,
            border_color="#cbd5e1" if self.current_mode == "light" else "#475569",
            hover_color="#e2e8f0" if self.current_mode == "light" else "#475569",
            command=self._on_browse_output_dir
        )
        btn_browse_out.pack(side="left", padx=4)

        btn_open_out = ctk.CTkButton(
            out_row,
            text="打开目录",
            width=86,
            height=34,
            corner_radius=8,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            fg_color="#ffffff" if self.current_mode == "light" else "#334155",
            text_color="#1e293b" if self.current_mode == "light" else "#f8fafc",
            border_width=1,
            border_color="#cbd5e1" if self.current_mode == "light" else "#475569",
            hover_color="#e2e8f0" if self.current_mode == "light" else "#475569",
            command=self._on_open_output_dir
        )
        btn_open_out.pack(side="left", padx=4)

        # Switches
        sw_row = ctk.CTkFrame(card2, fg_color="transparent")
        sw_row.pack(fill="x", padx=16, pady=(0, 14))

        self.skip_existing_var = tk.BooleanVar(value=self.cfg.get("skip_existing", True))
        chk_skip = ctk.CTkCheckBox(
            sw_row,
            text="若目标文件已存在且有效，自动跳过（防止重复转码覆盖）",
            variable=self.skip_existing_var,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color="#475569" if self.current_mode == "light" else "#cbd5e1",
            checkbox_width=18,
            checkbox_height=18,
            corner_radius=4,
            command=self._on_toggle_skip_existing
        )
        chk_skip.pack(side="left", padx=(0, 24))

        self.auto_open_var = tk.BooleanVar(value=self.cfg.get("auto_open_folder", True))
        chk_open = ctk.CTkCheckBox(
            sw_row,
            text="批量转换完成后自动打开输出文件夹",
            variable=self.auto_open_var,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color="#475569" if self.current_mode == "light" else "#cbd5e1",
            checkbox_width=18,
            checkbox_height=18,
            corner_radius=4,
            command=self._on_toggle_auto_open
        )
        chk_open.pack(side="left")

        # CARD 3: ⚡ 性能加速与编码器
        card3 = ctk.CTkFrame(
            settings_box,
            corner_radius=10,
            border_width=1,
            fg_color="#f8fafc" if self.current_mode == "light" else "#0f172a",
            border_color="#e2e8f0" if self.current_mode == "light" else "#334155"
        )
        card3.pack(fill="x", padx=16, pady=(0, 16))

        c3_head = ctk.CTkFrame(card3, fg_color="transparent")
        c3_head.pack(fill="x", padx=16, pady=(14, 8))

        lbl_c3_title = ctk.CTkLabel(
            c3_head,
            text="⚡ 多线程性能与编码器配置",
            font=ctk.CTkFont(family=FONT_FAMILY, size=14, weight="bold"),
            text_color="#0f172a" if self.current_mode == "light" else "#f8fafc"
        )
        lbl_c3_title.pack(side="left")

        p_row = ctk.CTkFrame(card3, fg_color="transparent")
        p_row.pack(fill="x", padx=16, pady=(0, 14))

        lbl_workers = ctk.CTkLabel(
            p_row,
            text="并发转换线程数:",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            text_color="#334155" if self.current_mode == "light" else "#e2e8f0"
        )
        lbl_workers.pack(side="left", padx=(0, 8))

        self.workers_combo = ctk.CTkComboBox(
            p_row,
            width=140,
            height=32,
            corner_radius=8,
            state="readonly",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            values=["2 线程", "3 线程 (推荐)", "4 线程", "6 线程", "8 线程 (极速)"],
            command=self._on_workers_changed
        )
        self.workers_combo.pack(side="left", padx=4)

        btn_custom_ffmpeg = ctk.CTkButton(
            p_row,
            text="⚙️ FFmpeg 编码器详细设置...",
            width=180,
            height=32,
            corner_radius=8,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            fg_color="#ffffff" if self.current_mode == "light" else "#334155",
            text_color="#1e293b" if self.current_mode == "light" else "#f8fafc",
            border_width=1,
            border_color="#cbd5e1" if self.current_mode == "light" else "#475569",
            hover_color="#e2e8f0" if self.current_mode == "light" else "#475569",
            command=self._on_ffmpeg_settings
        )
        btn_custom_ffmpeg.pack(side="right")

        # Bottom Bar for Step 2
        self.step2_bottom = ctk.CTkFrame(
            self.step2_frame,
            corner_radius=12,
            border_width=1,
            fg_color="#ffffff" if self.current_mode == "light" else "#1e293b",
            border_color="#e2e8f0" if self.current_mode == "light" else "#334155",
            height=54
        )
        self.step2_bottom.pack(side="bottom", fill="x")
        self.step2_bottom.pack_propagate(False)

        btn_back_step1 = ctk.CTkButton(
            self.step2_bottom,
            text="⬅ 上一步：返回歌曲列表",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13),
            width=180,
            height=38,
            corner_radius=8,
            fg_color="#f1f5f9" if self.current_mode == "light" else "#334155",
            text_color="#1e293b" if self.current_mode == "light" else "#f8fafc",
            border_width=1,
            border_color="#cbd5e1" if self.current_mode == "light" else "#475569",
            hover_color="#e2e8f0" if self.current_mode == "light" else "#475569",
            command=lambda: self.switch_to_step(1)
        )
        btn_back_step1.pack(side="left", padx=16, pady=8)

        self.btn_step2_start = ctk.CTkButton(
            self.step2_bottom,
            text="🚀 开始执行转换 (Alt+S)",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            width=200,
            height=38,
            corner_radius=8,
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            text_color="#ffffff",
            command=self._on_start_stop_clicked
        )
        self.btn_step2_start.pack(side="right", padx=16, pady=8)

    # =========================================================================
    # STEP 3 VIEW: 转换进度与结果 (PROGRESS & REAL-TIME RESULTS)
    # =========================================================================

    def _build_step3_view(self):
        self.step3_frame = ctk.CTkFrame(self.container, fg_color="transparent")

        # 1. Top Metrics & Progress Dashboard Card
        self.dashboard_card = ctk.CTkFrame(
            self.step3_frame,
            corner_radius=12,
            border_width=1,
            fg_color="#ffffff" if self.current_mode == "light" else "#1e293b",
            border_color="#e2e8f0" if self.current_mode == "light" else "#334155"
        )
        self.dashboard_card.pack(side="top", fill="x", pady=(0, 10))

        # Overall Progress Bar Row
        prog_header = ctk.CTkFrame(self.dashboard_card, fg_color="transparent")
        prog_header.pack(fill="x", padx=16, pady=(14, 6))

        self.lbl_dashboard_title = ctk.CTkLabel(
            prog_header,
            text="总体转换进度",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            text_color="#0f172a" if self.current_mode == "light" else "#f8fafc"
        )
        self.lbl_dashboard_title.pack(side="left")

        self.lbl_pct = ctk.CTkLabel(
            prog_header,
            text="0%",
            font=ctk.CTkFont(family=FONT_FAMILY, size=14, weight="bold"),
            text_color="#2563eb" if self.current_mode == "light" else "#60a5fa"
        )
        self.lbl_pct.pack(side="right")

        self.progress_bar = ctk.CTkProgressBar(
            self.dashboard_card,
            height=12,
            corner_radius=6,
            progress_color="#2563eb",
            fg_color="#e2e8f0" if self.current_mode == "light" else "#334155"
        )
        self.progress_bar.pack(fill="x", padx=16, pady=(0, 10))
        self.progress_bar.set(0.0)

        # 4 Metric KPI Badges in a row
        kpi_row = ctk.CTkFrame(self.dashboard_card, fg_color="transparent")
        kpi_row.pack(fill="x", padx=16, pady=(0, 10))

        # Helper to create metric box
        def make_kpi(parent, title, init_val, fg, border, tc):
            box = ctk.CTkFrame(parent, corner_radius=8, border_width=1, fg_color=fg, border_color=border, height=52)
            box.pack(side="left", fill="x", expand=True, padx=4)
            box.pack_propagate(False)
            l_t = ctk.CTkLabel(box, text=title, font=ctk.CTkFont(family=FONT_FAMILY, size=11), text_color="#64748b")
            l_t.pack(pady=(4, 0))
            l_v = ctk.CTkLabel(box, text=init_val, font=ctk.CTkFont(family=FONT_FAMILY, size=15, weight="bold"), text_color=tc)
            l_v.pack()
            return l_v

        is_light = self.current_mode == "light"
        self.kpi_pending = make_kpi(kpi_row, "⏳ 队列总计", "0 首", "#f8fafc" if is_light else "#0f172a", "#cbd5e1" if is_light else "#334155", "#0f172a" if is_light else "#f8fafc")
        self.kpi_success = make_kpi(kpi_row, "✅ 转换成功", "0 首", "#ecfdf5" if is_light else "#064e3b", "#a7f3d0" if is_light else "#059669", "#059669" if is_light else "#34d399")
        self.kpi_skipped = make_kpi(kpi_row, "⏭ 已跳过 (已存在)", "0 首", "#f1f5f9" if is_light else "#1e293b", "#cbd5e1" if is_light else "#475569", "#475569" if is_light else "#94a3b8")
        self.kpi_failed = make_kpi(kpi_row, "❌ 转换失败", "0 首", "#fef2f2" if is_light else "#451a1a", "#fecaca" if is_light else "#7f1d1d", "#dc2626" if is_light else "#f87171")

        # Current Track Subtitle Banner
        self.lbl_current_track = ctk.CTkLabel(
            self.dashboard_card,
            text="就绪: 等待启动转换任务",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color="#475569" if is_light else "#94a3b8",
            anchor="w"
        )
        self.lbl_current_track.pack(fill="x", padx=16, pady=(0, 12))

        # 2. Converted Songs Real-time Stream Table
        self.results_frame = ctk.CTkFrame(
            self.step3_frame,
            corner_radius=12,
            border_width=1,
            fg_color="#ffffff" if self.current_mode == "light" else "#1e293b",
            border_color="#e2e8f0" if self.current_mode == "light" else "#334155"
        )
        self.results_frame.pack(side="top", fill="both", expand=True, pady=(0, 10))

        res_cols = ("idx", "name", "target_fmt", "status", "size", "elapsed", "out_path")
        self.tree_res = ttk.Treeview(
            self.results_frame,
            columns=res_cols,
            show="headings",
            selectmode="browse",
            style="Result.Treeview"
        )

        self.tree_res.heading("idx", text="#", anchor="center")
        self.tree_res.heading("name", text="歌曲名称", anchor="w")
        self.tree_res.heading("target_fmt", text="转换格式", anchor="center")
        self.tree_res.heading("status", text="执行状态", anchor="center")
        self.tree_res.heading("size", text="输出大小", anchor="e")
        self.tree_res.heading("elapsed", text="耗时", anchor="center")
        self.tree_res.heading("out_path", text="输出文件路径", anchor="w")

        self.tree_res.column("idx", width=50, minwidth=40, anchor="center")
        self.tree_res.column("name", width=360, minwidth=240, anchor="w")
        self.tree_res.column("target_fmt", width=110, minwidth=90, anchor="center")
        self.tree_res.column("status", width=140, minwidth=110, anchor="center")
        self.tree_res.column("size", width=110, minwidth=80, anchor="e")
        self.tree_res.column("elapsed", width=90, minwidth=70, anchor="center")
        self.tree_res.column("out_path", width=350, minwidth=180, anchor="w")

        r_sc_y = ttk.Scrollbar(self.results_frame, orient="vertical", command=self.tree_res.yview)
        r_sc_x = ttk.Scrollbar(self.results_frame, orient="horizontal", command=self.tree_res.xview)
        self.tree_res.configure(yscrollcommand=r_sc_y.set, xscrollcommand=r_sc_x.set)

        r_sc_y.pack(side="right", fill="y", pady=4, padx=(0, 4))
        r_sc_x.pack(side="bottom", fill="x", padx=4, pady=(0, 4))
        self.tree_res.pack(side="left", fill="both", expand=True, padx=4, pady=4)

        # Empty State Placeholder for Results
        self.lbl_empty_res = ctk.CTkLabel(
            self.tree_res,
            text="⏳ 暂无转换结果\n开始转换后将在此实时显示转换记录，支持双击直接试听",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13),
            text_color="#94a3b8",
            justify="center"
        )
        self.lbl_empty_res.place(relx=0.5, rely=0.5, anchor="center")

        # Bindings for Step 3 results table
        self._setup_step3_tree_events()

        # 3. Bottom Action Bar for Step 3
        self.step3_bottom = ctk.CTkFrame(
            self.step3_frame,
            corner_radius=12,
            border_width=1,
            fg_color="#ffffff" if self.current_mode == "light" else "#1e293b",
            border_color="#e2e8f0" if self.current_mode == "light" else "#334155",
            height=54
        )
        self.step3_bottom.pack(side="bottom", fill="x")
        self.step3_bottom.pack_propagate(False)

        btn_back_to_list = ctk.CTkButton(
            self.step3_bottom,
            text="⬅ 返回选歌列表",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13),
            width=160,
            height=38,
            corner_radius=8,
            fg_color="#f1f5f9" if self.current_mode == "light" else "#334155",
            text_color="#1e293b" if self.current_mode == "light" else "#f8fafc",
            border_width=1,
            border_color="#cbd5e1" if self.current_mode == "light" else "#475569",
            hover_color="#e2e8f0" if self.current_mode == "light" else "#475569",
            command=lambda: self.switch_to_step(1)
        )
        btn_back_to_list.pack(side="left", padx=16, pady=8)

        btn_open_out_3 = ctk.CTkButton(
            self.step3_bottom,
            text="📂 打开输出目录",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13),
            width=140,
            height=38,
            corner_radius=8,
            fg_color="#f8fafc" if self.current_mode == "light" else "#334155",
            text_color="#1e293b" if self.current_mode == "light" else "#f8fafc",
            border_width=1,
            border_color="#cbd5e1" if self.current_mode == "light" else "#475569",
            hover_color="#e2e8f0" if self.current_mode == "light" else "#475569",
            command=self._on_open_output_dir
        )
        btn_open_out_3.pack(side="left", padx=4, pady=8)

        self.btn_step3_action = ctk.CTkButton(
            self.step3_bottom,
            text="▶ 开始执行转换",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            width=180,
            height=38,
            corner_radius=8,
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            text_color="#ffffff",
            command=self._on_start_stop_clicked
        )
        self.btn_step3_action.pack(side="right", padx=16, pady=8)

        # Global hotkey
        self.bind("<Alt-s>", lambda e: self._on_start_stop_clicked())

    # =========================================================================
    # DRAG & DROP AND CONFIGURATION SYNC
    # =========================================================================

    def _setup_dnd(self):
        try:
            self.drop_target_register(tkinterdnd2.DND_FILES)
            self.dnd_bind("<<Drop>>", self._on_drop_files)
        except Exception as e:
            print("DnD registration notice:", e)

    def _on_drop_files(self, event):
        files = self.tk.splitlist(event.data)
        if files:
            # If user drops files while on Step 2 or Step 3, switch back to Step 1
            if self.active_step != 1:
                self.switch_to_step(1)
            self._add_paths(files)

    def _apply_initial_config(self):
        fmt = self.cfg.get("target_format", "source")
        fmt_map = {
            "source": "源文件 (仅解密)",
            "mp3": "MP3 通用音频",
            "aac": "AAC / M4A (全兼容)"
        }
        self.segmented_format.set(fmt_map.get(fmt, "源文件 (仅解密)"))
        self._update_bitrate_ui(fmt)

        workers = self.cfg.get("max_workers", 3)
        worker_str_map = {2: "2 线程", 3: "3 线程 (推荐)", 4: "4 线程", 6: "6 线程", 8: "8 线程 (极速)"}
        self.workers_combo.set(worker_str_map.get(workers, "3 线程 (推荐)"))

    def _on_toggle_theme(self):
        new_mode = "dark" if self.current_mode == "light" else "light"
        self.current_mode = new_mode
        self.cfg["appearance_mode"] = new_mode
        self._save_settings()

        ctk.set_appearance_mode(new_mode)
        self._apply_canvas_bg(new_mode)
        self._init_styles(new_mode)

        self.btn_theme.configure(
            text="🌙 深色" if new_mode == "light" else "☀️ 浅色",
            fg_color="#f1f5f9" if new_mode == "light" else "#334155",
            text_color="#334155" if new_mode == "light" else "#f1f5f9",
            hover_color="#e2e8f0" if new_mode == "light" else "#475569"
        )
        self.title_label.configure(text_color="#0f172a" if new_mode == "light" else "#f8fafc")
        self.segmented_format.update_theme(
            selected_tc="#ffffff",
            unselected_tc="#334155" if new_mode == "light" else "#cbd5e1"
        )

    # =========================================================================
    # FORMAT & BITRATE HANDLERS
    # =========================================================================

    def _get_current_format_code(self) -> str:
        choice = self.segmented_format.get()
        if "MP3" in choice:
            return "mp3"
        elif "AAC" in choice:
            return "aac"
        return "source"

    def _on_format_changed(self, choice=None):
        fmt = self._get_current_format_code()
        self.cfg["target_format"] = fmt
        self._save_settings()
        self._update_bitrate_ui(fmt)
        self._update_tree_target_format_column()

    def _update_bitrate_ui(self, fmt: str):
        if fmt == "source":
            self.lbl_bitrate_title.configure(text_color="#94a3b8")
            self.bitrate_combo.configure(state="disabled", values=["无需重编码 (直接保留母带音质 FLAC/MP3)"])
            self.bitrate_combo.set("无需重编码 (直接保留母带音质 FLAC/MP3)")
            self.lbl_encoding_hint.configure(
                text="⚡ 源文件直接解密：瞬间提取 NCM 封装的母带音频（无损 FLAC 或 320k MP3），零压缩损耗，自动通过 Mutagen 写入完整的 ID3v2/FLAC 标签与内嵌高清封面。"
            )
        elif fmt == "mp3":
            self.lbl_bitrate_title.configure(text_color="#334155" if self.current_mode == "light" else "#e2e8f0")
            mp3_options = [
                "320 kbps (CBR 恒定码率 - 最高音质/推荐)",
                "256 kbps (CBR 恒定码率 - 高品质)",
                "192 kbps (CBR 恒定码率 - 标准品质)",
                "128 kbps (CBR 恒定码率 - 紧凑便携)",
                "VBR V0 (~245 kbps 动态码率 - 极高音质)",
                "VBR V2 (~190 kbps 动态码率 - 黄金平衡)",
                "VBR V5 (~130 kbps 动态码率 - 紧凑便携档)"
            ]
            self.bitrate_combo.configure(state="readonly", values=mp3_options)
            saved = self.cfg.get("mp3_bitrate", "320k")
            matched = False
            for opt in mp3_options:
                if opt.startswith(saved):
                    self.bitrate_combo.set(opt)
                    matched = True
                    break
            if not matched:
                self.bitrate_combo.set(mp3_options[0])

            self.lbl_encoding_hint.configure(
                text="🎵 MP3 通用编码 (libmp3lame)：车机、音响与老式播放设备首选！自动采用 ID3v2.3 规范并追加 ID3v1 尾部标签，内嵌高清封面，杜绝车机乱码或黑屏。"
            )
        elif fmt == "aac":
            self.lbl_bitrate_title.configure(text_color="#334155" if self.current_mode == "light" else "#e2e8f0")
            aac_options = [
                "320 kbps (CBR 恒定码率 - 极限高保真)",
                "256 kbps (CBR 恒定码率 - Apple iTunes Plus 推荐)",
                "192 kbps (CBR 恒定码率 - 标准高质量)",
                "128 kbps (CBR 恒定码率 - 高性价比便携)",
                "VBR 动态质量 (~190-220 kbps 动态高保真)",
                "VBR 动态质量 (~120-140 kbps 动态便携档)"
            ]
            self.bitrate_combo.configure(state="readonly", values=aac_options)
            saved = self.cfg.get("aac_bitrate", "256k")
            matched = False
            for opt in aac_options:
                if opt.startswith(saved):
                    self.bitrate_combo.set(opt)
                    matched = True
                    break
            if not matched:
                self.bitrate_combo.set(aac_options[1])

            self.lbl_encoding_hint.configure(
                text="🍎 AAC/M4A 高效保真编码：苹果生态与现代车载首选！采用通用的 .m4a 容器封装，启用 FastStart 流式秒开，杜绝车机寻轨漂移，内嵌专辑封面与完整元数据。"
            )

    def _on_bitrate_changed(self, choice: str):
        fmt = self._get_current_format_code()
        prefix = choice.split()[0]
        if fmt == "mp3":
            if "VBR V0" in choice:
                val = "vbr0"
            elif "VBR V2" in choice:
                val = "vbr2"
            elif "VBR V5" in choice:
                val = "vbr5"
            else:
                val = prefix
            self.cfg["mp3_bitrate"] = val
        elif fmt == "aac":
            if "190-220" in choice:
                val = "vbr_high"
            elif "120-140" in choice:
                val = "vbr_med"
            else:
                val = prefix
            self.cfg["aac_bitrate"] = val
        self._save_settings()
        self._update_tree_target_format_column()

    def _get_target_format_label(self) -> str:
        fmt = self._get_current_format_code()
        if fmt == "source":
            return "源格式 (解密)"
        elif fmt == "mp3":
            br = self.cfg.get("mp3_bitrate", "320k")
            return f"MP3 ({br.upper()})"
        elif fmt == "aac":
            br = self.cfg.get("aac_bitrate", "256k")
            return f"AAC M4A ({br.upper()})"
        return fmt

    def _update_tree_target_format_column(self):
        new_label = self._get_target_format_label()
        for iid in self.tree.get_children():
            vals = list(self.tree.item(iid, "values"))
            if len(vals) > 5:
                vals[5] = new_label
                self.tree.item(iid, values=vals)

    # =========================================================================
    # FFMPEG STATUS
    # =========================================================================

    def _check_ffmpeg_status(self):
        custom = self.cfg.get("custom_ffmpeg_path", "").strip() or None
        found = find_ffmpeg(custom)
        try:
            if found:
                self.after(0, lambda: self.ffmpeg_badge_btn.configure(
                    text="⚡ FFmpeg 已就绪",
                    fg_color="#ecfdf5",
                    text_color="#065f46",
                    border_color="#a7f3d0",
                    hover_color="#d1fae5"
                ))
            else:
                self.after(0, lambda: self.ffmpeg_badge_btn.configure(
                    text="⚠️ 未找到 FFmpeg (点击配置)",
                    fg_color="#fee2e2",
                    text_color="#991b1b",
                    border_color="#fca5a5",
                    hover_color="#fecaca"
                ))
        except Exception:
            pass

    def _on_ffmpeg_settings(self):
        curr = self.cfg.get("custom_ffmpeg_path", "")
        path = filedialog.askopenfilename(
            title="选择 FFmpeg 可执行文件 (ffmpeg.exe)",
            filetypes=[("Executable Files", "ffmpeg.exe;*.exe"), ("All Files", "*.*")],
            initialdir=os.path.dirname(curr) if curr and os.path.exists(curr) else "C:\\"
        )
        if path:
            self.cfg["custom_ffmpeg_path"] = path
            self._save_settings()
            self._check_ffmpeg_status()

    # =========================================================================
    # QUEUE & IMPORT HANDLERS (STEP 1)
    # =========================================================================

    def _on_add_files(self):
        files = filedialog.askopenfilenames(
            title="选择网易云音乐 VIP 歌曲 (.ncm)",
            filetypes=[("NetEase Cloud Music", "*.ncm"), ("All Files", "*.*")]
        )
        if files:
            self._add_paths(files)

    def _on_add_folder(self):
        folder = filedialog.askdirectory(title="选择包含歌曲的文件夹")
        if folder:
            self._add_paths([folder])

    def _on_import_vip_dir(self):
        if os.path.isdir(self.default_vip_dir):
            self._add_paths([self.default_vip_dir])
        else:
            messagebox.showinfo("提示", f"默认网易云下载目录不存在：\n{self.default_vip_dir}\n请使用「添加文件夹」手动选择。")

    def _add_paths(self, paths):
        def do_scan():
            items = self.task_manager.scan_files(paths, recursive=True)
            self.after(0, lambda: self._append_scanned_items(items))
        threading.Thread(target=do_scan, daemon=True).start()

    def _append_scanned_items(self, new_items):
        if not new_items:
            return

        auto_filter = self.auto_filter_var.get()
        out_dir = self.output_dir_var.get().strip()
        fmt = self._get_current_format_code()
        existing_map = self.task_manager.get_existing_output_map(out_dir)

        added_count = 0
        skipped_count = 0
        target_label = self._get_target_format_label()

        for it in new_items:
            is_conv = self.task_manager.is_item_already_converted(it['filename'], existing_map, fmt)
            it['is_already_converted'] = is_conv

            if auto_filter and is_conv:
                skipped_count += 1
                continue

            cmp_text = "已存在同名输出" if is_conv else "未转换 (新增)"
            idx = len(self.queue) + 1
            self.queue.append(it)
            added_count += 1

            src_type = "NCM" if it.get('is_ncm') else os.path.splitext(it['filename'])[1].lstrip('.').upper()

            self.tree.insert(
                "",
                "end",
                iid=it['id'],
                values=(
                    idx,
                    it['filename'],
                    it.get('size_str', '-'),
                    src_type,
                    cmp_text,
                    target_label,
                    it['path']
                )
            )

        self._refresh_queue_count()

        if auto_filter and skipped_count > 0:
            self.lbl_queue_count.configure(
                text=f"共 {len(self.queue)} 首 (已自动排除 {skipped_count} 首已转换)"
            )

    def _on_filter_unconverted(self):
        if not self.queue:
            messagebox.showinfo("提示", "当前队列为空，请先添加歌曲。")
            return

        out_dir = self.output_dir_var.get().strip()
        fmt = self._get_current_format_code()
        existing_map = self.task_manager.get_existing_output_map(out_dir)

        removed_iids = []
        kept_items = []

        for it in self.queue:
            is_conv = self.task_manager.is_item_already_converted(it['filename'], existing_map, fmt)
            it['is_already_converted'] = is_conv

            if is_conv:
                removed_iids.append(it['id'])
            else:
                kept_items.append(it)

        for iid in removed_iids:
            try:
                self.tree.delete(iid)
            except Exception:
                pass

        self.queue = kept_items
        for idx, it in enumerate(kept_items, start=1):
            vals = list(self.tree.item(it['id'], "values"))
            if vals:
                vals[0] = idx
                vals[4] = "未转换 (新增)"
                self.tree.item(it['id'], values=vals)

        self._refresh_queue_count()
        messagebox.showinfo(
            "筛选结果",
            f"增量比对完成！\n\n已成功剔除已转换歌曲：{len(removed_iids)} 首\n保留未转换歌曲：{len(kept_items)} 首"
        )

    def _on_remove_selected(self):
        selected = self.tree.selection()
        if not selected:
            return
        selected_set = set(selected)
        for iid in selected:
            self.tree.delete(iid)
        self.queue = [it for it in self.queue if it['id'] not in selected_set]
        for idx, it in enumerate(self.queue, start=1):
            vals = list(self.tree.item(it['id'], "values"))
            if vals:
                vals[0] = idx
                self.tree.item(it['id'], values=vals)
        self._refresh_queue_count()

    def _on_clear_list(self):
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        self.queue.clear()
        self._refresh_queue_count()

    def _refresh_queue_count(self):
        count = len(self.queue)
        self.lbl_queue_count.configure(text=f"共 {count} 首歌曲")
        self.btn_nav_step1.configure(text=f"① 选歌清单 ({count} 首)")
        self.kpi_pending.configure(text=f"{count} 首")

        if count == 0:
            self.lbl_empty_state.place(relx=0.5, rely=0.5, anchor="center")
        else:
            self.lbl_empty_state.place_forget()

    # =========================================================================
    # STEP 1 TREEVIEW CONTEXT MENU & DOUBLE CLICK
    # =========================================================================

    def _setup_step1_tree_events(self):
        self.tree.bind("<Button-3>", self._on_tree_right_click)
        self.tree.bind("<Double-Button-1>", self._on_tree_double_click)

        # Context Menu
        self.queue_menu = tk.Menu(self, tearoff=0)
        self.queue_menu.add_command(label="🎵 试听播放 (已完成歌曲)", command=self._on_play_or_open_completed)
        self.queue_menu.add_command(label="📁 在资源管理器中定位源文件", command=self._on_locate_source_file)
        self.queue_menu.add_separator()
        self.queue_menu.add_command(label="❌ 移除选中项", command=self._on_remove_selected)
        self.queue_menu.add_command(label="🔍 筛选未转换 (剔除已存在)", command=self._on_filter_unconverted)
        self.queue_menu.add_command(label="🗑️ 清空列表", command=self._on_clear_list)

    def _on_tree_right_click(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            if item not in self.tree.selection():
                self.tree.selection_set(item)
            self.queue_menu.post(event.x_root, event.y_root)

    def _on_tree_double_click(self, event):
        item = self.tree.identify_row(event.y)
        if not item:
            return
        it = next((x for x in self.queue if x['id'] == item), None)
        if not it:
            return

        out_path = it.get('output_path')
        if out_path and os.path.exists(out_path):
            try:
                os.startfile(out_path)
            except Exception as e:
                messagebox.showerror("打开失败", f"无法打开文件：\n{e}")
        elif os.path.exists(it['path']):
            try:
                subprocess.Popen(f'explorer /select,"{os.path.normpath(it["path"])}"')
            except Exception as e:
                messagebox.showerror("定位失败", f"无法定位源文件：\n{e}")

    def _on_locate_source_file(self):
        selected = self.tree.selection()
        if not selected:
            return
        it = next((x for x in self.queue if x['id'] == selected[0]), None)
        if it and os.path.exists(it['path']):
            subprocess.Popen(f'explorer /select,"{os.path.normpath(it["path"])}"')

    def _on_play_or_open_completed(self):
        selected = self.tree.selection()
        if not selected:
            return
        it = next((x for x in self.queue if x['id'] == selected[0]), None)
        if it:
            out_path = it.get('output_path')
            if out_path and os.path.exists(out_path):
                os.startfile(out_path)
            else:
                messagebox.showinfo("提示", "该歌曲尚未转换完成，无法播放。")

    # =========================================================================
    # STEP 3 RESULTS TREEVIEW CONTEXT MENU & DOUBLE CLICK
    # =========================================================================

    def _setup_step3_tree_events(self):
        self.tree_res.bind("<Button-3>", self._on_res_right_click)
        self.tree_res.bind("<Double-Button-1>", self._on_res_double_click)

        self.res_menu = tk.Menu(self, tearoff=0)
        self.res_menu.add_command(label="🎵 立即播放此歌曲", command=self._on_res_play)
        self.res_menu.add_command(label="📁 在资源管理器中定位文件", command=self._on_res_locate)
        self.res_menu.add_separator()
        self.res_menu.add_command(label="📋 复制输出文件路径", command=self._on_res_copy_path)

    def _on_res_right_click(self, event):
        item = self.tree_res.identify_row(event.y)
        if item:
            self.tree_res.selection_set(item)
            self.res_menu.post(event.x_root, event.y_root)

    def _on_res_double_click(self, event):
        item = self.tree_res.identify_row(event.y)
        if not item:
            return
        vals = self.tree_res.item(item, "values")
        if vals and len(vals) > 6:
            out_path = vals[6]
            if out_path and os.path.exists(out_path):
                try:
                    os.startfile(out_path)
                except Exception as e:
                    messagebox.showerror("播放失败", f"无法打开文件：\n{e}")

    def _on_res_play(self):
        sel = self.tree_res.selection()
        if not sel:
            return
        vals = self.tree_res.item(sel[0], "values")
        if vals and len(vals) > 6:
            out_path = vals[6]
            if out_path and os.path.exists(out_path):
                os.startfile(out_path)

    def _on_res_locate(self):
        sel = self.tree_res.selection()
        if not sel:
            return
        vals = self.tree_res.item(sel[0], "values")
        if vals and len(vals) > 6:
            out_path = vals[6]
            if out_path and os.path.exists(out_path):
                subprocess.Popen(f'explorer /select,"{os.path.normpath(out_path)}"')

    def _on_res_copy_path(self):
        sel = self.tree_res.selection()
        if not sel:
            return
        vals = self.tree_res.item(sel[0], "values")
        if vals and len(vals) > 6:
            out_path = vals[6]
            self.clipboard_clear()
            self.clipboard_append(out_path)

    # =========================================================================
    # SETTINGS EVENTS (STEP 2)
    # =========================================================================

    def _on_browse_output_dir(self):
        curr = self.output_dir_var.get().strip() or self.default_vip_dir
        chosen = filedialog.askdirectory(title="选择输出目录", initialdir=curr)
        if chosen:
            self.output_dir_var.set(chosen)
            self.cfg["output_dir"] = chosen
            self._save_settings()

    def _on_open_output_dir(self):
        out_dir = self.output_dir_var.get().strip()
        if not os.path.isdir(out_dir):
            try:
                os.makedirs(out_dir, exist_ok=True)
            except Exception as e:
                messagebox.showerror("创建目录失败", f"无法创建输出目录：\n{e}")
                return
        os.startfile(out_dir)

    def _on_toggle_skip_existing(self):
        self.cfg["skip_existing"] = self.skip_existing_var.get()
        self._save_settings()

    def _on_toggle_auto_open(self):
        self.cfg["auto_open_folder"] = self.auto_open_var.get()
        self._save_settings()

    def _on_toggle_auto_filter(self):
        self.cfg["auto_filter_existing"] = self.auto_filter_var.get()
        self._save_settings()

    def _on_workers_changed(self, choice: str):
        val = int(choice.split()[0])
        self.cfg["max_workers"] = val
        self._save_settings()

    # =========================================================================
    # CONVERSION PIPELINE (START / STOP & MONITORING)
    # =========================================================================

    def _on_start_stop_clicked(self):
        if self.task_manager.is_running:
            # Active -> Stop
            self.task_manager.cancel()
            self.lbl_current_track.configure(text="正在停止转换任务...")
            return

        if not self.queue:
            messagebox.showinfo("提示", "当前歌曲列表为空，请先添加待转换歌曲。")
            if self.active_step != 1:
                self.switch_to_step(1)
            return

        out_dir = self.output_dir_var.get().strip()
        if not out_dir:
            out_dir = os.path.join(self.default_vip_dir, "decrypted")
            self.output_dir_var.set(out_dir)
        os.makedirs(out_dir, exist_ok=True)

        fmt = self._get_current_format_code()
        custom_ffmpeg = self.cfg.get("custom_ffmpeg_path", "").strip() or None
        if fmt in ("mp3", "aac") and not find_ffmpeg(custom_ffmpeg):
            messagebox.showerror("错误", "未检测到可用的 FFmpeg！转码 MP3 或 AAC 需要 FFmpeg 支持。\n请点击顶部「FFmpeg 状态」配置路径。")
            return

        # Reset counters
        self.count_success = 0
        self.count_skipped = 0
        self.count_failed = 0
        self.count_total = len(self.queue)

        self.kpi_pending.configure(text=f"{self.count_total} 首")
        self.kpi_success.configure(text="0 首")
        self.kpi_skipped.configure(text="0 首")
        self.kpi_failed.configure(text="0 首")

        # Clear previous results tree
        for iid in self.tree_res.get_children():
            self.tree_res.delete(iid)
        self.lbl_empty_res.place_forget()

        # Update Start/Stop buttons
        stop_txt = "⏹ 停止转换"
        stop_color = "#dc2626"
        self.btn_step1_start.configure(text=stop_txt, fg_color=stop_color, hover_color="#b91c1c")
        self.btn_step2_start.configure(text=stop_txt, fg_color=stop_color, hover_color="#b91c1c")
        self.btn_step3_action.configure(text=stop_txt, fg_color=stop_color, hover_color="#b91c1c")

        self.progress_bar.set(0.0)
        self.lbl_pct.configure(text="0%")
        self.lbl_current_track.configure(text=f"正在启动多线程转换流水线 (共 {self.count_total} 首)...")

        # Automatically switch to Step 3 so user sees live conversion!
        self.switch_to_step(3)

        # Launch background execution thread
        threading.Thread(target=self._execute_conversion_thread, daemon=True).start()

    def _execute_conversion_thread(self):
        fmt = self._get_current_format_code()
        br = self.cfg.get("mp3_bitrate", "320k") if fmt == "mp3" else self.cfg.get("aac_bitrate", "256k")
        custom_ffmpeg = self.cfg.get("custom_ffmpeg_path", "").strip() or None
        out_dir = self.output_dir_var.get().strip()
        skip = self.skip_existing_var.get()
        workers = self.cfg.get("max_workers", 3)

        self.task_manager.run_batch(
            items=self.queue,
            target_format=fmt,
            bitrate=br,
            output_dir=out_dir,
            skip_existing=skip,
            max_workers=workers,
            custom_ffmpeg_path=custom_ffmpeg,
            on_item_update=self._on_item_updated,
            on_total_progress=self._on_progress_updated,
            on_finished=self._on_batch_finished
        )

    def _on_item_updated(self, it):
        def update():
            # Update Step 1 queue row status
            if self.tree.exists(it['id']):
                vals = list(self.tree.item(it['id'], "values"))
                if len(vals) > 4:
                    vals[4] = it.get('status_text', '')
                    self.tree.item(it['id'], values=vals)

            # Update Step 3 metrics and results row
            st = it.get('status')
            if st == TaskStatus.COMPLETED:
                self.count_success += 1
                self.kpi_success.configure(text=f"{self.count_success} 首")
                self._append_or_update_result_row(it, "✅ 转换成功")
            elif st == TaskStatus.SKIPPED:
                self.count_skipped += 1
                self.kpi_skipped.configure(text=f"{self.count_skipped} 首")
                self._append_or_update_result_row(it, "⏭ 已跳过 (已存在)")
            elif st == TaskStatus.FAILED:
                self.count_failed += 1
                self.kpi_failed.configure(text=f"{self.count_failed} 首")
                self._append_or_update_result_row(it, f"❌ 失败: {it.get('error', '未知错误')}")
            elif st in (TaskStatus.CONVERTING, TaskStatus.DECRYPTING):
                pct = int(it.get('progress', 0.0) * 100)
                self.lbl_current_track.configure(
                    text=f"正在转换: {it['filename']} ({pct}%)"
                )

        self.after(0, update)

    def _append_or_update_result_row(self, it, status_str):
        out_path = it.get('output_path', '')
        size_str = "-"
        if out_path and os.path.exists(out_path):
            try:
                sz = os.path.getsize(out_path)
                size_str = f"{sz / 1024 / 1024:.2f} MB"
            except Exception:
                pass

        idx = self.count_success + self.count_skipped + self.count_failed

        self.tree_res.insert(
            "",
            "end",
            iid=f"res_{it['id']}",
            values=(
                idx,
                it['filename'],
                self._get_target_format_label(),
                status_str,
                size_str,
                "-",
                out_path or "-"
            )
        )
        self.tree_res.yview_moveto(1.0)

    def _on_progress_updated(self, comp, tot, pct_float):
        def update():
            fraction = min(1.0, max(0.0, pct_float))
            self.progress_bar.set(fraction)
            self.lbl_pct.configure(text=f"{int(fraction * 100)}%")
        self.after(0, update)

    def _on_batch_finished(self, summary):
        def finish():
            # Reset action buttons
            start_txt_s1 = "🚀 直接开始转换 (Alt+S)"
            start_txt_s2 = "🚀 开始执行转换 (Alt+S)"
            start_txt_s3 = "🔄 重新转换 / 转换更多"
            blue = "#2563eb"

            self.btn_step1_start.configure(text=start_txt_s1, fg_color=blue, hover_color="#1d4ed8")
            self.btn_step2_start.configure(text=start_txt_s2, fg_color=blue, hover_color="#1d4ed8")
            self.btn_step3_action.configure(text=start_txt_s3, fg_color=blue, hover_color="#1d4ed8")

            self.progress_bar.set(1.0)
            self.lbl_pct.configure(text="100%")

            succ = summary.get("success", 0)
            skip = summary.get("skipped", 0)
            fail = summary.get("failed", 0)
            dur = summary.get("elapsed_sec", 0)

            status_msg = f"🎉 转换完成！成功 {succ} 首，跳过 {skip} 首，失败 {fail} 首，耗时 {dur} 秒。"
            self.lbl_current_track.configure(text=status_msg)

            # Auto open folder if configured
            if self.auto_open_var.get() and succ > 0:
                self._on_open_output_dir()

            # Beep notification
            try:
                self.bell()
            except Exception:
                pass

        self.after(0, finish)

    def _save_settings(self):
        save_config(self.cfg)

    def _on_close(self):
        if self.task_manager.is_running:
            self.task_manager.cancel()
        self._save_settings()
        self.destroy()


def main():
    app = CloudMusicConverterApp()
    app.mainloop()


if __name__ == "__main__":
    main()
