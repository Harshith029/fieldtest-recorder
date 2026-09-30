"""FieldTest Recorder — reference colour engine (the spec the Kotlin colour-engine must reproduce).

Pipeline: ArUco markers -> homography -> rectified card -> quality gates (blur, card fit error, glare)
-> grey-ramp linearisation + 3x3 correction fitted on the 24 patches -> CIELAB (D65) -> CIEDE2000
-> positive / negative / inconclusive with a reason code. Deterministic; no learned model.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).parent / "research"))
from sim import CARD, CARD_LIN_D65, GREY_IDX, M_RGB_TO_XYZ, WP, de, lab, srgb_decode  # noqa: E402

# ---- canonical card layout (units = pixels of the rectified 1000 x 700 card) ----
CARD_W, CARD_H = 1000, 700
MARKER = 120                                                             # was 80: too small under blur (E4 debug)
MARKERS = {0: (15, 15), 1: (865, 15), 2: (15, 565), 3: (865, 565)}      # top-left corners
MIN_MARKERS = 3                                                          # 3 markers = 12 points, enough for a homography
PATCH, GAP, PATCH_ORIGIN = 70, 10, (150, 170)                            # 6 x 4 grid
PATCH_EXTENT = (PATCH_ORIGIN[0], PATCH_ORIGIN[1], PATCH_ORIGIN[0] + 6 * (PATCH + GAP) - GAP,
                PATCH_ORIGIN[1] + 4 * (PATCH + GAP) - GAP)
WELLS = {"W1": (760, 250), "W2": (760, 430)}                             # centres
WELL_R = 60
ARUCO = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)

CARD_LAB_D65 = lab(CARD_LIN_D65 @ M_RGB_TO_XYZ.T)

# gates (initial values; to be tuned on real captures)
MAX_CARD_FIT_DE = 4.0
MIN_SHARPNESS = 5.0          # colour uses region medians, so only extreme blur is rejected (E4 tuning)
MAX_GLARE_FRACTION = 0.30
MAX_NEAREST_DE = 15.0
MIN_MARGIN_DE = 3.0


def patch_rect(i):
    r, c = divmod(i, 6)
    x0 = PATCH_ORIGIN[0] + c * (PATCH + GAP)
    y0 = PATCH_ORIGIN[1] + r * (PATCH + GAP)
    return x0, y0, PATCH, PATCH


def marker_corners_canonical(mid):
    x, y = MARKERS[mid]
    return np.array([[x, y], [x + MARKER, y], [x + MARKER, y + MARKER], [x, y + MARKER]], np.float32)


@dataclass
class WellReading:
    well: str
    outcome: str          # positive | negative | inconclusive
    reason: str
    lab: tuple | None
    nearest: str | None
    de_nearest: float | None
    margin: float | None
    consistent_with: list | None = None      # substances whose documented colour matches the reading
    profile: str | None = None               # profile id@version used for the decision


@dataclass
class CaptureResult:
    accepted: bool
    reason: str
    card_fit_de: float | None
    sharpness: float | None
    wells: list


def rectify(img_rgb):
    params = cv2.aruco.DetectorParameters()
    params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    detector = cv2.aruco.ArucoDetector(ARUCO, params)
    corners, ids, _ = detector.detectMarkers(cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY))
    if ids is None:
        return None
    found = {int(i): c.reshape(4, 2) for i, c in zip(ids.flatten(), corners) if int(i) in MARKERS}
    if len(found) < MIN_MARKERS:
        return None
    src = np.concatenate([found[m] for m in sorted(found)])
    dst = np.concatenate([marker_corners_canonical(m) for m in sorted(found)])
    H, _ = cv2.findHomography(src, dst, cv2.RANSAC, 3.0)
    return cv2.warpPerspective(img_rgb, H, (CARD_W, CARD_H), flags=cv2.INTER_AREA)


def fit_correction(card_srgb):
    lin = srgb_decode(card_srgb)
    tgt = CARD_LIN_D65
    luts = []
    for c in range(3):
        xs, ys = lin[GREY_IDX, c], tgt[GREY_IDX, 1]
        o = np.argsort(xs)
        luts.append((xs[o], ys[o]))

    def tone(l):
        out = np.empty_like(l)
        for c in range(3):
            xs, ys = luts[c]
            out[:, c] = np.interp(l[:, c], xs, ys)
            s0 = (ys[1] - ys[0]) / max(xs[1] - xs[0], 1e-6)
            s1 = (ys[-1] - ys[-2]) / max(xs[-1] - xs[-2], 1e-6)
            lo, hi = l[:, c] < xs[0], l[:, c] > xs[-1]
            out[lo, c] = ys[0] + (l[lo, c] - xs[0]) * s0
            out[hi, c] = ys[-1] + (l[hi, c] - xs[-1]) * s1
        return out

    M, *_ = np.linalg.lstsq(tone(lin), tgt, rcond=None)
    return lambda srgb: lab(np.clip(tone(srgb_decode(srgb)) @ M, 0, None) @ M_RGB_TO_XYZ.T)


def classify(L, profile):
    """profile: list of (name, class, Lab)."""
    d = np.array([float(de(L, p[2])) for p in profile])
    i = int(np.argmin(d))
    name, cls = profile[i][0], profile[i][1]
    other = [d[j] for j, p in enumerate(profile) if p[1] != cls]
    margin = (min(other) - d[i]) if other else 99.0
    if d[i] > MAX_NEAREST_DE:
        return "inconclusive", "unknown_colour", name, d[i], margin
    if margin < MIN_MARGIN_DE:
        return "inconclusive", "low_margin", name, d[i], margin
    return cls, "matched_profile", name, d[i], margin


REGION_R = 6.0      # dE00 radius of a colour group (E8 sweep)
REGION_M = 2.0      # required gap between the positive group and other colours (E8 sweep)


def classify_region(L, reference, R=REGION_R, M=REGION_M):
    """Colour-group classifier (replaces substance-nearest `classify`, see E8).

    reference: list of (substance, is_target, Lab) from the kit's documented colour table.
    The positive group is every colour within R of a target substance's reference colour; substances
    that share that colour are reported as 'also consistent with' (known cross-reactants), not as errors.
    Returns (outcome, reason, consistent_with, d_pos, d_other).
    """
    pos_labs = [r[2] for r in reference if r[1]]
    d_pos = min(float(de(L, p)) for p in pos_labs)
    in_pos_group = [r for r in reference if min(float(de(r[2], p)) for p in pos_labs) <= R]
    others = [r for r in reference if r not in in_pos_group]
    d_other = min((float(de(L, r[2])) for r in others), default=99.0)
    consistent = sorted({r[0] for r in reference if float(de(L, r[2])) <= R})
    if d_pos <= R and d_other - d_pos >= M:
        return "positive", "in_positive_colour_group", consistent, d_pos, d_other
    if d_other <= R and d_pos - d_other >= M:
        return "negative", "outside_positive_colour_group", consistent, d_pos, d_other
    if min(d_pos, d_other) > 2 * R:
        return "inconclusive", "unknown_colour", consistent, d_pos, d_other
    return "inconclusive", "between_groups", consistent, d_pos, d_other


CARD_XYZ_D65 = None


def _card_xyz():
    global CARD_XYZ_D65
    if CARD_XYZ_D65 is None:
        from sim import CARD, D65, xyz
        CARD_XYZ_D65 = xyz(CARD, D65)
    return CARD_XYZ_D65


def _homography(img_rgb):
    params = cv2.aruco.DetectorParameters()
    params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    corners, ids, _ = cv2.aruco.ArucoDetector(ARUCO, params).detectMarkers(cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY))
    if ids is None:
        return None
    found = {int(i): c.reshape(4, 2) for i, c in zip(ids.flatten(), corners) if int(i) in MARKERS}
    if len(found) < MIN_MARKERS:
        return None
    H, _ = cv2.findHomography(np.concatenate([found[m] for m in sorted(found)]),
                              np.concatenate([marker_corners_canonical(m) for m in sorted(found)]), cv2.RANSAC, 3.0)
    return H


def read_capture_linear(preview_rgb, raw_linear, profile) -> CaptureResult:
    """RAW / linear capture tier (ADR-13): locate the card on the preview, measure on unclipped linear
    camera RGB, fit a 3x3 from the 24 patches straight to XYZ (no sRGB gamut clipping, no tone curve)."""
    H = _homography(preview_rgb)
    if H is None:
        return CaptureResult(False, "card_not_found", None, None, [])
    card = cv2.warpPerspective(raw_linear, H, (CARD_W, CARD_H), flags=cv2.INTER_AREA)
    P = np.array([np.median(card[y + h // 4:y + 3 * h // 4, x + w // 4:x + 3 * w // 4].reshape(-1, 3), 0)
                  for x, y, w, h in (patch_rect(i) for i in range(24))])
    M, *_ = np.linalg.lstsq(P, _card_xyz(), rcond=None)
    fit_de = float(np.mean(de(lab(P @ M), CARD_LAB_D65)))
    if fit_de > MAX_CARD_FIT_DE:
        return CaptureResult(False, "bad_light", round(fit_de, 2), None, [])
    yy, xx = np.mgrid[0:CARD_H, 0:CARD_W]
    readings = {}
    for wid, (cx, cy) in WELLS.items():
        px = card[(xx - cx) ** 2 + (yy - cy) ** 2 <= (0.6 * WELL_R) ** 2]
        glare = px.max(1) >= 0.98                      # sensor saturation = specular highlight
        if glare.mean() > MAX_GLARE_FRACTION:
            readings[wid] = None
            continue
        keep = px[~glare]
        keep = keep[keep.sum(1) <= np.percentile(keep.sum(1), 50)]
        readings[wid] = lab(np.median(keep, 0) @ M)
    return CaptureResult(True, "ok", round(fit_de, 2), None, judge_wells(readings, profile))


def judge_wells(readings: dict, profile) -> list:
    """Classify every sample well; if the profile names a BLANK well (reagent only, same photo, same light),
    each sample is judged relative to it and the blank itself is reported, not classified."""
    blank_id = (getattr(profile, "layout", None) or {}).get("blank_well")
    blank_L = readings.get(blank_id) if blank_id else None
    tag = f"{profile.profile_id}@v{profile.version}"
    wells = []
    for wid, L in readings.items():
        if wid == blank_id:
            wells.append(WellReading(wid, "blank", "glare" if L is None else "reagent_blank",
                                     None if L is None else tuple(np.round(L, 1)), None, None, None, profile=tag))
            continue
        if L is None:
            wells.append(WellReading(wid, "inconclusive", "glare", None, None, None, None, profile=tag))
            continue
        if blank_id and blank_L is None:
            wells.append(WellReading(wid, "inconclusive", "blank_well_unreadable", tuple(np.round(L, 1)), None, None, None,
                                     profile=tag))
            continue
        outcome, reason, consistent = profile.classify(L, blank_L) if blank_id else profile.classify(L)
        wells.append(WellReading(wid, outcome, reason, tuple(np.round(L, 1)), None, None, None,
                                 consistent_with=consistent, profile=tag))
    return wells


def read_capture(img_rgb, profile) -> CaptureResult:
    card = rectify(img_rgb)
    if card is None:
        return CaptureResult(False, "card_not_found", None, None, [])
    x0, y0, x1, y1 = PATCH_EXTENT
    grey = cv2.cvtColor(card[y0:y1, x0:x1], cv2.COLOR_RGB2GRAY)
    sharp = float(cv2.Laplacian(grey, cv2.CV_64F).var())
    patches = []
    for i in range(24):
        x, y, w, h = patch_rect(i)
        roi = card[y + h // 4:y + 3 * h // 4, x + w // 4:x + 3 * w // 4].reshape(-1, 3)
        patches.append(np.median(roi, 0) / 255.0)
    patches = np.array(patches)
    corr = fit_correction(patches)
    fit_de = float(np.mean(de(corr(patches), CARD_LAB_D65)))
    if sharp < MIN_SHARPNESS:
        return CaptureResult(False, "blurred", fit_de, sharp, [])
    if fit_de > MAX_CARD_FIT_DE:
        return CaptureResult(False, "bad_light", fit_de, sharp, [])
    yy, xx = np.mgrid[0:CARD_H, 0:CARD_W]
    readings = {}
    for wid, (cx, cy) in WELLS.items():
        mask = (xx - cx) ** 2 + (yy - cy) ** 2 <= (0.6 * WELL_R) ** 2
        px = card[mask].astype(float)
        glare = (px.max(1) >= 245) | (px.min(1) >= 235)
        if glare.mean() > MAX_GLARE_FRACTION:
            readings[wid] = None
            continue
        # specular highlights only ever ADD light: estimate the reaction colour from the darker half
        keep = px[~glare]
        lum = keep @ np.array([0.2126, 0.7152, 0.0722])
        keep = keep[lum <= np.percentile(lum, 50)]
        readings[wid] = corr((np.median(keep, 0) / 255.0)[None])[0]
    if hasattr(profile, "classify"):              # signed KitProfile (colour groups / bands, blank-relative)
        return CaptureResult(True, "ok", round(fit_de, 2), round(sharp, 1), judge_wells(readings, profile))
    wells = []                                    # legacy list profile, kept only to reproduce E4
    for wid, L in readings.items():
        if L is None:
            wells.append(WellReading(wid, "inconclusive", "glare", None, None, None, None))
            continue
        outcome, reason, name, dn, mg = classify(L, profile)
        wells.append(WellReading(wid, outcome, reason, tuple(np.round(L, 1)), name, round(dn, 2), round(mg, 2)))
    return CaptureResult(True, "ok", round(fit_de, 2), round(sharp, 1), wells)
