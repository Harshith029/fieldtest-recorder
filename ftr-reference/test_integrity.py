"""E5: attack suite against the reference record format + offline verifier.

Scenario: two raids on the same phones. RAID-1 happened earlier; RAID-2 is the one in court: two officers on two
phones, 6 packages (P-1..P-6), witness-signed panchnama code. Every attack must be caught; the honest bundle must
verify while RAID-1's records stay withheld (headers only).
"""
import copy
import json
import time

from cryptography.hazmat.primitives.asymmetric import ec

import record_core as rc

new_key = lambda: ec.generate_private_key(ec.SECP256R1())
T0 = 1_790_000_000_000                                   # ms since epoch (Sep 2026)
LOC = rc.location_fix(28.6129, 77.2295, 6.5)             # a GNSS fix: lat/lon x1e7, accuracy in cm


def run_raid(dev, officer, op, crime, packages, outcome="positive", t=T0, images=None, loc=LOC):
    base = {"operation_id": op, "officer_id": officer, "crime_no": crime}
    dev.append("open", {**base, "device_time_ms": t})
    for k, p in enumerate(packages):
        img = f"jpeg-bytes-of-{op}-{p}".encode()
        rec = dev.append("test", rc.test_payload(op, p, officer, t + 60_000 * (k + 1), loc, gnss_time_ms=t + 60_000 * (k + 1),
                                                 crime_no=crime, profile="nddk-A-1", outcome=outcome, reason="in_positive_band",
                                                 lab_x100=[3820, 3150, -3400], kit_batch="NDDK-2026-07"),
                         image_bytes=img)
        if images is not None:
            images[rec["payload"]["image_sha256"]] = img
    dev.append("close", {**base, "device_time_ms": t + 600_000})


def build_scenario():
    ncb, sup_a, sup_b, server = new_key(), new_key(), new_key(), new_key()
    slist = rc.make_supervisor_list(ncb, {"SUP-A": rc.pub_pem(sup_a), "SUP-B": rc.pub_pem(sup_b)}, version=1)
    d1, d2 = rc.Device("DEV-1", new_key()), rc.Device("DEV-2", new_key())
    bindings = {
        "DEV-1": rc.make_binding("SUP-A", sup_a, "OFF-101", "DEV-1", rc.pub_pem(d1.key), "2026-10-01T00:00:00+05:30"),
        "DEV-2": rc.make_binding("SUP-A", sup_a, "OFF-102", "DEV-2", rc.pub_pem(d2.key), "2026-10-01T00:00:00+05:30"),
    }
    # an earlier, unrelated case on the same phones (must never be disclosed in RAID-2's bundle)
    run_raid(d1, "OFF-101", "RAID-1", "NCB/DZU/090/2026", ["P-1", "P-2"], t=T0 - 86_400_000)
    run_raid(d2, "OFF-102", "RAID-1", "NCB/DZU/090/2026", ["P-3"], t=T0 - 86_400_000)
    images = {}
    run_raid(d1, "OFF-101", "RAID-2", "NCB/DZU/112/2026", ["P-1", "P-2", "P-3"], images=images)
    run_raid(d2, "OFF-102", "RAID-2", "NCB/DZU/112/2026", ["P-4", "P-5", "P-6"], images=images)
    anchor = rc.make_anchor("RAID-2", [d1, d2])
    bundle = {"supervisor_list": slist, "bindings": bindings,
              "records": rc.disclose(d1.records, "RAID-2") + rc.disclose(d2.records, "RAID-2"),
              "images": images, "anchor_qr": anchor["qr"]}
    return dict(ncb=ncb, server=server, sup_a=sup_a, d1=d1, d2=d2, bundle=bundle, code=anchor["handwritten_code"])


S = build_scenario()
NCB_PUB = rc.pub_pem(S["ncb"])


def attempt(name, mutate):
    b = copy.deepcopy(S["bundle"])
    code = S["code"]
    out = mutate(b)
    if isinstance(out, str):
        code = out
    try:
        rc.verify_bundle(b, NCB_PUB, code, attestation_policy="test-flag")
        return name, "MISSED", ""
    except rc.VerificationError as e:
        return name, "caught", str(e)


def idx(b, dev, counter):
    return next(i for i, r in enumerate(b["records"]) if r["body"]["device_id"] == dev and r["body"]["counter"] == counter)


def raid2_test(b):
    return next(i for i, r in enumerate(b["records"]) if r.get("payload", {}).get("kind") == "test")


def edit_result(b):
    b["records"][raid2_test(b)]["payload"]["outcome"] = "negative"


