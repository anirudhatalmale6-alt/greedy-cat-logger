"""Icon detection engine using OpenCV template matching"""

import os
import cv2
import numpy as np
from config import FOOD_ITEMS, MATCH_THRESHOLD, TEMPLATES_DIR


class IconDetector:
    """Detects food icons from the Greedy Cat game using template matching."""

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
                score = self._match_template(icon_image, template)
                if score > best_score and score >= MATCH_THRESHOLD:
                    best_score = score
                    best_match = food_name

        return best_match, best_score

    def detect_result_row(self, result_strip_image, num_slots=10):
        """
        Detect all icons in the result strip at the bottom of the screen.
        The strip contains multiple small circular icons in a row.
        Returns list of detected food names (left to right = oldest to newest).
        """
        if result_strip_image is None or result_strip_image.size == 0:
            return []

        results = []
        h, w = result_strip_image.shape[:2]

        # Each icon is roughly equal-spaced in the strip
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

    def detect_latest_result(self, result_strip_image, num_slots=10):
        """
        Detect only the latest (rightmost) result from the result strip.
        Returns (food_name, confidence) or (None, 0).
        """
        if result_strip_image is None or result_strip_image.size == 0:
            return None, 0

        h, w = result_strip_image.shape[:2]
        icon_width = w // num_slots

        # Get the rightmost icon
        x_start = (num_slots - 1) * icon_width
        icon_crop = result_strip_image[:, x_start:]

        return self.detect_single_icon(icon_crop)

    def find_icons_in_image(self, full_image):
        """
        Find all template matches in a full image using sliding window.
        Returns list of (food_name, x, y, confidence).
        """
        if not self.templates:
            return []

        matches = []
        gray_image = cv2.cvtColor(full_image, cv2.COLOR_BGR2GRAY)

        for food_name, template_list in self.templates.items():
            for template in template_list:
                gray_template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
                th, tw = gray_template.shape[:2]

                # Skip if template is larger than image
                if th > gray_image.shape[0] or tw > gray_image.shape[1]:
                    # Resize template to fit
                    scale = min(gray_image.shape[0] / th, gray_image.shape[1] / tw) * 0.8
                    if scale < 0.3:
                        continue
                    gray_template = cv2.resize(gray_template, None, fx=scale, fy=scale)
                    th, tw = gray_template.shape[:2]

                result = cv2.matchTemplate(gray_image, gray_template, cv2.TM_CCOEFF_NORMED)
                locations = np.where(result >= MATCH_THRESHOLD)

                for pt in zip(*locations[::-1]):
                    matches.append((food_name, pt[0], pt[1], result[pt[1], pt[0]]))

        # Non-maximum suppression: remove overlapping detections
        matches = self._nms(matches)
        return matches

    def _match_template(self, image, template):
        """Match a single template against an image, return max confidence."""
        try:
            # Resize template to match image size if needed
            ih, iw = image.shape[:2]
            th, tw = template.shape[:2]

            if ih < 5 or iw < 5:
                return 0

            # Resize template to match the icon crop size
            template_resized = cv2.resize(template, (iw, ih))

            # Convert to grayscale for matching
            gray_img = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            gray_tmpl = cv2.cvtColor(template_resized, cv2.COLOR_BGR2GRAY)

            result = cv2.matchTemplate(gray_img, gray_tmpl, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(result)
            return max_val
        except Exception:
            return 0

    def _nms(self, matches, overlap_thresh=30):
        """Simple non-maximum suppression based on distance."""
        if not matches:
            return []

        # Sort by confidence descending
        matches.sort(key=lambda m: m[3], reverse=True)
        kept = []

        for match in matches:
            is_duplicate = False
            for kept_match in kept:
                dx = abs(match[1] - kept_match[1])
                dy = abs(match[2] - kept_match[2])
                if dx < overlap_thresh and dy < overlap_thresh:
                    is_duplicate = True
                    break
            if not is_duplicate:
                kept.append(match)

        return kept

    @property
    def is_ready(self):
        """Check if templates are loaded and ready for detection."""
        return len(self.templates) > 0

    @property
    def loaded_items(self):
        """List of food items that have templates loaded."""
        return list(self.templates.keys())
