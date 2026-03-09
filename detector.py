"""
Icon detection engine for Greedy Cat Result Logger v14.

APPROACH: Stability-based detection to prevent false triggers during wheel spin.

v14 — CRITICAL FIX: Spinning wheel false detection
The wheel shows food icons rotating rapidly. The detector was matching these
spinning icons and logging them as results. The fix uses TWO stability checks:

1. CONSECUTIVE MATCH: The same food must be detected in 3+ consecutive scans
   before it's logged. During spinning, different foods appear each scan.
   During the popup, the same food stays stable for many seconds.

2. IMAGE STABILITY: The captured crop must be visually stable (low pixel
   difference between consecutive frames). During spinning, pixels change
   dramatically. During the popup, the image barely changes.

Both conditions must be met before a result is logged.
"""

import os
import time
import cv2
import numpy as np
from config import FOOD_ITEMS, TEMPLATES_DIR


class IconDetector:
    """Detects food icons using stability-verified template matching."""

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
        self.match_threshold = 0.38  # Template matching threshold
        self.no_match_reset_count = 1  # Scans with no match to reset popup state
        self.popup_timeout = 10.0  # Seconds before popup_active auto-resets

        # STABILITY CONFIG (v14) — prevents detecting spinning wheel
        self.required_consecutive = 3  # Same food must match N times in a row
        self.image_stability_threshold = 8.0  # Max mean pixel diff for "stable"
        self.required_stable_frames = 2  # Image must be stable for N frames

        # Stability tracking
        self.consecutive_food = None  # Current food being tracked
        self.consecutive_count = 0  # How many times in a row
        self.prev_gray_crop = None  # Previous frame for stability check
        self.stable_frame_count = 0  # How many frames the image has been stable

        # Scale range
        self.match_scales = [
            0.3, 0.4, 0.5, 0.6, 0.75,
            1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0
        ]

        # Diagnostics
        self.last_scan_info = ""
        self.last_best_food = None
        self.last_best_score = 0
        self.last_best_scale = 0
        self.last_runner_up_food = None
        self.last_runner_up_score = 0
        self.last_image_diff = 0  # Pixel difference from previous frame
        self.total_scans = 0
        self.total_detections = 0

        # Auto-save scans for diagnostics
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

        gray = cv2.cvtColor(crop_image, cv2.COLOR_BGR2GRAY)
        if food_name not in self.references:
            self.references[food_name] = []
        self.references[food_name].append(gray)

        if len(self.references[food_name]) > 5:
            self.references[food_name] = self.references[food_name][-5:]

        print(f"[LEARN] Saved reference for {food_name} ({existing + 1} total)")

    def _check_image_stability(self, gray_crop):
        """
        Compare current frame with previous frame.
        Returns (is_stable, mean_diff).
        """
        if self.prev_gray_crop is None:
            self.prev_gray_crop = gray_crop.copy()
            self.stable_frame_count = 0
            return False, 0.0

        # Ensure same shape
        if self.prev_gray_crop.shape != gray_crop.shape:
            self.prev_gray_crop = gray_crop.copy()
            self.stable_frame_count = 0
            return False, 0.0

        # Calculate mean absolute pixel difference
        diff = cv2.absdiff(gray_crop, self.prev_gray_crop)
        mean_diff = float(np.mean(diff))

        self.last_image_diff = mean_diff
        self.prev_gray_crop = gray_crop.copy()

        if mean_diff <= self.image_stability_threshold:
            self.stable_frame_count += 1
        else:
            self.stable_frame_count = 0

        is_stable = self.stable_frame_count >= self.required_stable_frames
        return is_stable, mean_diff

    def identify_icon(self, crop_image):
        """
        Identify which food icon is in a cropped image.
        Returns: (food_name, confidence) or (None, 0)
        """
        if crop_image is None or crop_image.size == 0:
            return None, 0

        if not self.gray_templates and not self.references:
            return None, 0

        gray = cv2.cvtColor(crop_image, cv2.COLOR_BGR2GRAY)
        ch, cw = gray.shape[:2]

        food_scores = {}

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

                    if food not in food_scores or max_val > food_scores[food][0]:
                        food_scores[food] = (max_val, scale)
                except Exception:
                    continue

        # Match against learned references
        for food, ref_list in self.references.items():
            for ref_gray in ref_list:
                rh, rw = ref_gray.shape[:2]

                for scale in [0.7, 0.85, 1.0, 1.15, 1.3]:
                    nh = int(rh * scale)
                    nw = int(rw * scale)

                    if nh < 10 or nw < 10 or nh > ch - 2 or nw > cw - 2:
                        continue

                    try:
                        scaled = cv2.resize(ref_gray, (nw, nh))
                        result = cv2.matchTemplate(gray, scaled, cv2.TM_CCOEFF_NORMED)
                        _, max_val, _, _ = cv2.minMaxLoc(result)

                        boosted = max_val * 1.1
                        if food not in food_scores or boosted > food_scores[food][0]:
                            food_scores[food] = (boosted, scale)
                    except Exception:
                        continue

        if not food_scores:
            self.last_best_food = None
            self.last_best_score = 0
            self.last_best_scale = 0
            self.last_runner_up_food = None
            self.last_runner_up_score = 0
            return None, 0

        sorted_foods = sorted(food_scores.items(), key=lambda x: -x[1][0])

        best_food = sorted_foods[0][0]
        best_score = sorted_foods[0][1][0]
        best_scale = sorted_foods[0][1][1]

        runner_up_food = None
        runner_up_score = 0
        if len(sorted_foods) > 1:
            runner_up_food = sorted_foods[1][0]
            runner_up_score = sorted_foods[1][1][0]

        self.last_best_food = best_food
        self.last_best_score = best_score
        self.last_best_scale = best_scale
        self.last_runner_up_food = runner_up_food
        self.last_runner_up_score = runner_up_score

        if best_score >= self.match_threshold:
            return best_food, best_score
        return None, 0

    def scan_crop(self, crop_image):
        """
        Main detection method — stability-verified state machine.

        v14: Two stability checks prevent spinning wheel false detection:
        1. Same food must match 3+ consecutive scans
        2. Image pixels must be stable (low diff) for 2+ frames

        Only when BOTH conditions are met is a result logged.
        """
        if crop_image is None or crop_image.size == 0:
            self.last_scan_info = "Empty crop"
            return None, 0

        self.total_scans += 1
        now = time.time()

        # Check image stability FIRST (before template matching)
        gray_crop = cv2.cvtColor(crop_image, cv2.COLOR_BGR2GRAY)
        is_stable, pixel_diff = self._check_image_stability(gray_crop)

        # Try to identify food
        food, conf = self.identify_icon(crop_image)

        # Build diagnostic info
        stability_str = f"stable={self.stable_frame_count}" if is_stable else f"MOVING(diff={pixel_diff:.1f})"
        if self.last_best_food:
            best_info = (f"{self.last_best_food} {self.last_best_score:.0%} "
                         f"@{self.last_best_scale:.2f}x")
        else:
            best_info = "no match"

        # Auto-save scan for diagnostics
        if self.save_all_scans or self.debug_enabled:
            self._save_scan(crop_image, food, conf)

        # Time-based popup reset
        if self.popup_active and (now - self.last_detection_time) > self.popup_timeout:
            self.popup_active = False
            self.consecutive_food = None
            self.consecutive_count = 0
            print(f"[STATE] Popup timeout ({self.popup_timeout}s), auto-reset")

        if food and conf >= self.match_threshold:
            # Update consecutive tracking
            if food == self.consecutive_food:
                self.consecutive_count += 1
            else:
                self.consecutive_food = food
                self.consecutive_count = 1

            consec_str = f"x{self.consecutive_count}/{self.required_consecutive}"

            # Check if we meet BOTH stability requirements
            food_stable = self.consecutive_count >= self.required_consecutive
            image_stable = is_stable

            if not self.popup_active:
                if food_stable and image_stable:
                    # CONFIRMED popup — both checks passed!
                    self.popup_active = True
                    self.last_detection_time = now
                    self.last_detected_food = food
                    self.total_detections += 1
                    self.consecutive_no_match = 0

                    self.last_scan_info = (
                        f"CONFIRMED: {food} ({conf:.0%}) "
                        f"[{consec_str}, {stability_str}]")
                    print(f"[DETECT] Confirmed: {food} (conf: {conf:.1%}, "
                          f"consecutive: {self.consecutive_count}, "
                          f"pixel_diff: {pixel_diff:.1f})")
                    return food, conf

                elif food_stable and not image_stable:
                    # Food matches but image still changing — spinning wheel
                    self.last_scan_info = (
                        f"WAIT-UNSTABLE: {food} ({conf:.0%}) "
                        f"[{consec_str}, diff={pixel_diff:.1f} > {self.image_stability_threshold}]")
                    self.consecutive_no_match = 0
                    return None, 0

                else:
                    # Building up consecutive count
                    self.last_scan_info = (
                        f"Building: {food} ({conf:.0%}) "
                        f"[{consec_str}, {stability_str}]")
                    self.consecutive_no_match = 0
                    return None, 0

            elif food != self.last_detected_food:
                # Different food while popup active — new round?
                if food_stable and image_stable:
                    self.last_detection_time = now
                    self.last_detected_food = food
                    self.total_detections += 1

                    self.last_scan_info = (
                        f"NEW FOOD: {food} ({conf:.0%}) "
                        f"[was {self.last_detected_food}]")
                    print(f"[DETECT] New food: {food} (was {self.last_detected_food})")
                    return food, conf
                else:
                    self.last_scan_info = (
                        f"New? {food} ({conf:.0%}) "
                        f"[{consec_str}, {stability_str}] not stable yet")
                    return None, 0
            else:
                # Same food still showing
                elapsed = now - self.last_detection_time
                self.last_scan_info = (
                    f"Active: {food} ({conf:.0%}) "
                    f"[{elapsed:.0f}s] skip")
                self.consecutive_no_match = 0
                return None, 0
        else:
            # No match above threshold
            self.consecutive_no_match += 1
            # Reset consecutive tracking when no food matches
            self.consecutive_food = None
            self.consecutive_count = 0

            if self.consecutive_no_match >= self.no_match_reset_count:
                if self.popup_active:
                    self.popup_active = False
                    self.last_scan_info = f"Popup gone ({best_info}), ready [{stability_str}]"
                    print(f"[STATE] Popup gone, ready for next")
                else:
                    self.last_scan_info = f"Waiting ({best_info}) [{stability_str}]"
            else:
                self.last_scan_info = (
                    f"No match x{self.consecutive_no_match} "
                    f"({best_info}) [{stability_str}]")

            return None, 0

    def _save_scan(self, image, food, conf):
        """Save scan crop with diagnostic info in filename."""
        os.makedirs(self.debug_dir, exist_ok=True)
        self.scan_save_count += 1

        best = f"{self.last_best_food}_{self.last_best_score:.0%}" if self.last_best_food else "none_0%"
        stable = f"S{self.stable_frame_count}" if self.stable_frame_count > 0 else f"M{self.last_image_diff:.0f}"
        state = "DET" if food else "wait"
        fname = os.path.join(
            self.debug_dir,
            f"scan_{self.scan_save_count:05d}_{state}_{best}_{stable}.png")
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
