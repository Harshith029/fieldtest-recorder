"""Colour bands for the range decision model (build time only; the phone just stores and compares points).

A kit chart states a result as "colour in the range X to Y". Real readings also move with how much sample
went in and how pure it is. We model both with Beer-Lambert in reflectance space, relative to the reagent blank:
    absorbance A(t)   = (1 - t) * A_X + t * A_Y          t in [0, 1]   (along the chart range)
    reflectance R     = R_blank * exp(-k * A(t))         k in [K_LO, K_HI] (0.5-1.6x the chart's amount)
and store the CIELAB (D65) of each (t, k) as signed integers. Spectra come from the same reflectance recovery
used by the simulator (Meng 2015); this is documented physics, not a learned model, and anyone can recompute it.
"""
from __future__ import annotations

import numpy as np

import nij_colours
import sim

K_LO, K_HI = 0.5, 1.6
KS = np.round(np.arange(K_LO, K_HI + 1e-9, 0.1), 2)
TS = np.linspace(0, 1, 6)
WHITE = np.array([95.0, 0.0, 0.0])          # clear reagent on a white spot plate


_CACHE: dict = {}


def _refl(L):
    key = tuple(np.round(np.asarray(L, float), 3))
    if key not in _CACHE:
        _CACHE[key] = np.clip(nij_colours.reflectance(np.asarray(key, float)), 1e-4, 1.0)
    return _CACHE[key]


def band_points(lab_from, lab_to=None, blank=WHITE, ks=KS, ts=TS):
    lab_to = lab_from if lab_to is None else lab_to
    Rb = _refl(blank)
    Ax, Ay = -np.log(_refl(lab_from) / Rb), -np.log(_refl(lab_to) / Rb)
    pts = []
    for t in (ts if not np.allclose(lab_from, lab_to) else [0.0]):
        A = (1 - t) * Ax + t * Ay
        for k in ks:
            pts.append(sim.lab(sim.xyz(np.clip(Rb * np.exp(-k * A), 0, 1), sim.D65)))
    pts = np.round(np.array(pts) * 100).astype(int)
    return np.unique(pts, axis=0).tolist()


def amount_series(lab_true, k, blank=WHITE):
    """Colour of the same reaction at k x the reference amount (the test-data generator of E17, model A)."""
    Rb = _refl(blank)
    return sim.lab(sim.xyz(np.clip(Rb * (_refl(lab_true) / Rb) ** k, 0, 1), sim.D65))


def coverage_series(lab_true, f, blank=WHITE):
    """Model B for E17 (different physics): only a fraction f of the well reacts; reflectances mix linearly."""
    Rb = _refl(blank)
    return sim.lab(sim.xyz(np.clip(f * _refl(lab_true) + (1 - f) * Rb, 0, 1), sim.D65))
