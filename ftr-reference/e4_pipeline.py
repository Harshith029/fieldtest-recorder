"""E4: end-to-end test of the colour engine on rendered phone photos.

Each synthetic photo: the printed card (4 ArUco markers, 24 patches, 2 reaction wells) rendered spectrally
under one of five lights through a real camera sensor model (Nikon 5100 NPL data), with uneven lighting,
optional glare on a well, perspective tilt, rotation, blur, sensor noise, phone white balance/tone/saturation,
and JPEG compression. The engine then has to find the card and read both wells.
Reaction colours are ILLUSTRATIVE proxies, not real kit colours.
"""
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).parent / "research"))
import sim  # noqa: E402
import colour_engine as ce  # noqa: E402

import colour  # noqa: E402

rng = np.random.default_rng(2026)
N_IMAGES = int(sys.argv[1]) if len(sys.argv) > 1 else 500
MODE = sys.argv[2] if len(sys.argv) > 2 else "sep"      # sep | c10 | c7


def refl_from_lab(L):
    X = colour.Lab_to_XYZ(L, sim.WP)
    sd = colour.XYZ_to_sd(X, method="Meng 2015",
                          cmfs=colour.MSDS_CMFS["CIE 1931 2 Degree Standard Observer"].copy().align(sim.SHAPE),
                          illuminant=colour.SDS_ILLUMINANTS["D65"].copy().align(sim.SHAPE))
    return np.clip(sd.values, 0, 1)


V = sim.TRUE_LAB[sim.NAMES.index("violet")]
PLUM = colour.XYZ_to_Lab(colour.sRGB_to_XYZ(colour.notation.HEX_to_RGB("#6E2D6A")), sim.WP)


def confuser(target):
    from scipy.optimize import brentq
    k = brentq(lambda k: float(sim.de(V, V + k * (PLUM - V))) - target, 0, 1.5)
    return V + k * (PLUM - V)


# kit profile for the proxy kit: which outcome colours mean what
if MODE == "sep":
    CLASSES = {"violet": "positive", "no change": "negative", "yellow": "negative", "orange": "negative",
               "purple-brown": "negative", "brown": "negative", "blue": "negative"}
    LABS = {n: sim.TRUE_LAB[sim.NAMES.index(n)] for n in CLASSES}
    REFLS = {n: sim.REFL[sim.NAMES.index(n)] for n in CLASSES}
else:
    d = 10.0 if MODE == "c10" else 7.0
    CLASSES = {"violet": "positive", f"look-alike ({d:.0f} dE00)": "negative", "no change": "negative"}
    Lc = confuser(d)
    LABS = {"violet": V, list(CLASSES)[1]: Lc, "no change": sim.TRUE_LAB[sim.NAMES.index("no change")]}
    REFLS = {"violet": sim.REFL[sim.NAMES.index("violet")], list(CLASSES)[1]: refl_from_lab(Lc),
             "no change": sim.REFL[sim.NAMES.index("no change")]}
PROFILE = [(n, c, LABS[n]) for n, c in CLASSES.items()]
TRUTH_NAMES = list(CLASSES)
LIGHTS = list(sim.ILL)

from photo_sim import render, jitter, xx, yy, LABELS  # noqa: E402
import photo_sim  # noqa: E402
photo_sim.rng = rng

stats = defaultdict(Counter)
baseline = Counter()
t0 = time.perf_counter()
for n in range(N_IMAGES):
    light = LIGHTS[n % len(LIGHTS)]
    ill = sim.ILL[light]
    noise = 0.02 if "Sodium" in light else 0.01
    p_pos = 0.4 if MODE == "sep" else 0.5
    truth = [TRUTH_NAMES[0] if rng.random() < p_pos else
             (TRUTH_NAMES[1] if MODE != "sep" and rng.random() < 0.8 else TRUTH_NAMES[rng.integers(1, len(TRUTH_NAMES))])
             for _ in range(2)]
    wells = np.vstack([jitter(REFLS[t]) for t in truth])
    cond = sim.random_conditions()
    img, sigma = render(ill, wells, cond, glare_on=rng.random() < 0.2, noise=noise)
    res = ce.read_capture(img, PROFILE)
    st = stats[light]
    st["images"] += 1
    if not res.accepted:
        st["rejected:" + res.reason] += 1
        continue
    # baseline for comparison: same rectified image, no card correction (phone colours as-is)
    card = ce.rectify(img)
    for w, t in zip(res.wells, truth):
        true_cls = CLASSES[t]
        st["wells"] += 1
        if w.outcome == "inconclusive":
            st["inconclusive:" + w.reason] += 1
        elif w.outcome == true_cls:
            st["correct"] += 1
        else:
            st["WRONG " + ("false positive" if w.outcome == "positive" else "false negative")] += 1
        cx, cy = ce.WELLS[w.well]
        m = (xx - cx) ** 2 + (yy - cy) ** 2 <= (0.6 * ce.WELL_R) ** 2
        px = card[m].astype(float)
        L = sim.lab_from_srgb((np.median(px, 0) / 255.0)[None])[0]
        cls, *_ = ce.classify(L, PROFILE)
        baseline["wells"] += 1
        baseline["correct" if cls == true_cls else ("inconclusive" if cls == "inconclusive" else "wrong")] += 1

dt = time.perf_counter() - t0
print(f"MODE={MODE}: profile " + ", ".join(f"{n}={c}" for n, c in CLASSES.items()))
print(f"{N_IMAGES} rendered photos, {dt:.0f}s ({1000 * dt / N_IMAGES:.0f} ms per photo incl. rendering)\n")
print(f"{'light':28s} {'card found':>10s} {'rejected (reason)':>34s} {'wells read':>10s} {'correct':>8s} {'inconcl.':>9s} {'WRONG':>6s}")
tot = Counter()
for light in LIGHTS:
    st = stats[light]
    tot.update(st)
    rej = {k.split(':')[1]: v for k, v in st.items() if k.startswith('rejected')}
    found = st["images"] - rej.get("card_not_found", 0)
    rej_txt = ", ".join(f"{k} {v}" for k, v in rej.items() if k != "card_not_found") or "-"
    wells = st["wells"]
    inc = sum(v for k, v in st.items() if k.startswith("inconclusive"))
    wrong = sum(v for k, v in st.items() if k.startswith("WRONG"))
    pct = lambda x: f"{100 * x / wells:5.1f}%" if wells else "   -"
    print(f"{light:28s} {100 * found / st['images']:9.1f}% {rej_txt:>34s} {wells:>10d} {pct(st['correct']):>8s} {pct(inc):>9s} {pct(wrong):>6s}")
print("\nall lights, detail:", dict(sorted((k, v) for k, v in tot.items() if k not in ("images",))))
print(f"baseline without card correction (accepted photos only): "
      f"correct {100 * baseline['correct'] / baseline['wells']:.1f}%, wrong {100 * baseline['wrong'] / baseline['wells']:.1f}%, "
      f"inconclusive {100 * baseline['inconclusive'] / baseline['wells']:.1f}%")
