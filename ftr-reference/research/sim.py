"""Spectral simulation of phone-camera colour readings for field drug-test colours.

Models: reflectance x illuminant x real camera sensitivities (Nikon 5100, NPL data),
imperfect auto white balance, phone tone/saturation processing, sensor noise, 8-bit JPEG.
Compares reading the phone's sRGB directly vs correcting with a 24-patch reference card.
All reaction colours are ILLUSTRATIVE, not real NCB kit colours.
"""
import warnings
import numpy as np
import colour

warnings.filterwarnings("ignore")
rng = np.random.default_rng(7)
SHAPE = colour.SpectralShape(400, 700, 10)


def arr(sd):
    return sd.copy().align(SHAPE).values


CMF = arr(colour.MSDS_CMFS["CIE 1931 2 Degree Standard Observer"])
CAM = arr(colour.MSDS_CAMERA_SENSITIVITIES["Nikon 5100 (NPL)"])
CAM = np.clip(np.nan_to_num(CAM), 0, None)
ILL = {
    "Daylight (D65)": arr(colour.SDS_ILLUMINANTS["D65"]),
    "Tube light (FL2)": arr(colour.SDS_ILLUMINANTS["FL2"]),
    "White LED torch (LED-B3)": arr(colour.SDS_ILLUMINANTS["LED-B3"]),
    "Incandescent bulb (A)": arr(colour.SDS_ILLUMINANTS["A"]),
    "Sodium street lamp (HP1)": arr(colour.SDS_ILLUMINANTS["HP1"]),
}
D65 = ILL["Daylight (D65)"]
WP = colour.CCS_ILLUMINANTS["CIE 1931 2 Degree Standard Observer"]["D65"]
M_XYZ_TO_RGB = colour.RGB_COLOURSPACES["sRGB"].matrix_XYZ_to_RGB
M_RGB_TO_XYZ = colour.RGB_COLOURSPACES["sRGB"].matrix_RGB_to_XYZ

# 24-patch reference card reflectances (BabelColor average spectra)
CARD = np.array([arr(sd) for sd in colour.SDS_COLOURCHECKERS["BabelColor Average"].values()])
GREY_IDX = [18, 19, 20, 21, 22, 23]
WHITE_IDX = 18


def xyz(refl, ill):
    k = 1.0 / np.sum(ill * CMF[:, 1])
    return k * (refl * ill) @ CMF


def lab(X):
    return colour.XYZ_to_Lab(X, WP)


def de(a, b):
    return colour.delta_E(a, b, method="CIE 2000")


# Illustrative outcome colours (sRGB) recovered to plausible reflectance spectra.
OUTCOMES = {
    "no change": "#ECE7D9", "violet": "#5B2D8E", "purple-brown": "#5E3A4A",
    "blue": "#1F5FBF", "blue-green": "#1F8A8A", "brown": "#7A4B2A",
    "orange": "#D9772B", "red-pink": "#C8406A", "olive": "#7D8B3A", "yellow": "#E3C23A",
}


def recover(hexcol):
    rgb = colour.notation.HEX_to_RGB(hexcol)
    X = colour.sRGB_to_XYZ(rgb)
    sd = colour.XYZ_to_sd(X, method="Meng 2015",
                          cmfs=colour.MSDS_CMFS["CIE 1931 2 Degree Standard Observer"].copy().align(SHAPE),
                          illuminant=colour.SDS_ILLUMINANTS["D65"].copy().align(SHAPE))
    return np.clip(sd.values, 0.0, 1.0)


NAMES = list(OUTCOMES)
REFL = np.array([recover(OUTCOMES[n]) for n in NAMES])
TRUE_LAB = lab(xyz(REFL, D65))
CARD_LIN_D65 = np.clip(xyz(CARD, D65) @ M_XYZ_TO_RGB.T, 0, None)

