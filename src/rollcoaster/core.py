"""Core parsing and probability math for chained D6 and block dice calculations.

The calculator supports two reroll concepts:

- one local reroll encoded in a token such as 3++
- a shared pool of global rerolls, reported as 1RR and 2RR in the UI

Any single die may be rerolled at most once. A die that already has a built-in
reroll from ++ cannot also consume a shared RR.

Block dice tokens use Blood Bowl block die notation, e.g. 2d+ for a two-die
block targeting a "both-down-or-better" result. Negative counts (-2d) mean the
defending player picks, so all dice must show the desired face.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Union


@dataclass(frozen=True)
class RollTarget:
    """Single parsed roll target.

    `threshold` is the minimum D6 face needed to succeed.
    `local_rerolls` is 0 or 1 and counts whether the die has its own reroll.
    """

    threshold: int
    local_rerolls: int

    @property
    def token(self) -> str:
        """Rebuild the user-facing token, for example 3++."""
        return f"{self.threshold}{'+' * (self.local_rerolls + 1)}"

    @property
    def display_token(self) -> str:
        """Return the display token shown in logs and tables."""
        return self.token


# ---------------------------------------------------------------------------
# Block dice
# ---------------------------------------------------------------------------

# Standard Blood Bowl block die has 6 faces:
#   POW, POW/SKULL, BOTH DOWN, PUSH, PUSH, SKULL
# (PUSH appears on two faces, all others appear on one.)
_BLOCK_OUTCOME_FACES: dict[str, int] = {
    "": 2,    # POW + POW/SKULL  ("5+" equivalent)
    "+": 3,   # POW + POW/SKULL + BOTH DOWN  ("4+")
    "*": 1,   # POW only  ("6+")
    "-": 4,   # No turnover: POW + BOTH DOWN + PUSH×2  ("3+")
    "+-": 5,  # No skull: all except SKULL  ("2+")
    "/": 2,   # Push only: PUSH×2  ("5+" by face count)
}


def block_die_single_probability(outcome: str) -> float:
    """Return the probability of the desired outcome on one block die."""
    if outcome not in _BLOCK_OUTCOME_FACES:
        raise ValueError(
            f"Unknown block die outcome: {outcome!r}. "
            "Use '', '+', '*', '-', '+-', or '/'." 
        )
    return _BLOCK_OUTCOME_FACES[outcome] / 6


@dataclass(frozen=True)
class BlockDiceTarget:
    """A Blood Bowl block dice pool roll.

    `dice_count` is 1, 2, or 3.
    `negative` is True for -2d/-3d where the defender picks: all dice must show
    the desired face.  False means attacker picks: at least one die must match.
    `outcome` is one of '', '+', '*', '-', '+-', '/'.
    `local_rerolls` is 0 or 1 and works like on a D6 step (whole pool reroll).
    """

    dice_count: int
    negative: bool
    outcome: str
    local_rerolls: int = 0

    @property
    def token(self) -> str:
        """Rebuild the user-facing token, for example 2d+ or -3d+-."""
        sign = "-" if self.negative else ""
        reroll_marker = "++" if self.local_rerolls else ""
        return f"{sign}{self.dice_count}d{self.outcome}{reroll_marker}"

    @property
    def display_token(self) -> str:
        """Return the display token shown in logs and tables."""
        return self.token

    @property
    def base_probability(self) -> float:
        """Pool success probability on a single attempt."""
        p = block_die_single_probability(self.outcome)
        if self.negative:
            return p ** self.dice_count
        return 1 - (1 - p) ** self.dice_count


@dataclass(frozen=True)
class ArmorValueTarget:
    """A 2D6 armor break roll target such as a9, av9k, or av9sim.

    `target` is the minimum 2D6 sum required to succeed.
    `injury_suffix` optionally encodes a follow-up injury roll target:
    - k => 8+
    - i => 10+
    - ks/sk => 7+
    - si/is => 9+
    Adding `m` lowers the injury target by 1.
    `local_rerolls` is 0 or 1 for consistency with other step types.
    """

    target: int
    injury_suffix: str = ""
    local_rerolls: int = 0

    @property
    def token(self) -> str:
        """Rebuild a canonical token, for example av9 or av9ksm."""
        return f"av{self.target}{self.injury_suffix}"

    @property
    def display_token(self) -> str:
        """Return a friendlier label for logs and result tables."""

        if not self.injury_suffix:
            return f"av{self.target}"

        has_m = self.injury_suffix.endswith("m")
        core = self.injury_suffix[:-1] if has_m else self.injury_suffix
        label = {
            "k": "ko",
            "i": "injury",
            "ks": "stunty ko",
            "si": "stunty injury",
        }[core]
        if has_m:
            label += " (mb)"
        return f"av{self.target} {label}"


def armor_break_probability(target: int) -> float:
    """Probability that 2D6 is greater than or equal to ``target``."""

    if target < 1 or target > 11:
        raise ValueError("Armor value target must be between 1 and 11.")
    successful = sum(1 for die1 in range(1, 7) for die2 in range(1, 7) if die1 + die2 >= target)
    return successful / 36


_INJURY_BASE_TARGETS: dict[str, int] = {
    "k": 8,
    "i": 10,
    "ks": 7,
    "si": 9,
}


def _normalize_injury_suffix(suffix: str) -> str:
    """Normalise accepted injury suffix spellings into canonical form.

    Canonical forms are: `k`, `i`, `ks`, `si` with optional trailing `m`.
    """

    if not suffix:
        return ""

    lowered = suffix.lower()
    if any(ch not in "kism" for ch in lowered):
        raise ValueError(
            f"Invalid injury suffix: {suffix!r}. Use k, i, ks/sk, si/is, optionally with m."
        )

    m_count = lowered.count("m")
    if m_count > 1:
        raise ValueError(
            f"Invalid injury suffix: {suffix!r}. 'm' can be used at most once."
        )

    has_m = m_count == 1
    core = lowered.replace("m", "")
    core = {"sk": "ks", "is": "si"}.get(core, core)

    if core not in _INJURY_BASE_TARGETS:
        raise ValueError(
            f"Invalid injury suffix: {suffix!r}. Use k, i, ks/sk, si/is, optionally with m."
        )

    return core + ("m" if has_m else "")


def injury_roll_probability(suffix: str) -> float:
    """Return 2D6 injury success probability for a validated injury suffix."""

    normalized = _normalize_injury_suffix(suffix)
    if not normalized:
        return 1.0

    has_m = normalized.endswith("m")
    core = normalized[:-1] if has_m else normalized
    target = _INJURY_BASE_TARGETS[core] - (1 if has_m else 0)
    successful = sum(1 for die1 in range(1, 7) for die2 in range(1, 7) if die1 + die2 >= target)
    return successful / 36


def armor_and_injury_probability(target: ArmorValueTarget) -> float:
    """Probability for armor break plus optional injury roll."""

    return armor_break_probability(target.target) * injury_roll_probability(target.injury_suffix)


Step = Union[RollTarget, BlockDiceTarget, ArmorValueTarget]


@dataclass(frozen=True)
class StepResult:
    """Probability summary for one roll inside the chain."""

    token: str
    threshold: int | None  # None for non-D6 steps
    local_rerolls: int
    single_attempt_probability: float
    roll_probability: float
    cumulative_probabilities: dict[int, float]


@dataclass(frozen=True)
class CalculationResult:
    """Full result for a parsed sequence, including per-step and final odds."""

    sequence: list[Step]
    steps: list[StepResult]
    global_reroll_probabilities: dict[int, float]

    @property
    def final_probability(self) -> float:
        """Return the base chain chance without any shared rerolls."""
        if not self.global_reroll_probabilities:
            return 0.0
        return self.global_reroll_probabilities[0]

    def probability_with_global_rerolls(self, rerolls: int) -> float:
        """Return the final chain chance for a specific shared reroll budget."""
        return self.global_reroll_probabilities[rerolls]


def parse_roll_sequence(raw_text: str) -> list[Step]:
    """Split user input into ordered roll targets.

    Accepts D6 tokens (``2+``, ``3++``, ``224s3``), block dice tokens
    (``1d``, ``2d+``, ``-3d*``, ``2d+-``), and armor tokens (``a9``, ``av9``,
    ``av9k``, ``av9sim``)
    in any mix, separated by spaces or commas. Compact notation without
    whitespace such as ``3++2+2d-av9`` is also supported.
    """

    raw_parts = [p for p in re.split(r"[,\s]+", raw_text.strip()) if p]
    if not raw_parts:
        raise ValueError("Enter at least one target roll such as 2+, 3+, 4+.")

    raw_parts = _combine_spaced_armor_injury_tokens(raw_parts)

    result: list[Step] = []
    for part in raw_parts:
        result.extend(_parse_mixed_part(part))

    return result


def _combine_spaced_armor_injury_tokens(raw_parts: list[str]) -> list[str]:
    """Merge tokens like `av9 k` or `av9 s k m` into one logical armor token."""

    combined: list[str] = []
    index = 0
    while index < len(raw_parts):
        current = raw_parts[index]
        if _is_plain_armor_token(current):
            suffix_parts: list[str] = []
            next_index = index + 1
            while next_index < len(raw_parts) and _is_injury_suffix_fragment_token(raw_parts[next_index]):
                suffix_parts.append(raw_parts[next_index])
                next_index += 1

            if suffix_parts:
                combined.append(current + "".join(suffix_parts))
                index = next_index
                continue

            combined.append(current)
            index += 1
            continue

        combined.append(current)
        index += 1

    return combined


def _is_plain_armor_token(token: str) -> bool:
    """Return True for `aN`/`avN` tokens that do not already have a suffix."""

    return re.fullmatch(r"a(?:v)?(?:[1-9]|10|11)", token.lower()) is not None


def _is_injury_suffix_token(token: str) -> bool:
    """Return True when the token is a valid standalone injury suffix."""

    try:
        return bool(_normalize_injury_suffix(token))
    except ValueError:
        return False


def _is_injury_suffix_fragment_token(token: str) -> bool:
    """Return True for raw suffix fragments composed only of i/k/s/m letters."""

    return re.fullmatch(r"[kismKISM]+", token) is not None


def _parse_mixed_part(part: str) -> list[Step]:
    """Parse one compact segment that may mix D6 and block dice tokens.

    Supports strings like ``3++2+2d-av9`` with no whitespace between token
    types.
    """

    steps: list[Step] = []
    index = 0
    while index < len(part):
        if _starts_armor_token(part, index):
            target, index = _parse_armor_target_from(part, index)
            steps.append(target)
            continue

        if _starts_block_token(part, index):
            target, index = _parse_block_target_from(part, index)
            steps.append(target)
            continue

        target, index = _parse_d6_target_from(part, index)
        steps.append(target)

    return steps


def _starts_armor_token(text: str, index: int) -> bool:
    """Return True when an armor token starts at ``text[index]``."""

    if index >= len(text):
        return False
    if text[index].lower() != "a":
        return False

    next_index = index + 1
    if next_index < len(text) and text[next_index].lower() == "v":
        next_index += 1

    return next_index < len(text) and text[next_index].isdigit()


def _parse_armor_target_from(text: str, index: int) -> tuple[ArmorValueTarget, int]:
    """Parse one armor token (aN/avN plus optional injury suffix) from text."""

    start = index
    if text[index].lower() != "a":
        raise ValueError(f"Invalid armor token near {text[start:]!r}.")
    index += 1

    if index < len(text) and text[index].lower() == "v":
        index += 1

    if index >= len(text) or not text[index].isdigit():
        raise ValueError(
            f"Invalid armor token near {text[start:]!r}. Use a1..a11 or av1..av11."
        )

    # Parse one or two digits only because valid AV range is 1..11.
    digits = text[index]
    index += 1
    if index < len(text) and text[index].isdigit():
        digits += text[index]
        index += 1

    target = int(digits)
    if target < 1 or target > 11:
        raise ValueError(
            f"Invalid armor value {target}. Use a1..a11 or av1..av11."
        )

    suffix_start = index
    while index < len(text) and text[index].lower() in "kism":
        index += 1
    suffix = text[suffix_start:index]

    normalized_suffix = _normalize_injury_suffix(suffix)

    return ArmorValueTarget(target=target, injury_suffix=normalized_suffix), index


def _starts_block_token(text: str, index: int) -> bool:
    """Return True when a block token starts at ``text[index]``."""

    if index >= len(text):
        return False

    if text[index] == "-":
        return (
            index + 2 < len(text)
            and text[index + 1] in "123"
            and text[index + 2].lower() == "d"
        )

    return index + 1 < len(text) and text[index] in "123" and text[index + 1].lower() == "d"


def _parse_d6_target_from(text: str, index: int) -> tuple[RollTarget, int]:
    """Parse one compact D6 token from ``text`` starting at ``index``."""

    if index >= len(text) or text[index] < "1" or text[index] > "6":
        raise ValueError(
            f"Invalid roll target near {text[index:]!r}. "
            "Use values like 2+, 3++, 6+ or shorthand like 224s3."
        )

    threshold = int(text[index])
    local_rerolls = 0
    next_index = index + 1

    if text[next_index : next_index + 2] == "++":
        local_rerolls = 1
        next_index += 2
    elif next_index < len(text) and text[next_index] == "+":
        next_index += 1
    elif next_index < len(text) and text[next_index].lower() == "s":
        local_rerolls = 1
        next_index += 1

    return RollTarget(threshold=threshold, local_rerolls=local_rerolls), next_index


def _split_roll_tokens(raw_text: str) -> list[str]:
    """Expand user input into explicit tokens such as `2+` and `4++`."""

    raw_parts = [token for token in re.split(r"[,\s]+", raw_text.strip()) if token]
    expanded_tokens: list[str] = []

    for raw_part in raw_parts:
        expanded_tokens.extend(_expand_inline_token(raw_part))

    return expanded_tokens


def _expand_inline_token(token: str) -> list[str]:
    """Expand inline shorthand such as `224s3` or `33++` into explicit tokens."""

    expanded_tokens: list[str] = []
    index = 0
    compact_token = token.strip()

    while index < len(compact_token):
        current = compact_token[index]
        if current < "1" or current > "6":
            raise ValueError(
                f"Invalid roll target: {token!r}. Use values like 2+, 3++, 6+ or shorthand like 224s3."
            )

        explicit_token = f"{current}+"

        if compact_token[index + 1 : index + 3] == "++":
            explicit_token = f"{current}++"
            index += 2
        elif index + 1 < len(compact_token) and compact_token[index + 1] == "+":
            index += 1
        elif index + 1 < len(compact_token) and compact_token[index + 1].lower() == "s":
            explicit_token += "+"
            index += 1

        expanded_tokens.append(explicit_token)
        index += 1

    return expanded_tokens


def _parse_threshold(token: str) -> RollTarget:
    """Parse one token such as 4+ or 3++ into a structured roll target."""

    match = re.fullmatch(r"([1-6])(\+{1,2})", token.strip())
    if not match:
        raise ValueError(
            f"Invalid roll target: {token!r}. Use values like 2+, 3++, 6+. Each die can be rerolled at most once."
        )

    # A single plus means a normal target. A double plus means one built-in reroll.
    plus_count = len(match.group(2))
    local_rerolls = max(0, plus_count - 1)
    return RollTarget(threshold=int(match.group(1)), local_rerolls=local_rerolls)


def _parse_block_dice_token(token: str) -> BlockDiceTarget:
    """Parse a block dice token such as 2d+, -3d*, 1d, or 2d+++ into a BlockDiceTarget.

    An optional ``++`` suffix at the very end signals one built-in reroll of the
    whole pool (Brawler skill).  A ``++``-tagged step cannot also consume a
    shared team reroll.
    """

    token = token.strip()
    if not token:
        raise ValueError("Invalid block dice token: ''.")

    target, next_index = _parse_block_target_from(token, 0)
    if next_index != len(token):
        raise ValueError(
            f"Invalid block dice token: {token!r}. "
            "Use e.g. 1d, 2d+, 3d*, -2d, -3d-, 2d+-, or 2d+++ for Brawler."
        )
    return target


def _parse_block_target_from(text: str, index: int) -> tuple[BlockDiceTarget, int]:
    """Parse one block token from ``text`` starting at ``index``."""

    start = index
    negative = False

    if text[index] == "-":
        negative = True
        index += 1

    if index >= len(text) or text[index] not in "123":
        raise ValueError(
            f"Invalid block dice token near {text[start:]!r}. "
            "Use e.g. 1d, 2d+, 3d*, -2d, -3d-, 2d+-, or 2d+++ for Brawler."
        )
    dice_count = int(text[index])
    index += 1

    if index >= len(text) or text[index].lower() != "d":
        raise ValueError(
            f"Invalid block dice token near {text[start:]!r}. "
            "Use e.g. 1d, 2d+, 3d*, -2d, -3d-, 2d+-, or 2d+++ for Brawler."
        )
    index += 1

    outcome = ""
    local_rerolls = 0

    # Two-character outcome forms first.
    if text[index : index + 2] in ("+-", "-+"):
        outcome = "+-"
        index += 2
    # Single-character non-plus outcomes.
    elif index < len(text) and text[index] in "*/-":
        outcome = text[index]
        index += 1
    # Plus-run forms:
    #   +   => outcome '+'
    #   ++  => default outcome + Brawler
    #   +++ => outcome '+' + Brawler
    elif index < len(text) and text[index] == "+":
        plus_count = 0
        while index < len(text) and text[index] == "+":
            plus_count += 1
            index += 1

        if plus_count == 1:
            outcome = "+"
        elif plus_count == 2:
            local_rerolls = 1
        elif plus_count == 3:
            outcome = "+"
            local_rerolls = 1
        else:
            raise ValueError(
                f"Invalid block dice token near {text[start:index]!r}. "
                "Too many '+' markers after 'd'."
            )

    # Optional trailing Brawler for outcomes other than pure plus-run forms above.
    if local_rerolls == 0 and text[index : index + 2] == "++":
        local_rerolls = 1
        index += 2

    return (
        BlockDiceTarget(
            dice_count=dice_count,
            negative=negative,
            outcome=outcome,
            local_rerolls=local_rerolls,
        ),
        index,
    )


class RollSequenceCalculator:
    def calculate(self, sequence: list[Step], max_global_rerolls: int = 2) -> CalculationResult:
        """Calculate base and shared-reroll odds for an ordered roll sequence.

        The method evaluates the chain multiple times: once for each available
        global reroll budget from 0 up to `max_global_rerolls`. `sequence` may
        contain a mix of `RollTarget`, `BlockDiceTarget`, and `ArmorValueTarget`
        steps.
        """

        if not sequence:
            raise ValueError("Sequence cannot be empty.")
        if max_global_rerolls < 0:
            raise ValueError("Global rerolls cannot be negative.")
        for target in sequence:
            if target.local_rerolls not in (0, 1):
                raise ValueError("Each die can be rerolled at most once.")
            if isinstance(target, ArmorValueTarget) and target.local_rerolls != 0:
                raise ValueError("Armor steps do not allow rerolls.")

        steps: list[StepResult] = []
        # For each allowed reroll budget, keep the cumulative success chance after
        # every step so the UI can display step-by-step totals for base, 1RR, and 2RR.
        cumulative_histories = {rerolls: [] for rerolls in range(max_global_rerolls + 1)}

        for rerolls in range(max_global_rerolls + 1):
            # distribution[n] = probability that the chain has succeeded so far and
            # exactly n shared rerolls remain available for future rolls.
            distribution = [0.0] * (rerolls + 1)
            distribution[rerolls] = 1.0

            for target in sequence:
                distribution = self._advance_distribution(distribution, target)
                cumulative_histories[rerolls].append(sum(distribution))

        for index, target in enumerate(sequence):
            # Store the per-step view separately from the dynamic-programming state so
            # the GUI can explain each roll in plain terms.
            if isinstance(target, BlockDiceTarget):
                single_attempt_probability = target.base_probability
                roll_probability = 1 - (1 - single_attempt_probability) ** (target.local_rerolls + 1)
                threshold: int | None = None
            elif isinstance(target, ArmorValueTarget):
                single_attempt_probability = armor_and_injury_probability(target)
                roll_probability = 1 - (1 - single_attempt_probability) ** (target.local_rerolls + 1)
                threshold = None
            else:
                single_attempt_probability = self.roll_probability(target.threshold)
                roll_probability = self.roll_probability_with_local_rerolls(target.threshold, target.local_rerolls)
                threshold = target.threshold
            steps.append(
                StepResult(
                    token=target.display_token,
                    threshold=threshold,
                    local_rerolls=target.local_rerolls,
                    single_attempt_probability=single_attempt_probability,
                    roll_probability=roll_probability,
                    cumulative_probabilities={
                        rerolls: cumulative_histories[rerolls][index]
                        for rerolls in range(max_global_rerolls + 1)
                    },
                )
            )

        return CalculationResult(
            sequence=sequence,
            steps=steps,
            global_reroll_probabilities={
                rerolls: cumulative_histories[rerolls][-1]
                for rerolls in range(max_global_rerolls + 1)
            },
        )

    @staticmethod
    def roll_probability(threshold: int) -> float:
        """Probability that a single D6 attempt succeeds at the given threshold."""

        if threshold < 1 or threshold > 6:
            raise ValueError("Roll target must be between 1 and 6 on a D6.")
        successful_faces = 7 - threshold
        return successful_faces / 6

    @classmethod
    def roll_probability_with_local_rerolls(cls, threshold: int, local_rerolls: int) -> float:
        """Collapse local rerolls into one success probability for a single step.

        If a roll succeeds with probability p on one attempt, then with one local
        reroll it succeeds at least once with probability 1 - (1 - p)^2.
        """

        if local_rerolls not in (0, 1):
            raise ValueError("Each die can be rerolled at most once.")
        single_attempt_probability = cls.roll_probability(threshold)
        return 1 - ((1 - single_attempt_probability) ** (local_rerolls + 1))

    @staticmethod
    def _advance_distribution(distribution: list[float], target: Step) -> list[float]:
        """Advance the shared-reroll state by one roll, block pool, or armor roll.

        The current distribution represents successful paths only.

        A step with ++ uses its own reroll and cannot also spend a shared RR.
        A step without ++ may consume at most one shared RR after a failed first
        attempt. Paths that still fail after that are omitted because the chain ends.
        """

        next_distribution = [0.0] * len(distribution)
        if isinstance(target, ArmorValueTarget):
            # Armor steps are resolved as a single 2D6 roll with no reroll usage.
            single_attempt_probability = armor_and_injury_probability(target)
            for rerolls_remaining, state_probability in enumerate(distribution):
                if state_probability == 0:
                    continue
                next_distribution[rerolls_remaining] += state_probability * single_attempt_probability
            return next_distribution

        if isinstance(target, BlockDiceTarget):
            single_attempt_probability = target.base_probability
            local_roll_probability = 1 - (1 - single_attempt_probability) ** (target.local_rerolls + 1)
        else:
            single_attempt_probability = RollSequenceCalculator.roll_probability(target.threshold)
            local_roll_probability = RollSequenceCalculator.roll_probability_with_local_rerolls(
                target.threshold,
                target.local_rerolls,
            )

        for rerolls_remaining, state_probability in enumerate(distribution):
            if state_probability == 0:
                continue

            if target.local_rerolls == 1:
                next_distribution[rerolls_remaining] += state_probability * local_roll_probability
                continue

            next_distribution[rerolls_remaining] += state_probability * single_attempt_probability
            if rerolls_remaining > 0:
                # Shared RR is only available after the first failed attempt and can
                # only be used once on this die.
                next_distribution[rerolls_remaining - 1] += (
                    state_probability * (1 - single_attempt_probability) * single_attempt_probability
                )

        return next_distribution