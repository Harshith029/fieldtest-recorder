"""E1: How wrong is a phone's colour reading under field lighting, with and without the card?"""
import numpy as np
from sim import *

# sanity: spectral recovery reproduces the target colours under D65
rec = lab(xyz(REFL, D65))
tgt = lab(colour.sRGB_to_XYZ(np.array([colour.notation.HEX_to_RGB(OUTCOMES[n]) for n in NAMES])))
print("recovery check, max dE00 vs target sRGB:", round(float(de(rec, tgt).max()), 2))

TRIALS = 300
print(f"\nColour error of 10 outcome colours, dE00 (median / 95th pct), {TRIALS} random captures per light")
print(f"{'light':28s} {'phone as-is':>14s} {'card 3x3':>12s} {'card grey+3x3':>15s}")
summary = {}
for name, ill in ILL.items():
    noise = 0.004 if "Sodium" not in name else 0.006
    errs = {"raw": [], "3x3": [], "grey+3x3": []}
    for _ in range(TRIALS):
        cond = random_conditions()
        v_card = phone_capture(CARD, ill, cond, noise)
        v_obj = phone_capture(REFL, ill, cond, noise)
        errs["raw"].append(de(lab_from_srgb(v_obj), TRUE_LAB))
        for m in ("3x3", "grey+3x3"):
            corr = fit_card_correction(v_card, m)
            errs[m].append(de(corrected_lab(corr, v_obj), TRUE_LAB))
    row = {k: np.concatenate(v) for k, v in errs.items()}
    summary[name] = row
    f = lambda a: f"{np.median(a):5.1f} / {np.percentile(a, 95):5.1f}"
    print(f"{name:28s} {f(row['raw']):>14s} {f(row['3x3']):>12s} {f(row['grey+3x3']):>15s}")

# classification: nearest illustrative outcome with a margin rule
print("\nClassification of the 10 outcomes (card grey+3x3 correction), margin rule on dE00")
for M in (0, 3, 5):
    print(f"  margin >= {M}:")
    for name, ill in ILL.items():
        noise = 0.004 if "Sodium" not in name else 0.006
        right = wrong = inconc = 0
        for _ in range(150):
            cond = random_conditions()
            corr = fit_card_correction(phone_capture(CARD, ill, cond, noise), "grey+3x3")
            L = corrected_lab(corr, phone_capture(REFL, ill, cond, noise))
            for i in range(len(NAMES)):
                d = de(np.repeat(L[i:i + 1], len(NAMES), 0), TRUE_LAB)
                o = np.argsort(d)
                if d[o[1]] - d[o[0]] < M:
                    inconc += 1
                elif o[0] == i:
                    right += 1
                else:
                    wrong += 1
        n = right + wrong + inconc
        print(f"    {name:28s} correct {100*right/n:5.1f}%  wrong {100*wrong/n:5.1f}%  inconclusive {100*inconc/n:5.1f}%")

# which colours suffer most under sodium light even after correction
name = "Sodium street lamp (HP1)"
per = summary[name]["grey+3x3"].reshape(-1, len(NAMES))
print(f"\nWorst colours under {name} after correction (median dE00):")
for i in np.argsort(-np.median(per, 0))[:5]:
    print(f"  {NAMES[i]:14s} {np.median(per[:, i]):5.1f}")
