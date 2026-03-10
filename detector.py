"""
Icon detection engine for Greedy Cat Result Logger v16.

v16 — COLOR-BASED IDENTIFICATION (fixes misclassification)

ROOT CAUSE of v14/v15 bugs: Template matching was done on GRAYSCALE images,
so all color information was lost. At small scales (0.3x = 26px), all food
icons look structurally similar in grayscale, and corn's pattern happened
to win by default. Tomato (red) was detected as Corn (yellow) because the
detector literally couldn't see color.

FIX: HSV color histogram matching for food IDENTIFICATION.
- Template matching = "is there a food icon present?" (gatekeeper)
- Color histogram = "WHICH food is it?" (identifier)

This also fixes the HOT label issue: HOT badges overlay a small portion
of the icon, but the dominant color distribution remains recognizable.
Red tomato stays mostly red even with a HOT badge.

Stability checks from v14 are preserved (consecutive match + image stability).
"""

import os
import time
import cv2
import numpy as np
from config import FOOD_ITEMS, TEMPLATES_DIR


class IconDetector:
    """Detects food icons using color histogram identification."""

    def __init__(self, templates_dir=None):
        self.templates_dir = templates_dir or TEMPLATES_DIR
        self.templates = {}       # {food_name: BGR image}
        self.gray_templates = {}  # {food_name: grayscale image}
        self.color_profiles = {}  # {food_name: normalized HS histogram}

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
        self.match_threshold = 0.35  # Template matching threshold (gatekeeper only)
        self.color_threshold = 0.15  # Min color histogram correlation
        self.no_match_reset_count = 1
        self.popup_timeout = 10.0

        # STABILITY CONFIG (v14)
        self.required_consecutive = 3
        self.image_stability_threshold = 8.0
        self.required_stable_frames = 2

        # Stability tracking
        self.consecutive_food = None
        self.consecutive_count = 0
        self.prev_gray_crop = None
        self.stable_frame_count = 0

        # Scale range for template matching (gatekeeper)
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
        self.last_color_food = None
        self.last_color_score = 0
        self.last_color_runner_up = None
        self.last_color_runner_score = 0
        self.last_image_diff = 0
        self.total_scans = 0
        self.total_detections = 0

        # Auto-save scans for diagnostics
        self.save_all_scans = False
        self.debug_dir = "debug_captures"
        self.debug_enabled = False
        self.scan_save_count = 0

        self.load_templates()
        self.load_references()
        self._build_color_profiles()

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

    def _build_color_profiles(self):
        """
        Build 2D Hue-Saturation color profiles for each food template.

        Uses alpha channel (if present) to mask out transparent background.
        Only includes pixels with meaningful color (S > 30, V > 30).
        These profiles are compared against popup crops to identify food.
        """
        self.color_profiles = {}

        for food in FOOD_ITEMS:
            for ext in ('.png', '.jpg', '.jpeg', '.bmp'):
                path = os.path.join(self.templates_dir, food + ext)
                if not os.path.exists(path):
                    continue

                # Load WITH alpha channel for proper transparency masking
                img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
                if img is None:
                    continue

                if img.shape[2] == 4:
                    # Use alpha channel as mask
                    alpha = img[:, :, 3]
                    bgr = img[:, :, :3]
                    mask = np.zeros(alpha.shape, np.uint8)
                    mask[alpha > 128] = 255
                else:
                    bgr = img
                    mask = np.ones(img.shape[:2], np.uint8) * 255

                hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)

                # Exclude low-saturation (grays) and very dark pixels
                mask[hsv[:, :, 1] < 30] = 0
                mask[hsv[:, :, 2] < 30] = 0

                # 2D Hue-Saturation histogram (30 hue bins x 16 sat bins)
                hist = cv2.calcHist([hsv], [0, 1], mask,
                                    [30, 16], [0, 180, 0, 256])
                cv2.normalize(hist, hist, 0, 1, cv2.NORM_MINMAX)
                self.color_profiles[food] = hist
                break

        print(f"[COLOR] Built color profiles for {len(self.color_profiles)} foods: "
              f"{list(self.color_profiles.keys())}")

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

        if self.prev_gray_crop.shape != gray_crop.shape:
            self.prev_gray_crop = gray_crop.copy()
            self.stable_frame_count = 0
            return False, 0.0

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

    def _identify_by_color(self, crop_bgr):
        """
        Identify food by HSV color histogram comparison.

        Extracts the CENTER region of the crop (where the food icon is),
        builds a 2D Hue-Saturation histogram, and compares against all
        food color profiles.

        Returns: (food_name, correlation_score) or (None, 0)
        """
        if not self.color_profiles:
            return None, 0

        h, w = crop_bgr.shape[:2]

        # Extract center 60% of crop (food icon area)
        # The outer 20% on each side is popup background/border
        cs = int(min(h, w) * 0.3)
        ch, cw = h // 2, w // 2
        center = crop_bgr[max(0, ch - cs):ch + cs, max(0, cw - cs):cw + cs]

        if center.size == 0 or center.shape[0] < 10 or center.shape[1] < 10:
            return None, 0

        hsv = cv2.cvtColor(center, cv2.COLOR_BGR2HSV)

        # Mask: exclude dark pixels (background) and desaturated (text/UI)
        mask = np.ones(hsv.shape[:2], np.uint8) * 255
        mask[hsv[:, :, 1] < 30] = 0
        mask[hsv[:, :, 2] < 30] = 0

        # Check we have enough colored pixels
        colored_pixels = np.sum(mask > 0)
        if colored_pixels < 50:
            return None, 0

        # Build 2D HS histogram matching the profile format
        hist = cv2.calcHist([hsv], [0, 1], mask,
                            [30, 16], [0, 180, 0, 256])
        cv2.normalize(hist, hist, 0, 1, cv2.NORM_MINMAX)

        # Compare with each food's color profile
        scores = {}
        for food, profile in self.color_profiles.items():
            corr = cv2.compareHist(hist, profile, cv2.HISTCMP_CORREL)
            scores[food] = corr

        if not scores:
            return None, 0

        sorted_scores = sorted(scores.items(), key=lambda x: -x[1])
        best_food = sorted_scores[0][0]
        best_score = sorted_scores[0][1]

        # Update diagnostics
        self.last_color_food = best_food
        self.last_color_score = best_score
        if len(sorted_scores) > 1:
            self.last_color_runner_up = sorted_scores[1][0]
            self.last_color_runner_score = sorted_scores[1][1]
        else:
            self.last_color_runner_up = None
            self.last_color_runner_score = 0

        return best_food, best_score

    def _template_gate(self, crop_image):
        """
        Template matching as GATEKEEPER only — detects if any food icon is present.
        Does NOT determine which food (color does that).

        Returns: (best_food, best_score, best_scale) or (None, 0, 0)
        """
        if crop_image is None or crop_image.size == 0:
            return None, 0, 0

        if not self.gray_templates and not self.references:
            return None, 0, 0

        gray = cv2.cvtColor(crop_image, cv2.COLOR_BGR2GRAY)
        ch, cw = gray.shape[:2]

        best_score = 0
        best_food = None
        best_scale = 0

        # Match against all templates — find highest score regardless of food
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

        # Also check learned references
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
                        if boosted > best_score:
                            best_score = boosted
                            best_food = food
                            best_scale = scale
                    except Exception:
                        continue

        # Update diagnostics (template match info)
        self.last_best_food = best_food
        self.last_best_score = best_score
        self.last_best_scale = best_scale

        if best_score >= self.match_threshold:
            return best_food, best_score, best_scale
        return None, 0, 0

    def identify_icon(self, crop_image):
        """
        v16: Combined template + color identification.

        1. Template matching confirms a food icon is present (gatekeeper).
        2. Color histogram determines WHICH food it is (identifier).

        Template matching is grayscale-only and unreliable for food ID
        at small scales. Color histograms are scale-invariant and robust
        to HOT labels.
        """
        if crop_image is None or crop_image.size == 0:
            return None, 0

        # Step 1: Template matching — "is there any food icon?"
        tmpl_food, tmpl_score, tmpl_scale = self._template_gate(crop_image)

        if tmpl_food is None:
            # No food icon detected by template matching
            self.last_runner_up_food = None
            self.last_runner_up_score = 0
            return None, 0

        # Step 2: Color histogram — "WHICH food is it?"
        color_food, color_score = self._identify_by_color(crop_image)

        if color_food and color_score >= self.color_threshold:
            # Color match found — use color result with template confidence
            self.last_runner_up_food = self.last_color_runner_up
            self.last_runner_up_score = self.last_color_runner_score
            return color_food, tmpl_score

        # Color matching failed — fall back to template result
        # (This shouldn't happen often since color profiles cover all foods)
        self.last_runner_up_food = None
        self.last_runner_up_score = 0
        return tmpl_food, tmpl_score

    def scan_crop(self, crop_image):
        """
        Main detection method — stability-verified state machine.

        v14: Two stability checks prevent spinning wheel false detection:
        1. Same food must match 3+ consecutive scans
        2. Image pixels must be stable (low diff) for 2+ frames

        v16: Food identification now uses color histograms instead of
        unreliable grayscale template matching.
        """
        if crop_image is None or crop_image.size == 0:
            self.last_scan_info = "Empty crop"
            return None, 0

        self.total_scans += 1
        now = time.time()

        # Check image stability FIRST
        gray_crop = cv2.cvtColor(crop_image, cv2.COLOR_BGR2GRAY)
        is_stable, pixel_diff = self._check_image_stability(gray_crop)

        # Identify food (v16: color-based)
        food, conf = self.identify_icon(crop_image)

        # Build diagnostic info
        stability_str = (f"stable={self.stable_frame_count}"
                         if is_stable
                         else f"MOVING(diff={pixel_diff:.1f})")

        if self.last_best_food:
            tmpl_info = (f"tmpl:{self.last_best_food} {self.last_best_score:.0%} "
                         f"@{self.last_best_scale:.2f}x")
        else:
            tmpl_info = "tmpl:none"

        color_info = ""
        if self.last_color_food:
            color_info = (f" color:{self.last_color_food} {self.last_color_score:.2f}"
                          f" vs {self.last_color_runner_up}:{self.last_color_runner_score:.2f}")

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

            food_stable = self.consecutive_count >= self.required_consecutive
            image_stable = is_stable

            if not self.popup_active:
                if food_stable and image_stable:
                    self.popup_active = True
                    self.last_detection_time = now
                    self.last_detected_food = food
                    self.total_detections += 1
                    self.consecutive_no_match = 0

                    self.last_scan_info = (
                        f"CONFIRMED: {food} ({conf:.0%}) "
                        f"[{consec_str}, {stability_str}]{color_info}")
                    print(f"[DETECT] Confirmed: {food} (tmpl: {conf:.1%}, "
                          f"color: {self.last_color_food}={self.last_color_score:.2f}, "
                          f"consecutive: {self.consecutive_count}, "
                          f"pixel_diff: {pixel_diff:.1f})")
                    return food, conf

                elif food_stable and not image_stable:
                    self.last_scan_info = (
                        f"WAIT-UNSTABLE: {food} ({conf:.0%}) "
                        f"[{consec_str}, diff={pixel_diff:.1f}]{color_info}")
                    self.consecutive_no_match = 0
                    return None, 0

                else:
                    self.last_scan_info = (
                        f"Building: {food} ({conf:.0%}) "
                        f"[{consec_str}, {stability_str}]{color_info}")
                    self.consecutive_no_match = 0
                    return None, 0

            elif food != self.last_detected_food:
                if food_stable and image_stable:
                    self.last_detection_time = now
                    self.last_detected_food = food
                    self.total_detections += 1

                    self.last_scan_info = (
                        f"NEW FOOD: {food} ({conf:.0%}) "
                        f"[was {self.last_detected_food}]{color_info}")
                    print(f"[DETECT] New food: {food} (was {self.last_detected_food})")
                    return food, conf
                else:
                    self.last_scan_info = (
                        f"New? {food} ({conf:.0%}) "
                        f"[{consec_str}, {stability_str}]{color_info} not stable yet")
                    return None, 0
            else:
                elapsed = now - self.last_detection_time
                self.last_scan_info = (
                    f"Active: {food} ({conf:.0%}) "
                    f"[{elapsed:.0f}s] skip")
                self.consecutive_no_match = 0
                return None, 0
        else:
            # No match above threshold
            self.consecutive_no_match += 1
            self.consecutive_food = None
            self.consecutive_count = 0

            best_info = f"{tmpl_info}{color_info}"

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

        tmpl = f"T{self.last_best_food}_{self.last_best_score:.0%}" if self.last_best_food else "Tnone"
        color = f"C{self.last_color_food}_{self.last_color_score:.2f}" if self.last_color_food else "Cnone"
        stable = f"S{self.stable_frame_count}" if self.stable_frame_count > 0 else f"M{self.last_image_diff:.0f}"
        state = "DET" if food else "wait"
        fname = os.path.join(
            self.debug_dir,
            f"scan_{self.scan_save_count:05d}_{state}_{tmpl}_{color}_{stable}.png")
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
