"""
Statistics GUI for Greedy Cat Result Logger v2
Shows history as game icons, hot/cold items, percentages, streaks.
Dark theme matching reference software style.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import os
import threading
import time
import json
from datetime import datetime
from PIL import Image, ImageTk
from config import FOOD_ITEMS, FOOD_DISPLAY, FOOD_MULTIPLIER, TEMPLATES_DIR


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
        self.previous_strip_hash = ""
        self.scan_count = 0

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

    def _load_settings(self):
        """Load saved settings."""
        defaults = {"region_x": 0, "region_y": 0, "region_w": 450, "region_h": 50, "interval": 2.0}
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
        self._build_summary_cards()
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
        tk.Label(title_frame, text="Real-time auto-detection & statistics",
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
            ctrl, text="Set Region", font=("Segoe UI", 9),
            bg="#30363d", fg=self.TEXT_COLOR, relief="flat", padx=10, pady=5,
            command=self._set_region, cursor="hand2",
            activebackground="#484f58"
        ).pack(side="left", padx=3)

        tk.Button(
            ctrl, text="+ Manual Add", font=("Segoe UI", 9),
            bg="#1f6feb", fg="white", relief="flat", padx=10, pady=5,
            command=self._manual_add, cursor="hand2",
            activebackground="#388bfd"
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

        # --- Status ---
        self.time_label.config(text=datetime.now().strftime("%H:%M:%S"))
        self.scan_label.config(text=f"Scans: {self.scan_count}")

    # ================================================================
    #                      CONTROL ACTIONS
    # ================================================================

    def _toggle_monitoring(self):
        if self.monitoring:
            self.monitoring = False
            self.btn_monitor.config(text=" START MONITORING", bg="#238636")
            self.status_label.config(text="Stopped", fg=self.TEXT_DIM)
        else:
            if self.detector and not self.detector.is_ready:
                messagebox.showwarning("No Templates",
                    "No icon templates loaded!\nAdd images to the 'templates/' folder.")
                return
            if self.capturer and self.capturer.result_region is None:
                # Apply saved region
                s = self.settings
                self.capturer.set_result_region(
                    s["region_x"], s["region_y"], s["region_w"], s["region_h"])

            self.monitoring = True
            self.btn_monitor.config(text=" STOP MONITORING", bg="#da3633")
            self.status_label.config(text="MONITORING ACTIVE", fg=self.GREEN)
            self._start_monitor_thread()

    def _start_monitor_thread(self):
        def loop():
            while self.monitoring:
                try:
                    self._scan_once()
                except Exception as e:
                    print(f"Scan error: {e}")
                time.sleep(self.settings.get("interval", 2.0))
        self.monitor_thread = threading.Thread(target=loop, daemon=True)
        self.monitor_thread.start()

    def _scan_once(self):
        if not self.capturer or not self.detector:
            return

        img = self.capturer.capture_result_strip()
        if img is None:
            return

        self.scan_count += 1

        # Detect all icons in the result strip
        results = self.detector.detect_result_row(img)
        if not results:
            return

        # Create a hash of current results to detect changes
        current_hash = "|".join(results)
        if current_hash == self.previous_strip_hash:
            return  # No change

        # Find new results (compare with previous)
        if self.previous_strip_hash:
            prev_list = self.previous_strip_hash.split("|")
            # New items appear at the end (right side)
            if len(results) > len(prev_list):
                new_items = results[len(prev_list):]
            elif results != prev_list:
                # Results shifted: new one at end, oldest dropped
                new_items = [results[-1]]
            else:
                new_items = []
        else:
            # First scan — only take the last result to avoid logging old history
            new_items = [results[-1]] if results else []

        self.previous_strip_hash = current_hash

        for food in new_items:
            self.logger.add_result(food, confidence=0.9)

        self.root.after(0, self._refresh_stats)

    def _set_region(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Set Capture Region")
        dialog.geometry("380x320")
        dialog.configure(bg=self.BG_COLOR)
        dialog.transient(self.root)
        dialog.grab_set()

        tk.Label(dialog, text="Capture Region (Result Row)",
                 font=("Segoe UI", 12, "bold"), fg=self.TEXT_COLOR,
                 bg=self.BG_COLOR).pack(pady=10)

        tk.Label(dialog,
                 text="Enter the pixel coordinates of the\nResult row in the Xena/emulator window.\n\n"
                      "Use a screenshot tool to measure\nX, Y, Width, Height of the result area.",
                 font=("Segoe UI", 9), fg=self.TEXT_DIM,
                 bg=self.BG_COLOR, justify="center").pack(pady=5)

        fields = tk.Frame(dialog, bg=self.BG_COLOR)
        fields.pack(pady=10)

        entries = {}
        s = self.settings
        for i, (label, key, default) in enumerate([
            ("X:", "region_x", s["region_x"]),
            ("Y:", "region_y", s["region_y"]),
            ("Width:", "region_w", s["region_w"]),
            ("Height:", "region_h", s["region_h"]),
        ]):
            tk.Label(fields, text=label, font=("Segoe UI", 10),
                     fg=self.TEXT_COLOR, bg=self.BG_COLOR, width=8).grid(row=i, column=0, padx=5, pady=3)
            entry = tk.Entry(fields, font=("Segoe UI", 10), width=10)
            entry.insert(0, str(default))
            entry.grid(row=i, column=1, padx=5, pady=3)
            entries[key] = entry

        def apply():
            try:
                vals = {k: int(e.get()) for k, e in entries.items()}
                self.settings.update(vals)
                self._save_settings()
                if self.capturer:
                    self.capturer.set_result_region(
                        vals["region_x"], vals["region_y"],
                        vals["region_w"], vals["region_h"])
                self.status_label.config(
                    text=f"Region: ({vals['region_x']},{vals['region_y']}) "
                         f"{vals['region_w']}x{vals['region_h']}")
                dialog.destroy()
            except ValueError:
                messagebox.showerror("Error", "Please enter valid numbers.")

        tk.Button(dialog, text="Apply", font=("Segoe UI", 10, "bold"),
                  bg="#238636", fg="white", relief="flat", padx=20, pady=5,
                  command=apply).pack(pady=10)

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
        self.status_label.config(text=f"Added: {d['name']}")

    def _clear_all(self):
        if not self.logger.results:
            return
        if messagebox.askyesno("Clear All", "Delete all recorded results?"):
            self.logger.results.clear()
            self.logger._save_json()
            # Also clear CSV
            import os
            if os.path.exists(self.logger.csv_path):
                os.remove(self.logger.csv_path)
            self.previous_strip_hash = ""
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
