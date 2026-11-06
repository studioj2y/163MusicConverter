# -*- coding: utf-8 -*-
"""
config.py - Persistent Configuration Manager for CloudMusicConverter
Saves and loads user preferences from a local JSON file.
"""

import os
import json
from typing import Dict, Any

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")

DEFAULT_CONFIG: Dict[str, Any] = {
    "target_format": "source",            # 'source', 'mp3', 'aac'
    "mp3_bitrate": "320k",                # '320k', '256k', '192k', '128k', 'vbr0', 'vbr2'
    "aac_bitrate": "256k",                # '320k', '256k', '192k', '128k'
    "output_dir": r"D:\CloudMusic\VipSongsDownload\decrypted",
    "skip_existing": True,
    "auto_filter_existing": False,
    "max_workers": 3,
    "custom_ffmpeg_path": "",
    "appearance_mode": "light",            # 'light', 'dark', 'system'
    "color_theme": "blue",
    "auto_open_folder": True
}


def load_config() -> Dict[str, Any]:
    """Loads configuration with fallback to defaults."""
    cfg = DEFAULT_CONFIG.copy()
    if os.path.isfile(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    cfg.update(loaded)
        except Exception:
            pass
    return cfg


def save_config(cfg: Dict[str, Any]) -> None:
    """Saves configuration dict to JSON file."""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, indent=4, ensure_ascii=False)
    except Exception:
        pass
