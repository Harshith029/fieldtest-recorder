"""End-to-end check of the blank-well path through the real photo engine (JPEG and RAW tiers).

Rendered photos: W1 = sample well, W2 = reagent-only blank (clear). NCB kit Test A profile (layout blank_well=W2).
Cases: an opiate-range reaction, an amphetamine-range reaction, and a clear sample (no reaction).
Expected: reaction -> positive with the right substance listed; clear sample -> negative "no_colour_change";
the blank well is reported as the blank, never classified.
"""
import json
import warnings
from collections import Counter
from pathlib import Path

import numpy as np

warnings.filterwarnings("ignore")
import bands  # noqa: E402
import colour_engine as ce  # noqa: E402
import kit_profile as kp  # noqa: E402
import nij_colours as nc  # noqa: E402
import photo_sim as ps  # noqa: E402
import sim  # noqa: E402
from stats import fmt  # noqa: E402

HERE = Path(__file__).parent
prof = kp.KitProfile.from_dict(json.loads((HERE / "profiles" / "nddk-test-A.json").read_text()))
chart = {o[0]: o for o in __import__("nddk").CHART["A"]}
cases = {"morphine": (bands.amount_series(np.array(chart["morphine"][2]), 1.2), "morphine"),
         "amphetamines": (bands.amount_series(np.array(chart["amphetamines"][2]), 1.0), "amphetamine"),
         "clear sample": (bands.WHITE, None)}
blank_refl = nc.reflectance(bands.WHITE)
lights = [l for l in sim.ILL if "Sodium" not in l]
ps.reseed(7)
N = 40
for name, (lab_true, sub) in cases.items():
    tally = {"JPEG": Counter(), "RAW": Counter()}
    for i in range(N):
        wells = np.vstack([ps.jitter(nc.reflectance(lab_true)), ps.jitter(blank_refl)])
        jpeg, _, raw = ps.render(sim.ILL[lights[i % len(lights)]], wells, sim.random_conditions(),
                                 glare_on=False, noise=0.01, return_raw=True)
        for tier, res in (("JPEG", ce.read_capture(jpeg, prof)), ("RAW", ce.read_capture_linear(jpeg, raw, prof))):
            if not res.accepted:
                tally[tier]["rejected:" + res.reason] += 1
                continue
            w1, w2 = res.wells
            assert w2.outcome == "blank", w2
            ok = (w1.outcome == "positive" and sub in (w1.consistent_with or [])) if sub else \
                 (w1.outcome == "negative" and w1.reason == "no_colour_change")
            tally[tier]["correct" if ok else f"{w1.outcome}:{w1.reason}"] += 1
    for tier, c in tally.items():
        acc = sum(v for k, v in c.items() if not k.startswith("rejected"))
        print(f"{name:14s} {tier:4s} correct {fmt(c['correct'], acc):>22s}  other: {dict((k, v) for k, v in c.items() if k != 'correct')}")
