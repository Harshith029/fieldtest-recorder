"""E2: Rule 10(2) 'identical results on colour test' — separate photos vs one photo side by side.

Pairs of packages: SAME substance (only natural reaction variation, ~1 dE00) or DIFFERENT
by a true colour difference of d dE00. Decide 'identical' if measured dE00 < T.
"""
import numpy as np
from scipy.optimize import brentq
from sim import *

TRIALS = 400
LIGHTS = ["Daylight (D65)", "Tube light (FL2)", "White LED torch (LED-B3)", "Incandescent bulb (A)"]
BASE = ["violet", "blue", "brown", "orange", "olive"]


def shifted_refl(i, target_de, direction):
    """Reflectance whose D65 colour differs from outcome i by ~target_de dE00 along a random Lab direction."""
    L0 = TRUE_LAB[i]
    f = lambda s: float(de(L0, L0 + s * direction)) - target_de
    s = brentq(f, 0, 60) if target_de > 0 else 0
    Lt = L0 + s * direction
    X = colour.Lab_to_XYZ(Lt, WP)
    sd = colour.XYZ_to_sd(X, method="Meng 2015",
                          cmfs=colour.MSDS_CMFS["CIE 1931 2 Degree Standard Observer"].copy().align(SHAPE),
                          illuminant=colour.SDS_ILLUMINANTS["D65"].copy().align(SHAPE))
    return np.clip(sd.values, 0, 1)


def jitter(refl):
    # natural variation between two reactions of the same substance (~1 dE00)
    return np.clip(refl * (1 + rng.normal(0, 0.02, refl.shape[-1])), 0, 1)


def measure(pair, ill, same_frame, method):
    if same_frame:
        cond = random_conditions()
        card = phone_capture(CARD, ill, cond, 0.004)
        v = phone_capture(np.stack(pair), ill, cond, 0.004)
        if method == "raw":
            L = lab_from_srgb(v)
        else:
            L = corrected_lab(fit_card_correction(card, "grey+3x3"), v)
        return float(de(L[0], L[1]))
    Ls = []
    for refl in pair:
        cond = random_conditions()
        card = phone_capture(CARD, ill, cond, 0.004)
        v = phone_capture(refl[None], ill, cond, 0.004)
        Ls.append(lab_from_srgb(v)[0] if method == "raw" else corrected_lab(fit_card_correction(card, "grey+3x3"), v)[0])
    return float(de(Ls[0], Ls[1]))


# pre-build pairs
pairs_same, pairs_diff = {}, {d: [] for d in (4, 6, 10)}
for n in BASE:
    i = NAMES.index(n)
    pairs_same[n] = REFL[i]
    for d in pairs_diff:
        for _ in range(2):
            dirn = rng.normal(0, 1, 3); dirn /= np.linalg.norm(dirn)
            pairs_diff[d].append((REFL[i], shifted_refl(i, d, dirn)))

print("Measured dE00 between two packages (median / 95th pct) and error rates at threshold T")
for method in ("raw", "card"):
    for same_frame in (False, True):
        tag = f"{'phone as-is' if method=='raw' else 'card-corrected'}, {'same photo' if same_frame else 'separate photos'}"
        same_d, diff_d = [], {d: [] for d in pairs_diff}
        for t in range(TRIALS):
            ill = ILL[LIGHTS[t % len(LIGHTS)]]
            r = pairs_same[BASE[t % len(BASE)]]
            same_d.append(measure((jitter(r), jitter(r)), ill, same_frame, method))
            for d in pairs_diff:
                a, b = pairs_diff[d][t % len(pairs_diff[d])]
                diff_d[d].append(measure((jitter(a), jitter(b)), ill, same_frame, method))
        same_d = np.array(same_d)
        print(f"\n  {tag}")
        print(f"    same substance:       {np.median(same_d):4.1f} / {np.percentile(same_d,95):4.1f}")
        for d in diff_d:
            x = np.array(diff_d[d]); print(f"    truly {d:2d} dE00 apart:  {np.median(x):4.1f} / {np.percentile(x,95):4.1f}")
        for T in (3, 5):
            fd = 100 * np.mean(same_d >= T)
            fi = {d: 100 * np.mean(np.array(diff_d[d]) < T) for d in diff_d}
            print(f"    T={T}: same called different {fd:5.1f}% | different called identical: "
                  + ", ".join(f"{d} apart {fi[d]:5.1f}%" for d in fi))
