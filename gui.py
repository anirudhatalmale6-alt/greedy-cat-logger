"""
Statistics GUI for Greedy Cat Result Logger v10
Shows history as game icons, hot/cold items, percentages, streaks.
Dark theme matching reference software style.

v10: Capture verification dialog — tests if screen capture works before
     monitoring starts. Auto-switches to pyautogui fallback if mss returns
     black images (common with DirectX/OpenGL emulators like BlueStacks).
     Auto-saves first 20 scans for diagnostics.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import os
import threading
import time
import json
import cv2
from datetime import datetime
from PIL import Image, ImageTk
from config import FOOD_ITEMS, FOOD_DISPLAY, FOOD_MULTIPLIER, TEMPLATES_DIR
from predictor import Predictor


class StatsGUI:
    """Main statistics window for the Greedy Cat Result Logger."""

    BG_COLOR = "#0d1117"
    CARD_BG = "#161b22"
    HEADER_BG = "#1a1a2e"
    ACCENT = "#e94560"
    TEXT_COLOR = "#e6edf3"
    TEXT_DIM = "#8b949e"
    GOLD = "#FFD700"
    GREEN = "#3fb950"
    RED = "#f85149"
    BLUE = "#58a6ff"

    ICON_SIZE_SMALL = 28     # For result strip
    ICON_SIZE_TABLE = 32     # For stats table
    ICON_SIZE_BUTTON = 36    # For manual add buttons
    ICON_SIZE_CARD = 40      # For summary cards

    def __init__(self, logger, detector=None, capturer=None):
        self.logger = logger
        self.detector = detector
        self.capturer = capturer
        self.monitoring = False
        self.monitor_thread = None
        self.scan_count = 0
        self.predictor = Predictor()

        # Icon image cache
        self.icons = {}  # {food_name: {size: PhotoImage}}

        self.root = tk.Tk()
        self.root.title("Greedy Cat Result Logger")
        self.root.geometry("860x950")
        self.root.configure(bg=self.BG_COLOR)
        self.root.resizable(True, True)
        self.root.minsize(780, 700)

        # Load config
        self.config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")
        self.settings = self._load_settings()

        # Load icon images
        self._load_icons()

        self._build_gui()
        self._refresh_stats()
        self._update_calibration_status()

    def _load_settings(self):
        """Load saved settings."""
        defaults = {
            "region_x": 0, "region_y": 0, "region_w": 0, "region_h": 0,
            "icon_center_x": 0, "icon_center_y": 0, "crop_size": 150,
            "interval": 1.0,
            "debug_saves": False,
        }
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    saved = json.load(f)
                    defaults.update(saved)
            except Exception:
                pass
        return defaults

    def _save_settings(self):
        """Save settings to disk."""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.settings, f, indent=2)
        except Exception:
            pass

    def _load_icons(self):
        """Load game icon images from templates directory."""
        templates_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), TEMPLATES_DIR)
        for food in FOOD_ITEMS:
            self.icons[food] = {}
            for ext in ('.png', '.jpg', '.jpeg', '.bmp'):
                path = os.path.join(templates_dir, food + ext)
                if os.path.exists(path):
                    try:
                        pil_img = Image.open(path).convert("RGBA")
                        for size_name, size_px in [
                            ("small", self.ICON_SIZE_SMALL),
                            ("table", self.ICON_SIZE_TABLE),
                            ("button", self.ICON_SIZE_BUTTON),
                            ("card", self.ICON_SIZE_CARD),
                        ]:
                            resized = pil_img.resize((size_px, size_px), Image.LANCZOS)
                            self.icons[food][size_name] = ImageTk.PhotoImage(resized)
                    except Exception as e:
                        print(f"Failed to load icon for {food}: {e}")
                    break

    def _get_icon(self, food, size="small"):
        """Get a PhotoImage for a food item at the given size."""
        if food in self.icons and size in self.icons[food]:
            return self.icons[food][size]
        return None

    def _build_gui(self):
        """Build the complete GUI layout."""
        # Style
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Dark.TFrame", background=self.BG_COLOR)
        style.configure("Card.TFrame", background=self.CARD_BG)

        # Main scrollable area
        outer = tk.Frame(self.root, bg=self.BG_COLOR)
        outer.pack(fill="both", expand=True)

        canvas = tk.Canvas(outer, bg=self.BG_COLOR, highlightthickness=0)
        vsb = tk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        self.main_frame = tk.Frame(canvas, bg=self.BG_COLOR)

        self.main_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas_window = canvas.create_window((0, 0), window=self.main_frame, anchor="nw")

        def _on_canvas_configure(event):
            canvas.itemconfig(canvas_window, width=event.width)
        canvas.bind("<Configure>", _on_canvas_configure)

        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        def _on_mousewheel_linux(event):
            if event.num == 4:
                canvas.yview_scroll(-3, "units")
            elif event.num == 5:
                canvas.yview_scroll(3, "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        canvas.bind_all("<Button-4>", _on_mousewheel_linux)
        canvas.bind_all("<Button-5>", _on_mousewheel_linux)

        # ===== BUILD SECTIONS =====
        self._build_header()
        self._build_controls()
        self._build_calibration_info()
        self._build_summary_cards()
        self._build_prediction()
        self._build_recent_results()
        self._build_hot_cold()
        self._build_stats_table()
        self._build_result_history()
        self._build_status_bar()

    # ===================== HEADER =====================
    def _build_header(self):
        header = tk.Frame(self.main_frame, bg="#1a1a2e", pady=10)
        header.pack(fill="x", padx=5, pady=(5, 0))

        title_frame = tk.Frame(header, bg="#1a1a2e")
        title_frame.pack()

        tk.Label(title_frame, text="GREEDY CAT RESULT LOGGER",
                 font=("Segoe UI", 18, "bold"), fg=self.GOLD, bg="#1a1a2e").pack()
        tk.Label(title_frame, text="One-click calibrate, then auto-detect every round",
                 font=("Segoe UI", 9), fg=self.TEXT_DIM, bg="#1a1a2e").pack()

    # ===================== CONTROLS =====================
    def _build_controls(self):
        ctrl = tk.Frame(self.main_frame, bg=self.BG_COLOR, pady=6)
        ctrl.pack(fill="x", padx=10)

        self.btn_monitor = tk.Button(
            ctrl, text=" START MONITORING", font=("Segoe UI", 10, "bold"),
            bg="#238636", fg="white", relief="flat", padx=16, pady=5,
            command=self._toggle_monitoring, cursor="hand2",
            activebackground="#2ea043", activeforeground="white"
        )
        self.btn_monitor.pack(side="left", padx=3)

        tk.Button(
            ctrl, text="Calibrate", font=("Segoe UI", 9, "bold"),
            bg="#d29922", fg="white", relief="flat", padx=12, pady=5,
            command=self._calibrate, cursor="hand2",
            activebackground="#e3b341"
        ).pack(side="left", padx=3)

        tk.Button(
            ctrl, text="+ Manual Add", font=("Segoe UI", 9),
            bg="#1f6feb", fg="white", relief="flat", padx=10, pady=5,
            command=self._manual_add, cursor="hand2",
            activebackground="#388bfd"
        ).pack(side="left", padx=3)

        tk.Button(
            ctrl, text="Test Capture", font=("Segoe UI", 9),
            bg="#8957e5", fg="white", relief="flat", padx=10, pady=5,
            command=self._test_capture, cursor="hand2",
            activebackground="#a371f7"
        ).pack(side="left", padx=3)

        tk.Button(
            ctrl, text="Clear All", font=("Segoe UI", 9),
            bg="#da3633", fg="white", relief="flat", padx=10, pady=5,
            command=self._clear_all, cursor="hand2",
            activebackground="#f85149"
        ).pack(side="left", padx=3)

        tk.Button(
            ctrl, text="Export Excel", font=("Segoe UI", 9),
            bg="#9e6a03", fg="white", relief="flat", padx=10, pady=5,
            command=self._export_excel, cursor="hand2",
            activebackground="#bb8009"
        ).pack(side="right", padx=3)

        # Debug toggle
        self.debug_var = tk.BooleanVar(value=self.settings.get("debug_saves", False))
        self.debug_cb = tk.Checkbutton(
            ctrl, text="Save captures", font=("Segoe UI", 8),
            variable=self.debug_var, fg=self.TEXT_DIM, bg=self.BG_COLOR,
            selectcolor=self.CARD_BG, activebackground=self.BG_COLOR,
            command=self._toggle_debug
        )
        self.debug_cb.pack(side="right", padx=3)

    # ===================== CALIBRATION + LIVE PREVIEW =====================
    def _build_calibration_info(self):
        """Show calibration status + live crop preview."""
        self.cal_frame = tk.Frame(self.main_frame, bg=self.CARD_BG, pady=6, padx=10)
        self.cal_frame.pack(fill="x", padx=10, pady=(4, 0))

        # Top row: calibration status
        self.cal_status_label = tk.Label(
            self.cal_frame, text="",
            font=("Segoe UI", 9), fg=self.TEXT_DIM, bg=self.CARD_BG, anchor="w"
        )
        self.cal_status_label.pack(fill="x")

        # Live preview row (hidden until monitoring starts)
        self.preview_row = tk.Frame(self.cal_frame, bg=self.CARD_BG)
        self.preview_row.pack(fill="x", pady=(4, 0))

        # Preview thumbnail (100x100 pixels)
        # Create a blank placeholder image
        blank = Image.new("RGB", (100, 100), "#000000")
        self.preview_photo = ImageTk.PhotoImage(blank)
        self.preview_label = tk.Label(
            self.preview_row, image=self.preview_photo, bg="#000000",
            relief="solid", borderwidth=1
        )
        self.preview_label.pack(side="left", padx=(0, 8))
        self.latest_crop = None  # Shared variable for scan thread

        # Preview info
        info_frame = tk.Frame(self.preview_row, bg=self.CARD_BG)
        info_frame.pack(side="left", fill="x", expand=True)

        self.preview_match_label = tk.Label(
            info_frame, text="Best match: --",
            font=("Segoe UI", 11, "bold"), fg=self.TEXT_COLOR, bg=self.CARD_BG, anchor="w"
        )
        self.preview_match_label.pack(fill="x")

        self.preview_score_label = tk.Label(
            info_frame, text="Score: --  |  Scale: --  |  Threshold: 35%",
            font=("Consolas", 9), fg=self.TEXT_DIM, bg=self.CARD_BG, anchor="w"
        )
        self.preview_score_label.pack(fill="x")

        self.preview_state_label = tk.Label(
            info_frame, text="State: Stopped",
            font=("Segoe UI", 9), fg=self.TEXT_DIM, bg=self.CARD_BG, anchor="w"
        )
        self.preview_state_label.pack(fill="x")

        self.preview_refs_label = tk.Label(
            info_frame, text="",
            font=("Segoe UI", 8), fg="#484f58", bg=self.CARD_BG, anchor="w"
        )
        self.preview_refs_label.pack(fill="x")

        # Initially hide preview row
        self.preview_row.pack_forget()

    def _update_calibration_status(self):
        """Update the calibration status display."""
        ix = self.settings.get("icon_center_x", 0)
        iy = self.settings.get("icon_center_y", 0)
        cs = self.settings.get("crop_size", 150)

        if ix > 0 and iy > 0:
            self.cal_status_label.config(
                text=f"Calibrated: Icon at ({ix}, {iy}), crop {cs}x{cs}px  |  Ready to monitor",
                fg=self.GREEN
            )
        else:
            self.cal_status_label.config(
                text="Not calibrated  |  Click 'Calibrate' with a result popup visible on screen",
                fg="#d29922"
            )

    def _update_preview(self):
        """Update the live crop preview from the latest scan."""
        if self.latest_crop is None:
            return
        try:
            rgb = cv2.cvtColor(self.latest_crop, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(rgb)
            pil_img = pil_img.resize((100, 100), Image.LANCZOS)
            self.preview_photo = ImageTk.PhotoImage(pil_img)
            self.preview_label.config(image=self.preview_photo)
        except Exception:
            pass

        # Update match info
        if self.detector:
            food = self.detector.last_best_food
            score = self.detector.last_best_score
            scale = self.detector.last_best_scale
            threshold = self.detector.match_threshold

            if food:
                d = FOOD_DISPLAY.get(food, {})
                name = d.get("name", food)
                color = self.GREEN if score >= threshold else "#d29922" if score >= threshold * 0.7 else self.RED
                self.preview_match_label.config(
                    text=f"Best match: {name}", fg=color)
                self.preview_score_label.config(
                    text=f"Score: {score:.1%}  |  Scale: {scale:.2f}x  |  Threshold: {threshold:.0%}")
            else:
                self.preview_match_label.config(
                    text="Best match: --", fg=self.TEXT_DIM)

            # State
            state = self.detector.last_scan_info
            self.preview_state_label.config(text=f"State: {state}")

            # Refs count
            ref_count = sum(len(v) for v in self.detector.references.values())
            if ref_count > 0:
                self.preview_refs_label.config(
                    text=f"Learned references: {ref_count} (from manual adds)")
            else:
                self.preview_refs_label.config(
                    text="Tip: Use Manual Add while popup is visible to teach the program")

    # ===================== SUMMARY CARDS =====================
    def _build_summary_cards(self):
        cards = tk.Frame(self.main_frame, bg=self.BG_COLOR)
        cards.pack(fill="x", padx=10, pady=6)

        self.card_total = self._make_card(cards, "TOTAL ROUNDS", "0", self.BLUE)
        self.card_total.pack(side="left", fill="x", expand=True, padx=2)

        self.card_last = self._make_card(cards, "LAST RESULT", "--", self.GREEN)
        self.card_last.pack(side="left", fill="x", expand=True, padx=2)

        self.card_streak = self._make_card(cards, "STREAK", "--", "#d29922")
        self.card_streak.pack(side="left", fill="x", expand=True, padx=2)

        self.card_hot = self._make_card(cards, "HOT ITEM", "--", self.RED)
        self.card_hot.pack(side="left", fill="x", expand=True, padx=2)

    def _make_card(self, parent, title, value, accent):
        card = tk.Frame(parent, bg=self.CARD_BG)
        tk.Frame(card, bg=accent, height=3).pack(fill="x")
        tk.Label(card, text=title, font=("Segoe UI", 8, "bold"),
                 fg=self.TEXT_DIM, bg=self.CARD_BG).pack(pady=(6, 0))

        # Icon holder
        icon_label = tk.Label(card, bg=self.CARD_BG)
        icon_label.pack()
        card._icon_label = icon_label

        val = tk.Label(card, text=value, font=("Segoe UI", 16, "bold"),
                       fg=self.TEXT_COLOR, bg=self.CARD_BG)
        val.pack(pady=(0, 6))
        card._value_label = val
        return card

    # ===================== NEXT ROUND PREDICTION =====================
    def _build_prediction(self):
        section = tk.Frame(self.main_frame, bg=self.BG_COLOR)
        section.pack(fill="x", padx=10, pady=4)

        tk.Label(section, text="NEXT ROUND PROBABILITY",
                 font=("Segoe UI", 10, "bold"), fg="#c9d1d9",
                 bg=self.BG_COLOR, anchor="w").pack(fill="x", pady=(4, 2))

        pred_frame = tk.Frame(section, bg=self.CARD_BG, padx=10, pady=8)
        pred_frame.pack(fill="x")

        # Accent bar
        tk.Frame(pred_frame, bg="#8957e5", height=2).pack(fill="x", pady=(0, 6))

        # Top 3 prediction slots
        self.pred_slots = []
        slots_frame = tk.Frame(pred_frame, bg=self.CARD_BG)
        slots_frame.pack(fill="x")

        for i in range(3):
            slot = tk.Frame(slots_frame, bg=self.CARD_BG)
            slot.pack(side="left", fill="x", expand=True, padx=4)

            # Rank badge
            rank_colors = ["#FFD700", "#C0C0C0", "#CD7F32"]
            rank_labels = ["1st", "2nd", "3rd"]

            rank_lbl = tk.Label(slot, text=rank_labels[i],
                                font=("Segoe UI", 8, "bold"),
                                fg=rank_colors[i], bg=self.CARD_BG)
            rank_lbl.pack()

            # Icon
            icon_lbl = tk.Label(slot, bg=self.CARD_BG)
            icon_lbl.pack(pady=2)

            # Name
            name_lbl = tk.Label(slot, text="--",
                                font=("Segoe UI", 11, "bold"),
                                fg=self.TEXT_COLOR, bg=self.CARD_BG)
            name_lbl.pack()

            # Probability bar
            bar_outer = tk.Frame(slot, bg="#21262d", height=10, width=120)
            bar_outer.pack(pady=2)
            bar_outer.pack_propagate(False)
            bar_fill = tk.Frame(bar_outer, bg="#8957e5", height=10)
            bar_fill.place(x=0, y=0, relheight=1.0, width=0)

            # Percentage
            pct_lbl = tk.Label(slot, text="0%",
                               font=("Segoe UI", 14, "bold"),
                               fg="#8957e5", bg=self.CARD_BG)
            pct_lbl.pack()

            # Reason
            reason_lbl = tk.Label(slot, text="",
                                  font=("Segoe UI", 7),
                                  fg=self.TEXT_DIM, bg=self.CARD_BG,
                                  wraplength=130)
            reason_lbl.pack()

            self.pred_slots.append({
                "icon": icon_lbl, "name": name_lbl,
                "bar_outer": bar_outer, "bar_fill": bar_fill,
                "pct": pct_lbl, "reason": reason_lbl,
            })

        # Note
        tk.Label(pred_frame,
                 text="Based on frequency, recency, streaks & patterns (statistical estimate)",
                 font=("Segoe UI", 7), fg="#484f58", bg=self.CARD_BG).pack(pady=(6, 0))

    # ===================== RECENT RESULTS STRIP =====================
    def _build_recent_results(self):
        section = tk.Frame(self.main_frame, bg=self.BG_COLOR)
        section.pack(fill="x", padx=10, pady=4)

        hdr = tk.Frame(section, bg=self.BG_COLOR)
        hdr.pack(fill="x")
        tk.Label(hdr, text="RECENT RESULTS", font=("Segoe UI", 10, "bold"),
                 fg=self.GOLD, bg=self.BG_COLOR).pack(side="left")
        self.results_count_label = tk.Label(hdr, text="(0)",
                 font=("Segoe UI", 9), fg=self.TEXT_DIM, bg=self.BG_COLOR)
        self.results_count_label.pack(side="left", padx=5)

        self.strip_frame = tk.Frame(section, bg=self.CARD_BG, padx=6, pady=6)
        self.strip_frame.pack(fill="x", pady=2)

        self.strip_inner = tk.Frame(self.strip_frame, bg=self.CARD_BG)
        self.strip_inner.pack(fill="x")

        self.strip_placeholder = tk.Label(
            self.strip_inner, text="No results yet",
            font=("Segoe UI", 10), fg=self.TEXT_DIM, bg=self.CARD_BG
        )
        self.strip_placeholder.pack()

    # ===================== HOT / COLD =====================
    def _build_hot_cold(self):
        section = tk.Frame(self.main_frame, bg=self.BG_COLOR)
        section.pack(fill="x", padx=10, pady=4)

        row = tk.Frame(section, bg=self.BG_COLOR)
        row.pack(fill="x")

        # Hot
        hot_frame = tk.Frame(row, bg=self.CARD_BG, padx=10, pady=8)
        hot_frame.pack(side="left", fill="x", expand=True, padx=(0, 3))

        tk.Label(hot_frame, text="HOT (Last 20 rounds)",
                 font=("Segoe UI", 9, "bold"), fg="#f0883e",
                 bg=self.CARD_BG, anchor="w").pack(fill="x")
        self.hot_frame_inner = tk.Frame(hot_frame, bg=self.CARD_BG)
        self.hot_frame_inner.pack(fill="x", pady=3)

        # Cold
        cold_frame = tk.Frame(row, bg=self.CARD_BG, padx=10, pady=8)
        cold_frame.pack(side="left", fill="x", expand=True, padx=(3, 0))

        tk.Label(cold_frame, text="COLD (Missing last 50)",
                 font=("Segoe UI", 9, "bold"), fg=self.BLUE,
                 bg=self.CARD_BG, anchor="w").pack(fill="x")
        self.cold_frame_inner = tk.Frame(cold_frame, bg=self.CARD_BG)
        self.cold_frame_inner.pack(fill="x", pady=3)

    # ===================== STATS TABLE =====================
    def _build_stats_table(self):
        section = tk.Frame(self.main_frame, bg=self.BG_COLOR)
        section.pack(fill="x", padx=10, pady=4)

        tk.Label(section, text="ITEM STATISTICS",
                 font=("Segoe UI", 10, "bold"), fg=self.GOLD,
                 bg=self.BG_COLOR, anchor="w").pack(fill="x", pady=(4, 2))

        table = tk.Frame(section, bg=self.CARD_BG, padx=8, pady=6)
        table.pack(fill="x")

        # Configure columns
        table.columnconfigure(0, weight=0, minsize=40)   # Icon
        table.columnconfigure(1, weight=0, minsize=80)   # Name
        table.columnconfigure(2, weight=0, minsize=50)   # Count
        table.columnconfigure(3, weight=0, minsize=65)   # Pct
        table.columnconfigure(4, weight=1, minsize=150)  # Bar
        table.columnconfigure(5, weight=0, minsize=50)   # Mult
        table.columnconfigure(6, weight=0, minsize=60)   # Last seen

        # Headers
        for col, (text, anchor) in enumerate([
            ("", "center"), ("Item", "w"), ("Count", "center"),
            ("%", "center"), ("Distribution", "w"), ("Mult", "center"), ("Ago", "center")
        ]):
            tk.Label(table, text=text, font=("Segoe UI", 8, "bold"),
                     fg=self.TEXT_DIM, bg=self.CARD_BG, anchor=anchor
            ).grid(row=0, column=col, sticky="ew", padx=4, pady=2)

        self.stat_rows = {}
        for i, food in enumerate(FOOD_ITEMS, 1):
            d = FOOD_DISPLAY[food]

            # Icon
            icon_lbl = tk.Label(table, bg=self.CARD_BG)
            icon_img = self._get_icon(food, "table")
            if icon_img:
                icon_lbl.config(image=icon_img)
            else:
                icon_lbl.config(text=d["emoji"], font=("Segoe UI", 14))
            icon_lbl.grid(row=i, column=0, padx=4, pady=2)

            # Name
            tk.Label(table, text=d["name"], font=("Segoe UI", 10, "bold"),
                     fg=self.TEXT_COLOR, bg=self.CARD_BG, anchor="w"
            ).grid(row=i, column=1, sticky="w", padx=4, pady=2)

            # Count
            count_lbl = tk.Label(table, text="0", font=("Segoe UI", 10),
                                 fg=self.TEXT_COLOR, bg=self.CARD_BG, width=5)
            count_lbl.grid(row=i, column=2, padx=4, pady=2)

            # Percentage
            pct_lbl = tk.Label(table, text="0.0%", font=("Segoe UI", 10),
                               fg=self.TEXT_COLOR, bg=self.CARD_BG, width=6)
            pct_lbl.grid(row=i, column=3, padx=4, pady=2)

            # Bar
            bar_outer = tk.Frame(table, bg="#21262d", height=14)
            bar_outer.grid(row=i, column=4, sticky="ew", padx=4, pady=3)
            bar_outer.pack_propagate(False)

            bar_fill = tk.Frame(bar_outer, bg=d["color"], height=14)
            bar_fill.place(x=0, y=0, relheight=1.0, width=0)

            bar_pct_text = tk.Label(bar_outer, text="", font=("Segoe UI", 7),
                                    fg="white", bg=d["color"])

            # Multiplier
            mult_lbl = tk.Label(table, text=f"x{FOOD_MULTIPLIER[food]}",
                                font=("Segoe UI", 9, "bold"),
                                fg=self.GOLD, bg=self.CARD_BG)
            mult_lbl.grid(row=i, column=5, padx=4, pady=2)

            # Rounds ago
            ago_lbl = tk.Label(table, text="--", font=("Segoe UI", 9),
                               fg=self.TEXT_DIM, bg=self.CARD_BG, width=5)
            ago_lbl.grid(row=i, column=6, padx=4, pady=2)

            self.stat_rows[food] = {
                "count": count_lbl, "pct": pct_lbl,
                "bar_outer": bar_outer, "bar_fill": bar_fill,
                "bar_pct": bar_pct_text, "ago": ago_lbl,
            }

    # ===================== RESULT HISTORY =====================
    def _build_result_history(self):
        section = tk.Frame(self.main_frame, bg=self.BG_COLOR)
        section.pack(fill="x", padx=10, pady=4)

        tk.Label(section, text="RESULT HISTORY",
                 font=("Segoe UI", 10, "bold"), fg=self.GOLD,
                 bg=self.BG_COLOR, anchor="w").pack(fill="x", pady=(4, 2))

        hist_frame = tk.Frame(section, bg=self.CARD_BG, padx=6, pady=6)
        hist_frame.pack(fill="x")
        hist_frame.pack_propagate(False)
        hist_frame.config(height=220)

        self.history_text = tk.Text(
            hist_frame, bg=self.CARD_BG, fg=self.TEXT_COLOR,
            font=("Consolas", 10), relief="flat", wrap="word",
            state="disabled", insertbackground=self.TEXT_COLOR,
            selectbackground="#264f78"
        )
        hsb = tk.Scrollbar(hist_frame, orient="vertical", command=self.history_text.yview)
        self.history_text.configure(yscrollcommand=hsb.set)
        hsb.pack(side="right", fill="y")
        self.history_text.pack(fill="both", expand=True)

    # ===================== STATUS BAR =====================
    def _build_status_bar(self):
        status = tk.Frame(self.main_frame, bg="#010409", pady=4)
        status.pack(fill="x", padx=5, pady=(4, 5))

        self.status_label = tk.Label(
            status, text="Stopped", font=("Segoe UI", 8),
            fg=self.TEXT_DIM, bg="#010409", anchor="w"
        )
        self.status_label.pack(side="left", padx=8)

        self.time_label = tk.Label(
            status, text="", font=("Segoe UI", 8),
            fg=self.TEXT_DIM, bg="#010409"
        )
        self.time_label.pack(side="right", padx=8)

        self.scan_label = tk.Label(
            status, text="Scans: 0", font=("Segoe UI", 8),
            fg=self.TEXT_DIM, bg="#010409"
        )
        self.scan_label.pack(side="right", padx=8)

        # Diagnostic line — shows what the detector sees each scan
        self.diag_label = tk.Label(
            status, text="", font=("Consolas", 7),
            fg="#484f58", bg="#010409"
        )
        self.diag_label.pack(side="right", padx=8)

    # ================================================================
    #                      UPDATE / REFRESH
    # ================================================================

    def _refresh_stats(self):
        """Refresh all statistics displays."""
        stats = self.logger.get_statistics()
        total = stats["total"]

        # --- Summary cards ---
        self.card_total._value_label.config(text=str(total))

        if stats["last_result"]:
            food = stats["last_result"]
            d = FOOD_DISPLAY.get(food, {})
            self.card_last._value_label.config(text=d.get("name", food))
            icon = self._get_icon(food, "card")
            if icon:
                self.card_last._icon_label.config(image=icon)

        if stats["streaks"].get("current"):
            s = stats["streaks"]["current"]
            d = FOOD_DISPLAY.get(s["food"], {})
            self.card_streak._value_label.config(text=f"x{s['count']}")
            icon = self._get_icon(s["food"], "card")
            if icon:
                self.card_streak._icon_label.config(image=icon)

        if stats["recent_counts"]:
            hot = max(stats["recent_counts"], key=stats["recent_counts"].get)
            d = FOOD_DISPLAY.get(hot, {})
            hot_count = stats["recent_counts"][hot]
            self.card_hot._value_label.config(text=f"{d.get('name', hot)} ({hot_count})")
            icon = self._get_icon(hot, "card")
            if icon:
                self.card_hot._icon_label.config(image=icon)

        # --- Recent results strip (icon images) ---
        for w in self.strip_inner.winfo_children():
            w.destroy()

        recent = stats["recent_results"][-40:]  # Show last 40
        self.results_count_label.config(text=f"(Last {len(recent)})")

        if recent:
            # Display icons in a wrapping grid
            cols = 20
            for idx, food in enumerate(recent):
                r, c = divmod(idx, cols)
                icon = self._get_icon(food, "small")
                if icon:
                    lbl = tk.Label(self.strip_inner, image=icon, bg=self.CARD_BG)
                else:
                    d = FOOD_DISPLAY.get(food, {})
                    lbl = tk.Label(self.strip_inner, text=d.get("emoji", "?"),
                                   font=("Segoe UI", 12), bg=self.CARD_BG)
                lbl.grid(row=r, column=c, padx=1, pady=1)
        else:
            tk.Label(self.strip_inner, text="No results yet",
                     font=("Segoe UI", 10), fg=self.TEXT_DIM, bg=self.CARD_BG).pack()

        # --- Hot items ---
        for w in self.hot_frame_inner.winfo_children():
            w.destroy()
        if stats["recent_counts"]:
            sorted_hot = sorted(stats["recent_counts"].items(), key=lambda x: -x[1])
            for food, count in sorted_hot[:5]:
                item_frame = tk.Frame(self.hot_frame_inner, bg=self.CARD_BG)
                item_frame.pack(side="left", padx=4)
                icon = self._get_icon(food, "small")
                if icon:
                    tk.Label(item_frame, image=icon, bg=self.CARD_BG).pack(side="left")
                d = FOOD_DISPLAY.get(food, {})
                tk.Label(item_frame, text=f" {count}",
                         font=("Segoe UI", 10, "bold"), fg="#f0883e",
                         bg=self.CARD_BG).pack(side="left")

        # --- Cold items ---
        for w in self.cold_frame_inner.winfo_children():
            w.destroy()
        if stats["cold_items"]:
            for food in stats["cold_items"]:
                item_frame = tk.Frame(self.cold_frame_inner, bg=self.CARD_BG)
                item_frame.pack(side="left", padx=4)
                icon = self._get_icon(food, "small")
                if icon:
                    tk.Label(item_frame, image=icon, bg=self.CARD_BG).pack(side="left")
                d = FOOD_DISPLAY.get(food, {})
                tk.Label(item_frame, text=f" {d.get('name', food)}",
                         font=("Segoe UI", 9), fg=self.BLUE,
                         bg=self.CARD_BG).pack(side="left")
        else:
            tk.Label(self.cold_frame_inner, text="All items seen recently",
                     font=("Segoe UI", 9), fg=self.GREEN, bg=self.CARD_BG).pack(anchor="w")

        # --- Stats table ---
        max_count = max(stats["counts"].values()) if stats["counts"] else 1
        for food in FOOD_ITEMS:
            count = stats["counts"].get(food, 0)
            pct = (count / max(total, 1)) * 100
            row = self.stat_rows[food]
            row["count"].config(text=str(count))
            row["pct"].config(text=f"{pct:.1f}%")

            # Bar
            bar_width = int((count / max(max_count, 1)) * 250)
            row["bar_fill"].place(x=0, y=0, relheight=1.0, width=max(bar_width, 2))

            # Rounds ago
            ago = "--"
            for j, entry in enumerate(reversed(self.logger.results)):
                if entry["result"] == food:
                    ago = str(j)
                    break
            row["ago"].config(text=ago)

            # Color the "ago" by urgency
            if ago != "--":
                ago_val = int(ago)
                if ago_val == 0:
                    row["ago"].config(fg=self.GREEN)
                elif ago_val < 10:
                    row["ago"].config(fg=self.TEXT_COLOR)
                elif ago_val < 30:
                    row["ago"].config(fg="#d29922")
                else:
                    row["ago"].config(fg=self.RED)

        # --- History ---
        last_50 = self.logger.get_last_n_results(50)
        self.history_text.config(state="normal")
        self.history_text.delete("1.0", "end")
        for entry in reversed(last_50):
            food = entry["result"]
            d = FOOD_DISPLAY.get(food, {})
            emoji = d.get("emoji", "?")
            name = d.get("name", food)
            line = f" #{entry['round']:<8} {emoji} {name:<10}  {entry['time']}\n"
            self.history_text.insert("end", line)
        self.history_text.config(state="disabled")

        # --- Predictions ---
        top_preds = self.predictor.get_top_predictions(self.logger.results, n=3)
        for i, slot in enumerate(self.pred_slots):
            if i < len(top_preds):
                food, data = top_preds[i]
                d = FOOD_DISPLAY.get(food, {})
                icon = self._get_icon(food, "card")
                if icon:
                    slot["icon"].config(image=icon)
                slot["name"].config(text=d.get("name", food))
                prob = data["probability"]
                slot["pct"].config(text=f"{prob:.1f}%")
                # Bar width (max ~120px)
                bar_w = int((prob / 100) * 120)
                slot["bar_fill"].place(x=0, y=0, relheight=1.0, width=max(bar_w, 2))
                # Reasons
                reasons = data.get("reasons", [])
                slot["reason"].config(text=" | ".join(reasons[:2]))
            else:
                slot["name"].config(text="--")
                slot["pct"].config(text="0%")
                slot["reason"].config(text="")

        # --- Status ---
        self.time_label.config(text=datetime.now().strftime("%H:%M:%S"))
        self.scan_label.config(text=f"Scans: {self.scan_count}")

    # ================================================================
    #                      CALIBRATION
    # ================================================================

    def _calibrate(self):
        """
        One-click calibration: user clicks on the food icon center in the popup.
        The program saves those screen coordinates and uses a small crop
        around that point for all future detections.
        """
        if not self.capturer:
            messagebox.showwarning("No Capturer", "Screen capture module not available.")
            return

        # Stop monitoring if running
        was_monitoring = self.monitoring
        if was_monitoring:
            self.monitoring = False
            self.btn_monitor.config(text=" START MONITORING", bg="#238636")

        # Capture the full screen
        full_screen = self.capturer.capture_full_screen()
        if full_screen is None:
            messagebox.showerror("Error", "Could not capture screen.\nMake sure the game is visible.")
            return

        sh, sw = full_screen.shape[:2]

        # Create calibration window
        cal_win = tk.Toplevel(self.root)
        cal_win.title("Calibrate - Click on the Food Icon Center")
        cal_win.configure(bg="#0d1117")
        cal_win.attributes('-topmost', True)

        # Scale screenshot to fit in window
        max_w, max_h = min(sw, 1280), min(sh, 750)
        scale = min(max_w / sw, max_h / sh)
        display_w = int(sw * scale)
        display_h = int(sh * scale)

        # Instructions
        instr_frame = tk.Frame(cal_win, bg="#1a1a2e", padx=10, pady=8)
        instr_frame.pack(fill="x")

        tk.Label(instr_frame,
                 text="STEP 1: Make sure a result popup is visible in the game",
                 font=("Segoe UI", 11, "bold"), fg="#FFD700", bg="#1a1a2e",
                 anchor="w").pack(fill="x")
        tk.Label(instr_frame,
                 text="STEP 2: Click on the CENTER of the food icon in the popup below",
                 font=("Segoe UI", 11, "bold"), fg="#3fb950", bg="#1a1a2e",
                 anchor="w").pack(fill="x")
        tk.Label(instr_frame,
                 text="(The green rectangle shows the capture area that will be monitored)",
                 font=("Segoe UI", 9), fg="#8b949e", bg="#1a1a2e",
                 anchor="w").pack(fill="x")

        # Convert to PIL and display
        rgb = cv2.cvtColor(full_screen, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb)
        pil_img = pil_img.resize((display_w, display_h), Image.LANCZOS)
        tk_img = ImageTk.PhotoImage(pil_img)

        # Canvas with the screenshot
        canvas = tk.Canvas(cal_win, width=display_w, height=display_h,
                           cursor="crosshair", bg="#000000")
        canvas.pack(padx=5, pady=5)
        canvas.create_image(0, 0, anchor="nw", image=tk_img)
        canvas._img_ref = tk_img  # Prevent garbage collection

        # Track drawn items for cleanup
        drawn_items = []
        crop_size = self.settings.get("crop_size", 150)

        def on_click(event):
            # Convert display coordinates back to full screen coordinates
            screen_x = int(event.x / scale)
            screen_y = int(event.y / scale)

            # Clear previous drawn items
            for item in drawn_items:
                canvas.delete(item)
            drawn_items.clear()

            # Draw crop rectangle (green)
            half_disp = int(crop_size / 2 * scale)
            x1 = event.x - half_disp
            y1 = event.y - half_disp
            x2 = event.x + half_disp
            y2 = event.y + half_disp
            drawn_items.append(
                canvas.create_rectangle(x1, y1, x2, y2,
                                        outline="#00ff00", width=2, dash=(4, 2))
            )

            # Draw crosshair (red)
            drawn_items.append(
                canvas.create_line(event.x - 15, event.y, event.x + 15, event.y,
                                   fill="#ff0000", width=2)
            )
            drawn_items.append(
                canvas.create_line(event.x, event.y - 15, event.x, event.y + 15,
                                   fill="#ff0000", width=2)
            )

            # Draw coordinate label
            drawn_items.append(
                canvas.create_text(event.x + 20, event.y - 20,
                                   text=f"({screen_x}, {screen_y})",
                                   fill="#00ff00", font=("Consolas", 10, "bold"),
                                   anchor="nw")
            )

            # Try to identify what's at this position (verification)
            half = crop_size // 2
            cx = max(half, min(screen_x, sw - half))
            cy = max(half, min(screen_y, sh - half))
            test_crop = full_screen[cy - half:cy + half, cx - half:cx + half]

            verify_text = ""
            if self.detector and self.detector.is_ready and test_crop.size > 0:
                food, conf = self.detector.identify_icon(test_crop)
                if food:
                    d = FOOD_DISPLAY.get(food, {})
                    verify_text = f"Detected: {d.get('name', food)} ({conf:.0%})"
                    drawn_items.append(
                        canvas.create_text(event.x + 20, event.y + 5,
                                           text=verify_text,
                                           fill="#3fb950", font=("Segoe UI", 10, "bold"),
                                           anchor="nw")
                    )
                else:
                    drawn_items.append(
                        canvas.create_text(event.x + 20, event.y + 5,
                                           text="No match at this position",
                                           fill="#f85149", font=("Segoe UI", 9),
                                           anchor="nw")
                    )

            # Save coordinates
            self.settings["icon_center_x"] = screen_x
            self.settings["icon_center_y"] = screen_y
            self.settings["crop_size"] = crop_size
            self._save_settings()

        def on_confirm():
            ix = self.settings.get("icon_center_x", 0)
            iy = self.settings.get("icon_center_y", 0)
            if ix == 0 and iy == 0:
                messagebox.showwarning("Not Set",
                    "Please click on the food icon in the screenshot first.")
                return

            self._update_calibration_status()
            self.status_label.config(
                text=f"Calibrated: icon at ({ix}, {iy}), crop {crop_size}x{crop_size}px",
                fg=self.GREEN)
            cal_win.destroy()

            messagebox.showinfo("Calibration Complete",
                f"Icon position saved: ({ix}, {iy})\n"
                f"Crop region: {crop_size}x{crop_size} pixels\n\n"
                "Click START MONITORING to begin auto-detection.\n"
                "Keep the game window in the same position!")

        canvas.bind("<Button-1>", on_click)

        # Confirm button
        btn_frame = tk.Frame(cal_win, bg="#0d1117", pady=6)
        btn_frame.pack(fill="x")

        tk.Button(btn_frame, text="Confirm Calibration",
                  font=("Segoe UI", 11, "bold"),
                  bg="#238636", fg="white", relief="flat", padx=20, pady=6,
                  command=on_confirm, cursor="hand2").pack(side="left", padx=10)

        tk.Button(btn_frame, text="Cancel",
                  font=("Segoe UI", 10),
                  bg="#da3633", fg="white", relief="flat", padx=14, pady=6,
                  command=cal_win.destroy, cursor="hand2").pack(side="left", padx=5)

        # Crop size adjustment
        size_frame = tk.Frame(btn_frame, bg="#0d1117")
        size_frame.pack(side="right", padx=10)
        tk.Label(size_frame, text="Crop size:", font=("Segoe UI", 9),
                 fg=self.TEXT_DIM, bg="#0d1117").pack(side="left")

        size_var = tk.StringVar(value=str(crop_size))
        size_entry = tk.Entry(size_frame, textvariable=size_var,
                              font=("Segoe UI", 9), width=5)
        size_entry.pack(side="left", padx=3)
        tk.Label(size_frame, text="px", font=("Segoe UI", 9),
                 fg=self.TEXT_DIM, bg="#0d1117").pack(side="left")

        def update_crop_size(*args):
            nonlocal crop_size
            try:
                val = int(size_var.get())
                if 50 <= val <= 500:
                    crop_size = val
            except ValueError:
                pass

        size_var.trace_add("write", update_crop_size)

    # ================================================================
    #                      CAPTURE VERIFICATION
    # ================================================================

    def _verify_capture(self):
        """
        Verify that screen capture is working before starting monitoring.
        Tests both capture methods (mss and pyautogui) and shows the result.
        Auto-selects the working method.
        Returns True if user confirms capture looks correct.
        """
        ix = self.settings.get("icon_center_x", 0)
        iy = self.settings.get("icon_center_y", 0)
        crop_size = self.settings.get("crop_size", 150)
        half = crop_size // 2

        x = ix - half
        y = iy - half

        self.status_label.config(text="Testing capture methods...", fg="#d29922")
        self.root.update_idletasks()

        # Test both capture methods
        results = self.capturer.test_capture_methods(x, y, crop_size, crop_size)

        mss_img, mss_valid = results["mss"]
        pyag_img, pyag_valid = results["pyautogui"]

        # Save both for diagnostics
        debug_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "debug_captures")
        os.makedirs(debug_dir, exist_ok=True)
        if mss_img is not None:
            cv2.imwrite(os.path.join(debug_dir, "verify_mss.png"), mss_img)
        if pyag_img is not None:
            cv2.imwrite(os.path.join(debug_dir, "verify_pyautogui.png"), pyag_img)

        # Determine which method to use
        if mss_valid:
            self.capturer.use_fallback = False
            method_name = "mss (fast)"
            capture = mss_img
            method_note = ""
        elif pyag_valid:
            self.capturer.use_fallback = True
            method_name = "pyautogui (compatible)"
            capture = pyag_img
            method_note = ("NOTE: mss capture returned a black/invalid image.\n"
                           "Switched to pyautogui fallback (slightly slower but works).\n"
                           "This is normal for DirectX/OpenGL emulators like BlueStacks.")
        else:
            # Neither works
            messagebox.showerror("Capture Failed",
                "BOTH capture methods returned black or invalid images!\n\n"
                "The program CANNOT see the game screen at the calibrated position.\n\n"
                "Possible fixes:\n"
                "1. Make sure the game window is NOT minimized\n"
                "2. Make sure the result popup is visible on screen\n"
                "3. Try disabling hardware acceleration in BlueStacks:\n"
                "   Settings > Graphics > GPU Mode > Software\n"
                "4. Re-calibrate if the game window was moved or resized\n\n"
                f"Diagnostic images saved to:\n{debug_dir}")
            self.status_label.config(text="Capture verification FAILED", fg=self.RED)
            return False

        # --- Show verification dialog with the captured image ---
        verify_win = tk.Toplevel(self.root)
        verify_win.title("Capture Verification")
        verify_win.configure(bg="#0d1117")
        verify_win.transient(self.root)
        verify_win.grab_set()
        verify_win.attributes('-topmost', True)

        # Title
        tk.Label(verify_win,
                 text="CAPTURE VERIFICATION",
                 font=("Segoe UI", 14, "bold"), fg="#FFD700", bg="#0d1117"
        ).pack(pady=(10, 5))

        tk.Label(verify_win,
                 text=f"Capture method: {method_name}",
                 font=("Segoe UI", 10, "bold"), fg="#3fb950", bg="#0d1117"
        ).pack()

        if method_note:
            tk.Label(verify_win,
                     text=method_note,
                     font=("Segoe UI", 9), fg="#d29922", bg="#0d1117",
                     wraplength=500, justify="left"
            ).pack(padx=15, pady=3)

        tk.Label(verify_win,
                 text="This is what the program sees at the calibrated position:",
                 font=("Segoe UI", 10), fg="#8b949e", bg="#0d1117"
        ).pack(pady=(5, 8))

        # Show the captured crop (scaled up for visibility)
        display_size = 300
        rgb = cv2.cvtColor(capture, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb)
        pil_img = pil_img.resize((display_size, display_size), Image.NEAREST)
        tk_img = ImageTk.PhotoImage(pil_img)

        img_label = tk.Label(verify_win, image=tk_img, bg="#000000",
                             relief="solid", borderwidth=2)
        img_label.pack(padx=20, pady=5)
        img_label._img_ref = tk_img

        # Try detection on this capture
        if self.detector and self.detector.is_ready:
            food, conf = self.detector.identify_icon(capture)
            if food:
                d = FOOD_DISPLAY.get(food, {})
                detect_text = f"Detected: {d.get('name', food)} ({conf:.0%})"
                detect_color = "#3fb950"
            else:
                best = self.detector.last_best_food
                score = self.detector.last_best_score
                if best:
                    detect_text = f"No match yet (best: {best} at {score:.0%}, threshold: 35%)"
                else:
                    detect_text = "No match — popup may not be visible right now (that's OK)"
                detect_color = "#d29922"

            tk.Label(verify_win, text=detect_text,
                     font=("Segoe UI", 11, "bold"), fg=detect_color, bg="#0d1117"
            ).pack(pady=5)

        tk.Label(verify_win,
                 text="If the image shows the game area (not a black rectangle),\n"
                      "click 'Start Monitoring' to begin automatic detection.\n\n"
                      "A popup does NOT need to be visible right now — the program\n"
                      "will wait and detect popups as they appear.",
                 font=("Segoe UI", 9), fg="#8b949e", bg="#0d1117",
                 justify="center"
        ).pack(pady=5)

        result = {"confirmed": False}

        def on_start():
            result["confirmed"] = True
            verify_win.destroy()

        def on_cancel():
            verify_win.destroy()

        btn_frame = tk.Frame(verify_win, bg="#0d1117")
        btn_frame.pack(pady=10)

        tk.Button(btn_frame, text="Start Monitoring",
                  font=("Segoe UI", 11, "bold"),
                  bg="#238636", fg="white", relief="flat", padx=20, pady=6,
                  command=on_start, cursor="hand2"
        ).pack(side="left", padx=5)

        tk.Button(btn_frame, text="Cancel",
                  font=("Segoe UI", 10),
                  bg="#da3633", fg="white", relief="flat", padx=14, pady=6,
                  command=on_cancel, cursor="hand2"
        ).pack(side="left", padx=5)

        # Wait for dialog
        verify_win.wait_window()
        return result["confirmed"]

    # ================================================================
    #                      MONITORING
    # ================================================================

    def _toggle_monitoring(self):
        if self.monitoring:
            self.monitoring = False
            self.btn_monitor.config(text=" START MONITORING", bg="#238636")
            self.status_label.config(text="Stopped", fg=self.TEXT_DIM)
            self.preview_row.pack_forget()
        else:
            # Check calibration
            ix = self.settings.get("icon_center_x", 0)
            iy = self.settings.get("icon_center_y", 0)

            if ix == 0 or iy == 0:
                messagebox.showwarning("Not Calibrated",
                    "Please calibrate first!\n\n"
                    "1. Play a round so the result popup is visible\n"
                    "2. Click the 'Calibrate' button\n"
                    "3. Click on the food icon in the popup\n"
                    "4. Then start monitoring")
                return

            if self.detector and not self.detector.is_ready:
                messagebox.showwarning("No Templates",
                    "No icon templates loaded!\nAdd images to the 'templates/' folder.")
                return

            # Verify capture works before starting
            if not self._verify_capture():
                self.status_label.config(text="Monitoring cancelled", fg=self.TEXT_DIM)
                return

            # Apply settings to detector
            if self.detector:
                debug = self.settings.get("debug_saves", False)
                self.detector.debug_enabled = debug
                self.detector.save_all_scans = debug  # Save all scans when debug is ON
                self.detector.popup_active = False
                self.detector.consecutive_no_match = 0

            # Show live preview
            self.preview_row.pack(fill="x", pady=(4, 0))

            self.monitoring = True
            self.btn_monitor.config(text=" STOP MONITORING", bg="#da3633")
            self.status_label.config(
                text="MONITORING - Watching for results...", fg=self.GREEN)
            self._start_monitor_thread()

    def _start_monitor_thread(self):
        def loop():
            while self.monitoring:
                try:
                    self._scan_once()
                except Exception as e:
                    print(f"Scan error: {e}")
                time.sleep(self.settings.get("interval", 1.5))
        self.monitor_thread = threading.Thread(target=loop, daemon=True)
        self.monitor_thread.start()

    def _scan_once(self):
        """
        Capture the small calibrated crop and detect the food icon.
        State-machine approach: always tries to identify, logs once per popup.
        Updates the live preview with every scan.
        """
        if not self.capturer or not self.detector:
            return

        ix = self.settings.get("icon_center_x", 0)
        iy = self.settings.get("icon_center_y", 0)
        crop_size = self.settings.get("crop_size", 150)

        if ix == 0 or iy == 0:
            return

        # Capture a small region centered on the calibrated icon position
        half = crop_size // 2
        crop = self.capturer.capture_region(
            ix - half, iy - half, crop_size, crop_size)

        if crop is None:
            self.root.after(0, lambda: self.diag_label.config(text="Capture failed"))
            return

        self.scan_count += 1

        # Auto-save first 20 scans for diagnostics (always, no checkbox needed)
        if self.scan_count <= 20:
            debug_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "debug_captures")
            os.makedirs(debug_dir, exist_ok=True)
            cv2.imwrite(os.path.join(debug_dir, f"auto_scan_{self.scan_count:03d}.png"), crop)

        # Save crop for preview (thread-safe: just save reference)
        self.latest_crop = crop.copy()

        # Run detection (state machine handles logging logic)
        food_name, confidence = self.detector.scan_crop(crop)

        # Update preview and diagnostics on main thread
        self.root.after(0, self._update_preview)
        diag_text = self.detector.last_scan_info
        self.root.after(0, lambda t=diag_text: self.diag_label.config(text=t))

        if food_name:
            self.logger.add_result(food_name, confidence=confidence)
            self.root.after(0, self._refresh_stats)
            d = FOOD_DISPLAY.get(food_name, {})
            self.root.after(0, lambda fn=food_name, c=confidence: self.status_label.config(
                text=f"Round {self.logger.total_rounds}: "
                     f"{FOOD_DISPLAY.get(fn, {}).get('name', fn)} ({c:.0%})",
                fg=self.GREEN))

    def _toggle_debug(self):
        """Toggle debug capture saving."""
        enabled = self.debug_var.get()
        self.settings["debug_saves"] = enabled
        self._save_settings()
        if self.detector:
            self.detector.debug_enabled = enabled
        self.status_label.config(
            text=f"Debug saves: {'ON' if enabled else 'OFF'}")

    # ================================================================
    #                      OTHER ACTIONS
    # ================================================================

    def _manual_add(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Result")
        dialog.geometry("300x520")
        dialog.configure(bg=self.BG_COLOR)
        dialog.transient(self.root)
        dialog.grab_set()

        tk.Label(dialog, text="Select Result:",
                 font=("Segoe UI", 12, "bold"), fg=self.TEXT_COLOR,
                 bg=self.BG_COLOR).pack(pady=10)

        for food in FOOD_ITEMS:
            d = FOOD_DISPLAY[food]
            btn_frame = tk.Frame(dialog, bg=self.CARD_BG)
            btn_frame.pack(fill="x", padx=12, pady=2)

            icon = self._get_icon(food, "button")

            btn = tk.Button(
                btn_frame,
                text=f"  {d['name']}  (x{FOOD_MULTIPLIER[food]})",
                font=("Segoe UI", 11), compound="left",
                bg=self.CARD_BG, fg=self.TEXT_COLOR,
                activebackground=d["color"], activeforeground="white",
                relief="flat", pady=4, anchor="w", cursor="hand2",
                command=lambda f=food, dlg=dialog: self._do_manual_add(f, dlg)
            )
            if icon:
                btn.config(image=icon)
                btn.image = icon
            btn.pack(fill="x")

    def _do_manual_add(self, food, dialog):
        self.logger.add_result(food, confidence=1.0)
        dialog.destroy()
        self._refresh_stats()
        d = FOOD_DISPLAY[food]

        # Auto-learn: if monitoring is active and we have a crop, save as reference
        if self.monitoring and self.latest_crop is not None and self.detector:
            self.detector.save_reference(food, self.latest_crop)
            self.status_label.config(
                text=f"Added + learned: {d['name']} (saved reference crop)")
        else:
            self.status_label.config(text=f"Added: {d['name']}")

    def _test_capture(self):
        """
        Test BOTH capture methods on the calibrated region.
        Shows detailed diagnostics about what each method captures.
        """
        if not self.capturer:
            messagebox.showwarning("No Capturer", "Screen capture not available.")
            return

        ix = self.settings.get("icon_center_x", 0)
        iy = self.settings.get("icon_center_y", 0)
        crop_size = self.settings.get("crop_size", 150)

        if ix == 0 or iy == 0:
            messagebox.showwarning("Not Calibrated",
                "Please calibrate first by clicking the 'Calibrate' button.")
            return

        half = crop_size // 2
        x, y = ix - half, iy - half

        # Test both methods
        results = self.capturer.test_capture_methods(x, y, crop_size, crop_size)

        debug_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "debug_captures")
        os.makedirs(debug_dir, exist_ok=True)

        result_msg = f"Capture position: centered at ({ix}, {iy}), crop {crop_size}x{crop_size}\n\n"

        for method_name, (img, valid) in results.items():
            status = "VALID" if valid else "INVALID (black/uniform)"
            result_msg += f"--- {method_name} ---\n"
            result_msg += f"  Status: {status}\n"

            if img is not None:
                path = os.path.join(debug_dir, f"test_{method_name}.png")
                cv2.imwrite(path, img)
                result_msg += f"  Size: {img.shape[1]}x{img.shape[0]}\n"

                import numpy as np
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                result_msg += f"  Mean brightness: {np.mean(gray):.1f}\n"
                result_msg += f"  Std deviation: {np.std(gray):.1f}\n"

                if valid and self.detector and self.detector.is_ready:
                    food, conf = self.detector.identify_icon(img)
                    if food:
                        d = FOOD_DISPLAY.get(food, {})
                        result_msg += f"  Detection: {d.get('name', food)} ({conf:.1%})\n"
                    else:
                        result_msg += f"  Detection: no match\n"

                result_msg += f"  Saved to: {path}\n"
            else:
                result_msg += f"  Capture returned None (error)\n"
            result_msg += "\n"

        # Current method
        current = "pyautogui (fallback)" if self.capturer.use_fallback else "mss (default)"
        result_msg += f"Current method: {current}\n"
        result_msg += f"\nCheck the debug_captures/ folder for saved images."

        messagebox.showinfo("Capture Test Results", result_msg)
        self.status_label.config(text="Test complete — check results")

    def _clear_all(self):
        if not self.logger.results:
            return
        if messagebox.askyesno("Clear All", "Delete all recorded results?"):
            self.logger.results.clear()
            self.logger._save_json()
            # Also clear CSV
            if os.path.exists(self.logger.csv_path):
                os.remove(self.logger.csv_path)
            self._refresh_stats()
            self.status_label.config(text="All results cleared")

    def _export_excel(self):
        try:
            self.logger.save_excel()
            self.status_label.config(text=f"Saved: {self.logger.excel_path}")
            messagebox.showinfo("Exported", f"Results saved to:\n{self.logger.excel_path}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def run(self):
        def auto_refresh():
            if self.root.winfo_exists():
                self._refresh_stats()
                self.root.after(5000, auto_refresh)
        self.root.after(5000, auto_refresh)
        self.root.mainloop()
