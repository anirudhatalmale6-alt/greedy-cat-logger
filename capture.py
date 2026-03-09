"""Screen capture module for Greedy Cat Result Logger"""

import time
import mss
import numpy as np
import cv2
from PIL import Image


class ScreenCapture:
    """Handles screen capture from the emulator window."""

    def __init__(self):
        self.sct = mss.mss()
        self.result_region = None  # (x, y, width, height) - the Result row area
        self.last_capture = None
        self.last_capture_time = 0

    def set_result_region(self, x, y, width, height):
        """Set the region where the Result row appears."""
        self.result_region = {"left": x, "top": y, "width": width, "height": height}

    def capture_result_strip(self):
        """Capture the result strip region of the screen."""
        if self.result_region is None:
            return None

        try:
            screenshot = self.sct.grab(self.result_region)
            img = np.array(screenshot)
            # MSS captures in BGRA, convert to BGR for OpenCV
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            self.last_capture = img
            self.last_capture_time = time.time()
            return img
        except Exception as e:
            print(f"Screen capture error: {e}")
            return None

    def capture_full_screen(self):
        """Capture the full primary screen."""
        try:
            monitor = self.sct.monitors[1]  # Primary monitor
            screenshot = self.sct.grab(monitor)
            img = np.array(screenshot)
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            return img
        except Exception as e:
            print(f"Full screen capture error: {e}")
            return None

    def capture_region(self, x, y, width, height):
        """Capture a specific region of the screen."""
        try:
            region = {"left": x, "top": y, "width": width, "height": height}
            screenshot = self.sct.grab(region)
            img = np.array(screenshot)
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            return img
        except Exception as e:
            print(f"Region capture error: {e}")
            return None

    def capture_emulator_window(self, window_title="LDPlayer"):
        """
        Try to find and capture the emulator window.
        Falls back to full screen if window not found.
        """
        try:
            import pyautogui
            windows = pyautogui.getWindowsWithTitle(window_title)
            if windows:
                win = windows[0]
                return self.capture_region(win.left, win.top, win.width, win.height)
        except Exception:
            pass
        return self.capture_full_screen()

    @staticmethod
    def image_changed(img1, img2, threshold=5):
        """Check if two images are significantly different."""
        if img1 is None or img2 is None:
            return True
        if img1.shape != img2.shape:
            return True

        diff = cv2.absdiff(img1, img2)
        mean_diff = np.mean(diff)
        return mean_diff > threshold

    def get_monitors(self):
        """Get list of available monitors."""
        return self.sct.monitors
