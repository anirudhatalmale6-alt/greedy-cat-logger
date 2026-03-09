"""
Icon detection engine for Greedy Cat Result Logger v8.

APPROACH: State-machine + focused template matching (no frame-diff gate).
Every scan: try to identify the food icon in the crop.
- If food detected and popup wasn't active → LOG (new popup)
- If food detected and popup already active → skip (same popup)
- If no food detected for 2+ scans → popup gone, ready for next

v8 fixes: Removed has_changed() gate that was blocking detection.
Added diagnostic logging for remote debugging.
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

        # State machine
        self.popup_active = False
        self.last_detection_time = 0
        self.last_detected_food = None
        self.consecutive_no_match = 0

        # Config
        self.match_threshold = 0.45
        self.no_match_reset_count = 2  # Scans without match before resetting

        # Diagnostics
        self.last_scan_info = ""
        self.last_best_food = None
        self.last_best_score = 0
        self.total_scans = 0
        self.total_detections = 0

        # Debug capture saving
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

    def identify_icon(self, crop_image):
        """
        Identify which food icon is in a cropped image using multi-scale
        template matching.

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

            for scale in [0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0]:
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

        # Store for diagnostics
        self.last_best_food = best_food
        self.last_best_score = best_score

        if best_score >= self.match_threshold:
            return best_food, best_score
        return None, 0

    def scan_crop(self, crop_image):
        """
        Main detection method — state machine approach.

        Every scan: try to identify the food icon.
        - Food found + popup not active → NEW POPUP → log it
        - Food found + popup already active → same popup → skip
        - No food for 2+ scans → popup gone → reset state

        Returns: (food_name, confidence) or (None, 0)
        """
        if crop_image is None or crop_image.size == 0:
            self.last_scan_info = "Empty crop"
            return None, 0

        self.total_scans += 1

        # Always try to identify
        food, conf = self.identify_icon(crop_image)
        now = time.time()

        if food and conf >= self.match_threshold:
            self.consecutive_no_match = 0

            if not self.popup_active:
                # NEW popup detected! Log it
                self.popup_active = True
                self.last_detection_time = now
                self.last_detected_food = food
                self.total_detections += 1

                self.last_scan_info = f"NEW: {food} ({conf:.0%})"
                print(f"[DETECT] Round detected: {food} (confidence: {conf:.1%})")

                if self.debug_enabled:
                    self._save_debug(crop_image, food, conf)

                return food, conf
            else:
                # Popup already active — same popup, don't log again
                self.last_scan_info = f"Active: {food} ({conf:.0%}) [skip]"
                return None, 0
        else:
            # No food detected above threshold
            self.consecutive_no_match += 1
            best_info = f"best: {self.last_best_food} {self.last_best_score:.0%}" if self.last_best_food else "no match"

            if self.consecutive_no_match >= self.no_match_reset_count:
                if self.popup_active:
                    # Popup has disappeared — reset state
                    self.popup_active = False
                    self.last_scan_info = f"Popup gone ({best_info}), ready"
                    print(f"[STATE] Popup gone, ready for next detection")
                else:
                    self.last_scan_info = f"Waiting ({best_info})"
            else:
                self.last_scan_info = f"No match x{self.consecutive_no_match} ({best_info})"

            return None, 0

    # ---- Compatibility wrappers ----

    def find_best_match_in_region(self, image):
        food, conf = self.identify_icon(image)
        return food, conf, 0, 0

    def scan_full_window(self, current_frame):
        return self.scan_crop(current_frame)

    # ---- Debug ----

    def _save_debug(self, image, food, conf):
        """Save debug capture for troubleshooting."""
        os.makedirs(self.debug_dir, exist_ok=True)
        self.debug_count += 1
        fname = os.path.join(self.debug_dir,
                             f"detect_{self.debug_count:04d}_{food}_{conf:.0%}.png")
        cv2.imwrite(fname, image)
        # Keep only last 50
        files = sorted(
            [os.path.join(self.debug_dir, f) for f in os.listdir(self.debug_dir)
             if f.endswith('.png')],
            key=os.path.getmtime
        )
        while len(files) > 50:
            os.remove(files.pop(0))

    # ---- Properties ----

    @property
    def is_ready(self):
        return len(self.templates) > 0

    @property
    def loaded_items(self):
        return list(self.templates.keys())
