"""Regression tests for the parsing and probability engine."""

import unittest

from diced.core import (
    ArmorValueTarget,
    BlockDiceTarget,
    RollSequenceCalculator,
    RollTarget,
    armor_and_injury_probability,
    armor_break_probability,
    block_die_single_probability,
    injury_roll_probability,
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

    def test_parses_armor_token_short_form(self) -> None:
        self.assertEqual(parse_roll_sequence("a9"), [ArmorValueTarget(target=9)])

    def test_parses_armor_token_long_form(self) -> None:
        self.assertEqual(parse_roll_sequence("av10"), [ArmorValueTarget(target=10)])

    def test_parses_armor_with_injury_k_suffix(self) -> None:
        self.assertEqual(parse_roll_sequence("av9k"), [ArmorValueTarget(target=9, injury_suffix="k")])

    def test_parses_armor_with_injury_alias_suffixes(self) -> None:
        self.assertEqual(parse_roll_sequence("av9sk"), [ArmorValueTarget(target=9, injury_suffix="ks")])
        self.assertEqual(parse_roll_sequence("av9is"), [ArmorValueTarget(target=9, injury_suffix="si")])

    def test_parses_armor_with_injury_m_modifier(self) -> None:
        self.assertEqual(parse_roll_sequence("av9km"), [ArmorValueTarget(target=9, injury_suffix="km")])
        self.assertEqual(parse_roll_sequence("av9mks"), [ArmorValueTarget(target=9, injury_suffix="ksm")])

    def test_parses_spaced_armor_and_injury_suffix(self) -> None:
        self.assertEqual(parse_roll_sequence("av9 k"), [ArmorValueTarget(target=9, injury_suffix="k")])
        self.assertEqual(parse_roll_sequence("av9 sim"), [ArmorValueTarget(target=9, injury_suffix="sim")])

    def test_parses_multi_part_spaced_armor_suffix_in_any_order(self) -> None:
        self.assertEqual(parse_roll_sequence("av9 s k m"), [ArmorValueTarget(target=9, injury_suffix="ksm")])
        self.assertEqual(parse_roll_sequence("av9 m s i"), [ArmorValueTarget(target=9, injury_suffix="sim")])
        self.assertEqual(parse_roll_sequence("av9 m k"), [ArmorValueTarget(target=9, injury_suffix="km")])

    def test_parses_mixed_compact_with_armor(self) -> None:
        self.assertEqual(
            parse_roll_sequence("3++2+2d-av9"),
            [
                RollTarget(threshold=3, local_rerolls=1),
                RollTarget(threshold=2, local_rerolls=0),
                BlockDiceTarget(dice_count=2, negative=False, outcome="-"),
                ArmorValueTarget(target=9),
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

    def test_rejects_invalid_armor_tokens(self) -> None:
        with self.assertRaises(ValueError):
            parse_roll_sequence("av12")
        with self.assertRaises(ValueError):
            parse_roll_sequence("av9x")
        with self.assertRaises(ValueError):
            parse_roll_sequence("av9kk")

    def test_parses_weighted_reroll_suffix(self) -> None:
        self.assertEqual(
            parse_roll_sequence("3+p"),
            [RollTarget(threshold=3, local_rerolls=0, weighted_reroll=True)],
        )

    def test_parses_multiple_weighted_rerolls_in_chain(self) -> None:
        self.assertEqual(
            parse_roll_sequence("2+p 4+p 5+"),
            [
                RollTarget(threshold=2, local_rerolls=0, weighted_reroll=True),
                RollTarget(threshold=4, local_rerolls=0, weighted_reroll=True),
                RollTarget(threshold=5, local_rerolls=0),
            ],
        )

    def test_rejects_weighted_reroll_with_normal_reroll(self) -> None:
        with self.assertRaises(ValueError):
            parse_roll_sequence("3++p")

    def test_parses_weighted_reroll_short_form(self) -> None:
        # Short form: 3p is equivalent to 3+p
        self.assertEqual(
            parse_roll_sequence("3p"),
            [RollTarget(threshold=3, local_rerolls=0, weighted_reroll=True)],
        )

    def test_parses_mixed_weighted_reroll_forms(self) -> None:
        # Mix short form (3p) and long form (4+p)
        self.assertEqual(
            parse_roll_sequence("3p 4+p 5p"),
            [
                RollTarget(threshold=3, local_rerolls=0, weighted_reroll=True),
                RollTarget(threshold=4, local_rerolls=0, weighted_reroll=True),
                RollTarget(threshold=5, local_rerolls=0, weighted_reroll=True),
            ],
        )

    def test_parses_compact_weighted_reroll_short_form(self) -> None:
        # Compact notation with short form: 3p2p4p
        self.assertEqual(
            parse_roll_sequence("3p2p4p"),
            [
                RollTarget(threshold=3, local_rerolls=0, weighted_reroll=True),
                RollTarget(threshold=2, local_rerolls=0, weighted_reroll=True),
                RollTarget(threshold=4, local_rerolls=0, weighted_reroll=True),
            ],
        )


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

    def test_weighted_reroll_probability(self) -> None:
        # 3+p: first attempt 4/6; on failure Pro 3+ (2/3) then re-roll at 4/6
        result = RollSequenceCalculator().calculate(parse_roll_sequence("3+p"))
        expected = (4 / 6) + (2 / 6) * (2 / 3) * (4 / 6)
        self.assertAlmostEqual(result.steps[0].roll_probability, expected)
        self.assertAlmostEqual(result.final_probability, expected)

    def test_weighted_reroll_does_not_consume_shared_rr(self) -> None:
        # 3+p should have identical probability across base/1RR/2RR
        result = RollSequenceCalculator().calculate(parse_roll_sequence("3+p"), max_global_rerolls=2)
        expected = (4 / 6) + (2 / 6) * (2 / 3) * (4 / 6)
        self.assertAlmostEqual(result.probability_with_global_rerolls(0), expected)
        self.assertAlmostEqual(result.probability_with_global_rerolls(1), expected)
        self.assertAlmostEqual(result.probability_with_global_rerolls(2), expected)

    def test_mixed_chain_with_weighted_and_normal_rerolls(self) -> None:
        # 2+ (5/6) then 3+p then 4+ (3/6)
        result = RollSequenceCalculator().calculate(parse_roll_sequence("2+ 3+p 4+"))
        expected = (5 / 6) * ((4 / 6) + (2 / 6) * (2 / 3) * (4 / 6)) * (3 / 6)
        self.assertAlmostEqual(result.final_probability, expected)

    def test_weighted_reroll_display_token(self) -> None:
        # Verify that display_token shows "(pro)" label
        targets = parse_roll_sequence("3+p")
        self.assertEqual(targets[0].display_token, "3+ (pro)")


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


class ArmorBreakProbabilityTests(unittest.TestCase):
    """Verify 2D6 armor break probability by target value."""

    def test_probability_for_av9(self) -> None:
        # Sums >= 9 on 2D6: 10 outcomes out of 36.
        self.assertAlmostEqual(armor_break_probability(9), 10 / 36)

    def test_probability_for_av10(self) -> None:
        # Sums >= 10 on 2D6: 6 outcomes out of 36.
        self.assertAlmostEqual(armor_break_probability(10), 6 / 36)

    def test_rejects_invalid_av_range(self) -> None:
        with self.assertRaises(ValueError):
            armor_break_probability(12)

    def test_injury_probability_k_is_eight_plus(self) -> None:
        self.assertAlmostEqual(injury_roll_probability("k"), 15 / 36)

    def test_injury_probability_i_is_ten_plus(self) -> None:
        self.assertAlmostEqual(injury_roll_probability("i"), 6 / 36)

    def test_injury_probability_alias_and_m(self) -> None:
        # sk => 7+ (21/36), skm => 6+ (26/36)
        self.assertAlmostEqual(injury_roll_probability("sk"), 21 / 36)
        self.assertAlmostEqual(injury_roll_probability("ksm"), 26 / 36)

    def test_combined_armor_and_injury_probability(self) -> None:
        # av9k = (10/36) * (15/36)
        self.assertAlmostEqual(
            armor_and_injury_probability(ArmorValueTarget(target=9, injury_suffix="k")),
            (10 / 36) * (15 / 36),
        )

    def test_rejects_invalid_injury_suffix(self) -> None:
        with self.assertRaises(ValueError):
            injury_roll_probability("sx")

    def test_armor_display_token_is_friendly(self) -> None:
        self.assertEqual(ArmorValueTarget(target=9, injury_suffix="k").display_token, "av9 ko")
        self.assertEqual(ArmorValueTarget(target=9, injury_suffix="i").display_token, "av9 injury")
        self.assertEqual(ArmorValueTarget(target=9, injury_suffix="ks").display_token, "av9 stunty ko")
        self.assertEqual(ArmorValueTarget(target=9, injury_suffix="si").display_token, "av9 stunty injury")
        self.assertEqual(ArmorValueTarget(target=9, injury_suffix="km").display_token, "av9 ko (mb)")


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

    def test_brawler_rerolls_one_both_down_die(self) -> None:
        # 2d++ (Brawler): faces per die: good 2/6, Both Down 1/6, other 3/6.
        # Fail with at least one Both Down -> re-roll that die (2/6).
        p, q, o = 2 / 6, 1 / 6, 3 / 6
        fail = (q + o) ** 2
        fixable = fail - o ** 2
        expected = (1 - fail) + fixable * p
        result = RollSequenceCalculator().calculate(parse_roll_sequence("2d++"), max_global_rerolls=2)
        self.assertAlmostEqual(result.probability_with_global_rerolls(0), expected)
        # Brawler is always preferred; only failures without Both Down use the RR.
        single = 1 - (4 / 6) ** 2
        self.assertAlmostEqual(result.probability_with_global_rerolls(1), expected + o ** 2 * single)
        two = RollSequenceCalculator().calculate(parse_roll_sequence("2d++ 4+"), max_global_rerolls=1)
        no_brawler = RollSequenceCalculator().calculate(parse_roll_sequence("2d 4+"), max_global_rerolls=1)
        self.assertGreater(two.final_probability, no_brawler.final_probability)

    def test_brawler_rerolled_block_cannot_use_pro_or_team_rr(self) -> None:
        # A failed Brawler re-roll ends the chain: no Pro, no team RR on top.
        p, q, o = 2 / 6, 1 / 6, 3 / 6
        fail = (q + o) ** 2
        fixable = fail - o ** 2
        single = 1 - (4 / 6) ** 2
        result = RollSequenceCalculator().calculate(parse_roll_sequence("2d++"), pro=True)
        # Pro / RR only ever reach the failures without a Both Down (o**2).
        self.assertAlmostEqual(result.final_probability, (1 - fail) + fixable * p + o ** 2 * (2 / 3) * p)
        self.assertAlmostEqual(
            result.probability_with_global_rerolls(2), (1 - fail) + fixable * p + o ** 2 * single
        )

    def test_brawler_no_effect_when_both_down_is_wanted(self) -> None:
        calc = RollSequenceCalculator()
        self.assertEqual(
            calc.calculate(parse_roll_sequence("2d+++")).global_reroll_probabilities,
            calc.calculate(parse_roll_sequence("2d+")).global_reroll_probabilities,
        )

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

    def test_mixed_compact_chain_with_armor(self) -> None:
        # Add av9 armor break to the compact mixed chain.
        result = RollSequenceCalculator().calculate(parse_roll_sequence("3++2+2d-av9"))
        expected = (8 / 9) * (5 / 6) * (1 - (2 / 6) ** 2) * (10 / 36)
        self.assertAlmostEqual(result.final_probability, expected)

    def test_mixed_compact_chain_with_armor_and_injury(self) -> None:
        # Add av9k: armor 9+ then injury 8+.
        result = RollSequenceCalculator().calculate(parse_roll_sequence("3++2+2d-av9k"))
        expected = (8 / 9) * (5 / 6) * (1 - (2 / 6) ** 2) * (10 / 36) * (15 / 36)
        self.assertAlmostEqual(result.final_probability, expected)

    def test_shared_rerolls_do_not_apply_to_armor_step(self) -> None:
        # av9 is a fixed 2D6 check: RR budget must not change its chance.
        result = RollSequenceCalculator().calculate(parse_roll_sequence("av9"), max_global_rerolls=2)
        expected = 10 / 36
        self.assertAlmostEqual(result.probability_with_global_rerolls(0), expected)
        self.assertAlmostEqual(result.probability_with_global_rerolls(1), expected)
        self.assertAlmostEqual(result.probability_with_global_rerolls(2), expected)

    def test_rejects_local_reroll_on_armor_target(self) -> None:
        with self.assertRaises(ValueError):
            RollSequenceCalculator().calculate([ArmorValueTarget(target=9, local_rerolls=1)])


class ProToggleTests(unittest.TestCase):
    """Pro gives one 2/3 reroll for the whole sequence."""

    def calc(self, text: str):
        return RollSequenceCalculator().calculate(parse_roll_sequence(text), pro=True)

    def test_single_die(self) -> None:
        self.assertAlmostEqual(self.calc("4+").final_probability, 0.5 + 0.5 * (2 / 3) * 0.5)

    def test_pro_used_only_once(self) -> None:
        # both pass, or exactly one fails and Pro saves it
        expected = 0.25 + 2 * 0.25 * (2 / 3) * 0.5
        self.assertAlmostEqual(self.calc("4+ 4+").final_probability, expected)

    def test_no_effect_on_own_reroll_or_armor(self) -> None:
        self.assertAlmostEqual(
            self.calc("3++ av9").final_probability,
            RollSequenceCalculator().calculate(parse_roll_sequence("3++ av9")).final_probability,
        )

    def test_team_reroll_still_helps(self) -> None:
        result = self.calc("4+ 4+")
        self.assertGreater(result.probability_with_global_rerolls(1), result.final_probability)
        self.assertAlmostEqual(result.probability_with_global_rerolls(2), 0.5625)

    def test_any_p_enables_pro_for_whole_sequence(self) -> None:
        from diced.core import parse_roll_sequence_with_pro
        expected = self.calc("4+ 4+").final_probability
        for text in ("4+ 4+ p", "p 4+ 4+", "4+, p, 4+", "4+p 4+", "4p 4+", "4+ 4P"):
            steps, pro = parse_roll_sequence_with_pro(text)
            self.assertTrue(pro, text)
            got = RollSequenceCalculator().calculate(steps, pro=pro).final_probability
            self.assertAlmostEqual(got, expected, msg=text)
        self.assertFalse(parse_roll_sequence_with_pro("4+ 4+")[1])

    def test_pro_rerolls_single_block_die(self) -> None:
        p = 1 / 3
        # 2d: both dice failed, one re-rolled die must hit
        expected = (1 - (1 - p) ** 2) + (1 - p) ** 2 * (2 / 3) * p
        self.assertAlmostEqual(self.calc("2d").final_probability, expected)
        # -2d: only a pool with exactly one bad die can be fixed
        expected = p ** 2 + 2 * p * (1 - p) * (2 / 3) * p
        self.assertAlmostEqual(self.calc("-2d").final_probability, expected)

    def test_pro_off_matches_default(self) -> None:
        seq = parse_roll_sequence("2+ 3+ 2d av9")
        calc = RollSequenceCalculator()
        self.assertEqual(
            calc.calculate(seq).global_reroll_probabilities,
            calc.calculate(seq, pro=False).global_reroll_probabilities,
        )


class MightyBlowTests(unittest.TestCase):
    """Mighty Blow modifies either armour or injury, chosen after the armour roll."""

    def test_mb_can_push_armour_through(self) -> None:
        def at_least(t: int) -> float:
            return sum(1 for a in range(1, 7) for b in range(1, 7) if a + b >= t) / 36

        expected = at_least(9) * at_least(7) + (at_least(8) - at_least(9)) * at_least(8)
        self.assertAlmostEqual(
            armor_and_injury_probability(ArmorValueTarget(target=9, injury_suffix="km")), expected
        )


class SequenceOptionTests(unittest.TestCase):
    """Sequence-wide skills: b (Brawler), p (Pro), and the toggles."""

    def test_b_anywhere_gives_every_block_brawler(self) -> None:
        from diced.core import apply_options, parse_sequence

        for text in ("2d- b 3d* av9", "b2d-3d*av9", "2d-b 3d* av9", "2d- 3d* av9 B"):
            steps, options = parse_sequence(text)
            self.assertTrue(options.brawler, text)
            blocks = [s for s in apply_options(steps, options) if isinstance(s, BlockDiceTarget)]
            self.assertEqual([b.local_rerolls for b in blocks], [1, 1], text)
            self.assertEqual([b.outcome for b in blocks], ["-", "*"], text)

    def test_s_means_stunty_except_after_a_d6_digit(self) -> None:
        from diced.core import apply_options, parse_sequence

        for text in ("2d- s av9k", "2d-s av9k", "2d-sav9k", "2d s av9k", "av9s k", "av9ks"):
            steps, options = parse_sequence(text)
            self.assertTrue(options.stunty, text)
            armour = apply_options(steps, options)[-1]
            self.assertEqual(armour.injury_suffix, "ks", text)
        steps, options = parse_sequence("224s3")
        self.assertFalse(options.stunty)
        self.assertEqual(steps[2], RollTarget(threshold=4, local_rerolls=1))

    def test_block_toggle_upgrades_outcomes(self) -> None:
        from diced.core import SequenceOptions, apply_options

        steps = apply_options(parse_roll_sequence("2d 2d- 2d* 2d/"), SequenceOptions(block=True))
        self.assertEqual([s.outcome for s in steps], ["+", "+-", "*", "/"])

    def test_armour_outcomes(self) -> None:
        from diced.core import SequenceOptions, apply_options, armour_outcomes

        options = SequenceOptions(mighty_blow=True, stunty=True)
        steps = apply_options(parse_roll_sequence("1d av9"), options)
        out = armour_outcomes(RollSequenceCalculator(), steps, options)
        block = 1 / 6  # vs Stunty the stumble is only a push: Pow alone
        self.assertAlmostEqual(out["Break"][0], block * 15 / 36)  # MB: 8+
        ko = armor_and_injury_probability(ArmorValueTarget(target=9, injury_suffix="ksm"))
        cas = armor_and_injury_probability(ArmorValueTarget(target=9, injury_suffix="sim"))
        self.assertAlmostEqual(out["KO"][0], block * ko)
        self.assertAlmostEqual(out["CAS"][0], block * cas)
        self.assertIsNone(armour_outcomes(RollSequenceCalculator(), parse_roll_sequence("4+"), options))


class RulesCrossCheckTests(unittest.TestCase):
    """Independent brute-force checks of the dice rules."""

    FACES = ("pow", "stumble", "push", "push", "both", "skull")

    def _pick(self, faces, negative, block, stunty):
        """The result actually applied: attacker or defender picks by game value."""
        eff = ["push" if f == "stumble" and stunty else f for f in faces]
        # value for the attacker, low = bad
        value = {"skull": 0, "both": 4 if block else 1, "push": 2, "stumble": 3, "pow": 5}
        return (min if negative else max)(eff, key=value.get), eff

    def _wanted(self, outcome, chosen, eff, negative):
        sets = {
            "": {"pow", "stumble"}, "+": {"pow", "stumble", "both"}, "*": {"pow"},
            "-": {"pow", "stumble", "push"}, "+-": {"pow", "stumble", "push", "both"}, "/": {"push"},
        }[outcome]
        if negative:
            return chosen in sets
        return any(f in sets for f in eff)  # the attacker picks what they need

    def test_block_pools_by_brute_force(self) -> None:
        from itertools import product
        from diced.core import BlockDiceTarget

        for n, negative, outcome, block, stunty in product(
            (1, 2, 3), (False, True), ("", "+", "*", "-", "+-", "/"), (False, True), (False, True)
        ):
            if n == 1 and negative:
                continue
            block = block or "+" in outcome
            hits = 0
            for faces in product(self.FACES, repeat=n):
                chosen, eff = self._pick(faces, negative, block, stunty)
                hits += self._wanted(outcome, chosen, eff, negative)
            target = BlockDiceTarget(n, negative, outcome, block=block, stunty=stunty)
            with self.subTest(n=n, negative=negative, outcome=outcome, block=block, stunty=stunty):
                self.assertAlmostEqual(target.base_probability, hits / 6 ** n)

    def test_stunty_block_faces(self) -> None:
        from diced.core import BlockDiceTarget

        self.assertAlmostEqual(BlockDiceTarget(1, False, "", stunty=True).base_probability, 1 / 6)
        self.assertAlmostEqual(BlockDiceTarget(1, False, "+", block=True, stunty=True).base_probability, 2 / 6)
        self.assertAlmostEqual(BlockDiceTarget(1, False, "-", stunty=True).base_probability, 4 / 6)
        self.assertAlmostEqual(BlockDiceTarget(1, False, "/", stunty=True).base_probability, 3 / 6)
        self.assertAlmostEqual(BlockDiceTarget(1, False, "*", stunty=True).base_probability, 1 / 6)

    def test_defender_picks_push_only(self) -> None:
        from diced.core import BlockDiceTarget

        # Defender takes a Push over a Pow: success = no Skull, no Both Down, at least one Push.
        self.assertAlmostEqual(BlockDiceTarget(2, True, "/").base_probability, (16 - 4) / 36)

    def test_one_plus_is_two_plus(self) -> None:
        self.assertAlmostEqual(RollSequenceCalculator.roll_probability(1), 5 / 6)

    def test_brawler_then_nothing_else(self) -> None:
        from diced.core import BlockDiceTarget

        # 1d Brawler: Pow/stumble 2/6; Both Down (1/6) gets the Brawler re-roll (2/6) and
        # nothing else even with team re-rolls; Push/Skull (3/6) may use a team re-roll.
        t = BlockDiceTarget(1, False, "", local_rerolls=1)
        result = RollSequenceCalculator().calculate([t], max_global_rerolls=1)
        self.assertAlmostEqual(result.global_reroll_probabilities[0], 2 / 6 + 1 / 6 * 2 / 6)
        self.assertAlmostEqual(
            result.global_reroll_probabilities[1], 2 / 6 + 1 / 6 * 2 / 6 + 3 / 6 * 2 / 6
        )

    def test_pro_and_team_reroll_not_on_same_roll(self) -> None:
        # One 4+ with Pro and a team re-roll: only one of them on the failed die.
        result = RollSequenceCalculator().calculate(parse_roll_sequence("4+"), max_global_rerolls=1, pro=True)
        self.assertAlmostEqual(result.global_reroll_probabilities[1], 0.5 + 0.5 * 0.5)


if __name__ == "__main__":
    unittest.main()