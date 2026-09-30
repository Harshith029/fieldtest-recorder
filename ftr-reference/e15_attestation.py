"""E15: real Android key-attestation verification against Google's published sample chains.

Expected: genuine TEE and StrongBox samples verify (the samples come from Google's test-resources, so we read
their challenge rather than issue one); every tampered / foreign / replayed / revoked variant is rejected.
"""
import datetime as dt

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

import attestation as at

rev = at.load_revocation()
rows = []


def run(name, chain, challenge, expect_ok, **kw):
    v = at.verify(chain, challenge, revocation=kw.pop("revocation", rev), **kw)
    rows.append((name, "PASS" if v.ok == expect_ok else "FAIL", "accepted" if v.ok else "; ".join(v.reasons)[:95], v.attestation))


for lvl in ("EC_TEE", "EC_StrongBox"):
    chain = at.load_sample(lvl)
    att = at.parse_key_description(x509.load_pem_x509_certificate(chain[0]))
    # Google's samples come from development devices, so we report their boot state honestly and check both policies
    run(f"{lvl}: genuine chain (strict policy: locked + verified boot)", chain, att.challenge,
        expect_ok=(att.verified_boot_state == "Verified" and att.device_locked is True))
    run(f"{lvl}: genuine chain, correct challenge (chain + hardware checks only)", chain, att.challenge, expect_ok=True,
        require_locked=False) if att.verified_boot_state == "Verified" else None
    run(f"{lvl}: wrong challenge (replayed attestation)", chain, b"server-nonce-that-differs", expect_ok=False,
        require_locked=False)
    bad = bytearray(chain[1]); pos = len(bad) // 2; bad[pos] = ord("A") if bad[pos] != ord("A") else ord("B")
    run(f"{lvl}: tampered intermediate certificate", [chain[0], bytes(bad), chain[2], chain[3]], att.challenge, expect_ok=False,
        require_locked=False)
    run(f"{lvl}: chain out of order", [chain[1], chain[0], chain[2], chain[3]], att.challenge, expect_ok=False,
        require_locked=False)
    fake_rev = {"entries": {format(x509.load_pem_x509_certificate(chain[1]).serial_number, "x"): {"status": "REVOKED", "reason": "KEY_COMPROMISE"}}}
    run(f"{lvl}: intermediate on revocation list", chain, att.challenge, expect_ok=False, revocation=fake_rev,
        require_locked=False)
    other_key = ec.generate_private_key(ec.SECP256R1()).public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    run(f"{lvl}: attested key differs from enrolled key", chain, att.challenge, expect_ok=False,
        enrolled_pub_der=other_key, require_locked=False)

# a forged chain: attacker-made CA issuing a cert that CLAIMS StrongBox (fake extension copied from a real leaf)
real_leaf = x509.load_pem_x509_certificate(at.load_sample("EC_StrongBox")[0])
ext = real_leaf.extensions.get_extension_for_oid(at.KEY_DESCRIPTION_OID)
ca_key, leaf_key = ec.generate_private_key(ec.SECP256R1()), ec.generate_private_key(ec.SECP256R1())
name = lambda n: x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, n)])
now = dt.datetime.now(dt.timezone.utc)
ca = (x509.CertificateBuilder().subject_name(name("Fake Root")).issuer_name(name("Fake Root")).public_key(ca_key.public_key())
      .serial_number(1).not_valid_before(now).not_valid_after(now + dt.timedelta(days=9))
      .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True).sign(ca_key, hashes.SHA256()))
leaf = (x509.CertificateBuilder().subject_name(name("Android Keystore Key")).issuer_name(name("Fake Root"))
        .public_key(leaf_key.public_key()).serial_number(2).not_valid_before(now).not_valid_after(now + dt.timedelta(days=9))
        .add_extension(ext.value, critical=False).sign(ca_key, hashes.SHA256()))
pem = lambda c: c.public_bytes(serialization.Encoding.PEM)
att = at.parse_key_description(real_leaf)
run("forged chain claiming StrongBox (attacker's own root)", [pem(leaf), pem(ca)], att.challenge, expect_ok=False,
    require_locked=False)

# ---- success path (review finding: every earlier test "passed" by rejecting). Google's samples come from
# development devices, so we build a chain the way a locked production phone presents it, under a TEST root,
# and pass that root explicitly. Proves the accept path of the parser and of record_core end to end.
def der(tag: bytes, content: bytes) -> bytes:
    n = len(content)
    ln = bytes([n]) if n < 128 else (b"\x81" + bytes([n]) if n < 256 else b"\x82" + n.to_bytes(2, "big"))
    return tag + ln + content


