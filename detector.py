"""
Icon detection engine for Greedy Cat Result Logger v9.

APPROACH: State-machine + multi-scale template matching + auto-save diagnostics.
- Extended scale range (0.2x-8.0x) for small popup icons
- Every scan is optionally saved with diagnostic info
- Learned references from manual adds supplement static templates
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

        # Learned references from manual adds (actual popup crops)
        self.references = {}  # {food_name: [gray_image, ...]}
        self.references_dir = os.path.join(
            os.path.dirname(os.path.abspath(self.templates_dir)), "learned_refs")

        # State machine
        self.popup_active = False
        self.last_detection_time = 0
        self.last_detected_food = None
        self.consecutive_no_match = 0

        # Config
        self.match_threshold = 0.35  # Lowered from 0.45 for better sensitivity
        self.no_match_reset_count = 2

        # Scale range — covers popup icons (26px+) to large ones (200px+)
        # Min 0.3x (87*0.3=26px): smaller scales cause false positives on backgrounds
        self.match_scales = [
            0.3, 0.35, 0.4, 0.45, 0.5, 0.6, 0.75,
            1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0
        ]

        # Diagnostics
        self.last_scan_info = ""
        self.last_best_food = None
        self.last_best_score = 0
        self.last_best_scale = 0
        self.total_scans = 0
        self.total_detections = 0

        # Auto-save ALL scans for diagnostics
        self.save_all_scans = False
        self.debug_dir = "debug_captures"
        self.debug_enabled = False
        self.scan_save_count = 0

        self.load_templates()
        self.load_references()

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

    def load_references(self):
        """Load learned reference crops from manual adds."""
        self.references = {}
        if not os.path.exists(self.references_dir):
            return

        for food in FOOD_ITEMS:
            food_dir = os.path.join(self.references_dir, food)
            if os.path.isdir(food_dir):
                refs = []
                for fname in sorted(os.listdir(food_dir)):
                    if fname.endswith(('.png', '.jpg')):
                        img = cv2.imread(os.path.join(food_dir, fname))
                        if img is not None:
                            refs.append(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
                if refs:
                    self.references[food] = refs

    def save_reference(self, food_name, crop_image):
        """Save a crop as a learned reference for a food item."""
        food_dir = os.path.join(self.references_dir, food_name)
        os.makedirs(food_dir, exist_ok=True)

        existing = len([f for f in os.listdir(food_dir) if f.endswith('.png')])
        fname = os.path.join(food_dir, f"ref_{existing + 1:03d}.png")
        cv2.imwrite(fname, crop_image)

        # Reload references
        gray = cv2.cvtColor(crop_image, cv2.COLOR_BGR2GRAY)
        if food_name not in self.references:
            self.references[food_name] = []
        self.references[food_name].append(gray)

        # Keep only last 5 per food
        if len(self.references[food_name]) > 5:
            self.references[food_name] = self.references[food_name][-5:]

        print(f"[LEARN] Saved reference for {food_name} ({existing + 1} total)")

    def identify_icon(self, crop_image):
        """
        Identify which food icon is in a cropped image.
        Uses multi-scale template matching against both static templates
        and learned references.

        Returns: (food_name, confidence) or (None, 0)
        """
        if crop_image is None or crop_image.size == 0:
            return None, 0

        if not self.gray_templates and not self.references:
            return None, 0

        gray = cv2.cvtColor(crop_image, cv2.COLOR_BGR2GRAY)
        ch, cw = gray.shape[:2]

        best_food = None
        best_score = 0
        best_scale = 0

        # Match against static templates
        for food, tmpl in self.gray_templates.items():
            th, tw = tmpl.shape[:2]

            for scale in self.match_scales:
                nh = int(th * scale)
                nw = int(tw * scale)

                if nh < 10 or nw < 10 or nh > ch - 2 or nw > cw - 2:
                    continue

                try:
                    scaled = cv2.resize(tmpl, (nw, nh))
                    result = cv2.matchTemplate(gray, scaled, cv2.TM_CCOEFF_NORMED)
                    _, max_val, _, _ = cv2.minMaxLoc(result)

                    if max_val > best_score:
                        best_score = max_val
                        best_food = food
                        best_scale = scale
                except Exception:
                    continue

        # Match against learned references (higher weight — these are real popup crops)
        for food, ref_list in self.references.items():
            for ref_gray in ref_list:
                rh, rw = ref_gray.shape[:2]

                # References are already at the right scale (same crop size)
                # Just do direct matching at scale 1.0 and nearby
                for scale in [0.7, 0.85, 1.0, 1.15, 1.3]:
                    nh = int(rh * scale)
                    nw = int(rw * scale)

                    if nh < 10 or nw < 10 or nh > ch - 2 or nw > cw - 2:
                        continue

                    try:
                        scaled = cv2.resize(ref_gray, (nw, nh))
                        result = cv2.matchTemplate(gray, scaled, cv2.TM_CCOEFF_NORMED)
                        _, max_val, _, _ = cv2.minMaxLoc(result)

                        # Give learned references a 10% boost
                        boosted = max_val * 1.1

                        if boosted > best_score:
                            best_score = boosted
                            best_food = food
                            best_scale = scale
                    except Exception:
                        continue

        # Store for diagnostics
        self.last_best_food = best_food
        self.last_best_score = best_score
        self.last_best_scale = best_scale

        if best_score >= self.match_threshold:
            return best_food, best_score
        return None, 0

    def scan_crop(self, crop_image):
        """
        Main detection method — state machine approach.
        Always tries to identify. Logs once per popup appearance.
        """
        if crop_image is None or crop_image.size == 0:
            self.last_scan_info = "Empty crop"
            return None, 0

        self.total_scans += 1

        # Always try to identify
        food, conf = self.identify_icon(crop_image)
        now = time.time()

        # Build diagnostic info
        best_info = (f"{self.last_best_food} {self.last_best_score:.0%} "
                     f"@{self.last_best_scale:.2f}x") if self.last_best_food else "no match"

        # Auto-save scan for diagnostics
        if self.save_all_scans or self.debug_enabled:
            self._save_scan(crop_image, food, conf)

        if food and conf >= self.match_threshold:
            self.consecutive_no_match = 0

            if not self.popup_active:
                # NEW popup detected
                self.popup_active = True
                self.last_detection_time = now
                self.last_detected_food = food
                self.total_detections += 1

                self.last_scan_info = f"DETECTED: {food} ({conf:.0%}) @{self.last_best_scale:.1f}x"
                print(f"[DETECT] Round: {food} (conf: {conf:.1%}, scale: {self.last_best_scale:.2f}x)")
                return food, conf
            else:
                self.last_scan_info = f"Active: {food} ({conf:.0%}) [skip]"
                return None, 0
        else:
            self.consecutive_no_match += 1

            if self.consecutive_no_match >= self.no_match_reset_count:
                if self.popup_active:
                    self.popup_active = False
                    self.last_scan_info = f"Popup gone ({best_info}), ready"
                    print(f"[STATE] Popup gone, ready for next")
                else:
                    self.last_scan_info = f"Waiting ({best_info})"
            else:
                self.last_scan_info = f"No match x{self.consecutive_no_match} ({best_info})"

            return None, 0

    def _save_scan(self, image, food, conf):
        """Save scan crop with diagnostic info in filename."""
        os.makedirs(self.debug_dir, exist_ok=True)
        self.scan_save_count += 1

        best = f"{self.last_best_food}_{self.last_best_score:.0%}" if self.last_best_food else "none_0%"
        state = "DET" if food else "wait"
        fname = os.path.join(
            self.debug_dir,
            f"scan_{self.scan_save_count:05d}_{state}_{best}.png")
        cv2.imwrite(fname, image)

        # Keep only last 100
        try:
            files = sorted(
                [os.path.join(self.debug_dir, f) for f in os.listdir(self.debug_dir)
                 if f.startswith('scan_') and f.endswith('.png')],
                key=os.path.getmtime)
            while len(files) > 100:
                os.remove(files.pop(0))
        except Exception:
            pass

    # Compatibility
    def find_best_match_in_region(self, image):
        food, conf = self.identify_icon(image)
        return food, conf, 0, 0

    def scan_full_window(self, current_frame):
        return self.scan_crop(current_frame)

    @property
    def is_ready(self):
        return len(self.templates) > 0

    @property
    def loaded_items(self):
        return list(self.templates.keys())
