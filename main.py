"""
Greedy Cat Result Logger
========================
Monitors the Greedy Cat game on Android emulator (LDPlayer/BlueStacks)
and records results with statistics.

Usage:
    python main.py              # Launch GUI with auto-detection
    python main.py --manual     # Launch GUI in manual-only mode
    python main.py --calibrate  # Run calibration wizard

Requirements:
    pip install opencv-python-headless numpy Pillow mss pyautogui openpyxl
"""

import sys
import os
import argparse

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from logger import ResultLogger
from detector import IconDetector
from capture import ScreenCapture
from gui import StatsGUI


def main():
    parser = argparse.ArgumentParser(description="Greedy Cat Result Logger")
    parser.add_argument("--manual", action="store_true", help="Manual mode only (no screen detection)")
    parser.add_argument("--output", default=".", help="Output directory for result files")
    parser.add_argument("--templates", default="templates", help="Path to template images directory")
    args = parser.parse_args()

    print("=" * 50)
    print("  🐱 Greedy Cat Result Logger")
    print("=" * 50)

    # Initialize components
    output_dir = os.path.abspath(args.output)
    os.makedirs(output_dir, exist_ok=True)

    logger = ResultLogger(output_dir=output_dir)
    print(f"📁 Output directory: {output_dir}")
    print(f"📊 Loaded {logger.total_rounds} existing results")

    detector = None
    capturer = None

    if not args.manual:
        templates_dir = os.path.abspath(args.templates)
        detector = IconDetector(templates_dir=templates_dir)
        capturer = ScreenCapture()

        if detector.is_ready:
            print(f"✅ Templates loaded: {', '.join(detector.loaded_items)}")
        else:
            print(f"⚠️  No templates found in: {templates_dir}")
            print("   You can still use Manual mode to add results.")
            print("   To enable auto-detection, add icon images to templates/")

    print("\n🚀 Launching GUI...")

    gui = StatsGUI(logger, detector=detector, capturer=capturer)
    gui.run()


if __name__ == "__main__":
    main()