def der_int(tag, n):
    return der(tag, n.to_bytes(max(1, (n.bit_length() + 8) // 8), "big", signed=True))


def key_description(challenge: bytes, locked=True, boot_state=0, sec_level=1) -> bytes:
    rot = der(b"\x30", der(b"\x04", b"\x11" * 32) + der(b"\x01", b"\xff" if locked else b"\x00")
              + der_int(b"\x0a", boot_state) + der(b"\x04", b"\x22" * 32))
    hw = der(b"\x30", der(b"\xbf\x85\x40", rot))                         # [704] EXPLICIT RootOfTrust
    return der(b"\x30", der_int(b"\x02", 200) + der_int(b"\x0a", sec_level) + der_int(b"\x02", 200)
               + der_int(b"\x0a", sec_level) + der(b"\x04", challenge) + der(b"\x04", b"") + der(b"\x30", b"") + hw)


def make_chain(device_key, challenge, **kd):
    root_k, inter_k = ec.generate_private_key(ec.SECP256R1()), ec.generate_private_key(ec.SECP256R1())
    def cert(subj, iss, pub, signer, serial, ca, ext=None):
        b = (x509.CertificateBuilder().subject_name(name(subj)).issuer_name(name(iss)).public_key(pub).serial_number(serial)
             .not_valid_before(now).not_valid_after(now + dt.timedelta(days=9))
             .add_extension(x509.BasicConstraints(ca=ca, path_length=None), critical=True))
        if ext is not None:
            b = b.add_extension(x509.UnrecognizedExtension(at.KEY_DESCRIPTION_OID, ext), critical=False)
        return b.sign(signer, hashes.SHA256())
    root = cert("TEST attestation root", "TEST attestation root", root_k.public_key(), root_k, 11, True)
    inter = cert("TEST intermediate", "TEST attestation root", inter_k.public_key(), root_k, 12, True)
    leaf = cert("Android Keystore Key", "TEST intermediate", device_key.public_key(), inter_k, 13, False,
                key_description(challenge, **kd))
    spki = root.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    return [pem(leaf), pem(inter), pem(root)], {spki}


dev_key = ec.generate_private_key(ec.SECP256R1())
dev_spki = dev_key.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
nonce = b"enrol-nonce-7f3a"
chain_ok, test_roots = make_chain(dev_key, nonce)
run("SUCCESS PATH: locked, verified boot, TEE, right challenge + key (test root)", chain_ok, nonce, expect_ok=True,
    enrolled_pub_der=dev_spki, roots=test_roots)
run("same chain against Google's roots (root pinning)", chain_ok, nonce, expect_ok=False, enrolled_pub_der=dev_spki)
chain_unlocked, r2 = make_chain(dev_key, nonce, locked=False)
run("same device with bootloader unlocked", chain_unlocked, nonce, expect_ok=False, enrolled_pub_der=dev_spki, roots=r2)
chain_sw, r3 = make_chain(dev_key, nonce, sec_level=0)
run("key in software keystore, not TEE/StrongBox", chain_sw, nonce, expect_ok=False, enrolled_pub_der=dev_spki, roots=r3)

# ...and end to end through the offline verifier (strict policy, no test flag)
import record_core as rc  # noqa: E402
ncb, sup = ec.generate_private_key(ec.SECP256R1()), ec.generate_private_key(ec.SECP256R1())
d = rc.Device("DEV-A", dev_key)
d.append("open", {"operation_id": "OP", "officer_id": "OFF-1", "device_time_ms": 1_790_000_000_000})
d.append("test", rc.test_payload("OP", "P-1", "OFF-1", 1_790_000_060_000, rc.location_fix(28.6, 77.2, 5)), image_bytes=b"img")
d.append("close", {"operation_id": "OP", "officer_id": "OFF-1", "device_time_ms": 1_790_000_600_000})
anc = rc.make_anchor("OP", [d])
bundle = {"supervisor_list": rc.make_supervisor_list(ncb, {"SUP": rc.pub_pem(sup)}, 1),
          "bindings": {"DEV-A": rc.make_binding("SUP", sup, "OFF-1", "DEV-A", rc.pub_pem(dev_key), "2026-10-01",
                                                attestation_chain=[c.decode() for c in chain_ok], enrolment_nonce=nonce.decode())},
          "records": d.records, "images": {rc.sha256_hex(b"img"): b"img"}, "anchor_qr": anc["qr"]}
try:
    out = rc.verify_bundle(bundle, rc.pub_pem(ncb), anc["handwritten_code"], attestation_roots=test_roots)["status"]
except rc.VerificationError as e:
    out = f"rejected: {e}"
rows.append(("SUCCESS PATH end to end: record_core strict policy with attested binding",
             "PASS" if out == "VERIFIED" else "FAIL", out, None))

w = max(len(r[0]) for r in rows)
for n, st, why, a in rows:
    print(f"{st}  {n:{w}s}  -> {why}")
for lvl in ("EC_TEE", "EC_StrongBox"):
    a = at.parse_key_description(x509.load_pem_x509_certificate(at.load_sample(lvl)[0]))
    print(f"\n{lvl} decoded: attestation v{a.attestation_version}, key in {a.security_level}, "
          f"verified boot {a.verified_boot_state}, bootloader locked {a.device_locked}, challenge {a.challenge[:16]!r}")
print(f"\n{sum(r[1] == 'PASS' for r in rows)}/{len(rows)} checks behave as expected; revocation list entries loaded: "
      f"{len(rev['entries']) if rev else 0}")
