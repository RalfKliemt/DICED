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
    `weighted_reroll` is True if the suffix is `p` (2/3 reroll weight).
    """

    threshold: int
    local_rerolls: int
    weighted_reroll: bool = False

    @property
    def token(self) -> str:
        """Rebuild the user-facing token, for example 3++, 3+p."""
        if self.weighted_reroll:
            return f"{self.threshold}+p"
        return f"{self.threshold}{'+' * (self.local_rerolls + 1)}"

    @property
    def display_token(self) -> str:
        """Return the display token shown in logs and tables."""
        if self.weighted_reroll:
            return f"{self.threshold}+ (pro)"
        return self.token


# ---------------------------------------------------------------------------
# Block dice
# ---------------------------------------------------------------------------

# A block die has 6 faces: POW, POW* (stumble), PUSH, PUSH, BOTH DOWN, SKULL
# (attacker down). These counts are for one die without vs-Stunty.
_BLOCK_OUTCOME_FACES: dict[str, int] = {
    "": 2,    # POW + POW*  ("5+" equivalent)
    "+": 3,   # POW + POW* + BOTH DOWN  ("4+")
    "*": 1,   # POW only  ("6+")
    "-": 4,   # No turnover: POW + POW* + PUSH×2  ("3+")
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


POW, STUMBLE, PUSH, BOTH, SKULL = "pow", "stumble", "push", "both", "skull"
BLOCK_DIE_FACES = (POW, STUMBLE, PUSH, PUSH, BOTH, SKULL)


def _wanted_block_faces(outcome: str) -> frozenset[str]:
    """Faces the attacker needs for a block outcome code (after vs-Stunty)."""

    if outcome not in _BLOCK_OUTCOME_FACES:
        raise ValueError(f"Unknown block die outcome: {outcome!r}.")
    wanted = {
        "": {POW, STUMBLE},
        "*": {POW},
        "-": {POW, STUMBLE, PUSH},
        "/": {PUSH},
    }[outcome.replace("+", "")]
    if "+" in outcome:
        wanted = wanted | {BOTH}
    return frozenset(wanted)


@dataclass(frozen=True)
class BlockDiceTarget:
    """A Blood Bowl block dice pool roll.

    `dice_count` is 1, 2, or 3.
    `negative` is True for -2d/-3d where the defender picks: all dice must show
    the desired face.  False means attacker picks: at least one die must match.
    `outcome` is one of '', '+', '*', '-', '+-', '/'.
    `local_rerolls` is 0 or 1; 1 means Brawler (re-roll one unwanted Both Down die).
    `block` means the attacker has Block (set by the Block toggle; ``+`` implies it).
    `stunty` means the defender is Stunty: POW* (stumble) counts as a push.
    """

    dice_count: int
    negative: bool
    outcome: str
    local_rerolls: int = 0
    block: bool = False
    stunty: bool = False

    def face(self, face: str) -> str:
        """The face as it plays out: vs Stunty a stumble is only a push."""
        return PUSH if face == STUMBLE and self.stunty else face

    def succeeds(self, faces: tuple[str, ...]) -> bool:
        """Whether a rolled pool gives the wanted result.

        The attacker picks any die. The defender (``-2d``/``-3d``) picks the
        result worst for the attacker: Skull, then Both Down (unless the
        attacker has Block), Push, Stumble, Both Down with Block, Pow.
        """

        wanted = _wanted_block_faces(self.outcome)
        effective = [self.face(f) for f in faces]
        if not self.negative:
            return any(f in wanted for f in effective)
        has_block = self.block or "+" in self.outcome
        rank = {SKULL: 0, BOTH: 4 if has_block else 1, PUSH: 2, STUMBLE: 3, POW: 5}
        return min(effective, key=rank.__getitem__) in wanted

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
        from itertools import product

        hits = sum(self.succeeds(faces) for faces in product(BLOCK_DIE_FACES, repeat=self.dice_count))
        return hits / 6 ** self.dice_count


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
        if not core:
            return f"av{self.target} (mb)"
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
    if core in ("", "s"):
        # No injury roll: Stunty is irrelevant, MB can only help the armour roll.
        return "m" if has_m else ""

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
    if not core:
        return 1.0
    target = _INJURY_BASE_TARGETS[core] - (1 if has_m else 0)
    successful = sum(1 for die1 in range(1, 7) for die2 in range(1, 7) if die1 + die2 >= target)
    return successful / 36


def _two_d6_at_least(target: int) -> float:
    return sum(1 for d1 in range(1, 7) for d2 in range(1, 7) if d1 + d2 >= target) / 36


def armor_and_injury_probability(target: ArmorValueTarget) -> float:
    """Probability for armor break plus optional injury roll.

    Mighty Blow (+1) modifies either the armour roll or the injury roll, chosen
    after seeing the armour roll: an armour roll exactly one short is pushed
    through with MB (injury then unmodified); a roll that already breaks keeps
    MB for the injury roll.
    """

    normalized = _normalize_injury_suffix(target.injury_suffix)
    if not normalized.endswith("m"):
        return armor_break_probability(target.target) * injury_roll_probability(normalized)

    core = normalized[:-1]
    if not core:
        return _two_d6_at_least(target.target - 1)
    injury_target = _INJURY_BASE_TARGETS[core]
    broken_clean = _two_d6_at_least(target.target)
    exactly_one_short = _two_d6_at_least(target.target - 1) - broken_clean
    return (
        broken_clean * _two_d6_at_least(injury_target - 1)
        + exactly_one_short * _two_d6_at_least(injury_target)
    )


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


def parse_roll_sequence_with_pro(raw_text: str) -> tuple[list[Step], bool]:
    """Parse a sequence and detect Pro anywhere in it.

    Any ``p`` marks the whole sequence as having Pro: a standalone ``p`` token
    (``2+ p 4+``) as well as a suffix on a die (``3+p``, ``3p``). The returned
    steps have the per-die ``p`` removed; pass the flag as ``pro=`` to
    :meth:`RollSequenceCalculator.calculate`.
    """

    parts = [part for part in re.split(r"[,\s]+", raw_text.strip()) if part]
    has_pro = any(part.lower() == "p" for part in parts)
    remaining = " ".join(part for part in parts if part.lower() != "p")
    if not remaining:
        raise ValueError("Enter at least one target roll such as 2+, 3+, 4+.")

    steps: list[Step] = []
    for step in parse_roll_sequence(remaining):
        if isinstance(step, RollTarget) and step.weighted_reroll:
            has_pro = True
            step = RollTarget(threshold=step.threshold, local_rerolls=step.local_rerolls)
        steps.append(step)
    return steps, has_pro


@dataclass(frozen=True)
class SequenceOptions:
    """Skills that apply to the whole sequence."""

    block: bool = False
    pro: bool = False
    brawler: bool = False
    mighty_blow: bool = False
    stunty: bool = False

    def merged(self, other: "SequenceOptions") -> "SequenceOptions":
        return SequenceOptions(
            block=self.block or other.block,
            pro=self.pro or other.pro,
            brawler=self.brawler or other.brawler,
            mighty_blow=self.mighty_blow or other.mighty_blow,
            stunty=self.stunty or other.stunty,
        )

    @property
    def labels(self) -> list[str]:
        names = [
            ("Block", self.block),
            ("Pro", self.pro),
            ("Brawler", self.brawler),
            ("MB", self.mighty_blow),
            ("vs Stunty", self.stunty),
        ]
        return [name for name, on in names if on]


def parse_sequence(raw_text: str) -> tuple[list[Step], SequenceOptions]:
    """Parse a sequence and pick up sequence-wide skill letters.

    ``p`` anywhere (standalone or as a die suffix) means Pro, ``b`` anywhere
    means Brawler. Both apply to the whole sequence.
    """

    has_brawler = "b" in raw_text.lower()
    cleaned = re.sub(r"[bB]", " ", raw_text)
    cleaned, has_stunty = _extract_stunty(cleaned)
    steps, has_pro = parse_roll_sequence_with_pro(cleaned)
    return steps, SequenceOptions(pro=has_pro, brawler=has_brawler, stunty=has_stunty)


def _extract_stunty(text: str) -> tuple[str, bool]:
    """Remove every ``s`` meaning *vs Stunty* and report whether one was found.

    ``s`` is Stunty when it is part of an armour suffix (``av9s``, ``av9ks``)
    or stands anywhere else that is not right after a D6 digit, e.g. after a
    block token (``2d-s``) or on its own (``2d s av9``). An ``s`` directly after
    a D6 digit keeps its shorthand meaning (``224s3`` = ``2+ 2+ 4++ 3+``).
    """

    found = False

    def drop(match: re.Match[str]) -> str:
        nonlocal found
        found = True
        return match.group(1) + match.group(2)

    armour_suffix = re.compile(r"(a(?:v)?\d{1,2}[kim]*)[sS]([kimKIM]*)", re.IGNORECASE)
    previous = None
    while previous != text:
        previous = text
        text = armour_suffix.sub(drop, text)

    def drop_loose(_match: re.Match[str]) -> str:
        nonlocal found
        found = True
        return " "

    text = re.sub(r"(?<![1-6])[sS]", drop_loose, text)
    return text, found


def apply_options(steps: list[Step], options: SequenceOptions) -> list[Step]:
    """Apply sequence-wide skills to every matching step.

    Block turns Both Down into a success on all blocks (``''`` -> ``+``,
    ``-`` -> ``+-``). Brawler goes on every block. Mighty Blow and Stunty go on
    every armour step.
    """

    result: list[Step] = []
    for step in steps:
        if isinstance(step, BlockDiceTarget):
            outcome = step.outcome
            if options.block:
                outcome = {"": "+", "-": "+-"}.get(outcome, outcome)
            step = BlockDiceTarget(
                dice_count=step.dice_count,
                negative=step.negative,
                outcome=outcome,
                local_rerolls=1 if options.brawler else step.local_rerolls,
                block=options.block or "+" in outcome,
                stunty=options.stunty,
            )
        elif isinstance(step, ArmorValueTarget):
            step = with_injury(step, _injury_core(step.injury_suffix), options)
        result.append(step)
    return result


def _injury_core(suffix: str) -> str:
    """Return 'k', 'i' or '' from a canonical suffix (ignoring stunty and MB)."""

    core = suffix.replace("m", "").replace("s", "")
    return core


def with_injury(step: ArmorValueTarget, injury: str, options: SequenceOptions) -> ArmorValueTarget:
    """Return ``step`` asking for ``injury`` ('' break, 'k' KO, 'i' CAS)."""

    has_m = options.mighty_blow or step.injury_suffix.endswith("m")
    stunty = options.stunty or "s" in step.injury_suffix
    suffix = injury
    if injury and stunty:
        suffix = {"k": "ks", "i": "si"}[injury]
    if has_m:
        suffix += "m"
    return ArmorValueTarget(target=step.target, injury_suffix=_normalize_injury_suffix(suffix))


def armour_outcomes(
    calculator: "RollSequenceCalculator",
    steps: list[Step],
    options: SequenceOptions,
    max_global_rerolls: int = 2,
) -> dict[str, dict[int, float]] | None:
    """Chance to break armour, KO and casualty for the last armour step.

    Returns ``None`` when the sequence has no armour step.
    """

    armour_indexes = [i for i, step in enumerate(steps) if isinstance(step, ArmorValueTarget)]
    if not armour_indexes:
        return None
    last = armour_indexes[-1]
    outcomes: dict[str, dict[int, float]] = {}
    for label, injury in (("Break", ""), ("KO", "k"), ("CAS", "i")):
        variant = list(steps)
        variant[last] = with_injury(steps[last], injury, options)
        result = calculator.calculate(variant, max_global_rerolls=max_global_rerolls, pro=options.pro)
        outcomes[label] = dict(result.global_reroll_probabilities)
    return outcomes


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
    weighted_reroll = False
    next_index = index + 1

    # Check for 'p' directly after threshold (e.g., 3p)
    if next_index < len(text) and text[next_index].lower() == "p":
        weighted_reroll = True
        next_index += 1
    elif text[next_index : next_index + 2] == "++":
        local_rerolls = 1
        next_index += 2
    elif next_index < len(text) and text[next_index] == "+":
        next_index += 1
        # Check for 'p' suffix after the +
        if next_index < len(text) and text[next_index].lower() == "p":
            weighted_reroll = True
            next_index += 1
    elif next_index < len(text) and text[next_index].lower() == "s":
        local_rerolls = 1
        next_index += 1

    if local_rerolls > 0 and weighted_reroll:
        raise ValueError(
            f"Cannot use both ++ and p on same die near {text[index:next_index]!r}. "
            f"Use either 3++ or 3+p, not 3++p."
        )

    return RollTarget(
        threshold=threshold,
        local_rerolls=local_rerolls,
        weighted_reroll=weighted_reroll,
    ), next_index


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

    An optional ``++`` suffix at the very end marks Brawler: one die showing an
    unwanted Both Down may be re-rolled. Failures without a Both Down can still
    use a team re-roll or Pro.
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
    def calculate(
        self,
        sequence: list[Step],
        max_global_rerolls: int = 2,
        pro: bool = False,
    ) -> CalculationResult:
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
            cumulative_histories[rerolls].extend(self._chain_history(sequence, rerolls, pro))

        for index, target in enumerate(sequence):
            # Store the per-step view separately from the dynamic-programming state so
            # the GUI can explain each roll in plain terms.
            if isinstance(target, BlockDiceTarget):
                single_attempt_probability = target.base_probability
                ok, fail_classes = self._block_branches(target)
                roll_probability = ok + sum(prob * actions.get("free", 0.0) for prob, actions in fail_classes)
                threshold: int | None = None
            elif isinstance(target, ArmorValueTarget):
                single_attempt_probability = armor_and_injury_probability(target)
                roll_probability = 1 - (1 - single_attempt_probability) ** (target.local_rerolls + 1)
                threshold = None
            else:
                # RollTarget
                single_attempt_probability = self.roll_probability(target.threshold)
                if target.weighted_reroll:
                    roll_probability = self.roll_probability_with_weighted_reroll(target.threshold)
                else:
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
    def _block_branches(target: BlockDiceTarget) -> tuple[float, list[tuple[float, dict[str, float]]]]:
        """Enumerate one block pool face by face into success and failure classes.

        A failure class lists the re-rolls that can rescue it (only one per roll):

        - ``free`` (Brawler): re-roll one unwanted Both Down die. Always taken
          when it can help; the block then gets no other re-roll.
        - ``pro``: re-roll the best single die after passing the 3+ Pro roll.
        - ``rr``: team re-roll of the whole pool.
        """

        from itertools import product

        n = target.dice_count
        die = 1 / 6
        single = target.base_probability
        wanted = _wanted_block_faces(target.outcome)

        def rescue(faces: tuple[str, ...], index: int) -> float:
            """Chance of success after re-rolling die ``index`` once."""
            return sum(
                die
                for face in BLOCK_DIE_FACES
                if target.succeeds(faces[:index] + (face,) + faces[index + 1 :])
            )

        classes: dict[tuple[float, float], float] = {}
        ok = 0.0
        for faces in product(BLOCK_DIE_FACES, repeat=n):
            prob = die ** n
            if target.succeeds(faces):
                ok += prob
                continue
            free = 0.0
            if target.local_rerolls and BOTH not in wanted and BOTH in faces:
                free = rescue(faces, faces.index(BOTH))
            pro = max(rescue(faces, i) for i in range(n))
            key = (free, pro)
            classes[key] = classes.get(key, 0.0) + prob

        branches = []
        for (free, pro), prob in classes.items():
            actions: dict[str, float] = {}
            if free > 0:
                actions["free"] = free
            else:
                if single > 0:
                    actions["rr"] = single
                if pro > 0:
                    actions["pro"] = (2 / 3) * pro
            branches.append((prob, actions))
        return ok, branches

    @classmethod
    def _step_branches(cls, target: Step) -> tuple[float, list[tuple[float, dict[str, float]]]]:
        """Return (P first attempt succeeds, failure classes with rescue options)."""

        if isinstance(target, ArmorValueTarget):
            return armor_and_injury_probability(target), []
        if isinstance(target, BlockDiceTarget):
            return cls._block_branches(target)
        single = cls.roll_probability(target.threshold)
        if target.weighted_reroll:
            return single, [(1 - single, {"free": (2 / 3) * single})]
        if target.local_rerolls:
            return single, [(1 - single, {"free": single})]
        return single, [(1 - single, {"rr": single, "pro": (2 / 3) * single})]

    @classmethod
    def _chain_history(cls, sequence: list[Step], rerolls: int, pro: bool) -> list[float]:
        """Cumulative success after each step under the best re-roll policy.

        State is (team re-rolls left, Pro still available). A die is re-rolled at
        most once, so a failure uses at most one of: its own skill re-roll
        (``++``/Brawler), Pro (once per sequence), or a team re-roll. A skill
        re-roll is always used when it applies; otherwise the choice between Pro
        and a team re-roll is made with a backward value pass so scarce re-rolls
        go where they help most. The forward pass reports cumulative success.
        """

        n = len(sequence)
        branches = [cls._step_branches(target) for target in sequence]
        start = (rerolls, 1 if pro else 0)
        states = [(r, p) for r in range(rerolls + 1) for p in (0, 1)]

        value: list[dict[tuple[int, int], float]] = [dict() for _ in range(n + 1)]
        for state in states:
            value[n][state] = 1.0

        def transitions(i: int, r: int, p: int) -> list[tuple[float, tuple[int, int]]]:
            ok, fail_classes = branches[i]
            result = [(ok, (r, p))]
            for prob, actions in fail_classes:
                if "free" in actions:
                    # A skill re-roll (++ / Brawler) is always taken first; team
                    # re-rolls and Pro are kept for later steps.
                    result.append((prob * actions["free"], (r, p)))
                    continue
                options = []
                if "rr" in actions and r > 0:
                    options.append((actions["rr"], (r - 1, p)))
                if "pro" in actions and p:
                    options.append((actions["pro"], (r, 0)))
                if options:
                    success, nxt = max(options, key=lambda o: o[0] * value[i + 1][o[1]])
                    result.append((prob * success, nxt))
            return result

        for i in range(n - 1, -1, -1):
            for r, p in states:
                value[i][(r, p)] = sum(
                    prob * value[i + 1][nxt] for prob, nxt in transitions(i, r, p)
                )

        history: list[float] = []
        distribution = {start: 1.0}
        for i in range(n):
            next_distribution: dict[tuple[int, int], float] = {}
            for (r, p), mass in distribution.items():
                for prob, nxt in transitions(i, r, p):
                    next_distribution[nxt] = next_distribution.get(nxt, 0.0) + mass * prob
            distribution = next_distribution
            history.append(sum(distribution.values()))
        return history

    @staticmethod
    def roll_probability(threshold: int) -> float:
        """Probability that a single D6 attempt succeeds at the given threshold."""

        if threshold < 1 or threshold > 6:
            raise ValueError("Roll target must be between 1 and 6 on a D6.")
        # A natural 1 always fails, so 1+ is the same as 2+.
        successful_faces = 7 - max(threshold, 2)
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
    def roll_probability_with_weighted_reroll(threshold: int) -> float:
        """Probability for a die roll with weighted reroll (p suffix).

        First attempt at the threshold; if failed, a 3+ Pro roll (2/3) allows a
        re-roll at the same threshold. Formula: P + (1 - P) * (2/3) * P
        """

        first_attempt = RollSequenceCalculator.roll_probability(threshold)
        # After a failure the Pro roll (3+, 2/3) allows a re-roll of the die,
        # which must then succeed again at the normal target.
        return first_attempt + (1 - first_attempt) * (2 / 3) * first_attempt
