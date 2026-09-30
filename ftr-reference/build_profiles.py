"""Build signed kit profiles (the documented colour standard) and lint them.

For each reagent: a RULE profile (bootstrap: usable before validation data exists) and, where validation
readings exist (results/e8_features_*.csv, simulated for now), a REGION-MAP profile learned offline and frozen.
Signed with a TEST-ONLY profile-authority key; production keys are NCB's, offline, two-person.
"""
import csv
import json
import sys
import warnings
from pathlib import Path

import numpy as np
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from sklearn.ensemble import RandomForestClassifier
from sklearn.neighbors import NearestNeighbors

warnings.filterwarnings("ignore")
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE / "research"))
import kit_profile as kp  # noqa: E402
import nij_colours  # noqa: E402
import record_core as rc  # noqa: E402

OUT = HERE / "profiles"
OUT.mkdir(exist_ok=True)
KEY_FILE = OUT / "TEST_ONLY_profile_authority_key.pem"
FEATURES = {"Marquis": "Marquis", "Mecke": "Mecke", "Simon's": "Simons", "Cobalt thiocyanate": "Cobalt_thiocyanate"}
CONF = 0.8


def authority_key():
    if KEY_FILE.exists():
        return serialization.load_pem_private_key(KEY_FILE.read_bytes(), None)
    k = ec.generate_private_key(ec.SECP256R1())
    KEY_FILE.write_bytes(k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                         serialization.NoEncryption()))
    (OUT / "TEST_ONLY_profile_authority_pub.pem").write_text(rc.pub_pem(k))
    return k


def reference_x100(ref):
    return [{"substance": r["substance"], "target": bool(r["target"]), "lab_x100": [int(round(v * 100)) for v in r["lab"]],
             "munsell": r["munsell"], "colour_name": r["colour_name"], "phase": r["phase"]} for r in ref]


OUTLIER_DE = 20.0      # a training reading this far from its substance's documented colour is glare/mislabel
MIN_NEIGHBOURS = 3     # a map cell needs 3 training readings within `pad`, so one stray reading cannot make a zone


def region_map(features_key, reagent, exclude_light=None, pad=6):
    rows = list(csv.reader(open(HERE / "results" / f"e8_features_{features_key}.csv", encoding="utf-8")))
    rows = [r for r in rows if r[0] != exclude_light]
    ref = {r["substance"]: r["lab"] for r in nij_colours.reference(reagent)}
    lab_all = np.array([[float(v) for v in r[-3:]] for r in rows])
    keep = [i for i, r in enumerate(rows) if r[1] not in ref or float(kp.de(lab_all[i], ref[r[1]])) <= OUTLIER_DE]
    dropped = len(rows) - len(keep)
    rows, lab = [rows[i] for i in keep], lab_all[keep]
    y = np.array([1 if r[2] == "positive" else 0 for r in rows])
    m = RandomForestClassifier(n_estimators=300, random_state=0, n_jobs=-1).fit(lab, y)
    lo = np.floor(lab.min(0) - pad).astype(int); hi = np.ceil(lab.max(0) + pad).astype(int)
    axes = [np.arange(lo[i], hi[i] + 1) for i in range(3)]
    G = np.stack(np.meshgrid(*axes, indexing="ij"), -1).reshape(-1, 3).astype(float)
    p = m.predict_proba(G)
    cls = m.classes_[p.argmax(1)].astype(np.int8)
    cls[p.max(1) < CONF] = -1
    d, _ = NearestNeighbors(n_neighbors=MIN_NEIGHBOURS).fit(lab).kneighbors(G)
    cls[d[:, -1] > pad] = -1
    return kp.region_map_decision(cls.reshape([len(a) for a in axes]), lo,
                                  trained_on=f"simulated validation readings e8_features_{features_key} "
                                             f"(n={len(rows)}, {dropped} outliers removed)",
                                  conf_x100=int(CONF * 100))


def band_decision(ref, positive_group):
    """Range model built from single NIJ chips: each substance's chip at 0.5-1.6x amount (bands.py)."""
    import bands
    return {"type": "band", "tol_x100": 500, "margin_x100": 200, "source": "NIJ Std-0604.01 chips + Beer-Lambert amount",
            "outcomes": [{"name": r["substance"], "substances": [r["substance"]], "positive": bool(g),
                          "points_x100": bands.band_points(np.array(r["lab_x100"]) / 100)} for r, g in zip(ref, positive_group)]}


def build(write=True):
    key = authority_key()
    profiles = {}
    for reagent in nij_colours.TARGETS:
        ref = reference_x100(nij_colours.reference(reagent))
        slug = reagent.split(" (")[0].replace("'", "").replace(" ", "-").lower()
        rule = kp.KitProfile(f"demo-{slug}-rule", 1, reagent, ref, {"type": "rule", "r_x100": 600, "m_x100": 200}).sign(key)
        profiles[rule.profile_id] = rule
        issues = kp.lint(rule)
        if reagent in FEATURES:
            rm = kp.KitProfile(f"demo-{slug}-map", 2, reagent, ref, region_map(FEATURES[reagent], reagent)).sign(key)
            profiles[rm.profile_id] = rm
        bd = kp.KitProfile(f"demo-{slug}-band", 1, reagent, ref, band_decision(ref, rule.positive_group())).sign(key)
        profiles[bd.profile_id] = bd
        if write:
            for p in profiles.values():
                (OUT / f"{p.profile_id}.json").write_text(json.dumps(p.to_dict(), indent=1))
            with open(OUT / f"demo-{slug}.lint.txt", "w", encoding="utf-8") as f:
                f.write(f"Profile checker report: {reagent}\n")
                for lvl, msg in issues:
                    f.write(f"{lvl:5s} {msg}\n")
        n_err = sum(1 for l, _ in issues if l == "ERROR")
        n_warn = sum(1 for l, m in issues if l == "WARN" and "sRGB" not in m)
        n_gamut = sum(1 for l, m in issues if "sRGB" in m)
        n_info = sum(1 for l, _ in issues if l == "INFO")
        print(f"{reagent:30s} {len(ref):2d} colours | checker: {n_err:2d} ERROR, {n_warn:2d} WARN, "
              f"{n_gamut:2d} need RAW, {n_info} cross-reactants"
              + (" | region map built" if reagent in FEATURES else " | rule only (no validation readings)"))
    return profiles


if __name__ == "__main__":
    ps = build()
    pub = (OUT / "TEST_ONLY_profile_authority_pub.pem").read_text()
    print("\nall signatures verify:", all(p.verify(pub) for p in ps.values()))
    tampered = kp.KitProfile.from_dict(json.loads((OUT / "demo-marquis-rule.json").read_text()))
    tampered.reference[0]["target"] = not tampered.reference[0]["target"]
    print("tampered profile rejected:", not tampered.verify(pub))
    sizes = {p.name: p.stat().st_size // 1024 for p in OUT.glob("*-map.json")}
    print("region-map profile sizes (KB):", sizes)
