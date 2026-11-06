# -*- coding: utf-8 -*-
"""
build_exe.py - Build standalone Windows executable using PyInstaller
"""
import os
import sys
import subprocess

def build():
    root = os.path.dirname(os.path.abspath(__file__))
    os.chdir(root)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconsole",
        "--onefile",
        "--name", "163MusicConverter",
        "--icon", "app_icon.ico",
        "--add-data", "app_icon.ico;.",
        "--add-data", "app_icon.png;.",
        "--add-data", "settings.json.example;.",
        "--collect-data", "customtkinter",
        "--collect-data", "tkinterdnd2",
        "--clean",
        "app.py"
    ]
    print("Executing PyInstaller build...")
    res = subprocess.run(cmd)
    if res.returncode == 0:
        print("\n[SUCCESS] Build completed! Output: dist\\163MusicConverter.exe")
    else:
        print(f"\n[FAILED] PyInstaller exited with code {res.returncode}")

if __name__ == "__main__":
    build()
