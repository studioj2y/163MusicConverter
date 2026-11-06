# -*- coding: utf-8 -*-
"""
app.py - Elegant GUI for NetEase Music VIP Song Decryptor & Universal Converter
Crafted with modern light-mode card aesthetics, responsive layout, and DnD support.
"""

import os
import sys
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import customtkinter as ctk
import tkinterdnd2

from config import load_config, save_config
from task_manager import ConversionTaskManager, TaskStatus
from ffmpeg_engine import find_ffmpeg, get_ffmpeg_version

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

# Ensure UTF-8 output if terminal attached
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass


class ElegantSegmentedButton(ctk.CTkSegmentedButton):
    """
    Enhanced CTkSegmentedButton with active text inversion (pure white on active color).
    Guarantees crisp contrast and high legibility across Light and Dark themes.
    """
    def __init__(self, *args, selected_text_color="#ffffff", unselected_text_color="#334155", **kwargs):
        self._selected_text_color = selected_text_color
        self._unselected_text_color = unselected_text_color
        super().__init__(*args, **kwargs)
        self._refresh_button_colors()

    def _refresh_button_colors(self):
        for val, btn in self._buttons_dict.items():
            if val == self._current_value:
                btn.configure(text_color=self._selected_text_color)
            else:
                btn.configure(text_color=self._unselected_text_color)

    def _select_button_by_value(self, value: str):
        super()._select_button_by_value(value)
        if value in self._buttons_dict:
            self._buttons_dict[value].configure(text_color=self._selected_text_color)

    def _unselect_button_by_value(self, value: str):
        super()._unselect_button_by_value(value)
        if value in self._buttons_dict:
            self._buttons_dict[value].configure(text_color=self._unselected_text_color)

    def set(self, value: str, *args, **kwargs):
        super().set(value, *args, **kwargs)
        self._refresh_button_colors()

    def update_theme(self, selected_tc: str, unselected_tc: str):
        self._selected_text_color = selected_tc
        self._unselected_text_color = unselected_tc
        self._refresh_button_colors()


