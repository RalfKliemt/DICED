"""Flask web interface for the DICED calculator."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from flask import Flask, render_template, request

try:
    from .core import (
        CalculationResult,
        RollSequenceCalculator,
        SequenceOptions,
        apply_options,
        armour_outcomes,
        parse_sequence,
    )
except ImportError:
    # Support direct execution: `python src/diced/web.py`.
    src_dir = Path(__file__).resolve().parents[1]
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))
    from diced.core import (
        CalculationResult,
        RollSequenceCalculator,
        SequenceOptions,
        apply_options,
        armour_outcomes,
        parse_sequence,
    )


def format_percent(probability: float) -> str:
    """Format a probability as a percentage string with one decimal."""

    return f"{probability * 100:.1f}%"


def format_token_for_display(token: str) -> str:
    """Format a token for display, converting block dice notation.
    
    Examples:
        "2d+" → "2d (Block)"
        "3d-" → "3d (No Turnover)"
        "1d*" → "1d (Pow)"
        "2d/" → "2d (Push Only)"
        "2+" → "2+"  (unchanged)
    """
    match = re.fullmatch(r"(-?[123]d)(\+-|-\+|[+*/-])?(\+\+)?", token)
    if not match:
        return token
    base, outcome, brawler = match.groups()
    labels = {
        "+": ["Block"],
        "-": ["No Turnover"],
        "*": ["Pow"],
        "/": ["Push Only"],
        "+-": ["Block", "No Turnover"],
        "-+": ["Block", "No Turnover"],
    }.get(outcome or "", [])
    if brawler:
        labels.append("Brawler")
    return f"{base} ({', '.join(labels)})" if labels else base


TOGGLES = (
    ("block", "Block"),
    ("pro", "Pro"),
    ("brawler", "Brawler"),
    ("mighty_blow", "MB"),
    ("stunty", "vs Stunty"),
)


def build_log_line(
    result: CalculationResult,
    total_width: int = 66,
    options: SequenceOptions | None = None,
) -> str:
    """Return a dot-leader log line similar to the desktop GUI."""

    sequence = " ".join(format_token_for_display(step.token) for step in result.steps)
    if options and options.labels:
        sequence += f" [{', '.join(options.labels)}]"
    base = format_percent(result.final_probability)
    rr1 = format_percent(result.probability_with_global_rerolls(1))
    rr2 = format_percent(result.probability_with_global_rerolls(2))
    result_str = f"{base} ({rr1} / {rr2})"
    dots = max(6, total_width - len(sequence) - len(result_str))
    return f"{sequence} {'.' * dots} {result_str}"


def format_armour_outcomes(outcomes: dict[str, dict[int, float]] | None) -> str:
    """One line like 'Break 31.3% · KO 21.1% · CAS 11.6%' (no team re-rolls)."""

    if not outcomes:
        return ""
    return " · ".join(f"{label} {format_percent(values[0])}" for label, values in outcomes.items())


def build_result_view(
    result: CalculationResult,
    options: SequenceOptions | None = None,
    armour: dict[str, dict[int, float]] | None = None,
) -> dict[str, object]:
    """Convert calculator output into a template-friendly structure."""

    base = format_percent(result.probability_with_global_rerolls(0))
    rr1 = format_percent(result.probability_with_global_rerolls(1))
    rr2 = format_percent(result.probability_with_global_rerolls(2))

    return {
        "base": base,
        "rr1": rr1,
        "rr2": rr2,
        "rr_pair": f"{rr1} / {rr2}",
        "parsed_tokens": [format_token_for_display(step.token) for step in result.steps],
        "log_line": build_log_line(result, options=options),
        "armour": format_armour_outcomes(armour),
        "options": options.labels if options else [],
        "steps": [
            {
                "index": index,
                "token": step.token,
                "single_attempt": format_percent(step.single_attempt_probability),
                "built_in": format_percent(step.roll_probability),
                "base": format_percent(step.cumulative_probabilities[0]),
                "rr1": format_percent(step.cumulative_probabilities[1]),
                "rr2": format_percent(step.cumulative_probabilities[2]),
            }
            for index, step in enumerate(result.steps, start=1)
        ],
    }


def create_app() -> Flask:
    """Create the Flask application."""

    app = Flask(__name__)
    calculator = RollSequenceCalculator()

    @app.get("/")
    def index() -> str:
        sequence_text = request.args.get("sequence", "").strip()
        toggles = {name: request.args.get(name) == "1" for name, _label in TOGGLES}
        error = ""
        result_view = None
        log_lines: list[str] = []

        if sequence_text:
            try:
                parsed, typed = parse_sequence(sequence_text)
                options = SequenceOptions(**toggles).merged(typed)
                sequence = apply_options(parsed, options)
                result = calculator.calculate(sequence, max_global_rerolls=2, pro=options.pro)
                armour = armour_outcomes(calculator, sequence, options)
                result_view = build_result_view(result, options=options, armour=armour)
            except ValueError as exc:
                error = str(exc)

        return render_template(
            "index.html",
            sequence_text=sequence_text,
            toggles=toggles,
            toggle_labels=TOGGLES,
            error=error,
            result=result_view,
            log_lines=log_lines,
            examples=["3++ 3+", "2d+", "3++ 2+ 2d av9k"],
        )

    return app


app = create_app()


def main() -> None:
    """Run the development web server."""

    app.run(debug=True)


if __name__ == "__main__":
    main()