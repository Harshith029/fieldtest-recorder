"""E7: (a) choose decision thresholds from data (risk vs coverage); (b) does ML beat, or replace, the card?

Uses per-well features saved by E8 (rendered photos with NIJ reference colours):
light, substance, colour-group truth, raw well sRGB (no correction), 24 raw card patches, card-corrected Lab.
(b) compares, on the same wells:
  RULE          colour-group rule on card-corrected Lab (our design)
  ML-raw        RandomForest on raw well RGB only                 ("AI instead of a card")
  ML-raw+card   RandomForest on raw well RGB + raw card patches   ("learned calibration")
  ML-lab        RandomForest on card-corrected Lab
ML models abstain when top-class probability < 0.8, so they are compared fairly with the rule's abstention.
Evaluated in-distribution (random 50/50 split) and out-of-distribution (train 3 lights, test the unseen 4th).
"""
import contextlib
import csv
import io
import sys
import warnings
from pathlib import Path

import numpy as np
from sklearn.ensemble import RandomForestClassifier

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).parent / "research"))
import sim  # noqa: E402

HERE = Path(__file__).parent
RES = HERE / "results"
REAGENTS = {"Marquis": "Marquis", "Mecke": "Mecke", "Simons": "Simon's"}
R_DEF = 6.0


def load(key):
    rows = list(csv.reader(open(RES / f"e8_features_{key}.csv", encoding="utf-8")))
    light = np.array([r[0] for r in rows])
    y = np.array([1 if r[2] == "positive" else 0 for r in rows])
    X = np.array([[float(v) for v in r[3:]] for r in rows])
    return light, y, X[:, :3], X[:, 3:75], X[:, 75:78]


def reference(name):
    g = {"__name__": "x", "__file__": str(HERE / "e6_nij_colours.py")}
    src = open(HERE / "e6_nij_colours.py", encoding="utf-8").read().split("out_dir = ")[0]
    argv, sys.argv = sys.argv, ["x", name, "0"]
    with contextlib.redirect_stdout(io.StringIO()):
        exec(compile(src, "e6", "exec"), g)
    sys.argv = argv
    return [(a, cls == "positive", L) for a, cls, L, _, _ in g["outcomes"]]


def distances(lab, ref):
    pos = [L for _, t, L in ref if t]
    in_pos = [min(float(sim.de(L, p)) for p in pos) <= R_DEF for _, _, L in ref]
    others = [L for (_, _, L), inside in zip(ref, in_pos) if not inside]
    dp = np.array([min(float(sim.de(x, p)) for p in pos) for x in lab])
    do = np.array([min(float(sim.de(x, o)) for o in others) for x in lab])
    return dp, do


def rule(dp, do, r, M):
    pred = np.full(len(dp), -1)
    pred[(dp <= r) & (do - dp >= M)] = 1
    pred[(do <= r) & (dp - do >= M)] = 0
    return pred


def score(pred, y):
    cov = pred >= 0
    return 100 * np.mean(pred == y), 100 * np.mean(cov & (pred != y)), 100 * np.mean(~cov)


def rf(Xtr, ytr, Xte, conf=0.8, model=None):
    m = (model or RandomForestClassifier(n_estimators=300, random_state=0, n_jobs=-1)).fit(Xtr, ytr)
    p = m.predict_proba(Xte)
    pred = m.classes_[p.argmax(1)]
    pred[p.max(1) < conf] = -1
    return pred


from sklearn.discriminant_analysis import QuadraticDiscriminantAnalysis  # noqa: E402
from sklearn.neighbors import KNeighborsClassifier  # noqa: E402

EXPLAINABLE = {"kNN-15 (Lab)": lambda: KNeighborsClassifier(n_neighbors=15),
               "QDA (Lab)": lambda: QuadraticDiscriminantAnalysis(reg_param=0.05)}


print("(a) THRESHOLD STUDY  colour-group rule; group radius R=6 fixed; sweep acceptance radius r and margin M")
print(f"    {'reagent':8s} {'r':>3s} {'M':>3s} {'correct':>8s} {'wrong':>7s} {'inconcl':>8s}")
chosen = {}
data = {}
for key, name in REAGENTS.items():
    light, y, raw, card, lab = load(key)
    dp, do = distances(lab, reference(name))
    data[key] = (light, y, raw, card, lab, dp, do)
    grid = [(r, M, *score(rule(dp, do, r, M), y)) for r in (4, 5, 6, 7, 8) for M in (0, 1, 2, 3, 4)]
    for r, M, c, w, i in grid:
        if (r, M) in ((6, 2), (5, 3), (8, 0)):
            print(f"    {key:8s} {r:3d} {M:3d} {c:7.1f}% {w:6.1f}% {i:7.1f}%")
    ok = [g for g in grid if g[3] <= 0.5]
    best = max(ok, key=lambda g: g[2]) if ok else min(grid, key=lambda g: g[3])
    chosen[key] = best
    print(f"    {key:8s} best with wrong <= 0.5%: r={best[0]} M={best[1]} -> correct {best[2]:.1f}%, wrong {best[3]:.1f}%, inconclusive {best[4]:.1f}%")

print("\n(b) ML vs CARD  correct / wrong / abstain (%)")
print(f"    {'reagent':8s} {'test':22s} {'RULE (card)':>20s} {'ML-raw (no card)':>20s} {'ML-raw+card':>20s} {'ML-lab':>20s}")
fmt = lambda t: f"{t[0]:5.1f}/{t[1]:4.1f}/{t[2]:4.1f}"
rng = np.random.default_rng(0)
for key, (light, y, raw, card, lab, dp, do) in data.items():
    r, M = chosen[key][0], chosen[key][1]
    rule_pred = rule(dp, do, r, M)
    idx = rng.permutation(len(y)); tr, te = idx[: len(y) // 2], idx[len(y) // 2:]
    splits = [("random 50/50", tr, te)]
    for held in sorted(set(light)):
        splits.append((f"unseen: {held.split(' (')[0]}", np.where(light != held)[0], np.where(light == held)[0]))
    for label, tr, te in splits:
        cols = [score(rule_pred[te], y[te])]
        for Xf in (raw, np.hstack([raw, card]), lab):
            cols.append(score(rf(Xf[tr], y[tr], Xf[te]), y[te]))
        for mk in EXPLAINABLE.values():
            cols.append(score(rf(lab[tr], y[tr], lab[te], model=mk()), y[te]))
        print(f"    {key:8s} {label:22s} " + " ".join(f"{fmt(c):>20s}" for c in cols))
print("    (last two columns: explainable learned boundaries on card-corrected Lab: kNN-15, QDA)")
