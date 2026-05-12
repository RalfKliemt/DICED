"""Flask web interface for the DICED calculator."""

from __future__ import annotations

from flask import Flask, render_template, request

from .core import CalculationResult, RollSequenceCalculator, parse_roll_sequence


def format_percent(probability: float) -> str:
    """Format a probability as a percentage string with two decimals."""

    return f"{probability * 100:.2f}%"


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
        error = ""
        result_view = None

        if sequence_text:
            try:
                sequence = parse_roll_sequence(sequence_text)
                result = calculator.calculate(sequence, max_global_rerolls=2)
                result_view = build_result_view(result)
            except ValueError as exc:
                error = str(exc)

        return render_template(
            "index.html",
            sequence_text=sequence_text,
            error=error,
            result=result_view,
            examples=["224s3", "3++ 4+ 5+", "2+ 2d+ 4+", "2+, 3+, 4+"],
        )

    return app


app = create_app()


def main() -> None:
    """Run the development web server."""

    app.run(debug=True)