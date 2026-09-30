"""E11: "learn offline, look up online" — freeze a learned decision boundary into a signed CIELAB lookup table.

Train a RandomForest on card-corrected Lab from 3 lights, rasterise it into a 1-unit CIELAB grid
(cells where the forest is unsure, or outside the training data, become INCONCLUSIVE), then test the
frozen grid on the unseen 4th light. Questions: does the table keep the forest's accuracy? how big is it?
how fast is a lookup? is the lookup bit-for-bit reproducible?
"""
import csv
import hashlib
import sys
import time
import warnings
from pathlib import Path

import numpy as np
from sklearn.ensemble import RandomForestClassifier

warnings.filterwarnings("ignore")
RES = Path(__file__).parent / "results"
CONF = 0.8


def load(key):
    rows = list(csv.reader(open(RES / f"e8_features_{key}.csv", encoding="utf-8")))
    light = np.array([r[0] for r in rows])
    y = np.array([1 if r[2] == "positive" else 0 for r in rows])
    lab = np.array([[float(v) for v in r[-3:]] for r in rows])
    return light, y, lab


def build_grid(model, lab_train, pad=6):
    lo = np.floor(lab_train.min(0) - pad).astype(int); hi = np.ceil(lab_train.max(0) + pad).astype(int)
    axes = [np.arange(lo[i], hi[i] + 1) for i in range(3)]
    G = np.stack(np.meshgrid(*axes, indexing="ij"), -1).reshape(-1, 3).astype(float)
    p = model.predict_proba(G)
    cls = model.classes_[p.argmax(1)].astype(np.int8)
    cls[p.max(1) < CONF] = -1
    # cells far from any training colour are "unknown colour" -> inconclusive
    from sklearn.neighbors import NearestNeighbors
    d, _ = NearestNeighbors(n_neighbors=1).fit(lab_train).kneighbors(G)
    cls[d[:, 0] > pad] = -1
    return lo, hi, cls.reshape([len(a) for a in axes])


def lookup(grid, lab):
    lo, hi, cls = grid
    idx = np.rint(lab).astype(int) - lo
    inside = np.all((idx >= 0) & (idx < np.array(cls.shape)), 1)
    out = np.full(len(lab), -1, np.int8)
    ii = idx[inside]
    out[inside] = cls[ii[:, 0], ii[:, 1], ii[:, 2]]
    return out


def score(pred, y):
    cov = pred >= 0
    return 100 * np.mean(pred == y), 100 * np.mean(cov & (pred != y)), 100 * np.mean(~cov)


print(f"{'reagent':8s} {'unseen light':18s} {'forest c/w/a %':>18s} {'frozen table c/w/a %':>22s} {'agree':>6s} {'table size':>11s}")
for key in ("Marquis", "Mecke", "Simons"):
    light, y, lab = load(key)
    for held in sorted(set(light)):
        tr, te = light != held, light == held
        m = RandomForestClassifier(n_estimators=300, random_state=0, n_jobs=-1).fit(lab[tr], y[tr])
        p = m.predict_proba(lab[te]); rf_pred = m.classes_[p.argmax(1)]; rf_pred[p.max(1) < CONF] = -1
        grid = build_grid(m, lab[tr])
        t0 = time.perf_counter()
        for _ in range(1000):
            g_pred = lookup(grid, lab[te][:1])
        lat_us = (time.perf_counter() - t0) / 1000 * 1e6
        g_pred = lookup(grid, lab[te])
        agree = 100 * np.mean(g_pred == rf_pred)
        c1, w1, a1 = score(rf_pred, y[te]); c2, w2, a2 = score(g_pred, y[te])
        size_kb = grid[2].nbytes / 1024
        print(f"{key:8s} {held.split(' (')[0]:18s} {c1:5.1f}/{w1:4.1f}/{a1:4.1f}      {c2:5.1f}/{w2:4.1f}/{a2:4.1f}       {agree:5.1f}% {size_kb:8.0f} KB")
    digest = hashlib.sha256(grid[2].tobytes()).hexdigest()[:16]
    print(f"{'':8s} lookup latency ~{lat_us:.0f} us per reading (NumPy); table SHA-256 {digest}… (signed inside the kit profile)")
