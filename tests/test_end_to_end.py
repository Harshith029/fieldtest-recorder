"""The whole workflow through rendered photos: guided test -> capture -> read -> sign -> anchor -> verify -> tamper."""
import pytest

import run_demo


@pytest.fixture(scope="module")
def demo():
    return run_demo.run(write=False)


def test_bundle_verifies_offline_with_the_other_case_withheld(demo):
    v = demo["verification"]
    assert v["status"] == "VERIFIED" and v["devices"] == 2
    assert v["withheld_other_cases"] == 3


def test_every_tampering_attempt_is_caught(demo):
    assert all(t["result"] == "caught" for t in demo["tampering"])
    assert "mistyped" in demo["typo_in_code"]


def test_packet_results_follow_the_kit_and_the_chemistry(demo):
    p = {x["package"]: x for x in demo["packets"]}
    assert "morphine" in p["P-1"]["candidates"] and p["P-1"]["quantity_warning"]          # opiates differ in thresholds
    assert [t for _, t, _ in p["P-2"]["path"] if t] == ["A", "B"]                          # no reaction: A then B, stop
    assert p["P-2"]["path"][-1][0] == "stop-unless-suspicion"
    assert set(p["P-3"]["candidates"]) == {"amphetamine", "methamphetamine"}


def test_no_capture_was_misread(demo):
    truth = {"P-1": "positive", "P-2": "negative", "P-3": "positive"}
    for c in demo["captures"]:
        if c["outcome"] == "retake needed" or c["test"] == "C":
            continue
        assert c["outcome"] == truth[c["package"]], c


def test_log_reopens_and_reverifies(demo):
    assert demo["log_open_reverifies"] is True
    assert demo["searches"]["heroin"] and all(h[0] == "P-1" for h in demo["searches"]["heroin"])
