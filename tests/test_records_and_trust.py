"""Record format, trust model and offline verifier (E5, E10) + attestation (E15) + sync protocol (E14) + search log.

The experiment scripts run their scenarios at import time and keep their verdicts in module-level lists;
these tests import them once and assert every verdict, so CI fails if any attack slips through.
"""
import copy

import pytest

import record_core as rc


def test_every_tampering_attack_is_caught():
    import test_integrity as ti
    missed = [name for name, status, _ in ti.results if status != "caught"]
    assert not missed, f"attacks not caught: {missed}"
    assert len(ti.results) >= 18


def test_honest_bundle_verifies_and_other_cases_stay_withheld():
    import test_integrity as ti
    out = rc.verify_bundle(ti.S["bundle"], ti.NCB_PUB, ti.S["code"], attestation_policy="test-flag")
    assert out["status"] == "VERIFIED"
    assert out["withheld_other_cases"] > 0
    assert not any(r.get("payload", {}).get("operation_id") == "RAID-1" for r in ti.S["bundle"]["records"])


def test_strict_policy_demands_an_attestation_chain():
    import test_integrity as ti
    with pytest.raises(rc.VerificationError, match="attestation"):
        rc.verify_bundle(ti.S["bundle"], ti.NCB_PUB, ti.S["code"])


def test_panchnama_code_check_character_reports_typos():
    import test_integrity as ti
    code = ti.S["code"]
    bad = code[:3] + ("A" if code[3] != "A" else "B") + code[4:]
    with pytest.raises(rc.VerificationError, match="mistyped"):
        rc.verify_bundle(ti.S["bundle"], ti.NCB_PUB, bad, attestation_policy="test-flag")
    assert rc.code_well_formed(rc.format_code(code).lower())


def test_signing_refuses_values_that_json_cannot_hold_exactly():
    with pytest.raises(ValueError):
        rc.canon({"t": 2**53})
    with pytest.raises(ValueError):
        rc.canon({"x": 0.1})


def test_mock_location_is_flagged_not_hidden():
    import test_integrity as ti  # noqa: F401  (module prints its own mock-location check)
    d = rc.Device("D", __import__("cryptography.hazmat.primitives.asymmetric.ec", fromlist=["ec"]).generate_private_key(
        __import__("cryptography.hazmat.primitives.asymmetric.ec", fromlist=["ec"]).SECP256R1()))
    rec = d.append("test", rc.test_payload("OP", "P-1", "OFF", 1, rc.location_fix(28.6, 77.2, 3, mock=True)), b"img")
    assert rec["payload"]["location"]["mock"] is True
    assert not rc.payload_problems(rec["payload"])


def test_malformed_bundles_and_hostile_images_fail_closed():
    import e10_fuzz
    assert e10_fuzz.crashes == 0
    assert e10_fuzz.unhandled == 0


def test_sync_protocol_failure_scenarios():
    import e14_failures
    failed = [name for name, status, _ in e14_failures.results if status != "PASS"]
    assert not failed, f"failed scenarios: {failed}"
    assert len(e14_failures.results) >= 15


def test_android_attestation_accept_and_reject_paths():
    import e15_attestation
    failed = [name for name, status, _, _ in e15_attestation.rows if status != "PASS"]
    assert not failed, f"unexpected attestation verdicts: {failed}"
    assert any("SUCCESS PATH end to end" in r[0] and r[1] == "PASS" for r in e15_attestation.rows)


def test_searchable_log():
    import test_log
    failed = [name for name, ok, _ in test_log.checks if not ok]
    assert not failed, f"log checks failed: {failed}"


def test_edited_payload_breaks_verification_of_that_record_only():
    import test_integrity as ti
    b = copy.deepcopy(ti.S["bundle"])
    i = next(i for i, r in enumerate(b["records"]) if r.get("payload", {}).get("kind") == "test")
    b["records"][i]["payload"]["outcome"] = "negative"
    with pytest.raises(rc.VerificationError, match="payload altered"):
        rc.verify_bundle(b, ti.NCB_PUB, ti.S["code"], attestation_policy="test-flag")
