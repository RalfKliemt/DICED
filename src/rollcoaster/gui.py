"""Tkinter GUI for entering roll sequences and inspecting probability results."""

from __future__ import annotations

import re
import tkinter as tk
import tkinter.font as tkfont
from typing import Any

from .core import CalculationResult, RollSequenceCalculator, parse_roll_sequence


class RollCoasterApp:
    """Single-canvas coaster UI for the dice sequence calculator."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("RollCoaster")
        self.root.geometry("640x640")
        self.root.minsize(512, 512)

        self.calculator = RollSequenceCalculator()
        self.sequence_var = tk.StringVar(value="3++")
        self.result_main_var = tk.StringVar(value="")
        self.result_rr_var = tk.StringVar(value="")
        self.log_lines: list[str] = []

        self._build_layout()

        # Trigger calculation with Enter from anywhere in the window.
        self.root.bind("<Return>", self._handle_calculate)
        self.root.bind("<KP_Enter>", self._handle_calculate)

    def _build_layout(self) -> None:
        """Create a full-window canvas and place the three UI elements on it."""
        self.canvas_host = tk.Frame(self.root, bg="#e8e1d3")
        self.canvas_host.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(self.canvas_host, highlightthickness=0, bg="#e8e1d3", bd=0)
        self.canvas.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        self.entry = tk.Entry(
            self.canvas,
            textvariable=self.sequence_var,
            justify="center",
            font=("Helvetica", 22, "bold"),
            bd=0,
            # Tk Entry cannot be truly alpha-transparent, so this uses a near-
            # coaster tone to create an ~80% transparent visual effect.
            bg="#f8f8f7",
            highlightthickness=0,
            highlightbackground="#f8f8f7",
            highlightcolor="#587089",
            relief=tk.FLAT,
            fg="#1d1d1d",
            insertbackground="#1d1d1d",
        )
        self.entry.bind("<Return>", self._handle_entry_return)
        self.entry.bind("<KP_Enter>", self._handle_entry_return)

        self.go_button = tk.Button(
            self.canvas,
            text="Go!",
            command=self.calculate,
            font=("Helvetica", 12, "bold"),
            bg="#f2b84a",
            fg="#1a1a1a",
            activebackground="#ffc95e",
            activeforeground="#111111",
            relief=tk.RAISED,
            bd=1,
            padx=14,
            pady=5,
            cursor="hand2",
        )

        self.headline_label = tk.Label(
            self.canvas,
            text="ROLLS COASTER",
            font=("Impact", 32),
            bg="#fdfdfc",
            fg="#7a1515",
        )

        self.result_label = tk.Label(
            self.canvas,
            textvariable=self.result_main_var,
            font=("Helvetica", 48, "bold"),
            justify="center",
            bg="#fdfdfc",
            fg="#1a3f7a",
        )

        self.result_rr_label = tk.Label(
            self.canvas,
            textvariable=self.result_rr_var,
            font=("Helvetica", 22, "bold"),
            justify="center",
            bg="#fdfdfc",
            fg="#1a3f7a",
        )

        # Transparent-like log: no border and same color as coaster center.
        self.log_text = tk.Text(
            self.canvas,
            height=8,
            wrap=tk.NONE,
            state=tk.DISABLED,
            bg="#fdfdfc",
            fg="#3c3c3c",
            relief=tk.FLAT,
            borderwidth=0,
            highlightthickness=0,
            font="TkFixedFont",
        )
        self.log_text.tag_configure("dots", foreground="#c4c4c4")

        self.entry_window = self.canvas.create_window(0, 0, window=self.entry, width=460)
        self.go_button_window = self.canvas.create_window(0, 0, window=self.go_button)
        self.headline_window = self.canvas.create_window(0, 0, window=self.headline_label)
        self.result_window = self.canvas.create_window(0, 0, window=self.result_label)
        self.result_rr_window = self.canvas.create_window(0, 0, window=self.result_rr_label)
        self.log_window = self.canvas.create_window(
            0,
            0,
            window=self.log_text,
            width=640,
            height=130,
            anchor=tk.CENTER,
        )

        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.root.bind("<Configure>", self._on_root_resize, add="+")

    def _on_root_resize(self, _event: tk.Event) -> None:
        """Keep the canvas square and centered inside the window."""
        size = max(320, min(self.root.winfo_width(), self.root.winfo_height()) - 18)
        self.canvas.place_configure(width=size, height=size)

    def _on_canvas_configure(self, event: tk.Event) -> None:
        """Redraw background and keep widgets anchored to coaster-relative zones."""
        width = max(1, int(event.width))
        height = max(1, int(event.height))
        self._draw_background(width, height)
        self._position_widgets(width, height)

    def _draw_background(self, width: int, height: int) -> None:
        """Paint a large rounded white coaster with a subtle block-dice watermark."""
        self.canvas.delete("bg")

        margin = max(20, int(min(width, height) * 0.05))
        x1 = margin
        y1 = margin
        x2 = width - margin
        y2 = height - margin
        radius = max(36, int(min(width, height) * 0.08))

        self.canvas.create_rectangle(0, 0, width, height, fill="#e8e1d3", outline="", tags="bg")
        self._create_rounded_rect(
            self.canvas,
            x1 + 8,
            y1 + 12,
            x2 + 8,
            y2 + 12,
            radius,
            fill="#d9cfbe",
            outline="",
            tags="bg",
        )
        self._create_rounded_rect(
            self.canvas,
            x1,
            y1,
            x2,
            y2,
            radius,
            fill="#fdfdfc",
            outline="#d6d6d6",
            width=2,
            tags="bg",
        )

        cx = (x1 + x2) / 2
        cy = y1 + (y2 - y1) * 0.48
        self._draw_watermark(cx, cy, min(width, height), "bg")

        self._coaster_bounds = (x1, y1, x2, y2)

    def _draw_watermark(self, cx: float, cy: float, size_ref: int, tag: str) -> None:
        """Draw a faded dice watermark."""
        dice = max(42, int(size_ref * 0.08))
        gap = int(dice * 0.35)

        positions = [
            (cx - dice - gap, cy - int(dice * 0.45), 1),
            (cx, cy - int(dice * 0.6), 6),
            (cx + dice + gap, cy - int(dice * 0.35), 4),
        ]

        for px, py, pips in positions:
            self._create_rounded_rect(
                self.canvas,
                px - dice / 2,
                py - dice / 2,
                px + dice / 2,
                py + dice / 2,
                dice * 0.18,
                fill="#d9d9d9",
                outline="",
                tags=tag,
            )
            self._draw_pips(px, py, dice, pips, tag)

    def _draw_pips(self, cx: float, cy: float, size: int, pips: int, tag: str) -> None:
        """Draw pip patterns used by the watermark dice."""
        r = max(3, int(size * 0.06))
        offset = int(size * 0.17)
        wide_offset = int(size * 0.22)
        pip_sets = {
            1: [(0, 0)],
            2: [(-offset, -offset), (offset, offset)],
            3: [(-offset, -offset), (0, 0), (offset, offset)],
            4: [(-wide_offset, -wide_offset), (wide_offset, -wide_offset), (-wide_offset, wide_offset), (wide_offset, wide_offset)],
            6: [
                (-wide_offset, -wide_offset),
                (wide_offset, -wide_offset),
                (-wide_offset, 0),
                (wide_offset, 0),
                (-wide_offset, wide_offset),
                (wide_offset, wide_offset),
            ],
        }
        for dx, dy in pip_sets[pips]:
            self.canvas.create_oval(
                cx + dx - r,
                cy + dy - r,
                cx + dx + r,
                cy + dy + r,
                fill="#f4f4f4",
                outline="",
                tags=tag,
            )

    def _position_widgets(self, width: int, height: int) -> None:
        """Place entry, results, and log according to coaster-relative fractions."""
        x1, y1, x2, y2 = self._coaster_bounds
        coaster_w = x2 - x1
        coaster_h = y2 - y1
        center_x = x1 + coaster_w / 2

        entry_y = y1 + coaster_h * 0.29
        headline_y = entry_y - (coaster_h * 0.15)
        result_y = y1 + coaster_h * 0.60
        result_rr_y = y1 + coaster_h * 0.70
        log_y = y1 + coaster_h * 0.86

        self.canvas.coords(self.headline_window, center_x, headline_y)
        headline_font_size = max(42, int(min(width, height) * 0.1))
        self.headline_label.configure(font=("Impact", headline_font_size))

        self.canvas.coords(self.entry_window, center_x, entry_y)
        self.canvas.itemconfigure(self.entry_window, width=min(620, int(coaster_w * 0.68)))
        entry_width = min(620, int(coaster_w * 0.68))
        self.canvas.coords(self.go_button_window, center_x + (entry_width / 2) - 40, entry_y)

        self.canvas.coords(self.result_window, center_x, result_y)
        result_font_size = max(44, int(min(width, height) * 0.082))
        self.result_label.configure(font=("Helvetica", result_font_size, "bold"))

        self.canvas.coords(self.result_rr_window, center_x, result_rr_y)
        rr_font_size = max(18, int(result_font_size * 0.42))
        self.result_rr_label.configure(font=("Helvetica", rr_font_size, "bold"))

        self.canvas.coords(self.log_window, center_x, log_y)
        log_width = min(640, int(coaster_w * 0.68))
        self.canvas.itemconfigure(
            self.log_window,
            width=log_width,
            height=max(90, int(coaster_h * 0.17)),
        )

    @staticmethod
    def _create_rounded_rect(
        canvas: tk.Canvas,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        radius: float,
        **kwargs: Any,
    ) -> int:
        """Create a rounded rectangle on a Tk canvas."""
        points = [
            x1 + radius,
            y1,
            x2 - radius,
            y1,
            x2,
            y1,
            x2,
            y1 + radius,
            x2,
            y2 - radius,
            x2,
            y2,
            x2 - radius,
            y2,
            x1 + radius,
            y2,
            x1,
            y2,
            x1,
            y2 - radius,
            x1,
            y1 + radius,
            x1,
            y1,
        ]
        return canvas.create_polygon(points, smooth=True, splinesteps=18, **kwargs)

    def _handle_calculate(self, _event: tk.Event | None = None) -> None:
        self.calculate()

    def _handle_entry_return(self, _event: tk.Event | None = None) -> str:
        """Handle Enter in the sequence field exactly once."""
        self.calculate()
        return "break"

    def calculate(self) -> None:
        """Parse input and refresh large result text and compact log."""
        raw_sequence = self.sequence_var.get().strip()

        try:
            sequence = parse_roll_sequence(raw_sequence)
            result = self.calculator.calculate(sequence)
        except ValueError as error:
            self.result_main_var.set("-%")
            self.result_rr_var.set("(-% / -%)")
            self._append_log(f"{raw_sequence}: ERROR ({error})")
            self._focus_and_select_entry()
            return

        base = result.final_probability
        rr1 = result.probability_with_global_rerolls(1)
        rr2 = result.probability_with_global_rerolls(2)
        self.result_main_var.set(f"{base:.1%}")
        self.result_rr_var.set(f"({rr1:.1%} / {rr2:.1%})")
        self._append_log(self._format_log_entry(result))
        self._focus_and_select_entry()

    def _format_log_entry(self, result: CalculationResult) -> str:
        """Return a dot-leader log line with left sequence and right-aligned result."""
        sequence = " ".join(step.token for step in result.steps)
        base = result.final_probability
        rr1 = result.probability_with_global_rerolls(1)
        rr2 = result.probability_with_global_rerolls(2)
        result_str = f"{base:.1%} ({rr1:.1%} / {rr2:.1%})"

        font = tkfont.nametofont(self.log_text.cget("font"))
        log_width_px = max(1, self.log_text.winfo_width() - 12)
        char_width_px = max(1, font.measure("0"))
        total_width = max(48, int(log_width_px / char_width_px)-8)
        dots = max(6, total_width - len(sequence) - len(result_str))
        return f"{sequence} {'.' * dots} {result_str}"

    def _append_log(self, message: str) -> None:
        """Append to log and keep only the latest lines."""
        self.log_lines.append(message)
        self.log_lines = self.log_lines[-7:]
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        for index, line in enumerate(self.log_lines):
            match = re.search(r"\.{3,}", line)
            if match is None:
                self.log_text.insert(tk.END, line)
            else:
                self.log_text.insert(tk.END, line[: match.start()])
                self.log_text.insert(tk.END, line[match.start() : match.end()], "dots")
                self.log_text.insert(tk.END, line[match.end() :])

            if index < len(self.log_lines) - 1:
                self.log_text.insert(tk.END, "\n")
        self.log_text.configure(state=tk.DISABLED)

    def _focus_and_select_entry(self) -> None:
        """Return focus to sequence field and select all text."""
        self.entry.focus_set()
        self.entry.selection_range(0, tk.END)


def launch() -> None:
    """Start the Tkinter application and populate it with an initial example."""

    root = tk.Tk()
    app = RollCoasterApp(root)
    root.mainloop()