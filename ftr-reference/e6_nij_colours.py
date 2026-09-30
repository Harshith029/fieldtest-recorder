"""E6: can the engine read REAL published colour-test outcomes?

Source colours: NIJ Standard-0604.01, Table 1 (final colours as Munsell notation), parsed into
docs/research/data/nij0604_table1.csv. Munsell (Illuminant C) -> XYZ -> Bradford to D65 -> CIELAB.

Question 1 (no photos): how far apart are "target" outcomes from the nearest non-target outcome?
Question 2 (rendered photos): with those real colours, how often is the engine correct / wrong / inconclusive?
Every well reading is logged to results/e6_<reagent>.csv for the threshold study (E7).

Caveat: NIJ colours are for pure reference drugs; street samples are mixtures and vary.
"""
import csv
import sys
import warnings
from collections import Counter, defaultdict
from pathlib import Path

import colour
import numpy as np

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).parent / "research"))
import sim  # noqa: E402
import colour_engine as ce  # noqa: E402
import photo_sim  # noqa: E402

REAGENT = sys.argv[1] if len(sys.argv) > 1 else "Marquis"
N = int(sys.argv[2]) if len(sys.argv) > 2 else 200
photo_sim.reseed(hash(REAGENT) % 10_000)

TARGETS = {  # what a "positive" means for this reagent in our proxy profile
    "Marquis": {"Codeine", "Diacetylmorphine HCl", "Morphine monohydrate", "Oxycodone HCl"},   # opiates
    "Mecke": {"Codeine", "Diacetylmorphine HCl", "Morphine monohydrate", "Hydrocodone tartrate"},
    "Simon's": {"d-Methamphetamine HCl", "MDMA HCl"},                                          # secondary amines
    "Cobalt thiocyanate": {"Cocaine HCl"},
}
C = colour.CCS_ILLUMINANTS["CIE 1931 2 Degree Standard Observer"]["C"]


def munsell_to_lab(m):
    m = m.strip()
    if m == "Black":
        m = "N1.5"
    m = m.replace("N ", "N").rstrip("/")
    xyY = colour.munsell_colour_to_xyY(m)
    XYZ = colour.xyY_to_XYZ(xyY)
    XYZ = colour.chromatic_adaptation(XYZ, colour.xy_to_XYZ(C), colour.xy_to_XYZ(sim.WP), method="Von Kries",
                                      transform="Bradford")
    return colour.XYZ_to_Lab(XYZ, sim.WP)


rows = [r for r in csv.DictReader(open(Path(__file__).parent / "docs/research/data/nij0604_table1.csv", encoding="utf-8"))
        if r["reagent"] == REAGENT]
outcomes, skipped = [], []
for r in rows:
    try:
        L = munsell_to_lab(r["munsell"])
    except Exception as e:  # noqa: BLE001  (some notations fall outside the renotation data)
        skipped.append((r["analyte"], r["munsell"], type(e).__name__))
        continue
    cls = "positive" if r["analyte"] in TARGETS[REAGENT] else "negative"
    outcomes.append((r["analyte"], cls, L, r["munsell"], r["colour_name"]))

print(f"== {REAGENT}: {len(outcomes)} NIJ outcomes usable, {len(skipped)} skipped {skipped}")
print("\nQ1  Separability: each positive outcome vs its nearest NEGATIVE outcome (dE00, D65)")
for a, cls, L, mun, name in outcomes:
    if cls != "positive":
        continue
    d = sorted((float(sim.de(L, L2)), b, n2) for b, c2, L2, m2, n2 in outcomes if c2 == "negative")
    tag = "UNRESOLVABLE" if d[0][0] < 5 else ("hard" if d[0][0] < 10 else "resolvable")
    print(f"  {a:24s} {mun:12s} {name:24s} nearest negative: {d[0][1]:22s} dE00 {d[0][0]:5.1f}  -> {tag}")


def refl_from_lab(L):
    X = colour.Lab_to_XYZ(L, sim.WP)
    sd = colour.XYZ_to_sd(X, method="Meng 2015",
                          cmfs=colour.MSDS_CMFS["CIE 1931 2 Degree Standard Observer"].copy().align(sim.SHAPE),
                          illuminant=colour.SDS_ILLUMINANTS["D65"].copy().align(sim.SHAPE))
    return np.clip(sd.values, 0, 1)


REFL = {a: refl_from_lab(L) for a, _, L, _, _ in outcomes}
PROFILE = [(a, cls, L) for a, cls, L, _, _ in outcomes]
pos = [o for o in outcomes if o[1] == "positive"]
neg = [o for o in outcomes if o[1] == "negative"]
LIGHTS = [l for l in sim.ILL if "Sodium" not in l]      # sodium is rejected upstream (night mode handles it)

out_dir = Path(__file__).parent / "results"
out_dir.mkdir(exist_ok=True)
log = csv.writer(open(out_dir / f"e6_{REAGENT.replace(' ', '_').replace(chr(39), '')}.csv", "w", newline="", encoding="utf-8"))
log.writerow(["light", "truth", "truth_class", "outcome", "reason", "nearest", "de_nearest", "margin"])
stats, per_sub = Counter(), defaultdict(Counter)
for n in range(N):
    light = LIGHTS[n % len(LIGHTS)]
    truth = [(pos if photo_sim.rng.random() < 0.5 else neg) for _ in range(2)]
    truth = [grp[photo_sim.rng.integers(0, len(grp))] for grp in truth]
    wells = np.vstack([photo_sim.jitter(REFL[t[0]]) for t in truth])
    img, _ = photo_sim.render(sim.ILL[light], wells, sim.random_conditions(), glare_on=photo_sim.rng.random() < 0.2,
                              noise=0.01)
    res = ce.read_capture(img, PROFILE)
    if not res.accepted:
        stats["rejected:" + res.reason] += 1
        continue
    for w, t in zip(res.wells, truth):
        stats["wells"] += 1
        key = "inconclusive" if w.outcome == "inconclusive" else ("correct" if w.outcome == t[1] else
                                                                  "WRONG " + ("false positive" if w.outcome == "positive" else "false negative"))
        stats[key] += 1
        per_sub[t[0]][key] += 1
        log.writerow([light, t[0], t[1], w.outcome, w.reason, w.nearest, w.de_nearest, w.margin])

W = stats["wells"]
print(f"\nQ2  Engine on {N} rendered photos ({', '.join(l.split(' (')[0] for l in LIGHTS)}), {W} well readings:")
for k in ("correct", "inconclusive", "WRONG false positive", "WRONG false negative"):
    print(f"  {k:22s} {stats[k]:4d}  ({100 * stats[k] / max(W, 1):5.1f}%)")
print("  rejected photos:", {k: v for k, v in stats.items() if k.startswith("rejected")})
print("\n  per substance (correct / inconclusive / wrong):")
for a, c in sorted(per_sub.items(), key=lambda kv: -sum(v for k, v in kv[1].items() if k.startswith("WRONG"))):
    wrong = sum(v for k, v in c.items() if k.startswith("WRONG"))
    tot = sum(c.values())
    print(f"   {a:26s} n={tot:3d}  correct {c['correct']:3d}  inconcl {c['inconclusive']:3d}  wrong {wrong:3d}")
