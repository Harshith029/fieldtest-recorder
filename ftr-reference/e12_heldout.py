"""E12: held-out evaluation THROUGH THE REAL ENGINE PATH, several seeds, 95% intervals.

Fresh rendered photos (seeds never used to train the region maps), glare and uneven light ON, 4 normal lights.
Three configurations on the same photos:
  JPEG + rule profile         (phones without RAW, before validation data)
  JPEG + region-map profile   (phones without RAW, after validation data)
  RAW  + rule profile         (RAW/linear capture tier)
Truth = colour-group truth of the kit profile (target colours + documented cross-reactants).
Also checks the 'also consistent with' list contains the true substance on positive calls.
Usage: python e12_heldout.py <reagent> <photos per seed> <seed> [<seed> ...]
"""
import sys
import warnings
from collections import Counter
from pathlib import Path

import numpy as np

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).parent / "research"))
import build_profiles as bp  # noqa: E402
import colour_engine as ce  # noqa: E402
import nij_colours as nc  # noqa: E402
import photo_sim as ps  # noqa: E402
import sim  # noqa: E402
from stats import fmt  # noqa: E402

REAGENT, N = sys.argv[1], int(sys.argv[2])
SEEDS = [int(s) for s in sys.argv[3:]] or [101, 202, 303]
LIGHTS = [l for l in sim.ILL if "Sodium" not in l]

profiles = bp.build(write=False)
slug = REAGENT.split(" (")[0].replace("'", "").replace(" ", "-").lower()
rule, rmap = profiles[f"demo-{slug}-rule"], profiles.get(f"demo-{slug}-map")
ref = nc.reference(REAGENT)
refl = [nc.reflectance(r["lab"]) for r in ref]
grp = rule.positive_group()
pos_idx, neg_idx = np.where(grp)[0], np.where(~grp)[0]
configs = ["JPEG+rule", "JPEG+map", "RAW+rule"] if rmap else ["JPEG+rule", "RAW+rule"]

pooled = {c: Counter() for c in configs}
print(f"== {REAGENT}: {N} photos x {len(SEEDS)} seeds; positive group = {sorted({ref[i]['substance'] for i in pos_idx})}")
for seed in SEEDS:
    ps.reseed(seed)
    per = {c: Counter() for c in configs}
    for n in range(N):
        light = LIGHTS[n % len(LIGHTS)]
        pick = [int(ps.rng.choice(pos_idx if ps.rng.random() < 0.5 else neg_idx)) for _ in range(2)]
        wells = np.vstack([ps.jitter(refl[i]) for i in pick])
        jpeg, _, raw = ps.render(sim.ILL[light], wells, sim.random_conditions(),
                                 glare_on=ps.rng.random() < 0.2, noise=0.01, return_raw=True)
        results = {"JPEG+rule": ce.read_capture(jpeg, rule), "RAW+rule": ce.read_capture_linear(jpeg, raw, rule)}
        if rmap:
            results["JPEG+map"] = ce.read_capture(jpeg, rmap)
        for c, res in results.items():
            if not res.accepted:
                per[c]["rejected"] += 2
                continue
            for w, i in zip(res.wells, pick):
                truth = "positive" if grp[i] else "negative"
                k = "inconclusive" if w.outcome == "inconclusive" else ("correct" if w.outcome == truth else "wrong")
                per[c][k] += 1
                if w.outcome == "positive":
                    per[c]["pos_calls"] += 1
                    per[c]["attrib_ok"] += ref[i]["substance"] in (w.consistent_with or [])
    for c in configs:
        t = per[c]["correct"] + per[c]["wrong"] + per[c]["inconclusive"]
        print(f"   seed {seed}  {c:10s} correct {100 * per[c]['correct'] / t:5.1f}%  wrong {100 * per[c]['wrong'] / t:4.1f}%"
              f"  inconcl {100 * per[c]['inconclusive'] / t:4.1f}%  rejected photos {per[c]['rejected'] // 2}")
        pooled[c].update(per[c])
print("   POOLED (95% Clopper-Pearson):")
for c in configs:
    p = pooled[c]; t = p["correct"] + p["wrong"] + p["inconclusive"]
    print(f"   {c:10s} correct {fmt(p['correct'], t)} | wrong {fmt(p['wrong'], t)} | inconclusive {fmt(p['inconclusive'], t)}"
          f" | true substance listed on positive calls {p['attrib_ok']}/{p['pos_calls']}")
