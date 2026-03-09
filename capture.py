"""Screen capture module for Greedy Cat Result Logger"""

import time
import mss
import numpy as np
import cv2


class ScreenCapture:
    """Handles screen capture from the emulator window."""

    # Common emulator window titles
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
            monitor = self.sct.monitors[1]
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

    def find_emulator_window(self):
        """
        Find the emulator window (BlueStacks, LDPlayer, etc).
        Returns (x, y, width, height) or None.
        """
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

        # Fallback: try win32gui on Windows
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
