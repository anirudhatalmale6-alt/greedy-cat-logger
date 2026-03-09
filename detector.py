"""
Icon detection engine for Greedy Cat Result Logger.

Uses multiple detection strategies:
1. ORB feature matching (primary) — matches local visual features,
   robust to confetti/effects and scale changes.
2. Multi-scale template matching (secondary) — traditional approach.
3. Dominant color classification (fallback) — for when features are sparse.

The popup in Greedy Cat shows the winning food icon with celebration
effects. ORB features can match the icon even with surrounding noise.
"""

import os
import cv2
import numpy as np
from config import FOOD_ITEMS, MATCH_THRESHOLD, TEMPLATES_DIR


class IconDetector:
    """Detects food icons using ORB features + template matching."""

    SCALES = [0.5, 0.7, 1.0, 1.5, 2.0, 3.0, 4.0]

    # Dominant hue for each food (used as fallback)
    # Hue is 0-180 in OpenCV HSV
    FOOD_HUES = {
        "tomato":  {"hue": 5,   "sat_min": 120, "val_min": 100},
        "corn":    {"hue": 28,  "sat_min": 120, "val_min": 150},
        "chicken": {"hue": 15,  "sat_min": 20,  "val_min": 200},  # Whitish
        "cow":     {"hue": 18,  "sat_min": 80,  "val_min": 80},
        "carrot":  {"hue": 18,  "sat_min": 150, "val_min": 150},
        "fish":    {"hue": 105, "sat_min": 80,  "val_min": 100},
        "salad":   {"hue": 20,  "sat_min": 80,  "val_min": 120},  # Multicolor
        "pizza":   {"hue": 22,  "sat_min": 100, "val_min": 120},
        "shrimp":  {"hue": 12,  "sat_min": 80,  "val_min": 150},
        "pepper":  {"hue": 3,   "sat_min": 150, "val_min": 100},
    }

    def __init__(self, templates_dir=None):
        self.templates_dir = templates_dir or TEMPLATES_DIR
        self.templates = {}        # {name: [cv2_images]}
        self.template_kps = {}     # {name: [(keypoints, descriptors)]}
        self.orb = cv2.ORB_create(nfeatures=500)
        self.bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
        self.debug_enabled = False
        self.debug_dir = "debug_captures"
        self.load_templates()

    def load_templates(self):
        """Load all template images and extract ORB features."""
        self.templates = {}
        self.template_kps = {}

        if not os.path.exists(self.templates_dir):
            os.makedirs(self.templates_dir, exist_ok=True)
            return

        for food in FOOD_ITEMS:
            templates = []
            kps = []

            # Check directory
            food_dir = os.path.join(self.templates_dir, food)
            if os.path.isdir(food_dir):
                for fname in sorted(os.listdir(food_dir)):
                    if fname.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
                        t, k = self._load_one(os.path.join(food_dir, fname))
                        if t is not None:
                            templates.append(t)
                            kps.append(k)

            # Check single file
            for ext in ('.png', '.jpg', '.jpeg', '.bmp'):
                path = os.path.join(self.templates_dir, food + ext)
                if os.path.exists(path):
                    t, k = self._load_one(path)
                    if t is not None:
                        templates.append(t)
                        kps.append(k)

            if templates:
                self.templates[food] = templates
                self.template_kps[food] = kps

    def _load_one(self, path):
        """Load one template and compute ORB features at multiple scales."""
        img = cv2.imread(path)
        if img is None:
            return None, None

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Compute ORB at multiple scales for better matching
        all_kp = []
        all_des = []
        for scale in [0.5, 1.0, 2.0, 3.0]:
            h, w = gray.shape[:2]
            sh, sw = int(h * scale), int(w * scale)
            if sh < 20 or sw < 20:
                continue
            scaled = cv2.resize(gray, (sw, sh))
            kp, des = self.orb.detectAndCompute(scaled, None)
            if des is not None:
                all_kp.extend(kp)
                all_des.append(des)

        if all_des:
            combined_des = np.vstack(all_des)
        else:
            combined_des = None

        return img, (all_kp, combined_des)

    def find_best_match_in_region(self, image):
        """
        Primary detection: find best matching food icon in captured region.
        Returns (food_name, confidence, x, y) or (None, 0, 0, 0)
        """
        if image is None or image.size == 0 or not self.templates:
            return None, 0, 0, 0

        if self.debug_enabled:
            self._save_debug(image)

        # Method 1: ORB feature matching
        orb_match, orb_score = self._match_by_orb(image)

        # Method 2: Multi-scale template matching
        tmpl_match, tmpl_score, tx, ty = self._match_by_template(image)

        # Method 3: Color-based classification
        color_match, color_score = self._match_by_color(image)

        # Decision logic - combine results
        candidates = {}

        if orb_match and orb_score > 0:
            candidates.setdefault(orb_match, []).append(("orb", orb_score))
        if tmpl_match and tmpl_score > 0.4:
            candidates.setdefault(tmpl_match, []).append(("tmpl", tmpl_score))
        if color_match and color_score > 0:
            candidates.setdefault(color_match, []).append(("color", color_score))

        if not candidates:
            return None, 0, 0, 0

        # Score each candidate by number of methods agreeing + average confidence
        best_food = None
        best_combined = 0

        for food, methods in candidates.items():
            # More methods agreeing = higher score
            agreement_bonus = len(methods) * 0.15
            avg_score = sum(s for _, s in methods) / len(methods)
            combined = avg_score + agreement_bonus

            if combined > best_combined:
                best_combined = combined
                best_food = food

        if best_food:
            # Normalize confidence to 0-1
            final_conf = min(best_combined, 1.0)
            return best_food, final_conf, tx if tmpl_match == best_food else 0, ty if tmpl_match == best_food else 0

        return None, 0, 0, 0

    def _match_by_orb(self, image):
        """Match using ORB features."""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Compute features at multiple scales
        all_des = []
        for scale in [0.5, 1.0, 1.5]:
            h, w = gray.shape[:2]
            sh, sw = int(h * scale), int(w * scale)
            if sh < 20 or sw < 20 or sh > 2000 or sw > 2000:
                continue
            scaled = cv2.resize(gray, (sw, sh))
            kp, des = self.orb.detectAndCompute(scaled, None)
            if des is not None:
                all_des.append(des)

        if not all_des:
            return None, 0

        img_des = np.vstack(all_des)

        best_match = None
        best_score = 0

        for food_name, kp_list in self.template_kps.items():
            for _, tmpl_des in kp_list:
                if tmpl_des is None:
                    continue

                try:
                    # Use KNN matching with ratio test
                    matches = self.bf.knnMatch(tmpl_des, img_des, k=2)

                    # Apply Lowe's ratio test
                    good_matches = []
                    for m_pair in matches:
                        if len(m_pair) == 2:
                            m, n = m_pair
                            if m.distance < 0.75 * n.distance:
                                good_matches.append(m)

                    if len(good_matches) < 3:
                        continue

                    # Score based on number of good matches / total
                    score = len(good_matches) / max(len(matches), 1)

                    if score > best_score:
                        best_score = score
                        best_match = food_name

                except Exception:
                    continue

        return best_match, best_score

    def _match_by_template(self, image):
        """Multi-scale template matching."""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        ih, iw = gray.shape[:2]

        best_match = None
        best_score = 0
        best_x, best_y = 0, 0

        for food_name, template_list in self.templates.items():
            for template in template_list:
                gray_t = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)

                for scale in self.SCALES:
                    th = int(gray_t.shape[0] * scale)
                    tw = int(gray_t.shape[1] * scale)

                    if th < 10 or tw < 10 or th > ih or tw > iw:
                        continue

                    scaled = cv2.resize(gray_t, (tw, th))

                    try:
                        result = cv2.matchTemplate(gray, scaled, cv2.TM_CCOEFF_NORMED)
                        _, max_val, _, max_loc = cv2.minMaxLoc(result)

                        if max_val > best_score:
                            best_score = max_val
                            best_match = food_name
                            best_x, best_y = max_loc
                    except Exception:
                        continue

        return best_match, best_score, best_x, best_y

    def _match_by_color(self, image):
        """
        Classify by dominant color in the center of the image.
        Each food has a distinctive color — this works as a tiebreaker.
        """
        h, w = image.shape[:2]

        # Use center 50% of the image (where the food icon is)
        cx, cy = w // 4, h // 4
        center = image[cy:h - cy, cx:w - cx]

        if center.size == 0:
            center = image

        hsv = cv2.cvtColor(center, cv2.COLOR_BGR2HSV)

        # Get dominant hue (ignoring very dark or very unsaturated pixels)
        mask = (hsv[:, :, 1] > 50) & (hsv[:, :, 2] > 50)
        if np.sum(mask) < 10:
            return None, 0

        hues = hsv[:, :, 0][mask]
        sats = hsv[:, :, 1][mask]

        if len(hues) == 0:
            return None, 0

        # Compute hue histogram
        hue_hist, _ = np.histogram(hues, bins=36, range=(0, 180))
        dominant_hue = (np.argmax(hue_hist) * 5) + 2.5
        avg_sat = np.mean(sats)

        # Score each food by how close its expected hue is
        best_match = None
        best_score = 0

        for food, props in self.FOOD_HUES.items():
            expected_hue = props["hue"]

            # Circular hue distance
            hue_diff = min(abs(dominant_hue - expected_hue),
                           180 - abs(dominant_hue - expected_hue))

            # Score: lower distance = better match
            hue_score = max(0, 1.0 - (hue_diff / 30))

            # Saturation check
            if avg_sat < props["sat_min"] * 0.5:
                hue_score *= 0.5  # Penalize if saturation is too low

            if hue_score > best_score:
                best_score = hue_score
                best_match = food

        return best_match, best_score * 0.6  # Cap at 0.6 since color alone isn't definitive

    def detect_popup_icon(self, popup_image):
        """Alias."""
        name, conf, _, _ = self.find_best_match_in_region(popup_image)
        return name, conf

    def detect_single_icon(self, icon_image):
        """Detect which food item a single icon represents."""
        return self.detect_popup_icon(icon_image)

    def detect_result_row(self, result_strip_image, num_slots=10):
        """Legacy: detect icons in a result strip."""
        if result_strip_image is None or result_strip_image.size == 0:
            return []

        results = []
        h, w = result_strip_image.shape[:2]
        icon_width = w // num_slots

        for i in range(num_slots):
            x_start = i * icon_width
            x_end = min((i + 1) * icon_width, w)
            icon_crop = result_strip_image[:, x_start:x_end]
            if icon_crop.size == 0:
                continue
            food_name, conf = self.detect_popup_icon(icon_crop)
            if food_name:
                results.append(food_name)

        return results

    @staticmethod
    def compute_image_hash(image, hash_size=16):
        """Perceptual hash for change detection."""
        if image is None or image.size == 0:
            return ""
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            resized = cv2.resize(gray, (hash_size + 1, hash_size))
            diff = resized[:, 1:] > resized[:, :-1]
            return ''.join(['1' if b else '0' for row in diff for b in row])
        except Exception:
            return ""

    @staticmethod
    def hash_distance(hash1, hash2):
        """Hamming distance between two hashes."""
        if len(hash1) != len(hash2):
            return 999
        return sum(c1 != c2 for c1, c2 in zip(hash1, hash2))

    def _save_debug(self, image):
        """Save debug capture."""
        os.makedirs(self.debug_dir, exist_ok=True)
        import time
        fname = os.path.join(self.debug_dir, f"capture_{int(time.time())}.png")
        cv2.imwrite(fname, image)
        files = sorted(
            [os.path.join(self.debug_dir, f) for f in os.listdir(self.debug_dir) if f.endswith('.png')],
            key=os.path.getmtime
        )
        while len(files) > 20:
            os.remove(files.pop(0))

    @property
    def is_ready(self):
        return len(self.templates) > 0

    @property
    def loaded_items(self):
        return list(self.templates.keys())
