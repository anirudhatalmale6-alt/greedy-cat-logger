"""
Icon detection engine using OpenCV template matching.
Supports both popup-based and result-row-based detection.

The Greedy Cat game shows results as a popup window with a large
food icon in the center. This detector scans the popup area and
matches the icon against known templates at multiple scales.
"""

import os
import cv2
import numpy as np
from config import FOOD_ITEMS, MATCH_THRESHOLD, TEMPLATES_DIR


class IconDetector:
    """Detects food icons from the Greedy Cat game using template matching."""

    # Multiple scales to try for matching (popup icon can vary in size)
    SCALES = [0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.2, 1.5, 2.0]

    def __init__(self, templates_dir=None):
        self.templates_dir = templates_dir or TEMPLATES_DIR
        self.templates = {}  # {name: [template_images]}
        self.load_templates()

    def load_templates(self):
        """Load all template images from the templates directory."""
        self.templates = {}
        if not os.path.exists(self.templates_dir):
            os.makedirs(self.templates_dir, exist_ok=True)
            return

        for food in FOOD_ITEMS:
            food_dir = os.path.join(self.templates_dir, food)
            if os.path.isdir(food_dir):
                templates = []
                for fname in sorted(os.listdir(food_dir)):
                    if fname.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
                        img = cv2.imread(os.path.join(food_dir, fname))
                        if img is not None:
                            templates.append(img)
                if templates:
                    self.templates[food] = templates

            # Also check for single file like tomato.png
            for ext in ('.png', '.jpg', '.jpeg', '.bmp'):
                single = os.path.join(self.templates_dir, food + ext)
                if os.path.exists(single):
                    img = cv2.imread(single)
                    if img is not None:
                        if food not in self.templates:
                            self.templates[food] = []
                        self.templates[food].append(img)

    def detect_popup_icon(self, popup_image):
        """
        Detect the food icon in a popup result window.
        Uses multi-scale template matching to find the best match
        regardless of the icon size in the popup.

        Args:
            popup_image: BGR image of the popup area

        Returns:
            (food_name, confidence) or (None, 0)
        """
        if popup_image is None or popup_image.size == 0:
            return None, 0

        if not self.templates:
            return None, 0

        best_match = None
        best_score = 0

        gray_popup = cv2.cvtColor(popup_image, cv2.COLOR_BGR2GRAY)
        ph, pw = gray_popup.shape[:2]

        for food_name, template_list in self.templates.items():
            for template in template_list:
                gray_template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)

                for scale in self.SCALES:
                    th = int(gray_template.shape[0] * scale)
                    tw = int(gray_template.shape[1] * scale)

                    # Skip if scaled template is too small or bigger than popup
                    if th < 10 or tw < 10:
                        continue
                    if th > ph or tw > pw:
                        continue

                    scaled = cv2.resize(gray_template, (tw, th))

                    try:
                        result = cv2.matchTemplate(gray_popup, scaled, cv2.TM_CCOEFF_NORMED)
                        _, max_val, _, max_loc = cv2.minMaxLoc(result)

                        if max_val > best_score and max_val >= MATCH_THRESHOLD:
                            best_score = max_val
                            best_match = food_name
                    except Exception:
                        continue

        return best_match, best_score

    def detect_single_icon(self, icon_image):
        """
        Detect which food item a single icon image represents.
        Returns (food_name, confidence) or (None, 0).
        """
        if not self.templates:
            return None, 0

        best_match = None
        best_score = 0

        for food_name, template_list in self.templates.items():
            for template in template_list:
                score = self._match_direct(icon_image, template)
                if score > best_score and score >= MATCH_THRESHOLD:
                    best_score = score
                    best_match = food_name

        return best_match, best_score

    def detect_result_row(self, result_strip_image, num_slots=10):
        """
        Detect all icons in the result strip at the bottom of the screen.
        Returns list of detected food names.
        """
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

            food_name, confidence = self.detect_single_icon(icon_crop)
            if food_name:
                results.append(food_name)

        return results

    def find_best_match_in_region(self, image):
        """
        Find the single best matching food icon anywhere in the image.
        Uses multi-scale sliding window matching.

        Returns (food_name, confidence, x, y) or (None, 0, 0, 0)
        """
        if image is None or image.size == 0 or not self.templates:
            return None, 0, 0, 0

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

                        if max_val > best_score and max_val >= MATCH_THRESHOLD:
                            best_score = max_val
                            best_match = food_name
                            best_x, best_y = max_loc
                    except Exception:
                        continue

        return best_match, best_score, best_x, best_y

    def _match_direct(self, image, template):
        """Match a template against an image by resizing template to image size."""
        try:
            ih, iw = image.shape[:2]
            if ih < 5 or iw < 5:
                return 0

            template_resized = cv2.resize(template, (iw, ih))
            gray_img = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            gray_tmpl = cv2.cvtColor(template_resized, cv2.COLOR_BGR2GRAY)

            result = cv2.matchTemplate(gray_img, gray_tmpl, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(result)
            return max_val
        except Exception:
            return 0

    @staticmethod
    def compute_image_hash(image, hash_size=16):
        """
        Compute a perceptual hash of an image for change detection.
        Returns a hash string. Two similar images will have similar hashes.
        """
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
        """Hamming distance between two hashes. 0 = identical."""
        if len(hash1) != len(hash2):
            return 999
        return sum(c1 != c2 for c1, c2 in zip(hash1, hash2))

    @property
    def is_ready(self):
        return len(self.templates) > 0

    @property
    def loaded_items(self):
        return list(self.templates.keys())
