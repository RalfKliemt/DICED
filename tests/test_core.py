"""Regression tests for the parsing and probability engine."""

import unittest

from rollcoaster.core import (
    BlockDiceTarget,
    RollSequenceCalculator,
    RollTarget,
    block_die_single_probability,
    parse_roll_sequence,
)


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

    def test_parses_mixed_compact_d6_and_block_without_spaces(self) -> None:
        self.assertEqual(
            parse_roll_sequence("3++2+2d-"),
            [
                RollTarget(threshold=3, local_rerolls=1),
                RollTarget(threshold=2, local_rerolls=0),
                BlockDiceTarget(dice_count=2, negative=False, outcome="-"),
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


class BlockDiceProbabilityTests(unittest.TestCase):
    """Verify face-count probability for each outcome symbol."""

    def test_default_outcome_is_two_in_six(self) -> None:
        self.assertAlmostEqual(block_die_single_probability(""), 2 / 6)

    def test_plus_outcome_is_three_in_six(self) -> None:
        self.assertAlmostEqual(block_die_single_probability("+"), 3 / 6)

    def test_star_outcome_is_one_in_six(self) -> None:
        self.assertAlmostEqual(block_die_single_probability("*"), 1 / 6)

    def test_minus_outcome_is_four_in_six(self) -> None:
        self.assertAlmostEqual(block_die_single_probability("-"), 4 / 6)

    def test_plusminus_outcome_is_five_in_six(self) -> None:
        self.assertAlmostEqual(block_die_single_probability("+-"), 5 / 6)

    def test_slash_outcome_is_two_in_six(self) -> None:
        self.assertAlmostEqual(block_die_single_probability("/"), 2 / 6)

    def test_rejects_unknown_outcome(self) -> None:
        with self.assertRaises(ValueError):
            block_die_single_probability("?")


class ParseBlockDiceTests(unittest.TestCase):
    """Ensure block dice tokens are parsed correctly."""

    def test_parses_one_die_default(self) -> None:
        result = parse_roll_sequence("1d")
        self.assertEqual(result, [BlockDiceTarget(dice_count=1, negative=False, outcome="")])

    def test_parses_two_die_plus(self) -> None:
        result = parse_roll_sequence("2d+")
        self.assertEqual(result, [BlockDiceTarget(dice_count=2, negative=False, outcome="+")])

    def test_parses_three_die_star(self) -> None:
        result = parse_roll_sequence("3d*")
        self.assertEqual(result, [BlockDiceTarget(dice_count=3, negative=False, outcome="*")])

    def test_parses_negative_two_die(self) -> None:
        result = parse_roll_sequence("-2d")
        self.assertEqual(result, [BlockDiceTarget(dice_count=2, negative=True, outcome="")])

    def test_parses_negative_three_die_minus(self) -> None:
        result = parse_roll_sequence("-3d-")
        self.assertEqual(result, [BlockDiceTarget(dice_count=3, negative=True, outcome="-")])

    def test_parses_plusminus_normalised(self) -> None:
        self.assertEqual(parse_roll_sequence("2d+-"), [BlockDiceTarget(2, False, "+-")])
        self.assertEqual(parse_roll_sequence("2d-+"), [BlockDiceTarget(2, False, "+-")])

    def test_parses_slash_outcome(self) -> None:
        result = parse_roll_sequence("2d/")
        self.assertEqual(result, [BlockDiceTarget(dice_count=2, negative=False, outcome="/")])

    def test_parses_brawler_reroll_suffix(self) -> None:
        # 2d++ means default outcome with local reroll (Brawler)
        result = parse_roll_sequence("2d++")
        self.assertEqual(result, [BlockDiceTarget(dice_count=2, negative=False, outcome="", local_rerolls=1)])

    def test_parses_brawler_with_outcome(self) -> None:
        # 2d+++ means outcome '+' with local reroll (Brawler)
        result = parse_roll_sequence("2d+++")
        self.assertEqual(result, [BlockDiceTarget(dice_count=2, negative=False, outcome="+", local_rerolls=1)])

    def test_parses_mixed_chain(self) -> None:
        result = parse_roll_sequence("3+ 2d+ 4+")
        self.assertEqual(result, [
            RollTarget(threshold=3, local_rerolls=0),
            BlockDiceTarget(dice_count=2, negative=False, outcome="+"),
            RollTarget(threshold=4, local_rerolls=0),
        ])

    def test_rejects_invalid_block_token(self) -> None:
        with self.assertRaises(ValueError):
            parse_roll_sequence("4d+")  # 4 dice is not valid


class BlockDiceCalculatorTests(unittest.TestCase):
    """Verify probability math for block dice steps."""

    def test_one_die_base_probability(self) -> None:
        result = RollSequenceCalculator().calculate(parse_roll_sequence("1d"))
        self.assertAlmostEqual(result.final_probability, 2 / 6)

    def test_two_die_attacker_picks_at_least_one(self) -> None:
        # p = 2/6; P(at least one) = 1 - (4/6)^2
        result = RollSequenceCalculator().calculate(parse_roll_sequence("2d"))
        expected = 1 - (4 / 6) ** 2
        self.assertAlmostEqual(result.final_probability, expected)

    def test_three_die_attacker_picks(self) -> None:
        result = RollSequenceCalculator().calculate(parse_roll_sequence("3d"))
        expected = 1 - (4 / 6) ** 3
        self.assertAlmostEqual(result.final_probability, expected)

    def test_negative_two_die_all_must_succeed(self) -> None:
        # p = 2/6; P(all succeed) = (2/6)^2
        result = RollSequenceCalculator().calculate(parse_roll_sequence("-2d"))
        expected = (2 / 6) ** 2
        self.assertAlmostEqual(result.final_probability, expected)

    def test_negative_three_die_all_must_succeed(self) -> None:
        result = RollSequenceCalculator().calculate(parse_roll_sequence("-3d"))
        expected = (2 / 6) ** 3
        self.assertAlmostEqual(result.final_probability, expected)

    def test_global_reroll_on_block_dice(self) -> None:
        # 1d default: p = 2/6; with 1 global RR: 1 - (4/6)^2
        result = RollSequenceCalculator().calculate(parse_roll_sequence("1d"), max_global_rerolls=2)
        base = 2 / 6
        with_rr = 1 - (1 - base) ** 2
        self.assertAlmostEqual(result.probability_with_global_rerolls(0), base)
        self.assertAlmostEqual(result.probability_with_global_rerolls(1), with_rr)

    def test_brawler_reroll_on_block_dice(self) -> None:
        # 2d++ (Brawler): p_pool = 1-(4/6)^2; local reroll doubles attempt
        # effective p = 1 - (1 - p_pool)^2; no global RR consumed
        result = RollSequenceCalculator().calculate(parse_roll_sequence("2d++"), max_global_rerolls=2)
        p_pool = 1 - (4 / 6) ** 2
        expected = 1 - (1 - p_pool) ** 2
        self.assertAlmostEqual(result.probability_with_global_rerolls(0), expected)
        # Brawler uses its own reroll — shared RRs unchanged
        self.assertAlmostEqual(result.probability_with_global_rerolls(1), expected)
        self.assertAlmostEqual(result.probability_with_global_rerolls(2), expected)

    def test_mixed_chain_d6_and_block(self) -> None:
        # 3+ (4/6) then 2d+ (1-(3/6)^2 = 3/4)
        result = RollSequenceCalculator().calculate(parse_roll_sequence("3+ 2d+"))
        block_p = 1 - (3 / 6) ** 2
        self.assertAlmostEqual(result.final_probability, (4 / 6) * block_p)

    def test_mixed_compact_chain_d6_and_block(self) -> None:
        # 3++ then 2+ then 2d- in one compact input: 8/9 * 5/6 * (1-(2/6)^2)
        result = RollSequenceCalculator().calculate(parse_roll_sequence("3++2+2d-"))
        expected = (8 / 9) * (5 / 6) * (1 - (2 / 6) ** 2)
        self.assertAlmostEqual(result.final_probability, expected)


if __name__ == "__main__":
    unittest.main()