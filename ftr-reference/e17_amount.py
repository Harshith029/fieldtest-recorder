"""E17: does the decision survive realistic sample amounts, and does a blank well make "negative" possible?

Review finding (verified): the point rule works only at the NIJ chip's exact depth; a clear well never reads
negative. Compared here on the SAME readings:
  rule      old point-distance rule (+ blank well, so the comparison is about amount only)
  band      range model: documented colour at 0.5-1.6x amount (bands.py), blank-relative
Test colours come from TWO amount models so the band model is not only tested on its own assumption:
  A  Beer-Lambert, k = 0.4 ... 1.8   (0.4 and 1.8 lie OUTSIDE the band's 0.5-1.6 construction range)
  B  partial reaction (linear reflectance mix with the blank), f = 0.4 ... 1.0
Measurement noise: Gaussian, sigma 1.0 per CIELAB channel. Colour-level simulation (no photo rendering).
Part 2 runs the NCB kit (NDDK) chart bands; Part 3 walks the printed flow charts with narrowing + quantity flag.
All rates with 95% Clopper-Pearson intervals.
"""
import json
import warnings
from pathlib import Path

import numpy as np

warnings.filterwarnings("ignore")
import bands  # noqa: E402
import kit_profile as kp  # noqa: E402
import nddk  # noqa: E402
import nij_colours  # noqa: E402
from stats import fmt  # noqa: E402

HERE = Path(__file__).parent
P = {p.stem: kp.KitProfile.from_dict(json.loads(p.read_text())) for p in (HERE / "profiles").glob("*.json")
     if p.stem != "nddk-protocol"}
rng = np.random.default_rng(17)
N, SIG = 30, 1.0
BLANK = bands.WHITE
noisy = lambda L: np.asarray(L, float) + rng.normal(0, SIG, 3)
LEVELS = [("A", k) for k in (0.4, 0.5, 0.6, 0.8, 1.0, 1.2, 1.4, 1.6, 1.8)] + [("B", f) for f in (0.4, 0.6, 0.8)]


def gen(L, model, x):
    return bands.amount_series(L, x, BLANK) if model == "A" else bands.coverage_series(L, x, BLANK)


print("Part 1: NIJ demo reagents, positive-group sensitivity and false positives vs sample amount")
print("(pos = positive-group substances called positive; FP = other substances called positive; blank = clear well called negative)")
summary = {}
for reagent, slug in (("Marquis", "marquis"), ("Mecke", "mecke"), ("Simon's", "simons"), ("Cobalt thiocyanate", "cobalt-thiocyanate")):
    ref = nij_colours.reference(reagent)
    grp = P[f"demo-{slug}-rule"].positive_group()
    for method in ("rule", "band"):
        prof = P[f"demo-{slug}-{method}"]
        cells, tot = [], {"pos": [0, 0], "fp": [0, 0], "wrong": [0, 0]}
        for model, x in LEVELS:
            pos = fp = npos = nneg = wrong = 0
            for r, g in zip(ref, grp):
                base = gen(r["lab"], model, x)
                for _ in range(N):
                    out, _, cons = prof.classify(noisy(base), noisy(BLANK))
                    if g:
                        npos += 1; pos += out == "positive"; wrong += out == "negative"
                    else:
                        nneg += 1; fp += out == "positive"
            cells.append(f"{model}{x}:{100 * pos / npos:3.0f}/{100 * fp / nneg:2.0f}")
            if (model, x) not in (("A", 0.4), ("A", 1.8)):              # inside the realistic range
                tot["pos"][0] += pos; tot["pos"][1] += npos; tot["fp"][0] += fp; tot["fp"][1] += nneg
                tot["wrong"][0] += wrong; tot["wrong"][1] += npos
        bl = [prof.classify(noisy(BLANK), noisy(BLANK))[0] for _ in range(200)]
        summary[(reagent, method)] = (tot, sum(o == "negative" for o in bl))
        print(f"  {reagent:18s} {method:4s} pos%/FP%  " + " ".join(cells))
print("\n  pooled over amounts 0.5-1.6x (model A) and 0.4-0.8 coverage (model B):")
for (reagent, method), (tot, blank_neg) in summary.items():
    print(f"  {reagent:18s} {method:4s} positive-group called positive {fmt(*tot['pos']):>22s} | "
          f"others called positive {fmt(*tot['fp']):>20s} | clear well -> negative {fmt(blank_neg, 200)}")

