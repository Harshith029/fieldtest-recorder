"""Colour decisions and the NCB kit protocol: blank well, colour bands vs sample amount, flow charts, quantity warning."""
import json
from pathlib import Path

import numpy as np
import pytest

import bands
import kit_profile as kp
import nddk
import nij_colours

REF = Path(__file__).resolve().parents[1] / "ftr-reference"
PROFILES = {p.stem: kp.KitProfile.from_dict(json.loads(p.read_text())) for p in (REF / "profiles").glob("*.json")
            if p.stem != "nddk-protocol"}
CHART = {o[0]: np.array(o[2], float) for outs in nddk.CHART.values() for o in outs}


def test_signed_profiles_verify_and_tampering_is_detected():
    pub = (REF / "profiles" / "TEST_ONLY_profile_authority_pub.pem").read_text()
    assert all(p.verify(pub) for p in PROFILES.values())
    p = kp.KitProfile.from_dict(json.loads((REF / "profiles" / "nddk-test-A.json").read_text()))
    p.decision["tol_x100"] = 5000
    assert not p.verify(pub)


@pytest.mark.parametrize("pid", sorted(PROFILES))
def test_clear_well_reads_no_colour_change_against_the_blank(pid):
    out, reason, _ = PROFILES[pid].classify(np.array([95.0, 0.2, 0.8]), np.array([95.3, -0.1, 0.5]))
    assert (out, reason) == ("negative", "no_colour_change")


@pytest.mark.parametrize("pid", sorted(PROFILES))
def test_contaminated_blank_never_turns_a_positive_into_no_colour_change(pid):
    """Audit U27: sample carried into the blank well. Sample and blank then match, which used to read
    'negative, no colour change'. Every positive colour must instead come back inconclusive."""
    p = PROFILES[pid]
    for L in p.labs()[p.targets()]:
        if p.classify(L, np.array([95.0, 0.0, 0.0]))[0] != "positive":
            continue                                   # not called positive even with a clean blank
        out, reason, _ = p.classify(L, L + np.array([0.4, -0.3, 0.2]))
        assert (out, reason) == ("inconclusive", "blank_shows_reaction_colour"), (pid, L)


def test_without_a_blank_a_clear_well_is_never_called_positive():
    for pid, p in PROFILES.items():
        assert p.classify(np.array([94.0, 0.0, 0.0]))[0] != "positive", pid


def test_band_model_has_no_false_positives_where_the_point_rule_had_them():
    """E17 finding, cobalt thiocyanate at 1.4x sample amount: other blues must not read positive."""
    rule, band = PROFILES["demo-cobalt-thiocyanate-rule"], PROFILES["demo-cobalt-thiocyanate-band"]
    grp = rule.positive_group()
    others = [r["lab"] for r, g in zip(nij_colours.reference("Cobalt thiocyanate"), grp) if not g]
    fp_rule = sum(rule.classify(bands.amount_series(L, 1.4), bands.WHITE)[0] == "positive" for L in others)
    fp_band = sum(band.classify(bands.amount_series(L, 1.4), bands.WHITE)[0] == "positive" for L in others)
    assert fp_band == 0
    assert fp_rule > 0


@pytest.mark.parametrize("name,test,k", [("morphine", "A", 0.7), ("morphine", "A", 1.4), ("heroin", "A", 1.0),
                                         ("amphetamines", "A", 0.6), ("cannabis", "B", 1.3),
                                         ("cocaine or methaqualone", "E", 1.0), ("cocaine", "E34", 1.0)])
def test_nddk_chart_outcomes_hold_across_sample_amounts(name, test, k):
    subs = next(o[1] for o in nddk.CHART[test] if o[0] == name)
    out, _, cons = PROFILES[f"nddk-test-{test}"].classify(bands.amount_series(CHART[name], k), bands.WHITE)
    assert out == "positive"
    assert set(subs) <= set(cons)


def test_tests_without_a_printed_chart_are_inconclusive_not_guessed():
    out, reason, _ = nddk.classify_step({}, "C", None, None)
    assert out == "inconclusive" and "not available" in reason


def test_flow_chart_and_quantity_warning():
    prof = {t: PROFILES[f"nddk-test-{t}"] for t in nddk.CHART}
    blank = bands.WHITE

    def reader(truth):
        return lambda t: nddk.classify_step(prof, t, truth.get(t, blank), blank)

    blue = nddk.run_flow("impregnated paper or gelatine film", reader({"E": CHART["cocaine or methaqualone"]}))
    assert blue["candidates"] == ["cocaine", "methaqualone"] and "cannot be decided" in blue["quantity_warning"]
    green = nddk.run_flow("impregnated paper or gelatine film",
                          reader({"E": CHART["cocaine or methaqualone"], "E34": CHART["cocaine"]}))
    assert green["candidates"] == ["cocaine"] and green["quantity_warning"] is None
    clean = nddk.run_flow("resin or powder (opiate suspected)", reader({}))
    assert [t for _, t, _ in clean["path"] if t] == ["A", "B"] and clean["path"][-1][0] == "stop-unless-suspicion"


def test_protocol_file_is_signed():
    import record_core as rc
    doc = json.loads((REF / "profiles" / "nddk-protocol.json").read_text())
    pub = (REF / "profiles" / "TEST_ONLY_profile_authority_pub.pem").read_text()
    assert rc.verify_sig(pub, rc.canon(doc["body"]), doc["sig"])
