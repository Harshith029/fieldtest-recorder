"""E9: does flash/no-flash night mode survive a HANDHELD phone, and what capture settings does it need?

Under a sodium street lamp, two frames are taken ~0.1 s apart with small hand movement between them
(shift up to ~12 px, rotation up to ~1.5 deg, scale +/-1%): frame A ambient only, frame B ambient + phone flash.
Each frame is rectified with its OWN markers, then B - A isolates the flash-lit colours.
Variants:
  S0  street lamp only, normal capture                          (baseline: expected to be rejected)
  S1  one flash frame, normal phone auto-processing             (flash just added to ambient)
  F1  flash/no-flash, LOCKED exposure + white balance + LINEAR tone (Camera2 manual / RAW-like)
  F2  flash/no-flash, phone AUTO processing per frame           (what a naive app would get)
Metric: dE00 of the well colour vs truth, and correct / wrong / inconclusive with the proxy profile.
"""
import sys
import warnings
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).parent / "research"))
import sim  # noqa: E402
import colour_engine as ce  # noqa: E402
import photo_sim as ps  # noqa: E402

rng = np.random.default_rng(99)
N = int(sys.argv[1]) if len(sys.argv) > 1 else 60
SOD = sim.ILL["Sodium street lamp (HP1)"]; LED = sim.ILL["White LED torch (LED-B3)"]
SOD_n, LED_n = SOD / np.sum(SOD * sim.CMF[:, 1]), LED / np.sum(LED * sim.CMF[:, 1])
CLASSES = {"violet": "positive", "no change": "negative", "yellow": "negative", "orange": "negative",
           "purple-brown": "negative", "brown": "negative", "blue": "negative"}
PROFILE = [(n, c, sim.TRUE_LAB[sim.NAMES.index(n)]) for n, c in CLASSES.items()]
NAMES = list(CLASSES)
Wc, Hc = 1600, 1300


def raw_card(ill, wells, k):
    refl = np.vstack([ps.WHITE_REFL, ps.BLACK_REFL, sim.CARD, wells])
    return (refl @ (ill[:, None] * sim.CAM) * k)[ps.LABELS].astype(np.float32)


def base_h():
    src = np.float32([[0, 0], [ce.CARD_W, 0], [ce.CARD_W, ce.CARD_H], [0, ce.CARD_H]])
    ang = np.deg2rad(rng.uniform(-15, 15)); s = rng.uniform(0.7, 0.85)
    R = np.array([[np.cos(ang), -np.sin(ang)], [np.sin(ang), np.cos(ang)]])
    dst = (src - src.mean(0)) @ R.T * s + np.array([Wc / 2, Hc / 2]) + rng.normal(0, 30, (4, 2))
    return cv2.getPerspectiveTransform(src, dst.astype(np.float32))


def hand_move(H):
    a = np.deg2rad(rng.uniform(-1.5, 1.5)); s = 1 + rng.uniform(-0.01, 0.01)
    t = rng.uniform(-12, 12, 2)
    M = np.array([[s * np.cos(a), -s * np.sin(a), t[0]], [s * np.sin(a), s * np.cos(a), t[1]], [0, 0, 1]])
    return M @ H


