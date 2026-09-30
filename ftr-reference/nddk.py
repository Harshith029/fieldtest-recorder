"""NCB Narcotic Drugs Detection Kit (NDDK) as a signed, guided protocol.

Source: NICFS "A Forensic Guide for Crime Investigators", ch. 8, Figs 8.12-8.16 (docs/sources/), i.e. the kit
NCB supplies free to agencies. Encoded exactly as printed: Tests A-E, reagent order and drops, vessel, which
liquid layer to read, positives as colour RANGES, and the screening flow charts I and II.

Colour values are APPROXIMATE: sampled from a scanned, printed chart (tools: swatch extraction in E17 notes).
Where a range ends in a near-black swatch, the scan cannot recover its hue; that end is modelled as the same
reaction at up to 2.5x amount instead of a grey point (a grey endpoint would make dirty wells read positive).
Tests C and D: the guide prints the flow chart but not the procedure or colours -> classification returns
"inconclusive: chart not available" until NCB's kit sheet is added. Everything here must be replaced by
NCB's own kit sheet and validation data before operational use.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE / "research"))
import bands  # noqa: E402
import kit_profile as kp  # noqa: E402
import record_core as rc  # noqa: E402

SOURCE = "NICFS Forensic Guide ch.8 Fig 8.13 (scanned chart; colours approximate)"

# (outcome, substances, from Lab, to Lab or None for an unreadable dark end, k_hi)
CHART = {
    "A": [("opium", ["opium"], (49.8, 32.6, 17.8), None, 1.6),
          ("morphine", ["morphine"], (55.2, 22.2, -9.4), None, 2.5),
          ("codeine", ["codeine"], (59.5, 15.4, -12.2), (52.2, 11.2, 0.5), 1.6),
          ("heroin", ["heroin"], (74.1, 32.7, 8.5), (60.5, 21.3, -6.5), 1.6),
          ("amphetamines", ["amphetamine", "methamphetamine"], (80.4, 13.5, 50.1), None, 2.5),
          ("mescaline", ["mescaline"], (63.4, 44.9, 51.7), (46.2, 52.3, 33.2), 1.6)],
    "B": [("cannabis", ["ganja", "charas", "hashish oil"], (48.8, 53.6, 34.4), (61.2, 15.6, 16.1), 1.6)],
    "E": [("cocaine or methaqualone", ["cocaine", "methaqualone"], (66.1, -14.0, -24.5), None, 1.6)],
    "E34": [("cocaine", ["cocaine"], (82.5, -20.6, 24.2), None, 1.6),
            ("methaqualone", ["methaqualone"], (91.6, -9.0, 59.9), None, 1.6)],
}

STEPS = {
    "A": {"vessel": "spot plate", "read": "well", "procedure": [
            "opium: match-head of material + 2-3 drops water, smear 1-2 min, transfer the liquid to another well",
            "add 1 drop A1", "add 3 drops A2"], "read_after_s": 60,
          "note": "read time not printed; 60 s assumed until the kit sheet states it"},
    "B": {"vessel": "test tube", "read": "LOWER liquid layer (ignore upper layer)", "procedure": [
            "match-head of material in a tube", "add match-head of B1", "add 25 drops B2, shake 1 min",
            "add 25 drops B3, shake 2 min", "stand 2 min"], "read_after_s": 120},
    "C": {"vessel": "not printed", "read": "not printed", "procedure": ["not printed in the guide: needs NCB kit sheet"],
          "read_after_s": None, "targets": ["methamphetamine", "methylphenidate"]},
    "D": {"vessel": "not printed", "read": "not printed", "procedure": ["not printed in the guide: needs NCB kit sheet"],
          "read_after_s": None, "targets": ["barbiturates"]},
    "E": {"vessel": "test tube", "read": "solution", "procedure": [
            "powder the material; match-head in a tube", "add 1 drop E1, shake 10 s", "add 1 drop E2, shake 10 s"],
          "read_after_s": 20, "then_if_blue": "E34"},
    "E34": {"vessel": "test tube (fresh)", "read": "solution", "procedure": [
            "match-head of material in a tube", "add 5 drops E3", "add 3 drops E4"], "read_after_s": 30},
}

# Flow charts I and II (Figs 8.14, 8.15). "submit" = submit to laboratory.
FLOW = {
    "start": {"herb, resin or oil": "B-cannabis", "resin or powder (opiate suspected)": "A-opiates-I",
              "cigarettes, pipes, other": "submit-if-suspicion", "impregnated paper or gelatine film": "AC-amphetamines",
              "tablets, capsules, powders, liquids": ["AC-amphetamines", "A-opiates-II", "A-barbiturates-as-printed"]},
    "B-cannabis": {"tests": ["B"], "positive": "submit", "negative": "stop-unless-suspicion"},
    "A-opiates-I": {"tests": ["A"], "positive": "submit", "negative": "B-cannabis"},
    "A-opiates-II": {"tests": ["A"], "positive": "submit", "negative": "stop-unless-suspicion"},
    "AC-amphetamines": {"tests": ["A", "C"], "positive": "submit", "negative": "E-cocaine"},
    "E-cocaine": {"tests": ["E"], "positive": "submit", "negative": "D-barbiturates"},
    "D-barbiturates": {"tests": ["D"], "positive": "submit", "negative": "stop-unless-suspicion"},
    # right-hand branch of flow chart II is printed as "Try TEST A for: Barbiturates" (possibly meant Test D)
    "A-barbiturates-as-printed": {"tests": ["A"], "positive": "submit", "negative": "AC-all"},
    "AC-all": {"tests": ["A", "C"], "positive": "submit", "negative": "E-then-stop"},
    "E-then-stop": {"tests": ["E"], "positive": "submit", "negative": "stop-unless-suspicion"},
}

# NDPS small / commercial quantity, milligrams (S.O. 1055(E), 19 Oct 2001). Core entries confirmed in two
# sources; mescaline, methylphenidate, barbiturates from a secondary compilation (check against the Gazette).
NDPS_QTY_MG = {"heroin": (5_000, 250_000), "morphine": (5_000, 250_000), "codeine": (10_000, 1_000_000),
               "opium": (25_000, 2_500_000), "cocaine": (2_000, 100_000), "ganja": (1_000_000, 20_000_000),
               "charas": (100_000, 1_000_000), "amphetamine": (2_000, 50_000), "methamphetamine": (2_000, 50_000),
               "mdma": (500, 10_000), "methaqualone": (20_000, 500_000), "mescaline": (5_000, 100_000),
               "methylphenidate": (2_000, 50_000), "barbiturates": (20_000, 500_000)}


def build_profiles(key, write=True):
    out = {}
    for test, outcomes in CHART.items():
        dec = {"type": "band", "tol_x100": 500, "margin_x100": 200, "source": SOURCE, "outcomes": []}
        for name, subs, a, b, k_hi in outcomes:
            ks = np.round(np.arange(bands.K_LO, k_hi + 1e-9, 0.1), 2)
            dec["outcomes"].append({"name": name, "substances": subs, "positive": True,
                                    "points_x100": bands.band_points(np.array(a), None if b is None else np.array(b), ks=ks)})
        ref = [{"substance": n, "target": True, "lab_x100": [int(round(v * 100)) for v in a], "munsell": "",
                "colour_name": "chart swatch (approx.)", "phase": STEPS[test]["read"]} for n, _, a, _, _ in outcomes]
        p = kp.KitProfile(f"nddk-test-{test}", 1, f"NDDK Test {test}", ref, dec, STEPS[test]["read_after_s"] or 60,
                          layout={"blank_well": "W2"}).sign(key)
        out[test] = p
        if write:
            (HERE / "profiles" / f"nddk-test-{test}.json").write_text(json.dumps(p.to_dict()))
    protocol = {"type": "kit_protocol", "kit": "NCB Narcotic Drugs Detection Kit", "version": 1, "source": SOURCE,
                "steps": STEPS, "flow": FLOW, "profiles": {t: f"nddk-test-{t}@v1" for t in CHART},
                "ndps_quantity_mg": {k: list(v) for k, v in NDPS_QTY_MG.items()}}
    signed = {"body": protocol, "sig": rc.sign(key, rc.canon(protocol))}
    if write:
        (HERE / "profiles" / "nddk-protocol.json").write_text(json.dumps(signed, indent=1))
    return out, signed


def classify_step(profiles, test, L, blank_L):
    if test not in profiles:
        return "inconclusive", "kit chart for this test not available", []
    return profiles[test].classify(L, blank_L)


def _qty_key(s):
    return {"ganja": "ganja", "charas": "charas", "hashish oil": "charas"}.get(s, s)


def narrow(results: dict) -> dict:
    """Combine a sample's test results: candidates = intersection of positive tests' 'consistent with' lists
    (E3/E4 refines E). Adds the NDPS quantity warning when the candidates' thresholds differ."""
    pos = [set(r[2]) for t, r in results.items() if r[0] == "positive" and r[2]]
    cand = set.intersection(*pos) if pos else set()
    if "E34" in results and results["E34"][0] == "positive":
        cand = set(results["E34"][2])
    qty = {s: NDPS_QTY_MG.get(_qty_key(s)) for s in sorted(cand)}
    distinct = {v for v in qty.values() if v is not None}
    warn = None
    if len(distinct) > 1:
        warn = ("quantity category cannot be decided in the field: candidates have different NDPS thresholds ("
                + "; ".join(f"{s} {v[0] / 1000:g} g / {v[1] / 1000:g} g" for s, v in qty.items() if v) + ")")
    return {"candidates": sorted(cand), "quantity_warning": warn}


