"""Check that the offline JavaScript engine (docs/engine.js) matches core.py."""

import itertools
import json
import random
import shutil
import subprocess
import unittest
from pathlib import Path

from diced.core import (
    RollSequenceCalculator,
    SequenceOptions,
    apply_options,
    armour_outcomes,
    parse_sequence,
)

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "docs" / "engine.js"

TOKENS = [
    "2+", "3+", "4+", "5+", "6+", "3++", "4++", "2p", "4+p",
    "1d", "2d", "3d", "-2d", "-3d", "2d-", "3d*", "2d/", "2d+", "-2d+-", "2d++", "2d+++",
    "av8", "av9", "av10k", "av9i", "av9km", "av11sim", "av9m",
    "b", "p", "s", "224s3", "3++2+2d-av9",
]

FIXED_INPUTS = [
    "2d- s av9k", "2d-sav9k", "av9 s k", "av9 m k", "224s3", "4s", "b2d-4+", "2d b 4+ p av9",
    "3+p", "2+ p 4+", "1d av9", "-3d* av11ksm", "av9x", "", "7+", "2d++++", "av12", "4++p",
]

NODE_SCRIPT = r"""
const E = require(process.argv[1]);
const cases = JSON.parse(require("fs").readFileSync(0, "utf8"));
const out = cases.map(([text, toggles]) => {
  try {
    const r = E.evaluate(text, toggles);
    return { totals: r.totals, tokens: r.tokens, labels: r.labels, armour: r.armour };
  } catch (e) {
    return { error: true };
  }
});
process.stdout.write(JSON.stringify(out));
"""


def python_reference(text: str, toggles: dict[str, bool]) -> dict:
    calc = RollSequenceCalculator()
    try:
        parsed, typed = parse_sequence(text)
        options = SequenceOptions(**toggles).merged(typed)
        steps = apply_options(parsed, options)
        result = calc.calculate(steps, max_global_rerolls=2, pro=options.pro)
        armour = armour_outcomes(calc, steps, options)
    except ValueError:
        return {"error": True}
    return {
        "totals": [result.global_reroll_probabilities[r] for r in range(3)],
        "tokens": [step.display_token for step in steps],
        "labels": options.labels,
        "armour": (
            {label: [values[r] for r in range(3)] for label, values in armour.items()}
            if armour
            else None
        ),
    }


def js_display(token: str) -> str:
    """Python keeps raw block tokens in display_token; JS shows labels like the web UI."""
    from diced.web import format_token_for_display

    return format_token_for_display(token)


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class JavaScriptParityTests(unittest.TestCase):
    def test_engine_matches_python(self) -> None:
        rng = random.Random(7)
        names = ["block", "pro", "brawler", "mighty_blow", "stunty"]
        cases = []
        for text in FIXED_INPUTS:
            for bits in itertools.product([False, True], repeat=len(names)):
                cases.append((text, dict(zip(names, bits))))
        for _ in range(1500):
            text = " ".join(rng.choice(TOKENS) for _ in range(rng.randint(1, 5)))
            cases.append((text, {name: rng.random() < 0.3 for name in names}))

        proc = subprocess.run(
            ["node", "-e", NODE_SCRIPT, str(ENGINE)],
            input=json.dumps(cases),
            capture_output=True,
            text=True,
            check=True,
        )
        js_results = json.loads(proc.stdout)
        self.assertEqual(len(js_results), len(cases))

        for (text, toggles), js in zip(cases, js_results):
            py = python_reference(text, toggles)
            with self.subTest(text=text, toggles=toggles):
                self.assertEqual(js.get("error", False), py.get("error", False))
                if py.get("error"):
                    continue
                for a, b in zip(js["totals"], py["totals"]):
                    self.assertAlmostEqual(a, b, places=12)
                self.assertEqual(js["tokens"], [js_display(t) for t in py["tokens"]])
                self.assertEqual(js["labels"], py["labels"])
                self.assertEqual(js["armour"] is None, py["armour"] is None)
                if py["armour"]:
                    for label, values in py["armour"].items():
                        for a, b in zip(js["armour"][label], values):
                            self.assertAlmostEqual(a, b, places=12)


if __name__ == "__main__":
    unittest.main()
