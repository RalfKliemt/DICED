# RollCoaster

Small Python app for calculating the success chance of consecutive dice rolls on a D6.

It is aimed at sequences of dependent success checks where every roll in the chain
must succeed for the full action to succeed.

Example sequence:

- `224s3`

The app calculates:

- per-roll success chance
- local rerolls encoded directly in the target, for example `3++`
- cumulative success chance after each step
- total chain chance with `1RR` and `2RR` available across the sequence
- a simple visible log of calculations in the GUI

## Input Format

Enter targets either as explicit tokens separated by commas or spaces, or in a compact shorthand form.

- `2+` means a normal D6 roll succeeding on 2 or higher
- `3++` means a 3+ roll with one built-in reroll for that same die
- `224s3` means `2+ 2+ 4++ 3+`
- in shorthand, `s` marks a built-in reroll on the previous die

Each die can be rerolled at most once. That means:

- `++` is the maximum built-in reroll notation
- a die with `++` cannot also consume a shared `RR`

Examples:

- `2+, 3+, 4+`
- `3++ 4+ 5+`
- `224s3`
- `2+ 2+ 3++ 6+`

The order matters because the chain succeeds only if every step succeeds.

## Result Meaning

The GUI shows three overall probabilities:

- `Base`: the chain chance using only the rerolls written directly into the roll tokens
- `1RR`: the chain chance if you also have one shared reroll available to spend anywhere in the sequence
- `2RR`: the chain chance if you also have two shared rerolls available to spend anywhere in the sequence

The step details panel shows the same idea after each roll in the chain:

- `single attempt`: success chance before any built-in rerolls on that die
- `after built-in rerolls`: chance for that die after applying local rerolls from the token itself
- `cumulative base`, `1RR`, `2RR`: running total chance that the chain has survived to that point

## Reroll Math

For a single roll with success chance `p`:

- no local rerolls: `p`
- one local reroll: `1 - (1 - p)^2`

So a `3+` roll has `4/6` success on one attempt, while `3++` becomes:

- `1 - (1 - 4/6)^2`
- `1 - (2/6)^2`
- `8/9`, or about `88.89%`

Shared rerolls (`1RR`, `2RR`) are handled across the whole sequence instead of being locked to a single die. They can only be used on a die that does not already have a built-in reroll, and each die can consume at most one shared RR.

## Run

```bash
python app.py
```

If you install the project in editable mode:

```bash
pip install -e .
python -m rollcoaster
```

## Test

```bash
PYTHONPATH=src python -m unittest discover -s tests
```
