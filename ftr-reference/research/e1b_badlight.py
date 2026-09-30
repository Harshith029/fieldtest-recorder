"""E1b: (a) can the card itself tell us the light is bad?  (b) does phone flash fix sodium light?"""
import numpy as np
from sim import *

TRIALS = 200
CARD_LAB_D65 = lab(xyz(CARD, D65))

print("(a) Card self-check: mean dE00 of the 24 card patches AFTER correction (fit residual)")
for name, ill in ILL.items():
    res = []
    for _ in range(TRIALS):
        cond = random_conditions()
        v = phone_capture(CARD, ill, cond, 0.004)
        corr = fit_card_correction(v, "grey+3x3")
        res.append(np.mean(de(corrected_lab(corr, v), CARD_LAB_D65)))
    res = np.array(res)
    print(f"  {name:28s} median {np.median(res):4.1f}  5th pct {np.percentile(res,5):4.1f}  95th pct {np.percentile(res,95):4.1f}")

print("\n(b) Sodium street lamp + phone flash (LED-B3). ratio = flash light / street light at the sample")
SOD, LED = ILL["Sodium street lamp (HP1)"], ILL["White LED torch (LED-B3)"]
SOD_n, LED_n = SOD / np.sum(SOD * CMF[:, 1]), LED / np.sum(LED * CMF[:, 1])


def run(ill_fn, label, diff=False):
    errs = []
    for _ in range(TRIALS):
        cond = random_conditions()
        if not diff:
            ill = ill_fn()
            v_card, v_obj = phone_capture(CARD, ill, cond, 0.004), phone_capture(REFL, ill, cond, 0.004)
        else:
            # flash/no-flash: two frames with locked exposure; subtract ambient in linear raw
            r = ill_fn()
            both, amb = SOD_n + r * LED_n, SOD_n
            cond_lin = dict(cond, tone_gamma=1.0, sat=1.0)  # app uses locked, unprocessed capture
            def lin_raw(refl, ill):
                raw = refl @ (ill[:, None] * CAM)
                return raw + rng.normal(0, 1, raw.shape) * 0.004 * np.sqrt(np.clip(raw, 0, None) + 0.05)
            scale = (CARD[WHITE_IDX] @ (both[:, None] * CAM)).max()
            card = (lin_raw(CARD, both) - lin_raw(CARD, amb)) / scale
            obj = (lin_raw(REFL, both) - lin_raw(REFL, amb)) / scale
            wb = 1 / card[WHITE_IDX]
            to_srgb = lambda x: np.round(srgb_encode(np.clip((x * wb) @ CAM_CCM, 0, 1)) * 255) / 255
            v_card, v_obj = to_srgb(card), to_srgb(obj)
        corr = fit_card_correction(v_card, "grey+3x3")
        errs.append(de(corrected_lab(corr, v_obj), TRUE_LAB))
    e = np.concatenate(errs)
    print(f"  {label:44s} median {np.median(e):4.1f}  95th pct {np.percentile(e,95):5.1f}")


run(lambda: SOD, "street lamp only")
for r in (0.5, 1, 2, 4):
    run(lambda r=r: SOD_n + r * LED_n, f"street lamp + flash, ratio {r}")
for r in (0.5, 1, 2):
    run(lambda r=r: r, f"flash/no-flash subtraction, ratio {r}", diff=True)
