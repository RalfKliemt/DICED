"""Tkinter GUI for entering roll sequences and inspecting probability results."""

from __future__ import annotations

import re
import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox
from typing import Any

from .core import CalculationResult, RollSequenceCalculator, parse_roll_sequence


SYNTAX_HELP_TEXT = (
    "Connected 1 die rolls. The lower results are with 1 and 2 rerolls.\n\n"
    "- 2+ means a normal D6 roll succeeding on 2 or higher.\n"
    "- 3++ means a 3+ roll with one built-in reroll for that die.\n"
    "- You can leave out whitespace and + entirely, e.g. 2+3++4 and 23++4 both mean 2+ 3++ 4+.\n"
    "- p adds a 2/3 reroll chance on that die.\n\n"
    "Block dice:\n"
    "- 1d, 2d, 3d, -2d, -3d succeed on pow/pow*.\n"
    "- Add + (Block), - (Push), * (Pow only), / (Push only).\n"
    "- a9 or av9 is a 2D6 armor-break check.\n"
    "- Injury suffixes: k (KO), i (Injury), s (Stunty), m (Mighty Blow).\n\n"
    "Example: 2+ 4+ 12d+ av9im for an Ogre with Block to activate, dodge & injure a lone Human Lineman"
)


class DicedApp:
    """Single-canvas coaster UI for the dice sequence calculator."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("DICED")
        self.root.geometry("640x640")
        self.root.minsize(640, 640)
        self.root.maxsize(640, 640)

        # Match the fixed-size web layout.
        self.canvas_size = 620
        self.coaster_size = 584
        self.coaster_radius = 52
        self.shadow_dx = 10
        self.shadow_dy = 12

        self.calculator = RollSequenceCalculator()
        self.sequence_var = tk.StringVar(value="3++ 2+ 2d av9k")
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
        self.canvas.place(relx=0.5, rely=0.5, anchor=tk.CENTER, width=self.canvas_size, height=self.canvas_size)

        self.entry = tk.Entry(
            self.canvas,
            textvariable=self.sequence_var,
            justify="left",
            font=("Helvetica", 20, ""),
            bd=0,
            # Tk Entry cannot be truly alpha-transparent, so this uses a near-
            # coaster tone to create an ~80% transparent visual effect.
            bg="#ececec",
            highlightthickness=0,
            highlightbackground="#f8f8f7",
            highlightcolor="#587089",
            relief=tk.FLAT,
            fg="#1d1d1d",
            insertbackground="#1d1d1d",
            insertwidth=2,
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
            # relief=tk.RAISED,
            bd=0,
            padx=8,
            pady=4,
            # cursor="hand1",
        )

        self.help_button = tk.Button(
            self.canvas,
            text="?",
            command=self.show_syntax_help,
            font=("Helvetica", 12, "bold"),
            bg="#f2b84a",
            fg="#1a1a1a",
            activebackground="#ffc95e",
            activeforeground="#111111",
            # relief=tk.RAISED,
            bd=0,
            padx=0,
            pady=4,
        )

        self.headline_label = tk.Label(
            self.canvas,
            text="DICED",
            font=("Impact", 86),
            bg="#fdfdfc",
            fg="#7a1515",
        )

        self.result_label = tk.Label(
            self.canvas,
            textvariable=self.result_main_var,
            font=("Helvetica", 64, "bold"),
            justify="center",
            bg="#fdfdfc",
            fg="#1a3f7a",
        )

        self.result_rr_label = tk.Label(
            self.canvas,
            textvariable=self.result_rr_var,
            font=("Helvetica", 24, "bold"),
            justify="center",
            bg="#fdfdfc",
            fg="#1a3f7a",
        )

        # Transparent-like log: no border and same color as coaster center.
        self.log_text = tk.Text(
            self.canvas,
            height=8,
            wrap=tk.NONE,
            # state=tk.DISABLED,
            bg="#fdfdfc",
            fg="#3c3c3c",
            relief=tk.FLAT,
            borderwidth=0,
            highlightthickness=0,
            font=("Menlo", 12),
        )
        self.log_text.tag_configure("dots", foreground="#c4c4c4")

        self.entry_window = self.canvas.create_window(0, 0, window=self.entry, width=460)
        self.go_button_window = self.canvas.create_window(0, 0, window=self.go_button)
        self.help_button_window = self.canvas.create_window(0, 0, window=self.help_button)
        self.headline_window = self.canvas.create_window(0, 0, window=self.headline_label)
        self.result_window = self.canvas.create_window(0, 0, window=self.result_label)
        self.result_rr_window = self.canvas.create_window(0, 0, window=self.result_rr_label)
        self.log_window = self.canvas.create_window(
            0,
            0,
            window=self.log_text,
            width=532,
            height=156,
            anchor=tk.CENTER,
        )

        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self._on_root_resize(None)

    def _on_root_resize(self, _event: tk.Event) -> None:
        """Keep the canvas square and centered inside the window."""
        self.canvas.place_configure(width=self.canvas_size, height=self.canvas_size)

    def _on_canvas_configure(self, event: tk.Event) -> None:
        """Redraw background and keep widgets anchored to coaster-relative zones."""
        width = max(1, int(event.width))
        height = max(1, int(event.height))
        self._draw_background(width, height)
        self._position_widgets(width, height)

    def _draw_background(self, width: int, height: int) -> None:
        """Paint a large rounded white coaster matching the web layout."""
        self.canvas.delete("bg")

        x1 = (width - self.coaster_size) / 2
        y1 = (height - self.coaster_size) / 2
        x2 = x1 + self.coaster_size
        y2 = y1 + self.coaster_size
        radius = self.coaster_radius

        self.canvas.create_rectangle(0, 0, width, height, fill="#e8e1d3", outline="", tags="bg")
        self._create_rounded_rect(
            self.canvas,
            x1 + self.shadow_dx,
            y1 + self.shadow_dy,
            x2 + self.shadow_dx,
            y2 + self.shadow_dy,
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

        self._coaster_bounds = (x1, y1, x2, y2)

    def _position_widgets(self, width: int, height: int) -> None:
        """Place entry, results, and log according to coaster-relative fractions."""
        x1, y1, x2, y2 = self._coaster_bounds
        coaster_w = x2 - x1
        center_x = x1 + coaster_w / 2

        # These fixed positions mirror the web layout's 584px coaster grid.
        headline_y = y1 + 80
        entry_y = y1 + 176
        result_y = y1 + 256
        result_rr_y = result_y + 64
        log_y = result_rr_y + 128 + 32

        self.canvas.coords(self.headline_window, center_x, headline_y)

        self.canvas.coords(self.entry_window, center_x, entry_y)
        entry_width = 394
        self.canvas.itemconfigure(self.entry_window, width=entry_width)
        self.canvas.coords(self.go_button_window, center_x + (entry_width / 2) - 74, entry_y)
        self.canvas.coords(self.help_button_window, center_x + (entry_width / 2) - 18, entry_y)

        self.canvas.coords(self.result_window, center_x, result_y)

        self.canvas.coords(self.result_rr_window, center_x, result_rr_y)

        self.canvas.coords(self.log_window, center_x, log_y)
        self.canvas.itemconfigure(
            self.log_window,
            width=512,
            height=156,
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

    def show_syntax_help(self) -> None:
        """Show a compact syntax reference dialog."""
        messagebox.showinfo("DICED Syntax Help", SYNTAX_HELP_TEXT, parent=self.root)

    def calculate(self) -> None:
        """Parse input and refresh large result text and compact log."""
        raw_sequence = self.sequence_var.get().strip()

        try:
            sequence = parse_roll_sequence(raw_sequence)
            result = self.calculator.calculate(sequence)
        except ValueError as error:
            self.result_main_var.set("-%")
            self.result_rr_var.set("-% / -%")
            self._append_log(f"{raw_sequence}: ERROR ({error})")
            self._focus_and_select_entry()
            return

        base = result.final_probability
        rr1 = result.probability_with_global_rerolls(1)
        rr2 = result.probability_with_global_rerolls(2)
        self.result_main_var.set(f"{base:.1%}")
        self.result_rr_var.set(f"{rr1:.1%} / {rr2:.1%}")
        self._append_log(self._format_log_entry(result))
        self._focus_and_select_entry()

    def _format_log_entry(self, result: CalculationResult) -> str:
        """Return a dot-leader log line with left sequence and right-aligned result."""
        sequence = " ".join(step.token for step in result.steps)
        base = result.final_probability
        rr1 = result.probability_with_global_rerolls(1)
        rr2 = result.probability_with_global_rerolls(2)
        result_str = f"{base:.1%} ({rr1:.1%} / {rr2:.1%})"

        font = tkfont.Font(font=self.log_text.cget("font"))
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
    app = DicedApp(root)
    root.mainloop()