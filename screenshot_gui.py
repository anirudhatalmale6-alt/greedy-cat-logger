"""Take a screenshot of the GUI with sample data for client preview."""

import sys
import os
import random
import time
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import FOOD_ITEMS
from logger import ResultLogger
from gui import StatsGUI


def generate_sample_data(logger, num_results=85):
    """Generate realistic sample results."""
    weights = {
        "tomato": 12, "corn": 10, "chicken": 2, "cow": 7,
        "carrot": 11, "fish": 4, "salad": 11, "pizza": 13,
        "shrimp": 6, "pepper": 10,
    }
    items = []
    for food, w in weights.items():
        items.extend([food] * w)

    for i in range(num_results):
        food = random.choice(items)
        logger.add_result(food, round_number=871900 + i,
                          confidence=random.uniform(0.78, 0.98))


def take_screenshot(root, delay=3):
    def do_it():
        time.sleep(delay)
        try:
            import mss
            sct = mss.mss()
            x = root.winfo_rootx()
            y = root.winfo_rooty()
            w = root.winfo_width()
            h = root.winfo_height()
            region = {"left": x, "top": y, "width": w, "height": h}
            screenshot = sct.grab(region)
            from PIL import Image
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
            out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gui_screenshot_v2.png")
            img.save(out)
            print(f"Screenshot saved: {out}")
            root.after(500, root.destroy)
        except Exception as e:
            print(f"Screenshot failed: {e}")
            try:
                import subprocess
                x = root.winfo_rootx()
                y = root.winfo_rooty()
                w = root.winfo_width()
                h = root.winfo_height()
                out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gui_screenshot_v2.png")
                subprocess.run(["import", "-window", "root", "-crop",
                                f"{w}x{h}+{x}+{y}", out], timeout=10)
                print(f"Screenshot saved (import): {out}")
            except Exception as e2:
                print(f"Fallback also failed: {e2}")
            root.after(500, root.destroy)

    threading.Thread(target=do_it, daemon=True).start()


def main():
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_output")
    os.makedirs(out_dir, exist_ok=True)

    # Clear
    for f in os.listdir(out_dir):
        os.remove(os.path.join(out_dir, f))

    logger = ResultLogger(output_dir=out_dir)
    generate_sample_data(logger, 85)
    logger.save_excel()

    gui = StatsGUI(logger)
    take_screenshot(gui.root, delay=2)
    gui.run()


if __name__ == "__main__":
    main()
