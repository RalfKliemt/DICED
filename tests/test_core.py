"""Regression tests for the parsing and probability engine."""

import unittest

from rollcoaster.core import RollSequenceCalculator, RollTarget, parse_roll_sequence


class ParseRollSequenceTests(unittest.TestCase):
    """Ensure user input is converted into the expected structured targets."""

    def test_parses_comma_separated_values(self) -> None:
        self.assertEqual(
            parse_roll_sequence("2+, 3+, 4+"),
            [
                RollTarget(threshold=2, local_rerolls=0),
                RollTarget(threshold=3, local_rerolls=0),
                RollTarget(threshold=4, local_rerolls=0),
            ],
        )

    def test_parses_space_separated_values(self) -> None:
        self.assertEqual(
            parse_roll_sequence("2+ 5+ 6+"),
            [
                RollTarget(threshold=2, local_rerolls=0),
                RollTarget(threshold=5, local_rerolls=0),
                RollTarget(threshold=6, local_rerolls=0),
            ],
        )

    def test_parses_concatenated_explicit_values(self) -> None:
        self.assertEqual(
            parse_roll_sequence("2+3+4+"),
            [
                RollTarget(threshold=2, local_rerolls=0),
                RollTarget(threshold=3, local_rerolls=0),
                RollTarget(threshold=4, local_rerolls=0),
            ],
        )

    def test_parses_concatenated_mixed_values(self) -> None:
        self.assertEqual(
            parse_roll_sequence("2+3++4s5+"),
            [
                RollTarget(threshold=2, local_rerolls=0),
                RollTarget(threshold=3, local_rerolls=1),
                RollTarget(threshold=4, local_rerolls=1),
                RollTarget(threshold=5, local_rerolls=0),
            ],
        )

    def test_parses_compact_shorthand_values(self) -> None:
        self.assertEqual(
            parse_roll_sequence("224s3"),
            [
                RollTarget(threshold=2, local_rerolls=0),
                RollTarget(threshold=2, local_rerolls=0),
                RollTarget(threshold=4, local_rerolls=1),
                RollTarget(threshold=3, local_rerolls=0),
            ],
        )

    def test_parses_compact_with_trailing_reroll_marker(self) -> None:
        self.assertEqual(
            parse_roll_sequence("33++"),
            [
                RollTarget(threshold=3, local_rerolls=0),
                RollTarget(threshold=3, local_rerolls=1),
            ],
        )

    def test_parses_inline_mixed_notation(self) -> None:
        self.assertEqual(
            parse_roll_sequence("2+4s"),
            [
                RollTarget(threshold=2, local_rerolls=0),
                RollTarget(threshold=4, local_rerolls=1),
            ],
        )

    def test_parses_mixed_explicit_and_compact_values(self) -> None:
        self.assertEqual(
            parse_roll_sequence("2+ 4s 3++"),
            [
                RollTarget(threshold=2, local_rerolls=0),
                RollTarget(threshold=4, local_rerolls=1),
                RollTarget(threshold=3, local_rerolls=1),
            ],
        )

    def test_parses_local_reroll_notation(self) -> None:
        self.assertEqual(
            parse_roll_sequence("3++ 4+"),
            [
                RollTarget(threshold=3, local_rerolls=1),
                RollTarget(threshold=4, local_rerolls=0),
            ],
        )

    def test_rejects_multiple_rerolls_on_one_die(self) -> None:
        with self.assertRaises(ValueError):
            parse_roll_sequence("4+++")

    def test_rejects_empty_input(self) -> None:
        with self.assertRaises(ValueError):
            parse_roll_sequence("   ")

    def test_rejects_invalid_tokens(self) -> None:
        with self.assertRaises(ValueError):
            parse_roll_sequence("2+, 8+")

    def test_rejects_invalid_compact_tokens(self) -> None:
        with self.assertRaises(ValueError):
            parse_roll_sequence("22x3")


class RollSequenceCalculatorTests(unittest.TestCase):
    """Verify the calculator returns correct probabilities for common cases."""

    def test_calculates_cumulative_probability(self) -> None:
        result = RollSequenceCalculator().calculate(parse_roll_sequence("2+ 3+"))
        self.assertAlmostEqual(result.steps[0].roll_probability, 5 / 6)
        self.assertAlmostEqual(result.steps[1].roll_probability, 4 / 6)
        self.assertAlmostEqual(result.final_probability, (5 / 6) * (4 / 6))

    def test_applies_local_reroll_probability(self) -> None:
        result = RollSequenceCalculator().calculate(parse_roll_sequence("3++"))
        self.assertAlmostEqual(result.steps[0].single_attempt_probability, 4 / 6)
        self.assertAlmostEqual(result.steps[0].roll_probability, 1 - (2 / 6) ** 2)

    def test_calculates_global_reroll_probability(self) -> None:
        result = RollSequenceCalculator().calculate(parse_roll_sequence("3+ 4+"), max_global_rerolls=2)
        self.assertAlmostEqual(result.probability_with_global_rerolls(0), (4 / 6) * (3 / 6))
        self.assertAlmostEqual(result.probability_with_global_rerolls(1), 11 / 18)
        self.assertAlmostEqual(result.probability_with_global_rerolls(2), 2 / 3)

    def test_shared_reroll_cannot_stack_with_built_in_reroll(self) -> None:
        result = RollSequenceCalculator().calculate(parse_roll_sequence("3++"), max_global_rerolls=2)
        self.assertAlmostEqual(result.probability_with_global_rerolls(0), 8 / 9)
        self.assertAlmostEqual(result.probability_with_global_rerolls(1), 8 / 9)
        self.assertAlmostEqual(result.probability_with_global_rerolls(2), 8 / 9)

    def test_rejects_invalid_threshold(self) -> None:
        with self.assertRaises(ValueError):
            RollSequenceCalculator().calculate([RollTarget(threshold=7, local_rerolls=0)])


if __name__ == "__main__":
    unittest.main()