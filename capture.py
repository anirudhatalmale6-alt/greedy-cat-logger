"""Screen capture module for Greedy Cat Result Logger v9

Supports two capture methods:
1. mss (default) — fast, but may fail on DirectX/OpenGL windows (black screen)
2. pyautogui/PIL (fallback) — slower but more compatible with emulators

When BlueStacks or other emulators use hardware acceleration, mss often
captures a black rectangle instead of the actual game content. The fallback
method uses PIL's ImageGrab which handles this better on Windows.
"""

import time
import sys
import mss
import numpy as np
import cv2


class ScreenCapture:
    """Handles screen capture from the emulator window."""

    EMULATOR_TITLES = [
        "BlueStacks App Player",
        "BlueStacks",
        "LDPlayer",
        "NoxPlayer",
        "MEmu",
        "Xena",
    ]

    def __init__(self):
        self.sct = mss.mss()
        self.result_region = None
        self.last_capture = None
        self.last_capture_time = 0
        self.use_fallback = False  # True = use pyautogui instead of mss

    def set_result_region(self, x, y, width, height):
        """Set the region where the Result row appears."""
        self.result_region = {"left": x, "top": y, "width": width, "height": height}

    def capture_region(self, x, y, width, height):
        """Capture a specific region of the screen using the best available method."""
        if self.use_fallback:
            return self._capture_region_pyautogui(x, y, width, height)
        return self._capture_region_mss(x, y, width, height)

    def _capture_region_mss(self, x, y, width, height):
        """Capture using mss (fast but may fail on DirectX windows)."""
        try:
            region = {"left": x, "top": y, "width": width, "height": height}
            screenshot = self.sct.grab(region)
            img = np.array(screenshot)
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            return img
        except Exception as e:
            print(f"[mss] Capture error: {e}")
            return None

    def _capture_region_pyautogui(self, x, y, width, height):
        """Capture using pyautogui/PIL (more compatible with emulators)."""
        try:
            if sys.platform == "win32":
                from PIL import ImageGrab
                bbox = (x, y, x + width, y + height)
                screenshot = ImageGrab.grab(bbox=bbox)
                img = np.array(screenshot)
                img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
                return img
            else:
                import pyautogui
                screenshot = pyautogui.screenshot(region=(x, y, width, height))
                img = np.array(screenshot)
                img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
                return img
        except Exception as e:
            print(f"[pyautogui] Capture error: {e}")
            return None

    def capture_full_screen(self):
        """Capture the full primary screen."""
        if self.use_fallback:
            return self._capture_full_screen_pyautogui()
        return self._capture_full_screen_mss()

    def _capture_full_screen_mss(self):
        try:
            monitor = self.sct.monitors[1]
            screenshot = self.sct.grab(monitor)
            img = np.array(screenshot)
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            return img
        except Exception as e:
            print(f"[mss] Full screen capture error: {e}")
            return None

    def _capture_full_screen_pyautogui(self):
        try:
            if sys.platform == "win32":
                from PIL import ImageGrab
                screenshot = ImageGrab.grab()
                img = np.array(screenshot)
                img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
                return img
            else:
                import pyautogui
                screenshot = pyautogui.screenshot()
                img = np.array(screenshot)
                img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
                return img
        except Exception as e:
            print(f"[pyautogui] Full screen capture error: {e}")
            return None

    def capture_result_strip(self):
        """Capture the result strip region."""
        if self.result_region is None:
            return None
        r = self.result_region
        return self.capture_region(r["left"], r["top"], r["width"], r["height"])

    def test_capture_methods(self, x, y, width, height):
        """
        Test both capture methods and return results.
        Returns: {"mss": (image, is_valid), "pyautogui": (image, is_valid)}
        """
        results = {}

        # Test mss
        mss_img = self._capture_region_mss(x, y, width, height)
        mss_valid = self._validate_capture(mss_img)
        results["mss"] = (mss_img, mss_valid)

        # Test pyautogui
        pyag_img = self._capture_region_pyautogui(x, y, width, height)
        pyag_valid = self._validate_capture(pyag_img)
        results["pyautogui"] = (pyag_img, pyag_valid)

        return results

    @staticmethod
    def _validate_capture(img):
        """
        Check if a captured image is valid (not black/uniform).
        Returns True if the capture looks like real screen content.
        """
        if img is None:
            return False
        if img.size == 0:
            return False

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        std_dev = np.std(gray)
        mean_val = np.mean(gray)

        # Black screen: mean ~0, std ~0
        # Uniform color: std < 5
        # Real content: std > 10, mean varies
        if std_dev < 5:
            return False
        if mean_val < 3:  # Nearly all black
            return False
        return True

    def find_emulator_window(self):
        """Find the emulator window (BlueStacks, LDPlayer, etc)."""
        try:
            import pyautogui
            for title in self.EMULATOR_TITLES:
                windows = pyautogui.getWindowsWithTitle(title)
                if windows:
                    win = windows[0]
                    return {
                        "title": title,
                        "left": win.left,
                        "top": win.top,
                        "width": win.width,
                        "height": win.height,
                    }
        except Exception:
            pass

        try:
            import win32gui

            found = {}

            def enum_handler(hwnd, results):
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    for emu_title in self.EMULATOR_TITLES:
                        if emu_title.lower() in title.lower():
                            rect = win32gui.GetWindowRect(hwnd)
                            results["found"] = {
                                "title": title,
                                "left": rect[0],
                                "top": rect[1],
                                "width": rect[2] - rect[0],
                                "height": rect[3] - rect[1],
                            }

            win32gui.EnumWindows(enum_handler, found)
            if "found" in found:
                return found["found"]
        except ImportError:
            pass

        return None

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