def swap_photo(b):
    new = b"other-photo"
    b["images"][rc.sha256_hex(new)] = new
    b["records"][raid2_test(b)]["payload"]["image_sha256"] = rc.sha256_hex(new)


def delete_middle(b):
    del b["records"][raid2_test(b)]


def delete_last_of_phone(b):
    i = max(i for i, r in enumerate(b["records"]) if r["body"]["device_id"] == "DEV-1")
    del b["records"][i]


def reorder(b):
    i = raid2_test(b)
    b["records"][i], b["records"][i + 1] = b["records"][i + 1], b["records"][i]


def rerun_with_device_key(b):
    # corrupt officer re-creates DEV-1's whole history with "negative" results on the real device key
    d = rc.Device("DEV-1", S["d1"].key)
    run_raid(d, "OFF-101", "RAID-1", "NCB/DZU/090/2026", ["P-1", "P-2"], t=T0 - 86_400_000)
    run_raid(d, "OFF-101", "RAID-2", "NCB/DZU/112/2026", ["P-1", "P-2", "P-3"], outcome="negative", images=b["images"])
    b["records"] = rc.disclose(d.records, "RAID-2") + [r for r in b["records"] if r["body"]["device_id"] == "DEV-2"]
    b["anchor_qr"] = rc.make_anchor("RAID-2", [d, S["d2"]])["qr"]      # QR regenerated; the paper code is not


def admin_mints_device_with_server_key(b):
    fake = rc.Device("DEV-1", new_key())
    b["bindings"]["DEV-1"] = rc.make_binding("SUP-A", S["server"], "OFF-101", "DEV-1", rc.pub_pem(fake.key), "2026-10-01")
    run_raid(fake, "OFF-101", "RAID-2", "NCB/DZU/112/2026", [], images=b["images"])
    b["records"] = fake.records + [r for r in b["records"] if r["body"]["device_id"] == "DEV-2"]
    b["anchor_qr"] = rc.make_anchor("RAID-2", [fake, S["d2"]])["qr"]


def admin_swaps_supervisor_list(b):
    rogue = new_key()
    b["supervisor_list"] = rc.make_supervisor_list(rogue, {"SUP-A": rc.pub_pem(rogue)}, version=2)


def admin_rewrites_anchor_and_code(b):
    fake = rc.Device("DEV-1", new_key())
    b["bindings"]["DEV-1"] = rc.make_binding("SUP-A", S["server"], "OFF-101", "DEV-1", rc.pub_pem(fake.key), "2026-10-01")
    run_raid(fake, "OFF-101", "RAID-2", "NCB/DZU/112/2026", [])
    b["records"] = fake.records + [r for r in b["records"] if r["body"]["device_id"] == "DEV-2"]
    b["anchor_qr"] = rc.make_anchor("RAID-2", [fake, S["d2"]])["qr"]
    return S["code"]   # the court compares against the PAPER code, which the admin cannot change


def drop_whole_phone(b):
    b["records"] = [r for r in b["records"] if r["body"]["device_id"] == "DEV-1"]


def reassign_to_other_officer(b):
    b["bindings"]["DEV-1"]["body"]["officer_id"] = "OFF-999"


def unauthorised_supervisor(b):
    rogue = new_key()
    b["bindings"]["DEV-1"] = rc.make_binding("SUP-X", rogue, "OFF-101", "DEV-1", b["bindings"]["DEV-1"]["body"]["device_pub"], "2026-10-01")


# ---- attacks added after the external review (29 Sep 2026)
def withhold_record_of_this_raid(b):
    i = raid2_test(b)
    b["records"][i] = {"body": b["records"][i]["body"], "sig": b["records"][i]["sig"]}   # hide an inconvenient result


def claim_raid2_record_belongs_to_other_case(b):
    # officer re-signs a record in RAID-2's counter range as "RAID-1" (needs a whole new history; anchor still binds)
    d = rc.Device("DEV-1", S["d1"].key)
    run_raid(d, "OFF-101", "RAID-1", "NCB/DZU/090/2026", ["P-1", "P-2"], t=T0 - 86_400_000)
    run_raid(d, "OFF-101", "RAID-2", "NCB/DZU/112/2026", ["P-1", "P-2"], images=b["images"])
    d.append("test", rc.test_payload("RAID-1", "P-3", "OFF-101", T0 + 200_000, LOC), image_bytes=b"x")
    d.append("close", {"operation_id": "RAID-2", "officer_id": "OFF-101", "device_time_ms": T0 + 600_000})
    b["records"] = rc.disclose(d.records, "RAID-2") + [r for r in b["records"] if r["body"]["device_id"] == "DEV-2"]
    b["anchor_qr"] = rc.make_anchor("RAID-2", [d, S["d2"]])["qr"]
    return rc.make_anchor("RAID-2", [d, S["d2"]])["handwritten_code"]   # even with a matching paper code


