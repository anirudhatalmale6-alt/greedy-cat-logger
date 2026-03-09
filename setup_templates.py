"""
Quick Setup Script for Greedy Cat Result Logger
================================================
This script creates placeholder template images for initial setup.
Replace these with actual cropped icons from your game for best accuracy.

The tool can also work in MANUAL MODE without templates —
you just click the food icon buttons to log each result.
"""

import os
import cv2
import numpy as np
from config import FOOD_ITEMS, FOOD_DISPLAY

TEMPLATES_DIR = "templates"


def create_color_templates():
    """
    Create simple color-based template images.
    These are placeholders — replace with actual game icon crops for accuracy.
    """
    os.makedirs(TEMPLATES_DIR, exist_ok=True)

    # Color mapping (BGR format for OpenCV)
    color_map = {
        "tomato":  (71, 99, 255),    # Red
        "corn":    (0, 215, 255),     # Yellow
        "chicken": (0, 165, 255),     # Orange
        "cow":     (19, 69, 139),     # Brown
        "carrot":  (0, 140, 255),     # Dark orange
        "fish":    (225, 105, 65),    # Blue
        "salad":   (50, 205, 50),     # Green
        "pizza":   (0, 69, 255),      # Red-orange
        "shrimp":  (180, 105, 255),   # Pink
    }

    for food in FOOD_ITEMS:
        color = color_map.get(food, (128, 128, 128))

        # Create a 50x50 colored circle on dark background
        img = np.zeros((50, 50, 3), dtype=np.uint8)
        img[:] = (30, 30, 30)  # Dark background
        cv2.circle(img, (25, 25), 20, color, -1)
        cv2.circle(img, (25, 25), 20, (255, 255, 255), 1)

        save_path = os.path.join(TEMPLATES_DIR, f"{food}.png")
        cv2.imwrite(save_path, img)
        print(f"  Created: {save_path}")

    print(f"\n✅ Created {len(FOOD_ITEMS)} placeholder templates in {TEMPLATES_DIR}/")
    print("\n⚠️  IMPORTANT: For accurate detection, replace these with")
    print("   actual cropped icons from your game screenshot!")
    print("\n   Use: python extract_templates.py <your_screenshot.png>")
    print("   Or crop them manually from the game.")


if __name__ == "__main__":
    print("Setting up template images...")
    create_color_templates()
