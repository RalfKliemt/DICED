"""Tkinter GUI for entering roll sequences and inspecting probability results."""

from __future__ import annotations

import re
import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox
from typing import Any

from .core import (
    CalculationResult,
    RollSequenceCalculator,
    SequenceOptions,
    apply_options,
    armour_outcomes,
    parse_sequence,
)


SYNTAX_HELP_TEXT = (
    "Connected 1 die rolls. The lower results are with 1 and 2 rerolls.\n\n"
    "- 2+ means a normal D6 roll succeeding on 2 or higher.\n"
    "- 3++ means a 3+ roll with one built-in reroll for that die.\n"
    "- You can leave out whitespace and + entirely, e.g. 2+3++4 and 23++4 both mean 2+ 3++ 4+.\n"
    "- p anywhere (or the Pro key) gives the whole sequence one Pro reroll (2/3).\n"
    "- b anywhere (or the Brawler key) gives every block Brawler.\n\n"
    "Block dice:\n"
    "- 1d, 2d, 3d, -2d, -3d succeed on pow/pow*.\n"
    "- Add + (Block), - (No turnover: push or better), * (Pow only), / (Push only: exactly a push).\n"
    "- a9 or av9 is a 2D6 armor-break check.\n"
    "- k (KO) or i (Injury/CAS) after armour adds the injury roll; results list Break / KO / CAS.\n"
    "- s anywhere except right after a D6 digit (or vs Stunty) uses the Stunty table;\n"
    "  m after armour (or MB) is Mighty Blow.\n\n"
    "Example: 2+ 4+ 12d+ av9im for an Ogre with Block to activate, dodge & injure a lone Human Lineman"
)


PAGE = "#ffffff"
CARD = "#ffffff"
SHADOW = "#ffffff"
LINE = "#e0e0e0"
INK = "#212121"
ACCENT = "#4051b5"
BLUE = "#4051b5"
MUTED = "#757575"
DOTS = "#adadad"
KEY = "#f5f5f5"
KEY_HOVER = "#e8ebff"
KEY_BORDER = "#e0e0e0"
GO = "#4051b5"
GO_HOVER = "#526cfe"
SLAB = "Rockwell"
FIELD = "#ffffff"
ERROR = "#d32f2f"

THEMES = {
    "light": dict(
        PAGE="#ffffff", CARD="#ffffff", LINE="#e0e0e0", INK="#212121", BLUE="#4051b5",
        MUTED="#757575", DOTS="#adadad", KEY="#f5f5f5", KEY_HOVER="#e8ebff",
        KEY_BORDER="#e0e0e0", FIELD="#ffffff", ERROR="#d32f2f",
        GO="#4051b5", GO_HOVER="#526cfe",
    ),
    "dark": dict(
        PAGE="#1e2129", CARD="#1e2129", LINE="#2c303a", INK="#b4b8c2", BLUE="#8c97d6",
        MUTED="#7d8290", DOTS="#4e5361", KEY="#22252d", KEY_HOVER="#2b3150",
        KEY_BORDER="#2c303a", FIELD="#22252d", ERROR="#e57373",
        GO="#2f3c85", GO_HOVER="#3a4aa3",
    ),
}


def apply_theme(name: str) -> None:
    """Swap the module-level palette used when building widgets."""
    globals().update(THEMES[name])

# (label, kind, value, color). kind "token" adds a new space-separated token,
# "suffix" attaches to the last token.
KEYPAD: list[tuple[str | None, list[tuple[str, str, str, str]]]] = [
    ("SKILLS (WHOLE SEQUENCE)", [
        ("Block", "toggle", "block", "INK"),
        ("Pro", "toggle", "pro", "INK"),
        ("Brawler", "toggle", "brawler", "INK"),
        ("MB", "toggle", "mighty_blow", "INK"),
        ("vs Stunty", "toggle", "stunty", "INK"),
    ]),
    ("ROLL", [(f"{n}+", "token", f"{n}+", "INK") for n in range(2, 7)]),
    ("ROLL WITH SKILL REROLL", [(f"{n}++", "token", f"{n}++", "BLUE") for n in range(2, 7)]),
    ("BLOCK DICE", [(d, "token", d, "INK") for d in ("-3d", "-2d", "1d", "2d", "3d")]),
    (None, [
        ("\u2212 No TO", "suffix", "-", "INK"),
        ("* Pow", "suffix", "*", "INK"),
        ("/ Push only", "suffix", "/", "INK"),
        ("k KO", "suffix", "k", "INK"),
        ("i Inj", "suffix", "i", "INK"),
    ]),
    ("ARMOUR", [(f"av{n}", "token", f"av{n}", "INK") for n in range(7, 12)]),
]