def one_key_two_devices(b):
    # the officer runs a parallel, hidden chain under another device id with the same key
    ghost = rc.Device("DEV-GHOST", S["d1"].key)
    run_raid(ghost, "OFF-101", "RAID-2", "NCB/DZU/112/2026", ["P-1"], outcome="negative", images=b["images"])
    b["bindings"]["DEV-GHOST"] = copy.deepcopy(b["bindings"]["DEV-1"])
    b["records"] += ghost.records
    q = copy.deepcopy(b["anchor_qr"]); q["heads"].append({"device_id": "DEV-GHOST", "first_counter": 1,
                                                          "last_counter": ghost.counter, "head": ghost.head})
    q["heads"].sort(key=lambda h: h["device_id"]); b["anchor_qr"] = q
    return rc.b32_code(rc.sha256_hex(rc.canon(q)))


def operator_mismatch(b):
    d = rc.Device("DEV-1", S["d1"].key)
    run_raid(d, "OFF-101", "RAID-1", "NCB/DZU/090/2026", ["P-1", "P-2"], t=T0 - 86_400_000)
    run_raid(d, "OFF-777", "RAID-2", "NCB/DZU/112/2026", ["P-1", "P-2", "P-3"], images=b["images"])
    b["records"] = rc.disclose(d.records, "RAID-2") + [r for r in b["records"] if r["body"]["device_id"] == "DEV-2"]
    b["anchor_qr"] = rc.make_anchor("RAID-2", [d, S["d2"]])["qr"]
    return rc.make_anchor("RAID-2", [d, S["d2"]])["handwritten_code"]


def edit_time_beyond_2p53(b):
    i = raid2_test(b)
    b["records"][i]["payload"]["device_time_ms"] = 2**53 + 1                # value JCS would round


def record_without_time_or_gps(b):
    # a validly SIGNED test record that simply lacks timestamp and location (e.g. a buggy or patched app)
    d = rc.Device("DEV-1", S["d1"].key)
    run_raid(d, "OFF-101", "RAID-1", "NCB/DZU/090/2026", ["P-1", "P-2"], t=T0 - 86_400_000)
    base = {"operation_id": "RAID-2", "officer_id": "OFF-101"}
    d.append("open", {**base, "device_time_ms": T0})
    d.append("test", {**base, "package": "P-1", "outcome": "positive"}, image_bytes=b"x")
    d.append("close", {**base, "device_time_ms": T0 + 600_000})
    b["images"][rc.sha256_hex(b"x")] = b"x"
    b["records"] = rc.disclose(d.records, "RAID-2") + [r for r in b["records"] if r["body"]["device_id"] == "DEV-2"]
    b["anchor_qr"] = rc.make_anchor("RAID-2", [d, S["d2"]])["qr"]
    return rc.make_anchor("RAID-2", [d, S["d2"]])["handwritten_code"]


def mistyped_code(_b=None):
    c = S["code"]
    return c[:6] + ("A" if c[6] != "A" else "B") + c[7:]


results = [attempt(*a) for a in [
    ("edit a result", edit_result),
    ("swap photo and fix its hash", swap_photo),
    ("delete a middle record", delete_middle),
    ("delete a phone's LAST record", delete_last_of_phone),
    ("re-order records", reorder),
    ("re-run whole history on the real device key", rerun_with_device_key),
    ("admin mints device, signs binding with server key", admin_mints_device_with_server_key),
    ("admin replaces NCB supervisor list", admin_swaps_supervisor_list),
    ("admin rewrites records + QR (paper code unchanged)", admin_rewrites_anchor_and_code),
    ("hide one phone's records entirely", drop_whole_phone),
    ("re-assign device to another officer", reassign_to_other_officer),
    ("binding by an unauthorised 'supervisor'", unauthorised_supervisor),
    ("withhold one record of the anchored raid", withhold_record_of_this_raid),
    ("re-label a raid record as another case", claim_raid2_record_belongs_to_other_case),
    ("one key presented as two devices", one_key_two_devices),
    ("record claims a different operator", operator_mismatch),
    ("edit a value to above 2^53", edit_time_beyond_2p53),
    ("signed record without timestamp/GPS", record_without_time_or_gps),
]]
w = max(len(r[0]) for r in results)
for name, status, why in results:
    print(f"{name:{w}s}  {status:7s}  {why}")
