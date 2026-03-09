"""
Build Windows EXE using PyInstaller.
Run this on Windows: python build_exe.py
"""

import os
import sys
import subprocess


def build():
    # Check PyInstaller
    try:
        import PyInstaller
    except ImportError:
        print("Installing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    # Build command
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        "--name", "GreedyCatLogger",
        "--add-data", f"templates{os.pathsep}templates",
        "--hidden-import", "PIL._tkinter_finder",
        "--hidden-import", "mss",
        "--hidden-import", "mss.windows",
        "--icon", "NONE",
        "main.py",
    ]

    print("Building EXE...")
    print(" ".join(cmd))
    subprocess.check_call(cmd)

    print("\n" + "=" * 50)
    print("BUILD COMPLETE!")
    print(f"EXE file: dist/GreedyCatLogger.exe")
    print("=" * 50)


if __name__ == "__main__":
    build()
