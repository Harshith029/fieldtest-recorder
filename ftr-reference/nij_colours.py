"""Reference colours from NIJ Standard-0604.01 Table 1 (Munsell, Illuminant C) -> CIELAB (D65, Bradford).

One implementation shared by profile building and experiments.
"""
import csv
import sys
import warnings
from pathlib import Path

import colour
import numpy as np

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).parent / "research"))
import sim  # noqa: E402

CSV = Path(__file__).parent / "docs/research/data/nij0604_table1.csv"
C_WP = colour.CCS_ILLUMINANTS["CIE 1931 2 Degree Standard Observer"]["C"]

# What "positive" means for each reagent in our demonstration profiles (NCB's real kit sheets will replace these)
TARGETS = {
    "Marquis": {"Codeine", "Diacetylmorphine HCl", "Morphine monohydrate", "Oxycodone HCl"},       # opiates
    "Mecke": {"Codeine", "Diacetylmorphine HCl", "Morphine monohydrate", "Hydrocodone tartrate"},  # opiates
    "Simon's": {"d-Methamphetamine HCl", "MDMA HCl"},                                             # secondary amines
    "Cobalt thiocyanate": {"Cocaine HCl"},
    "Duquenois-Levine (modified)": {"THC"},                                                        # cannabis
}
PHASE = {"Duquenois-Levine (modified)": "chloroform"}   # the phase read for the result


def munsell_to_lab(m):
    m = m.strip()
    if m == "Black":
        m = "N1.5"
    m = m.replace("N ", "N").rstrip("/")
    XYZ = colour.xyY_to_XYZ(colour.munsell_colour_to_xyY(m))
    XYZ = colour.chromatic_adaptation(XYZ, colour.xy_to_XYZ(C_WP), colour.xy_to_XYZ(sim.WP),
                                      method="Von Kries", transform="Bradford")
    return colour.XYZ_to_Lab(XYZ, sim.WP)


def reference(reagent):
    """List of dicts: substance, target, lab (float array), munsell, colour_name, phase."""
    out, seen = [], set()
    for r in csv.DictReader(open(CSV, encoding="utf-8")):
        if r["reagent"] != reagent:
            continue
        if reagent in PHASE and r["phase"] not in (PHASE[reagent], "not extracted"):
            continue
        if (r["analyte"], r["munsell"]) in seen:
            continue
        seen.add((r["analyte"], r["munsell"]))
        try:
            L = munsell_to_lab(r["munsell"])
        except Exception:  # noqa: BLE001  notation outside renotation data
            continue
        out.append({"substance": r["analyte"], "target": r["analyte"] in TARGETS[reagent], "lab": np.asarray(L),
                    "munsell": r["munsell"], "colour_name": r["colour_name"], "phase": r["phase"]})
    return out


def reflectance(L):
    X = colour.Lab_to_XYZ(L, sim.WP)
    sd = colour.XYZ_to_sd(X, method="Meng 2015",
                          cmfs=colour.MSDS_CMFS["CIE 1931 2 Degree Standard Observer"].copy().align(sim.SHAPE),
                          illuminant=colour.SDS_ILLUMINANTS["D65"].copy().align(sim.SHAPE))
    return np.clip(sd.values, 0, 1)
