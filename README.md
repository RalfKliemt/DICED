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
- you can also leave out whitespace entirely, for example `2+3++4+` or `224s3`

Each die can be rerolled at most once. That means:

- `++` is the maximum built-in reroll notation
- a die with `++` cannot also consume a shared `RR`

Examples:

- `2+, 3+, 4+`
- `3++ 4+ 5+`
- `224s3`
- `2+ 2+ 3++ 6+`

The order matters because the chain succeeds only if every step succeeds.

## Block Dice

The standard Blood Bowl block die has 6 faces: POW, POW/SKULL, BOTH DOWN, PUSH, PUSH, SKULL.
Blood Bowl block dice can be mixed into a sequence. A block dice token looks like `2d+` — dice count, the letter `d`, and an optional outcome symbol.

**Dice count and sign**

| Token prefix | Meaning                                                             |
|--------------|---------------------------------------------------------------------|
| `1d`         | 1-die block                                                         |
| `2d`         | 2-die block — attacker picks, at least one die must show the result |
| `3d`         | 3-die block — attacker picks                                        |
| `-2d`        | 2-die block — defender picks, all dice must show the result         |
| `-3d`        | 3-die block — defender picks                                        |

**Outcome suffix** (append directly after `d`)

| Suffix        | Outcome                          | Faces (of 6) |
|---------------|----------------------------------|--------------|
| *(none)*      | POW or POW/SKULL                 | 2            |
| `+`           | Also BOTH DOWN                   | 3            |
| `*`           | POW only                         | 1            |
| `-`           | No turnover (not SKULL)          | 4            |
| `+-` or `-+`  | No skull (anything except SKULL) | 5            |
| `/`           | PUSH only                        | 2            |

Examples:

- `2d+` — 2-die block with Block skill (both-down-or-better)
- `-3d*` — 3-die block where the defender picks, requiring POW on all dice
- `3+ 2d+ 4+` — a mixed chain: a D6 roll, then a block, then another D6 roll

## Armor Break (2D6)

Armor break checks can also be part of the chain.

- Use `aN` or `avN` where `N` is the target sum on 2D6
- The roll succeeds when `2D6 >= N`
- Valid range is `1` to `11`

Examples:

- `a9`
- `av9`
- `3++2+2d-av9`

**Optional injury suffixes**

After `aN` or `avN`, you can add injury postfix letters. These represent a
second 2D6 roll after the armor break succeeds.

| Suffix | Meaning              | Injury target |
|--------|----------------------|---------------|
| `k`    | ko                   | `8+`          |
| `i`    | injury               | `10+`         |
| `sk`   | stunty ko            | `7+`          |
| `si`   | stunty injury        | `9+`          |
| `m`    | mighty blow modifier | lower by `1`  |

Rules:

- `m` lowers the injury target by `1`
- `s`, `k`, `i`, and `m` can be written in flexible order where the result is meaningful
- aliases are accepted: `sk` or `ks`, `si` or `is`
- you can also put spaces between the armor part and the injury letters
- no rerolls are used on armor or injury rolls

Examples:

- `av9k` = armor `9+`, then ko on `8+`
- `av9km` = armor `9+`, then ko on `7+`
- `av9sk` or `av9ks` = armor `9+`, then stunty ko on `7+`
- `av9sim`, `av9 m s i`, `av9 is m` all work
- `3++2+2d-av9 k` works with a space between `av9` and the injury suffix

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

## macOS App Bundle

You can build a small native `.app` bundle for macOS directly from this repo.

```bash
python setup_mac.py
```

This creates `dist/RollCoaster.app`.

Run it from Finder (double-click), or from Terminal:

```bash
open dist/RollCoaster.app
```

## Web Version

The project also includes a Flask frontend that reuses the same parsing and
probability engine.

Local run:

```bash
pip install -e .
python webapp.py
```

Or via the console script:

```bash
pip install -e .
rollcoaster-web
```

Open <http://127.0.0.1:5000/> and enter a sequence such as `224s3`.

## PythonAnywhere

The clean deployment path is to keep your existing PythonAnywhere site and point
 its WSGI config at this project.

Example WSGI file body:

```python
import sys
from pathlib import Path

project_home = Path("/home/yourusername/RollCoaster")
src_dir = project_home / "src"

if str(project_home) not in sys.path:
    sys.path.insert(0, str(project_home))
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from rollcoaster.web import app as application
```

Typical setup steps:

- clone or upload this project into your PythonAnywhere home directory
- create a virtualenv for the site and install the project with `pip install -e .`
- open the Web tab and set the virtualenv path for your site
- replace the default WSGI file contents with the snippet above
- reload the web app from the PythonAnywhere dashboard

## Test

```bash
PYTHONPATH=src python -m unittest discover -s tests
```

## License

This project is open source under the GNU General Public License, version 3 or
later. See [LICENSE](LICENSE).

Why this license:

- it allows people to use, modify, and redistribute the code
- it requires distributed derivative works to remain open source under the same license family
- it helps ensure follow-up projects built from this code stay open when they are shared

If you reuse or redistribute this project, please keep both [LICENSE](LICENSE)
and [NOTICE](NOTICE) with it so the original author remains credited.

In practical terms, people can fork and improve the project, but if they
distribute a modified version, they must also make the corresponding source
code available under GPLv3-compatible terms.

## Disclaimers

- This is an unofficial hobby project developed privately by an individual.
- No money is being made from this project.
- This repository is provided as-is, without warranty of any kind.
- This is a fan-made utility and is not affiliated with, endorsed by, or sponsored by Games Workshop or any other rights holder.
- Blood Bowl and related names may be trademarks of their respective owners.