class MusicConverterApp(ctk.CTk, tkinterdnd2.TkinterDnD.DnDWrapper):
    def __init__(self):
        super().__init__()
        self.TkdndVersion = tkinterdnd2.TkinterDnD._require(self)

        self.cfg = load_config()
        self.task_manager = ConversionTaskManager()
        self.items = []
        self.item_id_to_tree_id = {}
        self.is_converting = False
        self.current_mode = self.cfg.get("appearance_mode", "light")

        self._init_window()
        self._setup_tree_styles(self.current_mode)
        self._build_ui()
        self._setup_dnd()
        self._apply_initial_config()
        self._check_ffmpeg_status()

    def _init_window(self):
        # Set Windows App User Model ID so taskbar displays custom icon
        if os.name == 'nt':
            try:
                import ctypes
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Antigravity.CloudMusicConverter.App.1.0")
            except Exception:
                pass

        ctk.set_appearance_mode(self.current_mode)
        ctk.set_default_color_theme("blue")

        self.title("网易云音乐 VIP 歌曲解密 & 格式转换工具")
        self.geometry("1120x800")
        self.minsize(960, 680)

        # Set title bar & taskbar window icon
        icon_path = get_resource_path("app_icon.ico")
        if os.path.exists(icon_path):
            try:
                self.iconbitmap(icon_path)
            except Exception:
                pass

        # Set crisp window canvas background
        self._apply_canvas_bg(self.current_mode)

        # Center on screen
        self.update_idletasks()
        w = 1120
        h = 800
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = max(0, (sw - w) // 2)
        y = max(0, (sh - h) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Keyboard shortcuts
        self.bind("<Control-o>", lambda e: self._on_add_files())
        self.bind("<Control-d>", lambda e: self._on_add_folder())
        self.bind("<Control-f>", lambda e: self._on_filter_unconverted())
        self.bind("<Control-l>", lambda e: self._on_clear_list())
        self.bind("<Delete>", lambda e: self._on_remove_selected())

    def _apply_canvas_bg(self, mode: str):
        if mode == "light":
            self.configure(fg_color="#f8fafc")  # Slate-50 soft canvas
        else:
            self.configure(fg_color="#0f172a")  # Slate-900 dark canvas

    def _setup_tree_styles(self, mode: str):
        style = ttk.Style()
        style.theme_use("clam")

        if mode == "light":
            bg_color = "#ffffff"
            fg_color = "#1e293b"        # Slate-800
            field_bg = "#ffffff"
            select_bg = "#2563eb"       # Royal Blue
            select_fg = "#ffffff"
            header_bg = "#f1f5f9"       # Slate-100
            header_fg = "#334155"       # Slate-700
            hover_bg = "#e2e8f0"
        else:
            bg_color = "#1e293b"
            fg_color = "#f8fafc"
            field_bg = "#182234"
            select_bg = "#3b82f6"
            select_fg = "#ffffff"
            header_bg = "#334155"
            header_fg = "#f1f5f9"
            hover_bg = "#475569"

        style.configure(
            "Custom.Treeview",
            background=bg_color,
            foreground=fg_color,
            fieldbackground=field_bg,
            rowheight=32,
            font=("Segoe UI", 10),
            borderwidth=0
        )
        style.map(
            "Custom.Treeview",
            background=[("selected", select_bg)],
            foreground=[("selected", select_fg)]
        )

        style.configure(
            "Custom.Treeview.Heading",
            background=header_bg,
            foreground=header_fg,
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            padding=(8, 6)
        )
        style.map(
            "Custom.Treeview.Heading",
            background=[("active", hover_bg)]
        )

    def _build_ui(self):
        # =========================================================================
        # 1. TOP HEADER (BRANDING & STATUS)
        # =========================================================================
        self.top_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.top_frame.pack(side="top", fill="x", padx=20, pady=(16, 10))

        # Brand Logo + Title block
        brand_box = ctk.CTkFrame(self.top_frame, fg_color="transparent")
        brand_box.pack(side="left")

        # Decorative icon box
        icon_box = ctk.CTkFrame(
            brand_box,
            width=46,
            height=46,
            corner_radius=12,
            fg_color="#eff6ff",
            border_width=1,
            border_color="#bfdbfe"
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
                lbl_icon = ctk.CTkLabel(icon_box, text="🎧", font=ctk.CTkFont(size=22))
                lbl_icon.place(relx=0.5, rely=0.5, anchor="center")
        else:
            lbl_icon = ctk.CTkLabel(icon_box, text="🎧", font=ctk.CTkFont(size=22))
            lbl_icon.place(relx=0.5, rely=0.5, anchor="center")

        title_text_box = ctk.CTkFrame(brand_box, fg_color="transparent")
        title_text_box.pack(side="left")

        self.title_label = ctk.CTkLabel(
            title_text_box,
            text="网易云音乐 VIP 歌曲全能转换",
            font=ctk.CTkFont(size=19, weight="bold"),
            text_color="#0f172a" if self.current_mode == "light" else "#f8fafc"
        )
        self.title_label.pack(anchor="w")

        self.subtitle_label = ctk.CTkLabel(
            title_text_box,
            text="批量解密 NCM · 提取原始无损音质 · 智能转码为全兼容 MP3 / AAC",
            font=ctk.CTkFont(size=12),
            text_color="#64748b"
        )
        self.subtitle_label.pack(anchor="w")

        # Top Right Actions: Theme Toggle & FFmpeg Status Pill
        top_right_box = ctk.CTkFrame(self.top_frame, fg_color="transparent")
        top_right_box.pack(side="right", pady=4)

        # Theme toggle button
        theme_txt = "🌙 深色模式" if self.current_mode == "light" else "☀️ 浅色模式"
        self.btn_theme = ctk.CTkButton(
            top_right_box,
            text=theme_txt,
            width=90,
            height=28,
            corner_radius=14,
            font=ctk.CTkFont(size=11),
            fg_color="#f1f5f9" if self.current_mode == "light" else "#334155",
            text_color="#334155" if self.current_mode == "light" else "#f1f5f9",
            hover_color="#e2e8f0" if self.current_mode == "light" else "#475569",
            command=self._on_toggle_theme
        )
        self.btn_theme.pack(side="right", padx=(8, 0))

        # FFmpeg status badge
        self.ffmpeg_badge_btn = ctk.CTkButton(
            top_right_box,
            text="● 正在检测 FFmpeg...",
            font=ctk.CTkFont(size=11, weight="bold"),
            height=28,
            corner_radius=14,
            fg_color="#ecfdf5",
            text_color="#065f46",
            border_width=1,
            border_color="#a7f3d0",
            hover_color="#d1fae5",
            command=self._on_ffmpeg_settings
        )
        self.ffmpeg_badge_btn.pack(side="right")

        # =========================================================================
        # 2. ACTION TOOLBAR (IMPORT & QUEUE CONTROLS)
        # =========================================================================
        self.toolbar_frame = ctk.CTkFrame(
            self,
            corner_radius=12,
            border_width=1,
            fg_color="#ffffff" if self.current_mode == "light" else "#1e293b",
            border_color="#e2e8f0" if self.current_mode == "light" else "#334155"
        )
        self.toolbar_frame.pack(side="top", fill="x", padx=20, pady=(0, 10))

        # Add Files button
        btn_add_files = ctk.CTkButton(
            self.toolbar_frame,
            text="➕ 添加文件...",
            width=115,
            height=32,
            corner_radius=8,
            font=ctk.CTkFont(size=12),
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
            height=32,
            corner_radius=8,
            font=ctk.CTkFont(size=12),
            fg_color="#f8fafc" if self.current_mode == "light" else "#334155",
            text_color="#1e293b" if self.current_mode == "light" else "#f8fafc",
            border_width=1,
            border_color="#cbd5e1" if self.current_mode == "light" else "#475569",
            hover_color="#e2e8f0" if self.current_mode == "light" else "#475569",
            command=self._on_add_folder
        )
        btn_add_folder.pack(side="left", padx=4, pady=8)

        # One-click import default NetEase VIP download folder
        self.default_vip_dir = r"D:\CloudMusic\VipSongsDownload"
        btn_import_vip = ctk.CTkButton(
            self.toolbar_frame,
            text="⚡ 一键导入网易云目录",
            width=170,
            height=32,
            corner_radius=8,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#10b981",
            hover_color="#059669",
            text_color="#ffffff",
            command=self._on_import_vip_dir
        )
        btn_import_vip.pack(side="left", padx=6, pady=8)

        # Filter unconverted (keep only new songs)
        btn_filter = ctk.CTkButton(
            self.toolbar_frame,
            text="🔍 筛选未转换 (剔除已存在)",
            width=175,
            height=32,
            corner_radius=8,
            font=ctk.CTkFont(size=12, weight="bold"),
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

        # Remove Selected button
        btn_remove = ctk.CTkButton(
            self.toolbar_frame,
            text="移除选中",
            width=80,
            height=32,
            corner_radius=8,
            font=ctk.CTkFont(size=12),
            fg_color="transparent",
            text_color="#64748b",
            hover_color="#f1f5f9" if self.current_mode == "light" else "#334155",
            command=self._on_remove_selected
        )
        btn_remove.pack(side="left", padx=4, pady=8)

        # Clear List button
        btn_clear = ctk.CTkButton(
            self.toolbar_frame,
            text="清空列表",
            width=80,
            height=32,
            corner_radius=8,
            font=ctk.CTkFont(size=12),
            fg_color="transparent",
            text_color="#ef4444",
            hover_color="#fee2e2" if self.current_mode == "light" else "#451a1a",
            command=self._on_clear_list
        )
        btn_clear.pack(side="left", padx=4, pady=8)

        # Right queue count pill badge
        self.lbl_queue_count = ctk.CTkLabel(
            self.toolbar_frame,
            text="共 0 首歌曲",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#2563eb" if self.current_mode == "light" else "#60a5fa"
        )
        self.lbl_queue_count.pack(side="right", padx=16, pady=8)

        # =========================================================================
        # PACK FROM BOTTOM UP TO GUARANTEE ZERO SQUISHING / OVERLAPPING!
        # =========================================================================

        # =========================================================================
        # 5. BOTTOM FOOTER CARD (GLOBAL PROGRESS & BIG ACTION BUTTON)
        # =========================================================================
        self.bottom_frame = ctk.CTkFrame(
            self,
            corner_radius=12,
            border_width=1,
            fg_color="#ffffff" if self.current_mode == "light" else "#1e293b",
            border_color="#e2e8f0" if self.current_mode == "light" else "#334155"
        )
        self.bottom_frame.pack(side="bottom", fill="x", padx=20, pady=(0, 16))

        # Progress bar and status texts
        prog_box = ctk.CTkFrame(self.bottom_frame, fg_color="transparent")
        prog_box.pack(side="left", fill="x", expand=True, padx=16, pady=12)

        self.progress_bar = ctk.CTkProgressBar(
            prog_box,
            height=10,
            corner_radius=5,
            progress_color="#2563eb",
            fg_color="#e2e8f0" if self.current_mode == "light" else "#334155"
        )
        self.progress_bar.pack(fill="x", pady=(2, 6))
        self.progress_bar.set(0.0)

        self.lbl_global_status = ctk.CTkLabel(
            prog_box,
            text="就绪: 等待添加歌曲并开始",
            font=ctk.CTkFont(size=12),
            text_color="#475569" if self.current_mode == "light" else "#94a3b8",
            anchor="w"
        )
        self.lbl_global_status.pack(fill="x")

        # Large Action Button
        self.btn_start = ctk.CTkButton(
            self.bottom_frame,
            text="▶ 开始执行转换 (Alt+S)",
            font=ctk.CTkFont(size=14, weight="bold"),
            width=180,
            height=42,
            corner_radius=10,
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            text_color="#ffffff",
            command=self._on_start_stop_clicked
        )
        self.btn_start.pack(side="right", padx=16, pady=12)
        self.bind("<Alt-s>", lambda e: self._on_start_stop_clicked())

        # =========================================================================
        # 4. OPTIONS & ENCODING SETTINGS CARD
        # =========================================================================
        self.options_frame = ctk.CTkFrame(
            self,
            corner_radius=12,
            border_width=1,
            fg_color="#ffffff" if self.current_mode == "light" else "#1e293b",
            border_color="#e2e8f0" if self.current_mode == "light" else "#334155"
        )
        self.options_frame.pack(side="bottom", fill="x", padx=20, pady=(0, 10))

        # Row 1: Target Format Segmented Button & Bitrate Selector
        fmt_row = ctk.CTkFrame(self.options_frame, fg_color="transparent")
        fmt_row.pack(fill="x", padx=14, pady=(12, 6))

        lbl_target = ctk.CTkLabel(
            fmt_row,
            text="🎯 目标格式:",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#0f172a" if self.current_mode == "light" else "#f8fafc",
            width=80,
            anchor="w"
        )
        lbl_target.pack(side="left")

        self.segmented_format = ElegantSegmentedButton(
            fmt_row,
            values=["源文件 (仅解密)", "MP3 通用音频", "AAC / M4A (全兼容)"],
            font=ctk.CTkFont(size=12, weight="bold"),
            height=32,
            corner_radius=8,
            selected_color="#2563eb",
            selected_hover_color="#1d4ed8",
            unselected_color="#f1f5f9" if self.current_mode == "light" else "#334155",
            unselected_hover_color="#e2e8f0" if self.current_mode == "light" else "#475569",
            selected_text_color="#ffffff",
            unselected_text_color="#334155" if self.current_mode == "light" else "#94a3b8",
            command=self._on_format_changed
        )
        self.segmented_format.pack(side="left", padx=(4, 20))

        lbl_bitrate_title = ctk.CTkLabel(
            fmt_row,
            text="音质码率:",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#0f172a" if self.current_mode == "light" else "#f8fafc",
            width=70,
            anchor="w"
        )
        lbl_bitrate_title.pack(side="left")

        self.bitrate_combo = ctk.CTkComboBox(
            fmt_row,
            width=340,
            height=32,
            corner_radius=8,
            state="readonly",
            font=ctk.CTkFont(size=12),
            values=[],
            command=self._on_bitrate_changed
        )
        self.bitrate_combo.pack(side="left", padx=4)

        # Row 2: Optimization hint banner (Dynamic Callout Card)
        self.callout_frame = ctk.CTkFrame(
            self.options_frame,
            corner_radius=8,
            border_width=1,
            height=34,
            fg_color="#eff6ff",
            border_color="#bfdbfe"
        )
        self.callout_frame.pack(fill="x", padx=14, pady=(2, 8))
        self.callout_frame.pack_propagate(False)

        self.lbl_encoding_hint = ctk.CTkLabel(
            self.callout_frame,
            text="",
            font=ctk.CTkFont(size=11),
            text_color="#1e40af",
            anchor="w"
        )
        self.lbl_encoding_hint.pack(side="left", fill="both", expand=True, padx=10)

        # Row 3: Output directory and switches
        out_row = ctk.CTkFrame(self.options_frame, fg_color="transparent")
        out_row.pack(fill="x", padx=14, pady=(0, 12))

        lbl_out = ctk.CTkLabel(
            out_row,
            text="📂 输出目录:",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#0f172a" if self.current_mode == "light" else "#f8fafc",
            width=80,
            anchor="w"
        )
        lbl_out.pack(side="left")

        self.output_dir_var = tk.StringVar(value=self.cfg.get("output_dir", self.default_vip_dir + r"\decrypted"))
        self.entry_output_dir = ctk.CTkEntry(
            out_row,
            textvariable=self.output_dir_var,
            height=32,
            corner_radius=8,
            font=ctk.CTkFont(size=12)
        )
        self.entry_output_dir.pack(side="left", fill="x", expand=True, padx=(4, 6))

        btn_browse_out = ctk.CTkButton(
            out_row,
            text="浏览...",
            width=70,
            height=32,
            corner_radius=8,
            font=ctk.CTkFont(size=12),
            fg_color="#f8fafc" if self.current_mode == "light" else "#334155",
            text_color="#1e293b" if self.current_mode == "light" else "#f8fafc",
            border_width=1,
            border_color="#cbd5e1" if self.current_mode == "light" else "#475569",
            hover_color="#e2e8f0" if self.current_mode == "light" else "#475569",
            command=self._on_browse_output_dir
        )
        btn_browse_out.pack(side="left", padx=3)

        btn_open_out = ctk.CTkButton(
            out_row,
            text="📂 打开",
            width=70,
            height=32,
            corner_radius=8,
            font=ctk.CTkFont(size=12),
            fg_color="#f8fafc" if self.current_mode == "light" else "#334155",
            text_color="#1e293b" if self.current_mode == "light" else "#f8fafc",
            border_width=1,
            border_color="#cbd5e1" if self.current_mode == "light" else "#475569",
            hover_color="#e2e8f0" if self.current_mode == "light" else "#475569",
            command=self._on_open_output_dir
        )
        btn_open_out.pack(side="left", padx=3)

        self.skip_existing_var = tk.BooleanVar(value=self.cfg.get("skip_existing", True))
        chk_skip = ctk.CTkCheckBox(
            out_row,
            text="跳过已存在文件",
            variable=self.skip_existing_var,
            font=ctk.CTkFont(size=12),
            command=self._save_settings
        )
        chk_skip.pack(side="left", padx=(14, 4))

        self.auto_filter_var = tk.BooleanVar(value=self.cfg.get("auto_filter_existing", False))
        chk_auto_filter = ctk.CTkCheckBox(
            out_row,
            text="导入时自动排除已转换歌曲",
            variable=self.auto_filter_var,
            font=ctk.CTkFont(size=12),
            command=self._save_settings
        )
        chk_auto_filter.pack(side="left", padx=(10, 4))

        # =========================================================================
        # 3. MIDDLE AREA: FILE QUEUE (FILLS REMAINING VERTICAL SPACE)
        # =========================================================================
        self.tree_container = ctk.CTkFrame(
            self,
            corner_radius=12,
            border_width=1,
            fg_color="#ffffff" if self.current_mode == "light" else "#1e293b",
            border_color="#e2e8f0" if self.current_mode == "light" else "#334155"
        )
        self.tree_container.pack(side="top", fill="both", expand=True, padx=20, pady=(0, 10))

        tree_scroll_y = ttk.Scrollbar(self.tree_container, orient="vertical")
        self.tree = ttk.Treeview(
            self.tree_container,
            columns=("idx", "name", "size", "orig_fmt", "target_fmt", "status"),
            show="headings",
            style="Custom.Treeview",
            selectmode="extended",
            yscrollcommand=tree_scroll_y.set
        )
        tree_scroll_y.config(command=self.tree.yview)

        # Column definitions
        self.tree.heading("idx", text="#")
        self.tree.heading("name", text="歌曲 / 文件名")
        self.tree.heading("size", text="大小")
        self.tree.heading("orig_fmt", text="源格式")
        self.tree.heading("target_fmt", text="目标格式")
        self.tree.heading("status", text="状态")

        self.tree.column("idx", width=50, minwidth=40, anchor="center")
        self.tree.column("name", width=460, minwidth=240, anchor="w")
        self.tree.column("size", width=90, minwidth=70, anchor="center")
        self.tree.column("orig_fmt", width=80, minwidth=70, anchor="center")
        self.tree.column("target_fmt", width=120, minwidth=100, anchor="center")
        self.tree.column("status", width=220, minwidth=150, anchor="w")

        self.tree.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=4)
        tree_scroll_y.pack(side="right", fill="y", padx=(0, 4), pady=4)

        # Context menu & mouse interaction bindings
        self.tree.bind("<Button-3>", self._on_tree_right_click)
        self.tree.bind("<Double-1>", self._on_tree_double_click)

        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="▶ 播放/打开已转换音频", command=self._on_play_or_open_completed)
        self.context_menu.add_command(label="📂 在资源管理器中定位源文件", command=self._on_locate_source_file)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="🔍 筛选未转换 (Ctrl+F)", command=self._on_filter_unconverted)
        self.context_menu.add_command(label="❌ 移除选中项 (Delete)", command=self._on_remove_selected)
        self.context_menu.add_command(label="🗑️ 清空列表 (Ctrl+L)", command=self._on_clear_list)

        # Empty list stylish illustration card
        self.empty_card = ctk.CTkFrame(
            self.tree,
            corner_radius=12,
            border_width=1,
            fg_color="#f8fafc" if self.current_mode == "light" else "#182234",
            border_color="#e2e8f0" if self.current_mode == "light" else "#334155"
        )
        self.empty_card.place(relx=0.5, rely=0.5, anchor="center")

        lbl_drag_icon = ctk.CTkLabel(
            self.empty_card,
            text="📥",
            font=ctk.CTkFont(size=36)
        )
        lbl_drag_icon.pack(padx=30, pady=(16, 4))

        lbl_drag_title = ctk.CTkLabel(
            self.empty_card,
            text="支持直接批量拖拽文件或文件夹至此",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#1e293b" if self.current_mode == "light" else "#f8fafc"
        )
        lbl_drag_title.pack(padx=30, pady=(0, 2))

        lbl_drag_sub = ctk.CTkLabel(
            self.empty_card,
            text="可从网易云下载目录拖入 .ncm 加密歌曲，或点击上方「一键导入」",
            font=ctk.CTkFont(size=12),
            text_color="#64748b"
        )
        lbl_drag_sub.pack(padx=30, pady=(0, 16))

    def _setup_dnd(self):
        """Register Drag and Drop targets."""
        for target in (self, self.tree, self.tree_container, self.empty_card):
            try:
                target.drop_target_register(tkinterdnd2.DND_FILES)
                target.dnd_bind("<<Drop>>", self._on_drop_files)
            except Exception:
                pass

    def _on_drop_files(self, event):
        try:
            paths = self.tk.splitlist(event.data)
            self._add_paths(paths)
        except Exception as e:
            messagebox.showerror("拖放失败", f"无法解析拖放的文件: {e}")

    def _apply_initial_config(self):
        fmt = self.cfg.get("target_format", "source")
        if fmt == "source":
            self.segmented_format.set("源文件 (仅解密)")
        elif fmt == "mp3":
            self.segmented_format.set("MP3 通用音频")
        elif fmt in ("aac", "m4a"):
            self.segmented_format.set("AAC / M4A (全兼容)")
        self._update_bitrate_ui(fmt)

    def _on_toggle_theme(self):
        new_mode = "dark" if self.current_mode == "light" else "light"
        self.current_mode = new_mode
        self.cfg["appearance_mode"] = new_mode
        self._save_settings()

        ctk.set_appearance_mode(new_mode)
        self._apply_canvas_bg(new_mode)
        self._setup_tree_styles(new_mode)

        self.btn_theme.configure(
            text="🌙 深色模式" if new_mode == "light" else "☀️ 浅色模式",
            fg_color="#f1f5f9" if new_mode == "light" else "#334155",
            text_color="#334155" if new_mode == "light" else "#f1f5f9",
            hover_color="#e2e8f0" if new_mode == "light" else "#475569"
        )
        self.title_label.configure(
            text_color="#0f172a" if new_mode == "light" else "#f8fafc"
        )
        self.toolbar_frame.configure(
            fg_color="#ffffff" if new_mode == "light" else "#1e293b",
            border_color="#e2e8f0" if new_mode == "light" else "#334155"
        )
        self.tree_container.configure(
            fg_color="#ffffff" if new_mode == "light" else "#1e293b",
            border_color="#e2e8f0" if new_mode == "light" else "#334155"
        )
        self.options_frame.configure(
            fg_color="#ffffff" if new_mode == "light" else "#1e293b",
            border_color="#e2e8f0" if new_mode == "light" else "#334155"
        )
        self.bottom_frame.configure(
            fg_color="#ffffff" if new_mode == "light" else "#1e293b",
            border_color="#e2e8f0" if new_mode == "light" else "#334155"
        )
        self.empty_card.configure(
            fg_color="#f8fafc" if new_mode == "light" else "#182234",
            border_color="#e2e8f0" if new_mode == "light" else "#334155"
        )
        self.segmented_format.update_theme(
            selected_tc="#ffffff",
            unselected_tc="#334155" if new_mode == "light" else "#94a3b8"
        )
        self.segmented_format.configure(
            unselected_color="#f1f5f9" if new_mode == "light" else "#334155",
            unselected_hover_color="#e2e8f0" if new_mode == "light" else "#475569"
        )
        self._update_bitrate_ui(self._get_current_format_code())

    def _get_current_format_code(self) -> str:
        val = self.segmented_format.get()
        if "源文件" in val:
            return "source"
        elif "MP3" in val:
            return "mp3"
        elif "AAC" in val:
            return "aac"
        return "source"

    def _on_format_changed(self, choice=None):
        if not choice:
            choice = self.segmented_format.get()
        if "源文件" in choice:
            fmt_code = "source"
        elif "MP3" in choice:
            fmt_code = "mp3"
        elif "AAC" in choice:
            fmt_code = "aac"
        else:
            fmt_code = "source"
        self.cfg["target_format"] = fmt_code
        self._update_bitrate_ui(fmt_code)
        self._update_tree_target_format_column()
        self._save_settings()

    def _update_bitrate_ui(self, fmt: str):
        if fmt == "source":
            self.bitrate_combo.configure(state="normal", values=["保留原始音频品质"])
            self.bitrate_combo.set("保留原始音频品质")
            self.bitrate_combo.configure(state="disabled")
            self.callout_frame.configure(
                fg_color="#f0fdf4" if self.current_mode == "light" else "#062e1e",
                border_color="#bbf7d0" if self.current_mode == "light" else "#047857"
            )
            self.lbl_encoding_hint.configure(
                text="⚡ 原生无损提取：直接保留原曲无损 FLAC 或 320k MP3，无二次压缩损耗，速度极快！",
                text_color="#166534" if self.current_mode == "light" else "#86efac"
            )
        elif fmt == "mp3":
            options = [
                "320 kbps (CBR 恒定码率 - 最高音质/推荐)",
                "256 kbps (CBR 恒定码率 - 高品质)",
                "192 kbps (CBR 恒定码率 - 标准品质)",
                "128 kbps (CBR 恒定码率 - 紧凑便携)",
                "VBR V0 (~245 kbps 动态码率 - 极高音质)",
                "VBR V2 (~190 kbps 动态码率 - 黄金平衡)",
                "VBR V5 (~130 kbps 动态码率 - 相当于128k便携档)"
            ]
            self.bitrate_combo.configure(state="readonly", values=options)
            saved_mp3_br = self.cfg.get("mp3_bitrate", "320k")
            default_val = options[0]
            for opt in options:
                if saved_mp3_br in opt:
                    default_val = opt
                    break
            self.bitrate_combo.set(default_val)
            self.callout_frame.configure(
                fg_color="#eff6ff" if self.current_mode == "light" else "#172554",
                border_color="#bfdbfe" if self.current_mode == "light" else "#1d4ed8"
            )
            self.lbl_encoding_hint.configure(
                text="🚗 行业金标：采用 libmp3lame 编码，支持 CBR 恒定码率与 VBR 动态码率（含 ~130k V5 便携档）。写入 ID3v2.3 标签与内嵌封面，车载/手机 100% 兼容！",
                text_color="#1e40af" if self.current_mode == "light" else "#93c5fd"
            )
        elif fmt == "aac":
            options = [
                "320 kbps (CBR 恒定码率 - 极限高保真)",
                "256 kbps (CBR 恒定码率 - Apple iTunes Plus 推荐)",
                "192 kbps (CBR 恒定码率 - 标准高质量)",
                "128 kbps (CBR 恒定码率 - 高性价比便携)",
                "VBR 动态质量 (~190-220 kbps 动态高保真)",
                "VBR 动态质量 (~120-140 kbps 动态紧凑便携)"
            ]
            self.bitrate_combo.configure(state="readonly", values=options)
            saved_aac_br = self.cfg.get("aac_bitrate", "256k")
            default_val = options[1]
            for opt in options:
                if saved_aac_br in opt:
                    default_val = opt
                    break
            self.bitrate_combo.set(default_val)
            self.callout_frame.configure(
                fg_color="#f5f3ff" if self.current_mode == "light" else "#2e1065",
                border_color="#ddd6fe" if self.current_mode == "light" else "#6d28d9"
            )
            self.lbl_encoding_hint.configure(
                text="🍎 苹果与安卓高保真：采用 .m4a 容器封装，默认高保真 CBR 恒定码率（防车机寻轨漂移，兼备 VBR 选项），开启 FastStart 秒开索引与封面内嵌！",
                text_color="#5b21b6" if self.current_mode == "light" else "#c4b5fd"
            )

    def _on_bitrate_changed(self, choice: str):
        fmt = self._get_current_format_code()
        if fmt == "mp3":
            if "V0" in choice:
                self.cfg["mp3_bitrate"] = "vbr0"
            elif "V2" in choice:
                self.cfg["mp3_bitrate"] = "vbr2"
            elif "V5" in choice:
                self.cfg["mp3_bitrate"] = "vbr5"
            elif "320" in choice:
                self.cfg["mp3_bitrate"] = "320k"
            elif "256" in choice:
                self.cfg["mp3_bitrate"] = "256k"
            elif "192" in choice:
                self.cfg["mp3_bitrate"] = "192k"
            elif "128" in choice:
                self.cfg["mp3_bitrate"] = "128k"
        elif fmt == "aac":
            if "VBR" in choice and ("120" in choice or "140" in choice):
                self.cfg["aac_bitrate"] = "vbr_med"
            elif "VBR" in choice:
                self.cfg["aac_bitrate"] = "vbr_high"
            elif "320" in choice:
                self.cfg["aac_bitrate"] = "320k"
            elif "256" in choice:
                self.cfg["aac_bitrate"] = "256k"
            elif "192" in choice:
                self.cfg["aac_bitrate"] = "192k"
            elif "128" in choice:
                self.cfg["aac_bitrate"] = "128k"
        self._update_tree_target_format_column()
        self._save_settings()

    def _get_target_format_label(self) -> str:
        fmt = self._get_current_format_code()
        if fmt == "source":
            return "源文件 (仅解密)"
        elif fmt == "mp3":
            br = self.cfg.get("mp3_bitrate", "320k").upper()
            return f"MP3 ({br})"
        elif fmt == "aac":
            br = self.cfg.get("aac_bitrate", "256k").upper()
            return f"AAC/M4A ({br})"
        return fmt

    def _update_tree_target_format_column(self):
        lbl = self._get_target_format_label()
        for it in self.items:
            tree_id = self.item_id_to_tree_id.get(it['id'])
            if tree_id and self.tree.exists(tree_id):
                vals = list(self.tree.item(tree_id, "values"))
                if len(vals) >= 6:
                    vals[4] = lbl
                    self.tree.item(tree_id, values=vals)

    def _check_ffmpeg_status(self):
        custom_p = self.cfg.get("custom_ffmpeg_path")
        p = find_ffmpeg(custom_p)
        if p:
            v = get_ffmpeg_version(p)
            short_v = v.split()[2] if len(v.split()) > 2 else "已就绪"
            self.ffmpeg_badge_btn.configure(
                text=f"● FFmpeg 核心就绪 ({short_v})",
                fg_color="#ecfdf5",
                text_color="#065f46",
                border_color="#a7f3d0",
                hover_color="#d1fae5"
            )
        else:
            self.ffmpeg_badge_btn.configure(
                text="● FFmpeg 未检测到 (点击配置)",
                fg_color="#fef2f2",
                text_color="#991b1b",
                border_color="#fecaca",
                hover_color="#fee2e2"
            )

    def _on_ffmpeg_settings(self):
        custom_p = self.cfg.get("custom_ffmpeg_path", "")
        new_path = filedialog.askopenfilename(
            title="选择 ffmpeg.exe 可执行文件",
            filetypes=[("FFmpeg Executable", "ffmpeg.exe"), ("All Files", "*.*")]
        )
        if new_path:
            self.cfg["custom_ffmpeg_path"] = new_path
            self._save_settings()
            self._check_ffmpeg_status()
            messagebox.showinfo("FFmpeg 设置", f"已成功指定 FFmpeg 路径:\n{new_path}")

    def _on_add_files(self):
        files = filedialog.askopenfilenames(
            title="选择要转换的歌曲文件",
            filetypes=[
                ("网易云加密歌曲及通用音频", "*.ncm;*.flac;*.mp3;*.m4a;*.aac;*.wav;*.ogg"),
                ("网易云加密歌曲 (*.ncm)", "*.ncm"),
                ("所有文件 (*.*)", "*.*")
            ]
        )
        if files:
            self._add_paths(list(files))

    def _on_add_folder(self):
        folder = filedialog.askdirectory(title="选择包含歌曲的文件夹")
        if folder:
            self._add_paths([folder])

    def _on_import_vip_dir(self):
        vip_dir = self.default_vip_dir
        if not os.path.exists(vip_dir):
            messagebox.showwarning("目录不存在", f"未找到默认下载目录:\n{vip_dir}\n请使用[添加文件夹]手动选择。")
            return
        self._add_paths([vip_dir])

    def _add_paths(self, paths):
        if not paths:
            return

        def do_scan():
            new_items = self.task_manager.scan_files(paths, recursive=False)
            self.after(0, lambda: self._append_scanned_items(new_items))

        threading.Thread(target=do_scan, daemon=True).start()

    def _append_scanned_items(self, new_items):
        existing_paths = {it['path'] for it in self.items}
        added_count = 0
        filtered_count = 0
        tgt_label = self._get_target_format_label()

        auto_filter = self.auto_filter_var.get()
        existing_map = {}
        target_fmt = self._get_current_format_code()
        if auto_filter:
            out_dir = self.output_dir_var.get().strip()
            existing_map = self.task_manager.get_existing_output_map(out_dir)

        for it in new_items:
            if it['path'] in existing_paths:
                continue

            if auto_filter and self.task_manager.is_item_already_converted(it['filename'], existing_map, target_fmt):
                filtered_count += 1
                continue

            self.items.append(it)
            existing_paths.add(it['path'])

            idx = len(self.items)
            ext = os.path.splitext(it['filename'])[1].upper().lstrip('.')
            orig_fmt_str = f"NCM ({ext})" if it['is_ncm'] else ext

            tree_id = self.tree.insert(
                "",
                "end",
                values=(idx, it['filename'], it['size_str'], orig_fmt_str, tgt_label, it['status_text'])
            )
            self.item_id_to_tree_id[it['id']] = tree_id
            added_count += 1

        self._refresh_queue_count()

        if auto_filter and filtered_count > 0:
            self.lbl_global_status.configure(
                text=f"⚡ 导入完成：共扫描到 {len(new_items)} 首，已自动过滤 {filtered_count} 首已转换歌曲，载入 {added_count} 首新增待转换歌曲！"
            )
        elif added_count > 0:
            self.lbl_global_status.configure(
                text=f"已成功添加 {added_count} 首歌曲到待转换列表"
            )

    def _on_filter_unconverted(self):
        """
        Compares queue with output directory and strips out already-converted songs.
        """
        if self.is_converting:
            messagebox.showwarning("提示", "正在转换中，无法筛选列表。")
            return

        if not self.items:
            messagebox.showwarning("提示", "转换列表为空，请先添加文件或导入歌曲！")
            return

        out_dir = self.output_dir_var.get().strip()
        target_fmt = self._get_current_format_code()
        existing_map = self.task_manager.get_existing_output_map(out_dir)

        kept_items = []
        filtered_items = []

        for it in self.items:
            if self.task_manager.is_item_already_converted(it['filename'], existing_map, target_fmt):
                filtered_items.append(it)
            else:
                kept_items.append(it)

        if not filtered_items:
            messagebox.showinfo(
                "比对结果",
                f"🎉 比对完成！\n\n当前列表中的所有 {len(self.items)} 首歌曲均为未转换的新增歌曲（输出目录中暂无对应已转换音频）。"
            )
            return

        if not kept_items:
            if messagebox.askyesno(
                "比对结果",
                f"🎉 经与输出目录比对：\n当前列表中的所有 {len(filtered_items)} 首歌曲均已转换完毕！\n\n是否立即清空列表？"
            ):
                self._on_clear_list()
            else:
                self.lbl_global_status.configure(text=f"比对完成：列表全部 {len(filtered_items)} 首歌曲均已在输出目录完成转换。")
            return

        # Remove filtered items from Treeview
        for it in filtered_items:
            tid = self.item_id_to_tree_id.get(it['id'])
            if tid and self.tree.exists(tid):
                self.tree.delete(tid)
            if it['id'] in self.item_id_to_tree_id:
                del self.item_id_to_tree_id[it['id']]

        self.items = kept_items

        # Renumber remaining rows
        for idx, it in enumerate(self.items, 1):
            tid = self.item_id_to_tree_id.get(it['id'])
            if tid and self.tree.exists(tid):
                vals = list(self.tree.item(tid, "values"))
                vals[0] = idx
                self.tree.item(tid, values=vals)

        self._refresh_queue_count()

        msg = f"🔍 筛选完成：已剔除 {len(filtered_items)} 首已转换歌曲，保留 {len(kept_items)} 首新增待转换歌曲！"
        self.lbl_global_status.configure(text=msg)
        messagebox.showinfo(
            "筛选结果",
            f"已成功比对输出目录：\n\n"
            f"• 历史已转换 (已剔除): {len(filtered_items)} 首\n"
            f"• 新增待转换 (已保留): {len(kept_items)} 首\n\n"
            f"您可以直接点击「开始执行转换」处理新增歌曲！"
        )

    def _on_remove_selected(self):
        if self.is_converting:
            messagebox.showwarning("提示", "正在转换中，无法修改列表。")
            return

        selected_tree_ids = self.tree.selection()
        if not selected_tree_ids:
            return

        selected_set = set(selected_tree_ids)
        remaining_items = []
        for it in self.items:
            tid = self.item_id_to_tree_id.get(it['id'])
            if tid in selected_set:
                self.tree.delete(tid)
                if it['id'] in self.item_id_to_tree_id:
                    del self.item_id_to_tree_id[it['id']]
            else:
                remaining_items.append(it)

        self.items = remaining_items

        for idx, it in enumerate(self.items, 1):
            tid = self.item_id_to_tree_id.get(it['id'])
            if tid and self.tree.exists(tid):
                vals = list(self.tree.item(tid, "values"))
                vals[0] = idx
                self.tree.item(tid, values=vals)

        self._refresh_queue_count()

    def _on_clear_list(self):
        if self.is_converting:
            messagebox.showwarning("提示", "正在转换中，无法清空列表。")
            return
        for tid in self.tree.get_children():
            self.tree.delete(tid)
        self.items.clear()
        self.item_id_to_tree_id.clear()
        self.progress_bar.set(0.0)
        self.lbl_global_status.configure(text="就绪: 等待添加歌曲并开始")
        self._refresh_queue_count()

    def _on_tree_right_click(self, event):
        iid = self.tree.identify_row(event.y)
        if iid:
            if iid not in self.tree.selection():
                self.tree.selection_set(iid)
            self.context_menu.post(event.x_root, event.y_root)

    def _on_tree_double_click(self, event):
        iid = self.tree.identify_row(event.y)
        if not iid:
            return
        item_id = None
        for i_id, t_id in self.item_id_to_tree_id.items():
            if t_id == iid:
                item_id = i_id
                break
        if not item_id:
            return
        target_item = next((it for it in self.items if it['id'] == item_id), None)
        if not target_item:
            return

        out_path = target_item.get('output_path')
        if out_path and os.path.isfile(out_path):
            try:
                os.startfile(out_path)
                return
            except Exception:
                pass

        src_path = target_item.get('path')
        if src_path and os.path.isfile(src_path):
            try:
                subprocess.Popen(f'explorer /select,"{os.path.abspath(src_path)}"')
            except Exception:
                pass

    def _on_locate_source_file(self):
        sel = self.tree.selection()
        if not sel:
            return
        iid = sel[0]
        for it in self.items:
            if self.item_id_to_tree_id.get(it['id']) == iid:
                p = it.get('path')
                if p and os.path.isfile(p):
                    subprocess.Popen(f'explorer /select,"{os.path.abspath(p)}"')
                break

    def _on_play_or_open_completed(self):
        sel = self.tree.selection()
        if not sel:
            return
        iid = sel[0]
        for it in self.items:
            if self.item_id_to_tree_id.get(it['id']) == iid:
                out_p = it.get('output_path')
                if out_p and os.path.isfile(out_p):
                    try:
                        os.startfile(out_p)
                    except Exception as e:
                        messagebox.showerror("打开失败", f"无法播放文件: {e}")
                else:
                    messagebox.showinfo("提示", "该歌曲尚未转换完成，或输出文件不存在。")
                break

    def _refresh_queue_count(self):
        cnt = len(self.items)
        self.lbl_queue_count.configure(text=f"共 {cnt} 首歌曲")
        if cnt == 0:
            self.empty_card.place(relx=0.5, rely=0.5, anchor="center")
        else:
            self.empty_card.place_forget()

    def _on_browse_output_dir(self):
        folder = filedialog.askdirectory(title="选择输出目录", initialdir=self.output_dir_var.get())
        if folder:
            self.output_dir_var.set(folder)
            self.cfg["output_dir"] = folder
            self._save_settings()

    def _on_open_output_dir(self):
        out_dir = self.output_dir_var.get().strip()
        if not os.path.exists(out_dir):
            try:
                os.makedirs(out_dir, exist_ok=True)
            except Exception as e:
                messagebox.showerror("错误", f"无法创建目录: {e}")
                return
        if os.name == 'nt':
            os.startfile(out_dir)
        else:
            subprocess.Popen(['xdg-open', out_dir])

    def _on_start_stop_clicked(self):
        if self.is_converting:
            if messagebox.askyesno("确认停止", "确定要中止当前的解密与转换任务吗？"):
                self.btn_start.configure(text="正在停止...", state="disabled")
                self.task_manager.cancel()
            return

        if not self.items:
            messagebox.showwarning("提示", "转换列表为空，请先添加文件或拖入歌曲！")
            return

        out_dir = self.output_dir_var.get().strip()
        if not out_dir:
            messagebox.showwarning("提示", "请指定输出目录！")
            return

        target_fmt = self._get_current_format_code()
        if target_fmt in ('mp3', 'aac'):
            ffmpeg_p = find_ffmpeg(self.cfg.get("custom_ffmpeg_path"))
            if not ffmpeg_p:
                messagebox.showerror(
                    "缺少 FFmpeg 编码器",
                    f"转换为 {target_fmt.upper()} 格式需要 FFmpeg 编码器。\n请点击右上角配置 FFmpeg 路径，或切换为[源文件 (仅解密)]模式。"
                )
                return

        self.is_converting = True
        self.btn_start.configure(
            text="⏹ 停止转换",
            fg_color="#dc2626",
            hover_color="#b91c1c",
            state="normal"
        )
        self.progress_bar.set(0.0)
        self.lbl_global_status.configure(text=f"开始处理: 共 {len(self.items)} 首歌曲...")

        tgt_label = self._get_target_format_label()
        for idx, it in enumerate(self.items, 1):
            it['status'] = TaskStatus.PENDING
            it['status_text'] = "等待中"
            it['progress'] = 0.0
            tid = self.item_id_to_tree_id.get(it['id'])
            if tid and self.tree.exists(tid):
                self.tree.item(tid, values=(
                    idx,
                    it['filename'],
                    it['size_str'],
                    "NCM" if it['is_ncm'] else os.path.splitext(it['filename'])[1].upper().lstrip('.'),
                    tgt_label,
                    "等待中"
                ))

        threading.Thread(target=self._execute_conversion_thread, daemon=True).start()

    def _execute_conversion_thread(self):
        target_fmt = self._get_current_format_code()
        bitrate = self.cfg.get("mp3_bitrate", "320k") if target_fmt == "mp3" else self.cfg.get("aac_bitrate", "256k")
        out_dir = self.output_dir_var.get().strip()
        skip_existing = self.skip_existing_var.get()
        workers = self.cfg.get("max_workers", 3)
        custom_ffmpeg = self.cfg.get("custom_ffmpeg_path")

        self.task_manager.run_batch(
            items=self.items,
            target_format=target_fmt,
            bitrate=bitrate,
            output_dir=out_dir,
            skip_existing=skip_existing,
            max_workers=workers,
            custom_ffmpeg_path=custom_ffmpeg,
            on_item_update=lambda it: self.after(0, lambda: self._on_item_updated(it)),
            on_total_progress=lambda comp, tot, pct: self.after(0, lambda: self._on_progress_updated(comp, tot, pct)),
            on_finished=lambda summary: self.after(0, lambda: self._on_batch_finished(summary))
        )

    def _on_item_updated(self, it):
        tid = self.item_id_to_tree_id.get(it['id'])
        if tid and self.tree.exists(tid):
            vals = list(self.tree.item(tid, "values"))
            if len(vals) >= 6:
                vals[5] = it['status_text']
                self.tree.item(tid, values=vals)

    def _on_progress_updated(self, comp, tot, pct):
        self.progress_bar.set(pct)
        self.lbl_global_status.configure(
            text=f"正在处理: {comp} / {tot} 首 ({int(pct * 100)}%)"
        )

    def _on_batch_finished(self, summary):
        self.is_converting = False
        self.btn_start.configure(
            text="▶ 开始执行转换 (Alt+S)",
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            state="normal"
        )
        self.progress_bar.set(1.0 if not summary.get('cancelled') else self.progress_bar.get())

        status_msg = (
            f"处理完成！共 {summary['total']} 首 | "
            f"成功: {summary['success']} | "
            f"跳过: {summary['skipped']} | "
            f"失败: {summary['failed']} | "
            f"耗时: {summary['elapsed_sec']} 秒"
        )
        self.lbl_global_status.configure(text=status_msg)

        if summary.get('cancelled'):
            messagebox.showinfo("任务中止", "批量转换已被用户取消。")
        else:
            detail = (
                f"🎉 批量转换完成！\n\n"
                f"• 总歌曲数: {summary['total']} 首\n"
                f"• 成功完成: {summary['success']} 首\n"
                f"• 跳过已存在: {summary['skipped']} 首\n"
                f"• 转换失败: {summary['failed']} 首\n"
                f"• 总耗时: {summary['elapsed_sec']} 秒\n\n"
                f"输出目录:\n{summary['output_dir']}"
            )
            if messagebox.askyesno("处理完成", f"{detail}\n\n是否立即打开输出目录？"):
                self._on_open_output_dir()

    def _save_settings(self):
        self.cfg["target_format"] = self._get_current_format_code()
        self.cfg["output_dir"] = self.output_dir_var.get().strip()
        self.cfg["skip_existing"] = self.skip_existing_var.get()
        self.cfg["auto_filter_existing"] = self.auto_filter_var.get()
        self.cfg["appearance_mode"] = self.current_mode
        save_config(self.cfg)

    def _on_close(self):
        if self.is_converting:
            if not messagebox.askyesno("正在运行", "当前正在进行转换，确定要强制退出吗？"):
                return
            self.task_manager.cancel()
        self._save_settings()
        self.destroy()


def main():
    app = MusicConverterApp()
    app.mainloop()


if __name__ == "__main__":
    main()