def run_flow(nature: str, outcome_of) -> dict:
    """Walk the printed flow chart. outcome_of(test) -> (outcome, reason, consistent). Returns path + summary."""
    nxt = FLOW["start"][nature]
    branches = nxt if isinstance(nxt, list) else [nxt]
    path, results = [], {}
    for node in branches:
        while node in FLOW:
            tests = FLOW[node]["tests"]
            for t in tests:
                if t not in results:
                    results[t] = outcome_of(t)
                    path.append((node, t, results[t][0]))
                    if t == "E" and results[t][0] == "positive":
                        results["E34"] = outcome_of("E34"); path.append((node, "E34", results["E34"][0]))
            any_pos = any(results[t][0] == "positive" for t in tests)
            node = FLOW[node]["positive" if any_pos else "negative"]
        path.append((node, None, None))
        if node == "submit":
            break
    return {"path": path, "results": results, **narrow(results)}


if __name__ == "__main__":
    import build_profiles as bp
    key = bp.authority_key()
    profiles, protocol = build_profiles(key)
    for t, p in profiles.items():
        print(f"Test {t:3s}: {len(p.decision['outcomes'])} outcome band(s), "
              f"{sum(len(o['points_x100']) for o in p.decision['outcomes'])} points; read: {STEPS[t]['read']}")
    print("protocol signed:", rc.verify_sig(rc.pub_pem(key), rc.canon(protocol["body"]), protocol["sig"]))