# Camera "factory" matrix: white-balanced raw -> linear sRGB, fitted once under daylight.
_raw_d65 = CARD @ (D65[:, None] * CAM)
_raw_d65 = _raw_d65 / _raw_d65[WHITE_IDX]
CAM_CCM, *_ = np.linalg.lstsq(_raw_d65, CARD_LIN_D65 / CARD_LIN_D65[WHITE_IDX, 1] * 0.9, rcond=None)


def srgb_encode(x):
    x = np.clip(x, 0, 1)
    return np.where(x <= 0.0031308, 12.92 * x, 1.055 * x ** (1 / 2.4) - 0.055)


def srgb_decode(v):
    return np.where(v <= 0.04045, v / 12.92, ((v + 0.055) / 1.055) ** 2.4)


def phone_capture(refl, ill, cond, noise):
    """refl: (n,31) -> 8-bit-quantised sRGB in [0,1], using shared capture conditions `cond`."""
    raw = refl @ (ill[:, None] * CAM)
    white = (CARD[WHITE_IDX] @ (ill[:, None] * CAM))
    raw = raw / white.max() * cond["exposure"]
    # shot + read noise after averaging over the reaction region
    raw = raw + rng.normal(0, 1, raw.shape) * noise * np.sqrt(np.clip(raw, 0, None) + 0.05)
    # imperfect AWB: partial adaptation + random error (phones keep some warmth under tungsten)
    gains = (white / white.max()) ** (-cond["awb_alpha"]) * cond["awb_err"]
    lin = (raw * gains) @ CAM_CCM
    # phone "look": tone curve + saturation boost
    g = cond["tone_gamma"]
    lin = np.clip(lin, 0, 1) ** g
    lum = lin @ np.array([0.2126, 0.7152, 0.0722])
    lin = lum[:, None] + (lin - lum[:, None]) * cond["sat"]
    v = srgb_encode(lin)
    return np.round(v * 255) / 255


def random_conditions():
    return {
        "exposure": rng.uniform(0.7, 1.0),
        "awb_alpha": rng.uniform(0.6, 1.0),
        "awb_err": rng.normal(1, 0.04, 3),
        "tone_gamma": rng.uniform(0.85, 1.1),
        "sat": rng.uniform(1.0, 1.3),
    }


def lab_from_srgb(v):
    return lab(srgb_decode(v) @ M_RGB_TO_XYZ.T)


def fit_card_correction(card_srgb, method):
    lin = srgb_decode(card_srgb)
    tgt = CARD_LIN_D65
    if method == "3x3":
        M, *_ = np.linalg.lstsq(lin, tgt, rcond=None)
        return lambda x: srgb_decode(x) @ M
    if method == "grey+3x3":
        # per-channel tone linearisation from the 6 neutral patches, then 3x3
        luts = []
        for c in range(3):
            xs = lin[GREY_IDX, c]
            ys = tgt[GREY_IDX, 1]
            o = np.argsort(xs)
            luts.append((xs[o], ys[o]))

        def tone(l):
            out = np.empty_like(l)
            for c in range(3):
                xs, ys = luts[c]
                out[:, c] = np.interp(l[:, c], xs, ys, left=None, right=None)
                # linear extrapolation beyond the grey ramp
                lo = l[:, c] < xs[0]
                hi = l[:, c] > xs[-1]
                s0 = (ys[1] - ys[0]) / max(xs[1] - xs[0], 1e-6)
                s1 = (ys[-1] - ys[-2]) / max(xs[-1] - xs[-2], 1e-6)
                out[lo, c] = ys[0] + (l[lo, c] - xs[0]) * s0
                out[hi, c] = ys[-1] + (l[hi, c] - xs[-1]) * s1
            return out
        L = tone(lin)
        M, *_ = np.linalg.lstsq(L, tgt, rcond=None)
        return lambda x: tone(srgb_decode(x)) @ M
    raise ValueError(method)


def corrected_lab(corr, v):
    return lab(np.clip(corr(v), 0, None) @ M_RGB_TO_XYZ.T)