class DicedApp:
    """Card-style UI with a roll keypad for the dice sequence calculator."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("DICED")
        self.root.configure(bg=PAGE)
        self.root.resizable(False, False)

        self.calculator = RollSequenceCalculator()
        self.sequence_var = tk.StringVar(value="3++ 2+ 2d av9k")
        self.result_main_var = tk.StringVar(value="-%")
        self.result_rr_var = tk.StringVar(value="-% / -%")
        self.log_lines: list[str] = []
        self.compact = False
        self.dark = False
        self.toggles = {name: False for name in SequenceOptions.__dataclass_fields__}
        self.last_options = SequenceOptions()
        self.armour_var = tk.StringVar(value="")
        self.toggle_keys: dict[str, tuple[tk.Frame, tk.Label]] = {}
        apply_theme("light")
        self.result_state = "idle"

        self._build_layout()

        # Trigger calculation with Enter from anywhere in the window.
        self.root.bind("<Return>", self._handle_calculate)
        self.root.bind("<KP_Enter>", self._handle_calculate)

    def _make_key(
        self,
        parent: tk.Widget,
        text: str,
        command: Any,
        *,
        fg: str | None = None,
        bg: str | None = None,
        hover: str | None = None,
        border: str | None = None,
        font: tuple = ("Helvetica", 15, "bold"),
        pady: int = 9,
    ) -> tk.Frame:
        """Create a flat clickable key (tk.Button ignores colors on macOS)."""
        # Resolve palette at call time so theme switches take effect.
        fg = fg or INK
        bg = bg or KEY
        hover = hover or KEY_HOVER
        border = border or KEY_BORDER
        frame = tk.Frame(parent, bg=border, padx=1, pady=1)
        label = tk.Label(frame, text=text, font=font, fg=fg, bg=bg, pady=pady, cursor="hand2")
        label.pack(fill=tk.BOTH, expand=True)
        label.bind("<Enter>", lambda _e: label.configure(bg=hover))
        label.bind("<Leave>", lambda _e: label.configure(bg=bg))
        label.bind("<Button-1>", lambda _e: command())
        return frame

    def _sz(self, size: int) -> int:
        """Scale a size down to half in compact mode (with a readable minimum)."""
        return max(9, round(size / 2)) if self.compact else size

    def _pd(self, pad: int) -> int:
        return max(1, pad // 4) if self.compact else pad

    def toggle_option(self, name: str) -> None:
        """Toggle a sequence-wide skill (applies on the next Go!)."""
        self.toggles[name] = not self.toggles[name]
        self._style_toggle(name)

    def _toggle_colors(self, name: str, hover: bool = False) -> tuple[str, str, str]:
        """Return (fg, bg, border) for a toggle key in its current state."""
        if self.toggles[name]:
            return "#ffffff", GO_HOVER if hover else GO, GO
        return INK, KEY_HOVER if hover else KEY, KEY_BORDER

    def _style_toggle(self, name: str, hover: bool = False) -> None:
        """Recolour a toggle key in place (no rebuild, so no flicker)."""
        frame, label = self.toggle_keys[name]
        fg, bg, border = self._toggle_colors(name, hover)
        frame.configure(bg=border)
        label.configure(fg=fg, bg=bg)

    def toggle_theme(self) -> None:
        """Switch between light and dark palettes, keeping input and log."""
        self.dark = not self.dark
        apply_theme("dark" if self.dark else "light")
        self._rebuild()

    def toggle_compact(self) -> None:
        """Switch between normal and compact layout, keeping input and log."""
        self.compact = not self.compact
        self._rebuild()

    def _rebuild(self) -> None:
        self.root.configure(bg=PAGE)
        self.outer.destroy()
        self._build_layout()
        self._render_log()
        self._apply_result_color()
        self._fit_window()

    def _fit_window(self) -> None:
        """Natural size in normal mode; a square window in compact mode."""
        self.root.resizable(True, True)
        self.root.geometry("")
        self.root.update_idletasks()
        if self.compact:
            side = max(self.root.winfo_reqwidth(), self.root.winfo_reqheight())
            self.root.geometry(f"{side}x{side}")
            self.root.update_idletasks()
        self.root.resizable(False, False)

    def _build_layout(self) -> None:
        """Build app bar, entry, keypad, results, and log."""
        sz, pd = self._sz, self._pd
        outer = tk.Frame(self.root, bg=PAGE)
        outer.pack(fill=tk.BOTH, expand=True)
        self.outer = outer

        card_border = tk.Frame(outer, bg=PAGE)
        card_border.grid(row=0, column=0, sticky="nsew")
        outer.rowconfigure(0, weight=1)
        outer.columnconfigure(0, weight=1)
        card = tk.Frame(card_border, bg=CARD, pady=0)
        card.pack(fill=tk.BOTH, expand=True)
        card.columnconfigure(0, weight=1)
        # Compact: everything is anchored to the bottom of a square window.
        log_row = 5 if self.compact else 9
        if self.compact:
            # The keypad absorbs any height needed to keep the window square.
            card.rowconfigure(7, weight=1)

        header = tk.Frame(card, bg=GO, padx=pd(16), pady=pd(10))
        header.grid(row=0, column=0, sticky="ew", pady=(0, pd(14)))
        self.headline_label = tk.Label(header, text="DICED", font=(SLAB, sz(20), "bold"), bg=GO, fg="#ffffff")
        self.headline_label.pack(side=tk.LEFT)
        if not self.compact:
            tk.Label(
                header, text="Blood Bowl dice chain odds", font=(SLAB, 13), bg=GO, fg="#d9ddf3"
            ).pack(side=tk.LEFT, padx=(12, 0), pady=(4, 0))
        toggle = tk.Label(
            header,
            text=("\u25c9 Compact" if self.compact else "\u25cb Compact"),
            font=(SLAB, sz(12), "bold"),
            bg=GO,
            fg="#ffffff",
            cursor="hand2",
        )
        toggle.pack(side=tk.RIGHT)
        toggle.bind("<Button-1>", lambda _e: self.toggle_compact())
        theme_toggle = tk.Label(
            header,
            text=("\u2600" if self.dark else "\u263e"),
            font=("Helvetica", sz(16)),
            bg=GO,
            fg="#ffffff",
            cursor="hand2",
        )
        theme_toggle.pack(side=tk.RIGHT, padx=(0, pd(12)))
        theme_toggle.bind("<Button-1>", lambda _e: self.toggle_theme())

        # Entry with help button.
        entry_border = tk.Frame(card, bg=LINE, padx=1, pady=1)
        entry_border.grid(row=6, column=0, sticky="ew", padx=pd(24))
        entry_row = tk.Frame(entry_border, bg=FIELD)
        entry_row.pack(fill=tk.X)
        self.entry = tk.Entry(
            entry_row,
            textvariable=self.sequence_var,
            font=(SLAB, sz(20), "bold"),
            bd=0,
            bg=FIELD,
            fg=INK,
            highlightthickness=0,
            relief=tk.FLAT,
            insertbackground=INK,
            insertwidth=2,
        )
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(pd(12), pd(6)), pady=pd(10))
        self.entry.bind("<Return>", self._handle_entry_return)
        self.entry.bind("<KP_Enter>", self._handle_entry_return)
        self.help_button = self._make_key(
            entry_row, " ? ", self.show_syntax_help, font=("Helvetica", sz(13), "bold"), pady=pd(4)
        )
        self.help_button.pack(side=tk.RIGHT, padx=pd(8))

        # Keypad.
        keypad = tk.Frame(card, bg=CARD)
        keypad.grid(row=7, column=0, sticky="nsew", pady=(pd(10), 0), padx=pd(24))
        # Compact mode drops section labels and pairs sections side by side.
        columns = 5
        for col in range(columns):
            keypad.columnconfigure(col, weight=1, uniform="key")
        row = 0
        for index, (section, keys) in enumerate(KEYPAD):
            col_offset = 0
            if section and not self.compact:
                tk.Label(
                    keypad, text=section, font=(SLAB, 12, "bold"), bg=CARD, fg=MUTED, anchor="w"
                ).grid(row=row, column=0, columnspan=5, sticky="w", pady=(6, 2))
                row += 1
            for col, (text, kind, value, color) in enumerate(keys):
                small = kind != "token"
                if kind == "toggle":
                    frame = tk.Frame(keypad, padx=1, pady=1)
                    label = tk.Label(
                        frame, text=text, font=("Helvetica", sz(11), "bold"), pady=pd(11), cursor="hand2"
                    )
                    label.pack(fill=tk.BOTH, expand=True)
                    self.toggle_keys[value] = (frame, label)
                    self._style_toggle(value)
                    label.bind("<Enter>", lambda _e, n=value: self._style_toggle(n, hover=True))
                    label.bind("<Leave>", lambda _e, n=value: self._style_toggle(n))
                    label.bind(
                        "<ButtonRelease-1>",
                        lambda _e, n=value: (self.toggle_option(n), self._style_toggle(n, hover=True)),
                    )
                    frame.grid(row=row, column=col_offset + col, sticky="nsew", padx=(pd(3), pd(3)), pady=pd(3))
                    continue
                if self.compact and small:
                    text = text.split(" ")[0]
                key = self._make_key(
                    keypad,
                    text,
                    lambda k=kind, v=value: self._press_key(k, v),
                    fg=globals()[color],
                    font=("Helvetica", sz(11), "bold") if small else (SLAB, sz(16), "bold"),
                    pady=pd(11) if small else pd(9),
                )
                key.grid(
                    row=row,
                    column=col_offset + col,
                    sticky="nsew",
                    padx=(pd(10) if self.compact and col_offset and col == 0 else pd(3), pd(3)),
                    pady=pd(3),
                )
            if self.compact:
                keypad.rowconfigure(row, weight=1)
            row += 1

        actions = tk.Frame(keypad, bg=CARD)
        actions.grid(row=row, column=0, columnspan=columns, sticky="ew", pady=(pd(8), 0))
        actions.columnconfigure(0, weight=1, uniform="act")
        actions.columnconfigure(1, weight=1, uniform="act")
        actions.columnconfigure(2, weight=3, uniform="act")
        for col, (text, kind) in enumerate((("\u232b", "back"), ("Clear", "clear"))):
            self._make_key(
                actions,
                text,
                lambda k=kind: self._press_key(k, ""),
                font=("Helvetica", sz(12), "bold"),
                pady=pd(11),
            ).grid(row=0, column=col, sticky="nsew", padx=pd(3))
        self.go_button = self._make_key(
            actions,
            "Go!",
            self.calculate,
            bg=GO,
            hover=GO_HOVER,
            fg="#ffffff",
            border=GO,
            font=(SLAB, sz(17), "bold"),
            pady=pd(9),
        )
        self.go_button.grid(row=0, column=2, sticky="nsew", padx=pd(3))

        # Results.
        if not self.compact:
            tk.Frame(card, bg=LINE, height=1).grid(row=8, column=0, sticky="ew", pady=(pd(14), 0), padx=pd(24))
        self.result_label = tk.Label(
            card, textvariable=self.result_main_var, font=(SLAB, sz(60)), bg=CARD, fg=DOTS
        )
        self.result_label.grid(row=2, column=0, pady=(0 if self.compact else 4, 0))
        self.result_rr_label = tk.Label(
            card, textvariable=self.result_rr_var, font=(SLAB, sz(20), "bold"), bg=CARD, fg=DOTS
        )
        self.result_rr_label.grid(row=3, column=0)
        self.armour_label = tk.Label(
            card, textvariable=self.armour_var, font=(SLAB, sz(14), "bold"), bg=CARD, fg=INK
        )
        if self.armour_var.get():
            self.armour_label.grid(row=4, column=0)
        tk.Frame(card, bg=LINE, height=1).grid(row=5, column=0, sticky="ew", pady=(pd(12), pd(14)), padx=pd(24))

        # Log.
        self.log_text = tk.Text(
            card,
            height=1 if self.compact else 4,
            width=20 if self.compact else 58,
            wrap=tk.NONE,
            bg=CARD,
            fg=MUTED,
            relief=tk.FLAT,
            borderwidth=0,
            highlightthickness=0,
            font=("Menlo", 9 if self.compact else 11),
        )
        if not self.compact:  # compact mode hides the log
            self.log_text.grid(
                row=log_row,
                column=0,
                sticky="nsew",
                padx=pd(24),
                pady=(0, pd(8)) if self.compact else (8, 8),
            )
        self.log_text.tag_configure("dots", foreground=DOTS)

    def _apply_result_color(self) -> None:
        main, rr = {"idle": (DOTS, DOTS), "ok": (BLUE, INK), "error": (ERROR, ERROR)}[self.result_state]
        self.result_label.configure(fg=main)
        self.result_rr_label.configure(fg=rr)

    def _press_key(self, kind: str, value: str) -> None:
        """Edit the sequence entry according to a keypad press."""
        current = self.sequence_var.get().rstrip()
        if kind == "token":
            new = f"{current} {value}" if current else value
        elif kind == "suffix":
            new = current + value if current else current
        elif kind == "back":
            new = " ".join(current.split()[:-1])
        else:  # clear
            new = ""
        self.sequence_var.set(new)
        self.entry.focus_set()
        self.entry.selection_clear()
        self.entry.icursor(tk.END)

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
            parsed, typed = parse_sequence(raw_sequence)
            self.last_options = SequenceOptions(**self.toggles).merged(typed)
            sequence = apply_options(parsed, self.last_options)
            result = self.calculator.calculate(sequence, pro=self.last_options.pro)
            armour = armour_outcomes(self.calculator, sequence, self.last_options)
        except ValueError as error:
            self.result_main_var.set("-%")
            self.result_rr_var.set("-% / -%")
            self.result_state = "error"
            self._set_armour("")
            self._apply_result_color()
            self._append_log(f"{raw_sequence}: ERROR ({error})")
            self._focus_and_select_entry()
            return

        base = result.final_probability
        rr1 = result.probability_with_global_rerolls(1)
        rr2 = result.probability_with_global_rerolls(2)
        self.result_main_var.set(f"{base:.1%}")
        self.result_rr_var.set(f"1 RR {rr1:.1%}  /  2 RR {rr2:.1%}")
        self.result_state = "ok"
        self._apply_result_color()
        self._set_armour(
            "  \u00b7  ".join(f"{label} {values[0]:.1%}" for label, values in armour.items()) if armour else ""
        )
        self._append_log(self._format_log_entry(result))
        self._focus_and_select_entry()

    def _set_armour(self, text: str) -> None:
        """Show Break / KO / CAS chances below the reroll line, or hide the row."""
        self.armour_var.set(text)
        if text:
            self.armour_label.grid(row=4, column=0)
        else:
            self.armour_label.grid_remove()

    def _format_log_entry(self, result: CalculationResult) -> str:
        """Return a dot-leader log line with left sequence and right-aligned result."""
        sequence = " ".join(step.token for step in result.steps)
        if self.last_options.labels:
            sequence += f" [{', '.join(self.last_options.labels)}]"
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
        self._render_log()

    def _render_log(self) -> None:
        """Redraw the log text widget from stored lines."""
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        for index, line in enumerate(reversed(self.log_lines)):
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