print(f"\ncaught {sum(r[1]=='caught' for r in results)}/{len(results)} attacks")

honest = rc.verify_bundle(S["bundle"], NCB_PUB, S["code"], attestation_policy="test-flag")
print("honest RAID-2 bundle:", honest)
print("RAID-1 payloads present in RAID-2 bundle:",
      sum(1 for r in S["bundle"]["records"] if r.get("payload", {}).get("operation_id") == "RAID-1"))
print("panchnama code to hand-write:", rc.format_code(S["code"]), f"({len(S['code'])} chars: 65 bits + check character)")

# transcription errors: a typo is reported as a typo, not as tampering; common look-alikes are accepted
try:
    rc.verify_bundle(S["bundle"], NCB_PUB, mistyped_code(), attestation_policy="test-flag")
    print("one-character typo: MISSED")
except rc.VerificationError as e:
    print("one-character typo ->", e)
lower = rc.format_code(S["code"]).lower()
print("lower case with hyphens accepted:", rc.verify_bundle(S["bundle"], NCB_PUB, lower, attestation_policy="test-flag")["status"])
single = sum(not rc.code_well_formed(S["code"][:i] + ch + S["code"][i + 1:])
             for i in range(14) for ch in rc.B32 if ch != S["code"][i])
swaps = [(i, S["code"][:i] + S["code"][i + 1] + S["code"][i] + S["code"][i + 2:]) for i in range(13) if S["code"][i] != S["code"][i + 1]]
print(f"check character catches {single}/{14 * 31} single-character errors, "
      f"{sum(not rc.code_well_formed(c) for _, c in swaps)}/{len(swaps)} adjacent swaps")

# mock location is flagged, not hidden
d = rc.Device("DEV-M", new_key()); sup = new_key()
run_raid(d, "OFF-9", "OP-M", "X/1", ["P-1"], loc=rc.location_fix(28.6, 77.2, 3.0, mock=True))
bm = {"supervisor_list": rc.make_supervisor_list(S["ncb"], {"SUP": rc.pub_pem(sup)}, 1),
      "bindings": {"DEV-M": rc.make_binding("SUP", sup, "OFF-9", "DEV-M", rc.pub_pem(d.key), "2026-10-01")},
      "records": d.records, "images": {r["payload"]["image_sha256"]: b"jpeg-bytes-of-OP-M-P-1" for r in d.records if "image_sha256" in r["payload"]}}
am = rc.make_anchor("OP-M", [d]); bm["anchor_qr"] = am["qr"]
print("mock-location record:", rc.verify_bundle(bm, NCB_PUB, am["handwritten_code"], attestation_policy="test-flag")["flags"])

# float and big-integer guards at signing time
for bad in ({"de00": 4.1}, {"t": 2**53}):
    try:
        rc.canon(bad); print("guard MISSED for", bad)
    except ValueError as e:
        print("guard ->", e)

# canonical-form equivalence under our rules: JCS == sorted compact json for ASCII keys, no floats
body = S["bundle"]["records"][raid2_test(S["bundle"])]["payload"]
print("JCS equals sorted compact JSON under our rules:",
      rc.canon(body) == json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode())

# verification speed for a large seizure: one phone, 1000 test records
big = rc.Device("DEV-B", new_key())
imgs = {}
run_raid(big, "OFF-1", "OP-big", "X/2", [f"P-{i+1}" for i in range(1000)], images=imgs)
sup = new_key()
bb = {"supervisor_list": rc.make_supervisor_list(S["ncb"], {"SUP-A": rc.pub_pem(sup)}, 1),
      "bindings": {"DEV-B": rc.make_binding("SUP-A", sup, "OFF-1", "DEV-B", rc.pub_pem(big.key), "2026-10-01")},
      "records": big.records, "images": imgs}
a = rc.make_anchor("OP-big", [big]); bb["anchor_qr"] = a["qr"]
t = time.perf_counter(); rc.verify_bundle(bb, NCB_PUB, a["handwritten_code"], attestation_policy="test-flag"); dt = time.perf_counter() - t
print(f"verified 1002 records in {dt:.2f}s on this laptop ({1002/dt:.0f} records/s)")

# ---- attestation policy (U4): strict mode must demand a real Android attestation chain
try:
    rc.verify_bundle(S["bundle"], NCB_PUB, S["code"])          # default strict, bindings carry only the flag
    print("strict policy without chain: MISSED")
except rc.VerificationError as e:
    print("strict policy without chain: caught ->", e)
