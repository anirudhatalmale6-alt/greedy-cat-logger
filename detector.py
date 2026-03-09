"""
Icon detection engine for Greedy Cat Result Logger v7.

APPROACH: One-click calibration + focused template matching.
1. User calibrates once by clicking on the food icon center in a popup
2. Program captures a small region (~150x150px) around that point
3. Template matching on this clean, focused crop reliably identifies the food
4. Frame differencing detects when the popup changes (new round result)

This is robust because:
- Small focused crop contains mostly the food icon (minimal confetti noise)
- Template matching works well on clean, centered icon images
- Frame differencing catches every popup change
- 5-second cooldown prevents double-logging
"""

import os
import time
import cv2
import numpy as np
from config import FOOD_ITEMS, TEMPLATES_DIR


class IconDetector:
    """Detects food icons using focused template matching on a calibrated crop."""

    def __init__(self, templates_dir=None):
        self.templates_dir = templates_dir or TEMPLATES_DIR
        self.templates = {}       # {food_name: BGR image}
        self.gray_templates = {}  # {food_name: grayscale image}

        self.previous_crop = None
        self.last_detection_time = 0
        self.cooldown_seconds = 5
        self.match_threshold = 0.40

        self.debug_enabled = False
        self.debug_dir = "debug_captures"
        self.debug_count = 0

        self.load_templates()

    def load_templates(self):
        """Load template images from the templates directory."""
        self.templates = {}
        self.gray_templates = {}

        if not os.path.exists(self.templates_dir):
            os.makedirs(self.templates_dir, exist_ok=True)
            return

        for food in FOOD_ITEMS:
            for ext in ('.png', '.jpg', '.jpeg', '.bmp'):
                path = os.path.join(self.templates_dir, food + ext)
                if os.path.exists(path):
                    img = cv2.imread(path)
                    if img is not None:
                        self.templates[food] = img
                        self.gray_templates[food] = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                    break

            # Also check subdirectory
            food_dir = os.path.join(self.templates_dir, food)
            if os.path.isdir(food_dir) and food not in self.templates:
                for fname in sorted(os.listdir(food_dir)):
                    if fname.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
                        img = cv2.imread(os.path.join(food_dir, fname))
                        if img is not None:
                            self.templates[food] = img
                            self.gray_templates[food] = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                        break

    def identify_icon(self, crop_image):
        """
        Identify which food icon is in a cropped image using multi-scale
        template matching on grayscale images.

        Returns: (food_name, confidence) or (None, 0)
        """
        if crop_image is None or crop_image.size == 0 or not self.gray_templates:
            return None, 0

        gray = cv2.cvtColor(crop_image, cv2.COLOR_BGR2GRAY)
        ch, cw = gray.shape[:2]

        best_food = None
        best_score = 0

        for food, tmpl in self.gray_templates.items():
            th, tw = tmpl.shape[:2]

            # Try multiple scales — the template might be smaller or larger
            # than the icon as it appears in the game popup
            for scale in [0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0]:
                nh = int(th * scale)
                nw = int(tw * scale)

                if nh < 12 or nw < 12 or nh > ch - 2 or nw > cw - 2:
                    continue

                try:
                    scaled = cv2.resize(tmpl, (nw, nh))
                    result = cv2.matchTemplate(gray, scaled, cv2.TM_CCOEFF_NORMED)
                    _, max_val, _, _ = cv2.minMaxLoc(result)

                    if max_val > best_score:
                        best_score = max_val
                        best_food = food
                except Exception:
                    continue

        if best_score >= self.match_threshold:
            return best_food, best_score
        return None, 0

    def has_changed(self, current_crop):
        """
        Check if the captured crop has changed significantly from previous.
        Always updates the stored previous frame.

        Returns True if a popup change was detected.
        """
        if current_crop is None:
            return False

        if self.previous_crop is None:
            self.previous_crop = current_crop.copy()
            return False

        try:
            size = (64, 64)
            prev = cv2.cvtColor(cv2.resize(self.previous_crop, size), cv2.COLOR_BGR2GRAY)
            curr = cv2.cvtColor(cv2.resize(current_crop, size), cv2.COLOR_BGR2GRAY)

            diff = np.mean(cv2.absdiff(prev, curr))
            self.previous_crop = current_crop.copy()

            return diff > 12
        except Exception:
            self.previous_crop = current_crop.copy()
            return False

    def scan_crop(self, crop_image):
        """
        Main detection method for the monitoring loop.

        1. Check if the crop changed (popup appeared/changed)
        2. If yes, try to identify the food icon
        3. Cooldown prevents double-logging the same popup

        Returns: (food_name, confidence) or (None, 0)
        """
        if crop_image is None or crop_image.size == 0:
            return None, 0

        now = time.time()

        # During cooldown, just update the previous frame and skip
        if now - self.last_detection_time < self.cooldown_seconds:
            self.previous_crop = crop_image.copy()
            return None, 0

        # Check if frame changed significantly
        if not self.has_changed(crop_image):
            return None, 0

        # Frame changed — try to identify the food icon
        food, conf = self.identify_icon(crop_image)

        if food:
            self.last_detection_time = now
            if self.debug_enabled:
                self._save_debug(crop_image, food, conf)
            return food, conf

        return None, 0

    # ---- Compatibility wrappers (used by GUI test capture etc.) ----

    def find_best_match_in_region(self, image):
        """Compatibility: find food icon in a captured region."""
        food, conf = self.identify_icon(image)
        return food, conf, 0, 0

    def scan_full_window(self, current_frame):
        """Compatibility: redirects to scan_crop."""
        return self.scan_crop(current_frame)

    def detect_popup_icon(self, popup_image):
        return self.identify_icon(popup_image)

    def detect_single_icon(self, icon_image):
        return self.identify_icon(icon_image)

    # ---- Debug ----

    def _save_debug(self, image, food, conf):
        """Save debug capture for troubleshooting."""
        os.makedirs(self.debug_dir, exist_ok=True)
        self.debug_count += 1
        fname = os.path.join(self.debug_dir,
                             f"detect_{self.debug_count:04d}_{food}_{conf:.0%}.png")
        cv2.imwrite(fname, image)
        # Keep only last 30
        files = sorted(
            [os.path.join(self.debug_dir, f) for f in os.listdir(self.debug_dir)
             if f.endswith('.png')],
            key=os.path.getmtime
        )
        while len(files) > 30:
            os.remove(files.pop(0))

    # ---- Properties ----

    @property
    def is_ready(self):
        return len(self.templates) > 0

    @property
    def loaded_items(self):
        return list(self.templates.keys())
