"""
Extract icon templates from a Greedy Cat game screenshot.
This script helps you create the template images needed for auto-detection.

Usage:
    python extract_templates.py screenshot.png

It will open the image and let you click on each icon to extract it.
Or you can provide pre-defined crop coordinates.
"""

import sys
import os
import cv2
import numpy as np
from config import FOOD_ITEMS, FOOD_DISPLAY

TEMPLATES_DIR = "templates"


def extract_from_wheel(image_path):
    """
    Extract individual food icons from the game wheel screenshot.
    Uses color-based and position-based detection.
    """
    img = cv2.imread(image_path)
    if img is None:
        print(f"Error: Cannot read image {image_path}")
        return

    h, w = img.shape[:2]
    print(f"Image size: {w}x{h}")

    os.makedirs(TEMPLATES_DIR, exist_ok=True)

    # The wheel icons are in circular positions around center
    # From the screenshot analysis, approximate icon positions on the wheel
    # These are rough estimates based on the screenshot - user should refine

    # Also extract from the Result row at the bottom
    # The Result row is at the very bottom of the screenshot
    result_row_y = int(h * 0.96)  # Bottom 4% of image
    result_row = img[result_row_y:, :]

    if result_row.size > 0:
        cv2.imwrite(os.path.join(TEMPLATES_DIR, "result_row_sample.png"), result_row)
        print(f"Saved result row sample: {result_row.shape}")

    print("\n" + "=" * 50)
    print("INTERACTIVE TEMPLATE EXTRACTION")
    print("=" * 50)
    print("\nInstructions:")
    print("1. A window will show the game screenshot")
    print("2. For each food item, click the TOP-LEFT corner of the icon")
    print("3. Then click the BOTTOM-RIGHT corner")
    print("4. The icon will be saved as a template")
    print("5. Press 'S' to skip an item, 'Q' to quit\n")

    # Resize for display if too large
    display_scale = 1.0
    max_display = 900
    if h > max_display:
        display_scale = max_display / h
        display_img = cv2.resize(img, None, fx=display_scale, fy=display_scale)
    else:
        display_img = img.copy()

    clicks = []

    def mouse_callback(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            clicks.append((int(x / display_scale), int(y / display_scale)))
            # Draw marker
            cv2.circle(display_img, (x, y), 5, (0, 255, 0), -1)
            cv2.imshow("Extract Templates", display_img)

    cv2.namedWindow("Extract Templates", cv2.WINDOW_AUTOSIZE)
    cv2.setMouseCallback("Extract Templates", mouse_callback)

    for food in FOOD_ITEMS:
        d = FOOD_DISPLAY[food]
        print(f"\n→ Click on {d['name']} ({d['emoji']}) — TOP-LEFT then BOTTOM-RIGHT")
        print("  Press 'S' to skip, 'Q' to quit")

        clicks.clear()
        cv2.imshow("Extract Templates", display_img)

        while len(clicks) < 2:
            key = cv2.waitKey(100)
            if key == ord('s') or key == ord('S'):
                print(f"  Skipped {d['name']}")
                break
            elif key == ord('q') or key == ord('Q'):
                print("Quitting...")
                cv2.destroyAllWindows()
                return

        if len(clicks) >= 2:
            x1, y1 = clicks[0]
            x2, y2 = clicks[1]
            x1, x2 = min(x1, x2), max(x1, x2)
            y1, y2 = min(y1, y2), max(y1, y2)

            icon = img[y1:y2, x1:x2]
            if icon.size > 0:
                save_path = os.path.join(TEMPLATES_DIR, f"{food}.png")
                cv2.imwrite(save_path, icon)
                print(f"  ✅ Saved {save_path} ({x2 - x1}x{y2 - y1})")
            else:
                print(f"  ❌ Invalid crop region")

    cv2.destroyAllWindows()
    print("\n✅ Template extraction complete!")
    print(f"Templates saved to: {os.path.abspath(TEMPLATES_DIR)}/")


def auto_extract_result_icons(image_path):
    """
    Automatically extract individual icons from the Result row
    using contour detection.
    """
    img = cv2.imread(image_path)
    if img is None:
        print(f"Error: Cannot read {image_path}")
        return

    h, w = img.shape[:2]

    # The Result row is at the very bottom
    # From the screenshot: "Result:" text + icons
    # Approximately bottom 5% of the image
    row_top = int(h * 0.955)
    result_row = img[row_top:, :]

    os.makedirs(os.path.join(TEMPLATES_DIR, "_extracted"), exist_ok=True)

    # Convert to HSV and find circular icons
    gray = cv2.cvtColor(result_row, cv2.COLOR_BGR2GRAY)
    circles = cv2.HoughCircles(
        gray, cv2.HOUGH_GRADIENT, dp=1, minDist=20,
        param1=50, param2=30, minRadius=10, maxRadius=30
    )

    if circles is not None:
        circles = np.uint16(np.around(circles))
        for i, (x, y, r) in enumerate(circles[0]):
            # Crop square around circle
            padding = 5
            x1 = max(0, x - r - padding)
            y1 = max(0, y - r - padding)
            x2 = min(result_row.shape[1], x + r + padding)
            y2 = min(result_row.shape[0], y + r + padding)

            icon = result_row[y1:y2, x1:x2]
            save_path = os.path.join(TEMPLATES_DIR, "_extracted", f"icon_{i:02d}.png")
            cv2.imwrite(save_path, icon)
            print(f"Extracted icon {i}: ({x}, {y}) r={r}")

        print(f"\n✅ Extracted {len(circles[0])} icons to {TEMPLATES_DIR}/_extracted/")
        print("Review these and rename them to the correct food names:")
        for food in FOOD_ITEMS:
            print(f"  → {food}.png")
    else:
        print("No circular icons detected. Try extract_from_wheel() instead.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python extract_templates.py <screenshot.png>")
        print("       python extract_templates.py <screenshot.png> --auto")
        sys.exit(1)

    image_path = sys.argv[1]

    if "--auto" in sys.argv:
        auto_extract_result_icons(image_path)
    else:
        extract_from_wheel(image_path)
