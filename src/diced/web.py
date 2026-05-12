"""Flask web interface for the DICED calculator."""

from __future__ import annotations

import sys
from pathlib import Path

from flask import Flask, render_template, request, session

try:
    from .core import CalculationResult, RollSequenceCalculator, parse_roll_sequence
except ImportError:
    # Support direct execution: `python src/diced/web.py`.
    src_dir = Path(__file__).resolve().parents[1]
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))
    from diced.core import CalculationResult, RollSequenceCalculator, parse_roll_sequence


def format_percent(probability: float) -> str:
    """Format a probability as a percentage string with one decimal."""

    return f"{probability * 100:.1f}%"


def build_log_line(result: CalculationResult, total_width: int = 66) -> str:
    """Return a dot-leader log line similar to the desktop GUI."""

    sequence = " ".join(step.token for step in result.steps)
    base = format_percent(result.final_probability)
    rr1 = format_percent(result.probability_with_global_rerolls(1))
    rr2 = format_percent(result.probability_with_global_rerolls(2))
    result_str = f"{base} ({rr1} / {rr2})"
    dots = max(6, total_width - len(sequence) - len(result_str))
    return f"{sequence} {'.' * dots} {result_str}"


def build_result_view(result: CalculationResult) -> dict[str, object]:
    """Convert calculator output into a template-friendly structure."""

    base = format_percent(result.probability_with_global_rerolls(0))
    rr1 = format_percent(result.probability_with_global_rerolls(1))
    rr2 = format_percent(result.probability_with_global_rerolls(2))

    return {
        "base": base,
        "rr1": rr1,
        "rr2": rr2,
        "rr_pair": f"({rr1} / {rr2})",
        "parsed_tokens": [step.token for step in result.steps],
        "log_line": build_log_line(result),
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
    app.config["SECRET_KEY"] = "diced-dev-secret"
    calculator = RollSequenceCalculator()

    @app.get("/")
    def index() -> str:
        sequence_text = request.args.get("sequence", "").strip()
        error = ""
        result_view = None
        log_lines = session.get("log_lines", [])

        if sequence_text:
            try:
                sequence = parse_roll_sequence(sequence_text)
                result = calculator.calculate(sequence, max_global_rerolls=2)
                result_view = build_result_view(result)
                log_lines.append(result_view["log_line"])
            except ValueError as exc:
                error = str(exc)
                log_lines.append(f"{sequence_text}: ERROR ({error})")

            session["log_lines"] = log_lines[-7:]
            log_lines = session["log_lines"]

        return render_template(
            "index.html",
            sequence_text=sequence_text,
            error=error,
            result=result_view,
            log_lines=log_lines,
            examples=["224s3", "3++ 4+ 5+", "2+ 2d+ 4+", "2+, 3+, 4+"],
        )

    return app


app = create_app()


def main() -> None:
    """Run the development web server."""

    app.run(debug=True)


if __name__ == "__main__":
    main()