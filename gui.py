"""
Statistics GUI for Greedy Cat Result Logger
Shows history, hot items, percentages, streaks, and recent results.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import threading
import time
from datetime import datetime
from config import FOOD_ITEMS, FOOD_DISPLAY, FOOD_MULTIPLIER


class StatsGUI:
    """Main statistics window for the Greedy Cat Result Logger."""

    BG_COLOR = "#1a1a2e"
    CARD_BG = "#16213e"
    HEADER_BG = "#0f3460"
    ACCENT = "#e94560"
    TEXT_COLOR = "#ffffff"
    TEXT_DIM = "#a0a0b0"
    GOLD = "#FFD700"

    def __init__(self, logger, detector=None, capturer=None):
        self.logger = logger
        self.detector = detector
        self.capturer = capturer
        self.monitoring = False
        self.monitor_thread = None
        self.previous_results = []

        self.root = tk.Tk()
        self.root.title("🐱 Greedy Cat Result Logger")
        self.root.geometry("820x900")
        self.root.configure(bg=self.BG_COLOR)
        self.root.resizable(True, True)

        # Set minimum size
        self.root.minsize(750, 700)

        self._build_gui()
        self._refresh_stats()

    def _build_gui(self):
        """Build the complete GUI layout."""
        # Main scrollable frame
        main_canvas = tk.Canvas(self.root, bg=self.BG_COLOR, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=main_canvas.yview)
        self.main_frame = tk.Frame(main_canvas, bg=self.BG_COLOR)

        self.main_frame.bind(
            "<Configure>",
            lambda e: main_canvas.configure(scrollregion=main_canvas.bbox("all"))
        )
        main_canvas.create_window((0, 0), window=self.main_frame, anchor="nw")
        main_canvas.configure(yscrollcommand=scrollbar.set)

        main_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Enable mouse wheel scrolling
        def _on_mousewheel(event):
            main_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        main_canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # ===== HEADER =====
        self._build_header()

        # ===== CONTROL BAR =====
        self._build_controls()

        # ===== SUMMARY CARDS =====
        self._build_summary_cards()

        # ===== RECENT RESULTS (Icon Strip) =====
        self._build_recent_results()

        # ===== HOT / COLD ITEMS =====
        self._build_hot_cold()

        # ===== STATISTICS TABLE =====
        self._build_stats_table()

        # ===== LAST RESULTS LIST =====
        self._build_result_history()

        # ===== STATUS BAR =====
        self._build_status_bar()

    def _build_header(self):
        header = tk.Frame(self.main_frame, bg=self.HEADER_BG, pady=12)
        header.pack(fill="x", padx=5, pady=(5, 0))

        tk.Label(
            header, text="🐱 GREEDY CAT RESULT LOGGER",
            font=("Segoe UI", 18, "bold"), fg=self.GOLD, bg=self.HEADER_BG
        ).pack()

        tk.Label(
            header, text="Real-time game result tracking & statistics",
            font=("Segoe UI", 10), fg=self.TEXT_DIM, bg=self.HEADER_BG
        ).pack()

    def _build_controls(self):
        ctrl = tk.Frame(self.main_frame, bg=self.BG_COLOR, pady=8)
        ctrl.pack(fill="x", padx=10)

        self.btn_monitor = tk.Button(
            ctrl, text="▶ START MONITORING", font=("Segoe UI", 11, "bold"),
            bg="#28a745", fg="white", relief="flat", padx=20, pady=6,
            command=self._toggle_monitoring, cursor="hand2"
        )
        self.btn_monitor.pack(side="left", padx=5)

        tk.Button(
            ctrl, text="📁 Set Region", font=("Segoe UI", 10),
            bg="#6c757d", fg="white", relief="flat", padx=12, pady=6,
            command=self._set_region, cursor="hand2"
        ).pack(side="left", padx=5)

        tk.Button(
            ctrl, text="➕ Manual Add", font=("Segoe UI", 10),
            bg="#17a2b8", fg="white", relief="flat", padx=12, pady=6,
            command=self._manual_add, cursor="hand2"
        ).pack(side="left", padx=5)

        tk.Button(
            ctrl, text="💾 Export Excel", font=("Segoe UI", 10),
            bg="#ffc107", fg="black", relief="flat", padx=12, pady=6,
            command=self._export_excel, cursor="hand2"
        ).pack(side="right", padx=5)

        tk.Button(
            ctrl, text="🔄 Refresh", font=("Segoe UI", 10),
            bg="#6c757d", fg="white", relief="flat", padx=12, pady=6,
            command=self._refresh_stats, cursor="hand2"
        ).pack(side="right", padx=5)

    def _build_summary_cards(self):
        """Build the top summary cards row."""
        cards_frame = tk.Frame(self.main_frame, bg=self.BG_COLOR)
        cards_frame.pack(fill="x", padx=10, pady=5)

        # Total Rounds
        self.card_total = self._make_card(cards_frame, "Total Rounds", "0", self.ACCENT)
        self.card_total.pack(side="left", fill="x", expand=True, padx=3)

        # Last Result
        self.card_last = self._make_card(cards_frame, "Last Result", "--", "#4CAF50")
        self.card_last.pack(side="left", fill="x", expand=True, padx=3)

        # Current Streak
        self.card_streak = self._make_card(cards_frame, "Current Streak", "--", "#FF9800")
        self.card_streak.pack(side="left", fill="x", expand=True, padx=3)

        # Hot Item
        self.card_hot = self._make_card(cards_frame, "🔥 Hot Item", "--", "#F44336")
        self.card_hot.pack(side="left", fill="x", expand=True, padx=3)

    def _make_card(self, parent, title, value, accent_color):
        card = tk.Frame(parent, bg=self.CARD_BG, relief="flat", bd=0)

        # Accent bar on top
        tk.Frame(card, bg=accent_color, height=3).pack(fill="x")

        tk.Label(
            card, text=title, font=("Segoe UI", 9), fg=self.TEXT_DIM, bg=self.CARD_BG
        ).pack(pady=(8, 0))

        value_label = tk.Label(
            card, text=value, font=("Segoe UI", 20, "bold"), fg=self.TEXT_COLOR, bg=self.CARD_BG
        )
        value_label.pack(pady=(0, 8))

        card._value_label = value_label
        return card

    def _build_recent_results(self):
        """Build the recent results icon strip."""
        section = tk.Frame(self.main_frame, bg=self.BG_COLOR)
        section.pack(fill="x", padx=10, pady=5)

        tk.Label(
            section, text="📋 RECENT RESULTS (Last 30)",
            font=("Segoe UI", 11, "bold"), fg=self.GOLD, bg=self.BG_COLOR, anchor="w"
        ).pack(fill="x", pady=(5, 3))

        self.results_strip = tk.Frame(section, bg=self.CARD_BG, padx=8, pady=8)
        self.results_strip.pack(fill="x")

        self.strip_label = tk.Label(
            self.results_strip, text="No results yet — start monitoring or add manually",
            font=("Segoe UI", 10), fg=self.TEXT_DIM, bg=self.CARD_BG, wraplength=700
        )
        self.strip_label.pack()

    def _build_hot_cold(self):
        """Build hot and cold items section."""
        section = tk.Frame(self.main_frame, bg=self.BG_COLOR)
        section.pack(fill="x", padx=10, pady=5)

        # Hot items
        hot_frame = tk.Frame(section, bg=self.CARD_BG, padx=10, pady=8)
        hot_frame.pack(fill="x", pady=2)

        tk.Label(
            hot_frame, text="🔥 HOT ITEMS (Last 20 rounds)",
            font=("Segoe UI", 10, "bold"), fg="#FF5722", bg=self.CARD_BG, anchor="w"
        ).pack(fill="x")

        self.hot_items_label = tk.Label(
            hot_frame, text="--", font=("Segoe UI", 12),
            fg=self.TEXT_COLOR, bg=self.CARD_BG, anchor="w", wraplength=700
        )
        self.hot_items_label.pack(fill="x", pady=3)

        # Cold items
        cold_frame = tk.Frame(section, bg=self.CARD_BG, padx=10, pady=8)
        cold_frame.pack(fill="x", pady=2)

        tk.Label(
            cold_frame, text="❄️ COLD ITEMS (Not seen in last 50)",
            font=("Segoe UI", 10, "bold"), fg="#2196F3", bg=self.CARD_BG, anchor="w"
        ).pack(fill="x")

        self.cold_items_label = tk.Label(
            cold_frame, text="--", font=("Segoe UI", 12),
            fg=self.TEXT_COLOR, bg=self.CARD_BG, anchor="w", wraplength=700
        )
        self.cold_items_label.pack(fill="x", pady=3)

    def _build_stats_table(self):
        """Build the statistics percentage table."""
        section = tk.Frame(self.main_frame, bg=self.BG_COLOR)
        section.pack(fill="x", padx=10, pady=5)

        tk.Label(
            section, text="📊 ITEM STATISTICS",
            font=("Segoe UI", 11, "bold"), fg=self.GOLD, bg=self.BG_COLOR, anchor="w"
        ).pack(fill="x", pady=(5, 3))

        table_frame = tk.Frame(section, bg=self.CARD_BG, padx=10, pady=8)
        table_frame.pack(fill="x")

        # Header row
        headers = ["Item", "Count", "Percentage", "Bar", "Multiplier"]
        for col, header in enumerate(headers):
            tk.Label(
                table_frame, text=header, font=("Segoe UI", 9, "bold"),
                fg=self.TEXT_DIM, bg=self.CARD_BG, anchor="w"
            ).grid(row=0, column=col, sticky="w", padx=8, pady=3)

        self.stat_rows = {}
        for row_idx, food in enumerate(FOOD_ITEMS, 1):
            display = FOOD_DISPLAY[food]

            # Icon + Name
            name_label = tk.Label(
                table_frame, text=f"{display['emoji']} {display['name']}",
                font=("Segoe UI", 11), fg=self.TEXT_COLOR, bg=self.CARD_BG, anchor="w"
            )
            name_label.grid(row=row_idx, column=0, sticky="w", padx=8, pady=2)

            # Count
            count_label = tk.Label(
                table_frame, text="0", font=("Segoe UI", 11),
                fg=self.TEXT_COLOR, bg=self.CARD_BG, anchor="center", width=6
            )
            count_label.grid(row=row_idx, column=1, padx=8, pady=2)

            # Percentage
            pct_label = tk.Label(
                table_frame, text="0.0%", font=("Segoe UI", 11),
                fg=self.TEXT_COLOR, bg=self.CARD_BG, anchor="center", width=8
            )
            pct_label.grid(row=row_idx, column=2, padx=8, pady=2)

            # Progress bar
            bar_frame = tk.Frame(table_frame, bg="#333333", width=200, height=16)
            bar_frame.grid(row=row_idx, column=3, padx=8, pady=2, sticky="w")
            bar_frame.pack_propagate(False)

            bar_fill = tk.Frame(bar_frame, bg=display["color"], height=16)
            bar_fill.place(x=0, y=0, relheight=1.0, width=0)

            # Multiplier
            mult_label = tk.Label(
                table_frame, text=f"x{FOOD_MULTIPLIER[food]}",
                font=("Segoe UI", 10), fg=self.GOLD, bg=self.CARD_BG, anchor="center"
            )
            mult_label.grid(row=row_idx, column=4, padx=8, pady=2)

            self.stat_rows[food] = {
                "count": count_label,
                "pct": pct_label,
                "bar_frame": bar_frame,
                "bar_fill": bar_fill,
            }

    def _build_result_history(self):
        """Build the scrollable result history list."""
        section = tk.Frame(self.main_frame, bg=self.BG_COLOR)
        section.pack(fill="x", padx=10, pady=5)

        tk.Label(
            section, text="📜 RESULT HISTORY (Last 50)",
            font=("Segoe UI", 11, "bold"), fg=self.GOLD, bg=self.BG_COLOR, anchor="w"
        ).pack(fill="x", pady=(5, 3))

        history_frame = tk.Frame(section, bg=self.CARD_BG, padx=8, pady=8, height=200)
        history_frame.pack(fill="x")
        history_frame.pack_propagate(False)

        self.history_text = tk.Text(
            history_frame, bg=self.CARD_BG, fg=self.TEXT_COLOR,
            font=("Consolas", 10), relief="flat", wrap="word",
            state="disabled", height=10
        )
        self.history_text.pack(fill="both", expand=True)

    def _build_status_bar(self):
        """Build the bottom status bar."""
        status = tk.Frame(self.main_frame, bg="#0d1117", pady=5)
        status.pack(fill="x", padx=5, pady=(5, 5))

        self.status_label = tk.Label(
            status, text="⏸ Stopped — Click 'START MONITORING' to begin",
            font=("Segoe UI", 9), fg=self.TEXT_DIM, bg="#0d1117", anchor="w"
        )
        self.status_label.pack(side="left", padx=10)

        self.time_label = tk.Label(
            status, text="", font=("Segoe UI", 9), fg=self.TEXT_DIM, bg="#0d1117"
        )
        self.time_label.pack(side="right", padx=10)

    # ===== UPDATE METHODS =====

    def _refresh_stats(self):
        """Refresh all statistics displays."""
        stats = self.logger.get_statistics()

        # Summary cards
        self.card_total._value_label.config(text=str(stats["total"]))

        if stats["last_result"]:
            food = stats["last_result"]
            d = FOOD_DISPLAY.get(food, {})
            self.card_last._value_label.config(
                text=f"{d.get('emoji', '')} {d.get('name', food)}"
            )

        if stats["streaks"].get("current"):
            s = stats["streaks"]["current"]
            d = FOOD_DISPLAY.get(s["food"], {})
            self.card_streak._value_label.config(
                text=f"{d.get('emoji', '')} x{s['count']}"
            )

        # Hot item (most frequent in last 20)
        if stats["recent_counts"]:
            hot = max(stats["recent_counts"], key=stats["recent_counts"].get)
            d = FOOD_DISPLAY.get(hot, {})
            self.card_hot._value_label.config(
                text=f"{d.get('emoji', '')} {d.get('name', hot)}"
            )

        # Recent results strip
        if stats["recent_results"]:
            emojis = []
            for food in stats["recent_results"]:
                d = FOOD_DISPLAY.get(food, {})
                emojis.append(d.get("emoji", "❓"))
            self.strip_label.config(text="  ".join(emojis))

        # Hot items
        if stats["recent_counts"]:
            hot_text = "  ".join(
                f"{FOOD_DISPLAY.get(f, {}).get('emoji', '')} {f}: {c}"
                for f, c in sorted(stats["recent_counts"].items(), key=lambda x: -x[1])
            )
            self.hot_items_label.config(text=hot_text)

        # Cold items
        if stats["cold_items"]:
            cold_text = "  ".join(
                f"{FOOD_DISPLAY.get(f, {}).get('emoji', '')} {FOOD_DISPLAY.get(f, {}).get('name', f)}"
                for f in stats["cold_items"]
            )
            self.cold_items_label.config(text=cold_text)
        else:
            self.cold_items_label.config(text="All items seen recently ✓")

        # Stats table
        total = max(stats["total"], 1)
        for food in FOOD_ITEMS:
            count = stats["counts"].get(food, 0)
            pct = (count / total) * 100

            row = self.stat_rows[food]
            row["count"].config(text=str(count))
            row["pct"].config(text=f"{pct:.1f}%")

            # Update bar width (max 200px)
            bar_width = int((pct / 100) * 200)
            row["bar_fill"].place(x=0, y=0, relheight=1.0, width=max(bar_width, 1))

        # History
        last_50 = self.logger.get_last_n_results(50)
        self.history_text.config(state="normal")
        self.history_text.delete("1.0", "end")
        for entry in reversed(last_50):
            food = entry["result"]
            d = FOOD_DISPLAY.get(food, {})
            line = f"  #{entry['round']:>5}  {d.get('emoji', '❓')} {d.get('name', food):<10}  {entry['time']}\n"
            self.history_text.insert("end", line)
        self.history_text.config(state="disabled")

        # Update time
        self.time_label.config(text=datetime.now().strftime("%H:%M:%S"))

    # ===== CONTROL METHODS =====

    def _toggle_monitoring(self):
        """Start or stop automatic monitoring."""
        if self.monitoring:
            self.monitoring = False
            self.btn_monitor.config(text="▶ START MONITORING", bg="#28a745")
            self.status_label.config(text="⏸ Monitoring stopped")
        else:
            if self.detector and not self.detector.is_ready:
                messagebox.showwarning(
                    "No Templates",
                    "No icon templates loaded!\n\n"
                    "Please add template images to the 'templates/' folder.\n"
                    "Each food item needs a subfolder or image file.\n\n"
                    "Example: templates/tomato.png, templates/carrot.png"
                )
                return
            if self.capturer and self.capturer.result_region is None:
                messagebox.showwarning(
                    "No Region Set",
                    "Please set the screen capture region first.\n"
                    "Click '📁 Set Region' to define the Result row area."
                )
                return

            self.monitoring = True
            self.btn_monitor.config(text="⏹ STOP MONITORING", bg="#dc3545")
            self.status_label.config(text="🔴 Monitoring active — scanning every 2 seconds...")
            self._start_monitor_thread()

    def _start_monitor_thread(self):
        """Start the background monitoring thread."""
        def monitor_loop():
            while self.monitoring:
                try:
                    self._scan_once()
                except Exception as e:
                    print(f"Scan error: {e}")
                time.sleep(2)

        self.monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self.monitor_thread.start()

    def _scan_once(self):
        """Perform a single scan of the game screen."""
        if not self.capturer or not self.detector:
            return

        img = self.capturer.capture_result_strip()
        if img is None:
            return

        # Detect all icons in the result strip
        results = self.detector.detect_result_row(img)

        # Check if results changed (new round detected)
        if results and results != self.previous_results:
            # Find new results (at the end)
            if self.previous_results:
                # The new result is typically the last one
                new_items = results[len(self.previous_results):]
                if not new_items and results[-1:] != self.previous_results[-1:]:
                    new_items = results[-1:]
            else:
                new_items = results[-1:]  # First scan, just take the last

            for food in new_items:
                self.logger.add_result(food)

            self.previous_results = results[:]
            # Update GUI on main thread
            self.root.after(0, self._refresh_stats)

    def _set_region(self):
        """Open a dialog to set the screen capture region."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Set Capture Region")
        dialog.geometry("400x300")
        dialog.configure(bg=self.BG_COLOR)
        dialog.transient(self.root)
        dialog.grab_set()

        tk.Label(
            dialog, text="Enter the Result Row coordinates",
            font=("Segoe UI", 12, "bold"), fg=self.TEXT_COLOR, bg=self.BG_COLOR
        ).pack(pady=10)

        tk.Label(
            dialog,
            text="These are the pixel coordinates of the\n'Result:' row at the bottom of the emulator.\n\n"
                 "Tip: Use a screenshot tool to find the\nexact X, Y, Width, Height values.",
            font=("Segoe UI", 9), fg=self.TEXT_DIM, bg=self.BG_COLOR, justify="center"
        ).pack(pady=5)

        fields_frame = tk.Frame(dialog, bg=self.BG_COLOR)
        fields_frame.pack(pady=10)

        entries = {}
        for i, (label, default) in enumerate([("X:", "0"), ("Y:", "900"), ("Width:", "450"), ("Height:", "50")]):
            tk.Label(
                fields_frame, text=label, font=("Segoe UI", 10),
                fg=self.TEXT_COLOR, bg=self.BG_COLOR, width=8
            ).grid(row=i, column=0, padx=5, pady=3)
            entry = tk.Entry(fields_frame, font=("Segoe UI", 10), width=10)
            entry.insert(0, default)
            entry.grid(row=i, column=1, padx=5, pady=3)
            entries[label] = entry

        def apply():
            try:
                x = int(entries["X:"].get())
                y = int(entries["Y:"].get())
                w = int(entries["Width:"].get())
                h = int(entries["Height:"].get())
                if self.capturer:
                    self.capturer.set_result_region(x, y, w, h)
                self.status_label.config(text=f"✅ Region set: ({x}, {y}) {w}x{h}")
                dialog.destroy()
            except ValueError:
                messagebox.showerror("Invalid Input", "Please enter valid numbers.")

        tk.Button(
            dialog, text="Apply", font=("Segoe UI", 11, "bold"),
            bg="#28a745", fg="white", relief="flat", padx=20, pady=5,
            command=apply
        ).pack(pady=10)

    def _manual_add(self):
        """Open a dialog to manually add a result."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Result Manually")
        dialog.geometry("350x450")
        dialog.configure(bg=self.BG_COLOR)
        dialog.transient(self.root)
        dialog.grab_set()

        tk.Label(
            dialog, text="Select the result:",
            font=("Segoe UI", 12, "bold"), fg=self.TEXT_COLOR, bg=self.BG_COLOR
        ).pack(pady=10)

        for food in FOOD_ITEMS:
            d = FOOD_DISPLAY[food]
            btn = tk.Button(
                dialog,
                text=f"  {d['emoji']}  {d['name']}  (x{FOOD_MULTIPLIER[food]})",
                font=("Segoe UI", 12),
                bg=self.CARD_BG, fg=self.TEXT_COLOR,
                activebackground=d["color"], activeforeground="white",
                relief="flat", pady=5, anchor="w",
                cursor="hand2",
                command=lambda f=food, dlg=dialog: self._do_manual_add(f, dlg)
            )
            btn.pack(fill="x", padx=15, pady=2)

    def _do_manual_add(self, food, dialog):
        """Add a manual result and close dialog."""
        self.logger.add_result(food, confidence=1.0)
        dialog.destroy()
        self._refresh_stats()
        d = FOOD_DISPLAY[food]
        self.status_label.config(text=f"✅ Added: {d['emoji']} {d['name']}")

    def _export_excel(self):
        """Export results to Excel file."""
        try:
            self.logger.save_excel()
            self.status_label.config(text=f"💾 Saved to {self.logger.excel_path}")
            messagebox.showinfo("Exported", f"Results saved to:\n{self.logger.excel_path}")
        except Exception as e:
            messagebox.showerror("Export Error", str(e))

    def run(self):
        """Start the GUI event loop."""
        # Auto-refresh every 5 seconds
        def auto_refresh():
            if self.root.winfo_exists():
                self._refresh_stats()
                self.root.after(5000, auto_refresh)
        self.root.after(5000, auto_refresh)

        self.root.mainloop()
