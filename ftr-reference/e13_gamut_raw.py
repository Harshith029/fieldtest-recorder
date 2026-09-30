"""E13: are some published reaction colours unmeasurable through a phone JPEG, and does RAW/linear capture fix it?

Finding that prompted it: cobalt thiocyanate blues lie far outside sRGB; engine error ~9 dE00 vs ~2-3 in gamut,
while the spectral model reproduces the reference colours exactly (recovery error 0.00).
Two capture paths on the SAME rendered scenes:
  JPEG   phone processing -> sRGB (clipped) -> card correction           (current engine)
  RAW    linear camera RGB (12-bit, unclipped gamut) -> 3x3 fit from the 24 patches straight to XYZ
Metric: median / 95th dE00 between measured and reference colour, split in-gamut vs out-of-gamut,
and colour-group correctness with the demo rule profiles.
"""
import sys
import warnings
from collections import defaultdict
from pathlib import Path

import colour
import cv2
import numpy as np

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).parent / "research"))
import colour_engine as ce  # noqa: E402
import kit_profile as kp  # noqa: E402
import nij_colours as nc  # noqa: E402
import photo_sim as ps  # noqa: E402
import sim  # noqa: E402
import build_profiles as bp  # noqa: E402
from stats import ci  # noqa: E402

N = int(sys.argv[1]) if len(sys.argv) > 1 else 120
ps.reseed(1313)
CARD_XYZ_D65 = sim.xyz(sim.CARD, sim.D65)
LIGHTS = [l for l in sim.ILL if "Sodium" not in l]


def gamut_excess(L):
    rgb = colour.XYZ_to_sRGB(colour.Lab_to_XYZ(L, sim.WP))
    return float(max(0, -rgb.min(), rgb.max() - 1))


def read_linear(jpeg, raw):
    """Locate the card on the JPEG preview, then measure on the linear RAW image."""
    params = cv2.aruco.DetectorParameters(); params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    corners, ids, _ = cv2.aruco.ArucoDetector(ce.ARUCO, params).detectMarkers(cv2.cvtColor(jpeg, cv2.COLOR_RGB2GRAY))
    if ids is None:
        return None
    found = {int(i): c.reshape(4, 2) for i, c in zip(ids.flatten(), corners) if int(i) in ce.MARKERS}
    if len(found) < ce.MIN_MARKERS:
        return None
    H, _ = cv2.findHomography(np.concatenate([found[m] for m in sorted(found)]),
                              np.concatenate([ce.marker_corners_canonical(m) for m in sorted(found)]), cv2.RANSAC, 3.0)
    card = cv2.warpPerspective(raw, H, (ce.CARD_W, ce.CARD_H), flags=cv2.INTER_AREA)
    P = np.array([np.median(card[y + h // 4:y + 3 * h // 4, x + w // 4:x + 3 * w // 4].reshape(-1, 3), 0)
                  for x, y, w, h in (ce.patch_rect(i) for i in range(24))])
    M, *_ = np.linalg.lstsq(P, CARD_XYZ_D65, rcond=None)
    labs = []
    for cx, cy in ce.WELLS.values():
        m = (ps.xx - cx) ** 2 + (ps.yy - cy) ** 2 <= (0.6 * ce.WELL_R) ** 2
        px = card[m]
        lum = px.sum(1)
        px = px[lum <= np.percentile(lum, 50)]
        labs.append(sim.lab(np.median(px, 0) @ M))
    return labs


profiles = {p.reagent: p for p in bp.build(write=False).values() if p.decision["type"] == "rule"}
for reagent in ("Cobalt thiocyanate", "Mecke", "Marquis", "Simon's"):
    ref = nc.reference(reagent)
    refl = {i: nc.reflectance(r["lab"]) for i, r in enumerate(ref)}
    grp = profiles[reagent].positive_group()
    err = {"JPEG": defaultdict(list), "RAW": defaultdict(list)}
    correct = {"JPEG": [0, 0, 0], "RAW": [0, 0, 0]}          # correct, wrong, inconclusive
    for n in range(N):
        light = LIGHTS[n % len(LIGHTS)]
        pick = [int(ps.rng.integers(0, len(ref))) for _ in range(2)]
        wells = np.vstack([ps.jitter(refl[i]) for i in pick])
        jpeg, _, raw = ps.render(sim.ILL[light], wells, sim.random_conditions(), glare_on=False, noise=0.01, return_raw=True)
        res = ce.read_capture(jpeg, profiles[reagent])
        lin = read_linear(jpeg, raw)
        if not res.accepted or lin is None:
            continue
        for w, L_raw, i in zip(res.wells, lin, pick):
            g = "out-of-gamut" if gamut_excess(ref[i]["lab"]) > 0.02 else "in-gamut"
            truth = "positive" if grp[i] else "negative"
            for path, L in (("JPEG", np.array(w.lab) if w.lab else None), ("RAW", L_raw)):
                if L is None:
                    continue
                err[path][g].append(float(sim.de(L, ref[i]["lab"])))
                out, _, _ = profiles[reagent].classify(L)
                correct[path][0 if out == truth else (2 if out == "inconclusive" else 1)] += 1
    print(f"== {reagent}")
    for path in ("JPEG", "RAW"):
        parts = []
        for g in ("in-gamut", "out-of-gamut"):
            e = np.array(err[path][g])
            parts.append(f"{g}: {np.median(e):4.1f}/{np.percentile(e, 95):5.1f} (n={len(e)})" if len(e) else f"{g}: -")
        c, w, i = correct[path]; t = c + w + i
        lo, hi = ci(w, t)
        print(f"   {path:4s} error med/95th  " + "   ".join(parts)
              + f"   | correct {100 * c / t:5.1f}%  wrong {100 * w / t:4.1f}% [95% CI {lo:.1f}-{hi:.1f}]  inconcl {100 * i / t:4.1f}%")