def photograph(raw, H, gains, tone=1.0, sat=1.0):
    img = cv2.warpPerspective(raw, H, (Wc, Hc), borderValue=(0.05, 0.05, 0.05))
    img = img + rng.normal(0, 1, img.shape).astype(np.float32) * 0.01 * np.sqrt(np.clip(img, 0, None) + 0.05)
    lin = (img.reshape(-1, 3) * gains) @ sim.CAM_CCM
    lin = np.clip(lin, 0, 1) ** tone
    lum = lin @ np.array([0.2126, 0.7152, 0.0722]); lin = lum[:, None] + (lin - lum[:, None]) * sat
    u8 = (np.clip(sim.srgb_encode(lin), 0, 1) * 255 + 0.5).astype(np.uint8).reshape(Hc, Wc, 3)
    ok, buf = cv2.imencode(".jpg", cv2.cvtColor(u8, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 92])
    return cv2.cvtColor(cv2.imdecode(buf, cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB)


def rectify_linear(img_u8):
    params = cv2.aruco.DetectorParameters(); params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    corners, ids, _ = cv2.aruco.ArucoDetector(ce.ARUCO, params).detectMarkers(cv2.cvtColor(img_u8, cv2.COLOR_RGB2GRAY))
    if ids is None:
        return None
    found = {int(i): c.reshape(4, 2) for i, c in zip(ids.flatten(), corners) if int(i) in ce.MARKERS}
    if len(found) < ce.MIN_MARKERS:
        return None
    Hm, _ = cv2.findHomography(np.concatenate([found[m] for m in sorted(found)]),
                               np.concatenate([ce.marker_corners_canonical(m) for m in sorted(found)]), cv2.RANSAC, 3.0)
    lin = sim.srgb_decode(img_u8.astype(np.float32) / 255.0).astype(np.float32)
    return cv2.warpPerspective(lin, Hm, (ce.CARD_W, ce.CARD_H), flags=cv2.INTER_AREA)


def read_linear_card(card_lin):
    """Run the normal correction/decision on a linear card image (after flash-ambient subtraction)."""
    srgb = sim.srgb_encode(np.clip(card_lin, 0, 1))
    patches = np.array([np.median(srgb[y + h // 4:y + 3 * h // 4, x + w // 4:x + 3 * w // 4].reshape(-1, 3), 0)
                        for x, y, w, h in (ce.patch_rect(i) for i in range(24))])
    corr = ce.fit_correction(patches)
    fit = float(np.mean(sim.de(corr(patches), ce.CARD_LAB_D65)))
    labs = []
    for cx, cy in ce.WELLS.values():
        m = (ps.xx - cx) ** 2 + (ps.yy - cy) ** 2 <= (0.6 * ce.WELL_R) ** 2
        labs.append(corr(np.median(srgb[m], 0)[None])[0])
    return fit, labs


stats = {k: Counter() for k in ("S0", "S1", "F1", "F2")}
errs = {k: [] for k in stats}
for n in range(N):
    ratio = [0.5, 1.0, 2.0][n % 3]
    truth = [NAMES[rng.integers(0, len(NAMES))] for _ in range(2)]
    wells = np.vstack([ps.jitter(sim.REFL[sim.NAMES.index(t)]) for t in truth])
    both = SOD_n + ratio * LED_n
    white_both = sim.CARD[sim.WHITE_IDX] @ (both[:, None] * sim.CAM)
    k = 0.9 / white_both.max()
    rawA, rawB = raw_card(SOD_n, wells, k), raw_card(both, wells, k)
    HA = base_h(); HB = hand_move(HA)
    cond = sim.random_conditions()
    auto = lambda ill_white, c: (ill_white / ill_white.max()) ** (-c["awb_alpha"]) * c["awb_err"]
    white_A = sim.CARD[sim.WHITE_IDX] @ (SOD_n[:, None] * sim.CAM)
    # S0: street lamp only, auto processing (exposure boosted by auto-exposure)
    imgS0 = photograph(rawA / max(rawA.max(), 1e-6) * 0.9, HA, auto(white_A, cond), cond["tone_gamma"], cond["sat"])
    # S1: single flash frame, auto processing
    imgS1 = photograph(rawB, HB, auto(white_both, cond), cond["tone_gamma"], cond["sat"])
    for key, img in (("S0", imgS0), ("S1", imgS1)):
        res = ce.read_capture(img, PROFILE)
        if not res.accepted:
            stats[key]["rejected:" + res.reason] += 2
            continue
        for w, t in zip(res.wells, truth):
            stats[key]["inconclusive" if w.outcome == "inconclusive" else ("correct" if w.outcome == CLASSES[t] else "wrong")] += 1
            if w.lab is not None:
                errs[key].append(float(sim.de(np.array(w.lab), sim.TRUE_LAB[sim.NAMES.index(t)])))
    # F1: locked exposure + locked flash white balance + linear tone, both frames identical settings
    g_lock = 1 / (white_both / white_both.max())
    A1, B1 = photograph(rawA, HA, g_lock), photograph(rawB, HB, g_lock)
    # F2: auto processing chosen independently per frame
    c2 = sim.random_conditions()
    A2 = photograph(rawA / max(rawA.max(), 1e-6) * 0.9, HA, auto(white_A, c2), c2["tone_gamma"], c2["sat"])
    c3 = sim.random_conditions()
    B2 = photograph(rawB, HB, auto(white_both, c3), c3["tone_gamma"], c3["sat"])
    for key, (A, B) in (("F1", (A1, B1)), ("F2", (A2, B2))):
        la, lb = rectify_linear(A), rectify_linear(B)
        if la is None or lb is None:
            stats[key]["rejected:card_not_found"] += 2
            continue
        fit, labs = read_linear_card(np.clip(lb - la, 0, None))
        if fit > ce.MAX_CARD_FIT_DE:
            stats[key]["rejected:bad_light"] += 2
            continue
        for L, t in zip(labs, truth):
            out, *_ = ce.classify(L, PROFILE)
            stats[key]["inconclusive" if out == "inconclusive" else ("correct" if out == CLASSES[t] else "wrong")] += 1
            errs[key].append(float(sim.de(L, sim.TRUE_LAB[sim.NAMES.index(t)])))

desc = {"S0": "street lamp only (normal capture)", "S1": "one flash frame (auto processing)",
        "F1": "flash/no-flash, LOCKED + LINEAR capture", "F2": "flash/no-flash, AUTO processing"}
print(f"{N} handheld trials under a sodium street lamp (flash:lamp ratios 0.5, 1, 2)\n")
print(f"{'variant':42s} {'colour error dE00 (med / 95th)':>30s} {'correct':>8s} {'wrong':>6s} {'inconcl':>8s} {'rejected':>9s}")
for k in stats:
    s = stats[k]; tot = sum(s.values())
    e = np.array(errs[k])
    et = f"{np.median(e):5.1f} / {np.percentile(e, 95):5.1f}" if len(e) else "      -"
    rej = sum(v for kk, v in s.items() if kk.startswith("rejected"))
    p = lambda x: f"{100 * x / tot:5.1f}%"
    print(f"{desc[k]:42s} {et:>30s} {p(s['correct']):>8s} {p(s['wrong']):>6s} {p(s['inconclusive']):>8s} {p(rej):>9s}")
