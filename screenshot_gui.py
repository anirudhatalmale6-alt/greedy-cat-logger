"""
Take a screenshot of the GUI for the client preview.
Uses Playwright to render the GUI as a web page screenshot alternative.
Actually just uses tkinter + PIL to capture the window.
"""

import sys
import os
import random
import time
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import FOOD_ITEMS
from logger import ResultLogger
from gui import StatsGUI


def generate_sample_data(logger, num_results=80):
    """Generate sample results."""
    weights = {
        "tomato": 15, "corn": 10, "chicken": 3, "cow": 8,
        "carrot": 12, "fish": 5, "salad": 12, "pizza": 15, "shrimp": 7,
    }
    items = []
    for food, weight in weights.items():
        items.extend([food] * weight)

    for i in range(num_results):
        food = random.choice(items)
        logger.add_result(food, round_number=871900 + i, confidence=random.uniform(0.8, 0.99))


def take_screenshot_after_delay(root, delay=3):
    """Take a screenshot of the tkinter window after a delay."""
    def do_screenshot():
        time.sleep(delay)
        try:
            import subprocess
            # Use xdotool and import to capture the window
            x = root.winfo_rootx()
            y = root.winfo_rooty()
            w = root.winfo_width()
            h = root.winfo_height()

            # Use import (ImageMagick) to capture the window
            output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gui_screenshot.png")
            subprocess.run([
                "import", "-window", "root",
                "-crop", f"{w}x{h}+{x}+{y}",
                output_path
            ], timeout=10)
            print(f"Screenshot saved to: {output_path}")

            # Close after screenshot
            root.after(1000, root.destroy)
        except Exception as e:
            print(f"Screenshot failed: {e}")
            # Try alternative method
            try:
                import mss
                sct = mss.mss()
                x = root.winfo_rootx()
                y = root.winfo_rooty()
                w = root.winfo_width()
                h = root.winfo_height()
                region = {"left": x, "top": y, "width": w, "height": h}
                screenshot = sct.grab(region)
                output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gui_screenshot.png")
                from PIL import Image
                img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
                img.save(output_path)
                print(f"Screenshot saved (mss): {output_path}")
                root.after(1000, root.destroy)
            except Exception as e2:
                print(f"Alternative screenshot also failed: {e2}")
                root.after(1000, root.destroy)

    thread = threading.Thread(target=do_screenshot, daemon=True)
    thread.start()


def main():
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_output")
    os.makedirs(output_dir, exist_ok=True)

    # Clear existing test data
    for f in os.listdir(output_dir):
        os.remove(os.path.join(output_dir, f))

    logger = ResultLogger(output_dir=output_dir)
    generate_sample_data(logger, 80)
    logger.save_excel()

    gui = StatsGUI(logger)

    # Take screenshot after GUI renders
    take_screenshot_after_delay(gui.root, delay=2)

    gui.run()


if __name__ == "__main__":
    main()
