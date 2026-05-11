"""Core parsing and probability math for chained D6 roll calculations.

The calculator supports two reroll concepts:

- one local reroll encoded in a token such as 3++
- a shared pool of global rerolls, reported as 1RR and 2RR in the UI

Any single die may be rerolled at most once. A die that already has a built-in
reroll from ++ cannot also consume a shared RR.
"""

from __future__ import annotations

from dataclasses import dataclass
import re


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


@dataclass(frozen=True)
class StepResult:
    """Probability summary for one roll inside the chain."""

    token: str
    threshold: int
    local_rerolls: int
    single_attempt_probability: float
    roll_probability: float
    cumulative_probabilities: dict[int, float]


@dataclass(frozen=True)
class CalculationResult:
    """Full result for a parsed sequence, including per-step and final odds."""

    sequence: list[RollTarget]
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


def parse_roll_sequence(raw_text: str) -> list[RollTarget]:
    """Split user input into ordered roll targets.

    Input accepts either explicit tokens such as `2+, 3++, 4+` or compact
    shorthand such as `224s3`, where `s` marks a built-in reroll on the die
    immediately before it.
    """

    tokens = _split_roll_tokens(raw_text)
    if not tokens:
        raise ValueError("Enter at least one target roll such as 2+, 3+, 4+.")

    return [_parse_threshold(token) for token in tokens]


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


class RollSequenceCalculator:
    def calculate(self, sequence: list[RollTarget], max_global_rerolls: int = 2) -> CalculationResult:
        """Calculate base and shared-reroll odds for an ordered roll sequence.

        The method evaluates the chain multiple times: once for each available
        global reroll budget from 0 up to `max_global_rerolls`.
        """

        if not sequence:
            raise ValueError("Sequence cannot be empty.")
        if max_global_rerolls < 0:
            raise ValueError("Global rerolls cannot be negative.")
        for target in sequence:
            if target.local_rerolls not in (0, 1):
                raise ValueError("Each die can be rerolled at most once.")

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
            single_attempt_probability = self.roll_probability(target.threshold)
            roll_probability = self.roll_probability_with_local_rerolls(target.threshold, target.local_rerolls)
            steps.append(
                StepResult(
                    token=target.token,
                    threshold=target.threshold,
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
    def _advance_distribution(distribution: list[float], target: RollTarget) -> list[float]:
        """Advance the shared-reroll state by one roll.

        The current distribution represents successful paths only.

        A die with ++ uses its own reroll and cannot also spend a shared RR.
        A die without ++ may consume at most one shared RR after a failed first
        attempt. Paths that still fail after that are omitted because the chain ends.
        """

        next_distribution = [0.0] * len(distribution)
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