print("\nClear well WITHOUT a blank in the frame (old behaviour):",
      {s: P[s].classify(noisy(BLANK))[:2] for s in ("demo-marquis-rule", "demo-simons-map")})
print("Simon's region map at white after the guard + outlier removal:",
      [P["demo-simons-map"].classify(np.array(L, float))[:2] for L in ([95, 0, 0], [92, 0, -2], [88, 0, 0])])

print("\nPart 2: NCB kit chart bands (approximate colours), each outcome across its range and amount")
tot_ok = tot_n = tot_wrong = 0
for test, outcomes in nddk.CHART.items():
    prof = P[f"nddk-test-{test}"]
    for name, subs, a, b, k_hi in outcomes:
        ok = n = wrong = neg = miss = 0
        where = {}
        ends = [np.array(a)] + ([np.array(b)] if b is not None else [])
        for end in ends:
            for model, x in [("A", k) for k in (0.5, 0.8, 1.0, 1.3, 1.6)] + [("B", 0.5), ("B", 0.8)]:
                base = gen(end, model, x)
                for _ in range(N):
                    out, reason, cons = prof.classify(noisy(base), noisy(BLANK))
                    n += 1
                    ok += out == "positive" and set(subs) <= set(cons)
                    is_neg = out == "negative"
                    is_miss = out == "positive" and not set(subs) <= set(cons)
                    neg += is_neg; miss += is_miss; wrong += is_neg or is_miss
                    if is_neg or is_miss:
                        where[f"{model}{x}"] = where.get(f"{model}{x}", 0) + 1
        tot_ok += ok; tot_n += n; tot_wrong += wrong
        print(f"  Test {test:3s} {name:24s} correct {fmt(ok, n):>22s}  wrong {fmt(wrong, n):>20s}"
              + (f"  [{neg} no-change, {miss} list misses; at {where}]" if wrong else ""))
    bl = [prof.classify(noisy(BLANK), noisy(BLANK))[0] for _ in range(200)]
    print(f"  Test {test:3s} {'clear well (blank)':24s} negative {fmt(sum(o == 'negative' for o in bl), 200)}")
print(f"  all NDDK outcomes: correct {fmt(tot_ok, tot_n)}, wrong {fmt(tot_wrong, tot_n)} "
      "(wrong = called negative, or positive without the true substance in the list)")

print("\nPart 3: guided protocol (printed flow charts) with narrowing and the NDPS quantity warning")
prof = {t: P[f"nddk-test-{t}"] for t in nddk.CHART}
col = {o[0]: np.array(o[2]) for outs in nddk.CHART.values() for o in outs}


def scenario(title, nature, truth):
    def outcome_of(test):
        L = truth.get(test)
        if L is None:
            return nddk.classify_step(prof, test, noisy(BLANK), noisy(BLANK)) if test in prof else \
                nddk.classify_step(prof, test, noisy(BLANK), noisy(BLANK))
        return nddk.classify_step(prof, test, noisy(L), noisy(BLANK))
    r = nddk.run_flow(nature, outcome_of)
    steps = " -> ".join(f"{t}:{o}" for _, t, o in r["path"] if t) + f" -> {r['path'][-1][0]}"
    print(f"  {title}\n    {steps}\n    candidates {r['candidates']}; {r['quantity_warning'] or 'quantity category decidable'}")


scenario("white powder, opiate reaction (purple) on Test A", "resin or powder (opiate suspected)", {"A": col["morphine"]})
scenario("tablet, amphetamine-range colour on Test A", "tablets, capsules, powders, liquids", {"A": col["amphetamines"]})
scenario("powder, blue on Test E, E3/E4 not yet run", "impregnated paper or gelatine film",
         {"E": col["cocaine or methaqualone"], "E34": None})
scenario("powder, blue on Test E, green on E3/E4", "impregnated paper or gelatine film",
         {"E": col["cocaine or methaqualone"], "E34": col["cocaine"]})
scenario("dried herb, red lower layer on Test B", "herb, resin or oil", {"B": col["cannabis"]})
