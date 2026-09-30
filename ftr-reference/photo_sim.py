"""Photo simulator: renders realistic phone photos of the FieldTest Recorder card with two reaction wells.

Spectral model: reflectance x illuminant x real camera sensitivities (Nikon 5100, NPL data) -> uneven light,
optional glare, perspective/rotation/scale, blur, sensor noise, phone white balance/tone/saturation, JPEG.
"""
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).parent / "research"))
import sim  # noqa: E402
import colour_engine as ce  # noqa: E402

rng = np.random.default_rng(2026)


def reseed(seed):
    global rng
    rng = np.random.default_rng(seed)


# label map of the flat card: 0 white card, 1 black marker ink, 2..25 patches, 26/27 wells
LABELS = np.zeros((ce.CARD_H, ce.CARD_W), np.uint8)
for mid, (x, y) in ce.MARKERS.items():
    m = cv2.aruco.generateImageMarker(ce.ARUCO, mid, ce.MARKER)
    LABELS[y:y + ce.MARKER, x:x + ce.MARKER] = np.where(m < 128, 1, 0)
for i in range(24):
    x, y, w, h = ce.patch_rect(i)
    LABELS[y:y + h, x:x + w] = 2 + i
yy, xx = np.mgrid[0:ce.CARD_H, 0:ce.CARD_W]
for k, (cx, cy) in enumerate(ce.WELLS.values()):
    LABELS[(xx - cx) ** 2 + (yy - cy) ** 2 <= ce.WELL_R ** 2] = 26 + k
WHITE_REFL = sim.CARD[sim.WHITE_IDX] * 0.97
BLACK_REFL = np.full_like(WHITE_REFL, 0.04)


def render(ill, well_refl, cond, glare_on, noise, return_raw=False):
    """Returns (jpeg_rgb_uint8, blur_sigma) or, with return_raw, also the RAW-like linear camera image:
    demosaiced camera RGB after exposure, noise and sensor saturation at 1.0, quantised to 12 bits,
    before any colour matrix, gamut clipping, tone curve or JPEG (what Camera2 RAW/linear capture gives)."""
    refl = np.vstack([WHITE_REFL, BLACK_REFL, sim.CARD, well_refl])           # 28 reflectances
    white = sim.CARD[sim.WHITE_IDX] @ (ill[:, None] * sim.CAM)
    raw_lut = refl @ (ill[:, None] * sim.CAM) / white.max() * cond["exposure"]
    raw = raw_lut[LABELS].astype(np.float32)
    # uneven lighting across the card
    cx, cy = rng.uniform(0, ce.CARD_W), rng.uniform(0, ce.CARD_H)
    s = rng.uniform(0, 0.25)
    shade = 1 - s * (((xx - cx) ** 2 + (yy - cy) ** 2) / (ce.CARD_W ** 2 + ce.CARD_H ** 2))
    raw *= shade[..., None].astype(np.float32)
    if glare_on:
        gx, gy = list(ce.WELLS.values())[rng.integers(2)]
        g = np.exp(-(((xx - gx - rng.normal(0, 15)) ** 2 + (yy - gy - rng.normal(0, 15)) ** 2) / (2 * rng.uniform(15, 45) ** 2)))
        raw += (g[..., None] * rng.uniform(0.5, 2.0) * (white / white.max())).astype(np.float32)
    # place card in a larger scene with perspective, rotation, scale
    Wc, Hc = 1600, 1300
    scene = rng.uniform(0.02, 0.25, (Hc, Wc, 1)).astype(np.float32) * np.array([1, 0.9, 0.8], np.float32)
    src = np.float32([[0, 0], [ce.CARD_W, 0], [ce.CARD_W, ce.CARD_H], [0, ce.CARD_H]])
    scale = rng.uniform(0.65, 0.9)       # viewfinder guide keeps the whole card in frame
    ang = np.deg2rad(rng.uniform(-20, 20))
    R = np.array([[np.cos(ang), -np.sin(ang)], [np.sin(ang), np.cos(ang)]])
    c = src.mean(0)
    dst = (src - c) @ R.T * scale + np.array([Wc / 2, Hc / 2])
    dst += rng.normal(0, 40, dst.shape)                                         # perspective tilt
    H = cv2.getPerspectiveTransform(src, dst.astype(np.float32))
    warped = cv2.warpPerspective(raw, H, (Wc, Hc), flags=cv2.INTER_LINEAR, borderValue=(-1, -1, -1))
    mask = warped[..., 0] < 0
    warped[mask] = scene[mask] if scene.shape[-1] == 3 else np.repeat(scene, 3, -1)[mask]
    sigma = rng.uniform(0, 2.5)
    if sigma > 0.3:
        warped = cv2.GaussianBlur(warped, (0, 0), sigma)
    warped = warped + rng.normal(0, 1, warped.shape).astype(np.float32) * noise * np.sqrt(np.clip(warped, 0, None) + 0.05)
    # phone processing
    gains = (white / white.max()) ** (-cond["awb_alpha"]) * cond["awb_err"]
    lin = (warped.reshape(-1, 3) * gains) @ sim.CAM_CCM
    lin = np.clip(lin, 0, 1) ** cond["tone_gamma"]
    lum = lin @ np.array([0.2126, 0.7152, 0.0722])
    lin = lum[:, None] + (lin - lum[:, None]) * cond["sat"]
    img = (np.clip(sim.srgb_encode(lin), 0, 1) * 255 + 0.5).astype(np.uint8).reshape(Hc, Wc, 3)
    ok, buf = cv2.imencode(".jpg", cv2.cvtColor(img, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, int(rng.integers(70, 96))])
    jpeg = cv2.cvtColor(cv2.imdecode(buf, cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB)
    if return_raw:
        raw12 = np.round(np.clip(warped, 0, 1) * 4095) / 4095
        return jpeg, sigma, raw12.astype(np.float32)
    return jpeg, sigma


def jitter(refl):
    return np.clip(refl * (1 + rng.normal(0, 0.02, refl.shape)), 0, 1)


