"""Android hardware key attestation verification (replaces the `hw_attested` flag placeholder, U4).

Checks, in order: chain signatures leaf -> root; root public key is one of Google's published attestation
roots; no certificate is on Google's revocation list; the attestation extension says the key lives in secure
hardware (TEE or StrongBox); verified boot is VERIFIED and the bootloader is LOCKED; the challenge equals the
server's enrolment nonce; the attested public key is the key being enrolled.
Schema: https://source.android.com/docs/security/features/keystore/attestation#schema
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa

KEY_DESCRIPTION_OID = x509.ObjectIdentifier("1.3.6.1.4.1.11129.2.1.17")
SECURITY_LEVEL = {0: "Software", 1: "TrustedEnvironment", 2: "StrongBox"}
BOOT_STATE = {0: "Verified", 1: "SelfSigned", 2: "Unverified", 3: "Failed"}
TAG_ROOT_OF_TRUST = 704
SAMPLES = Path(__file__).parent / "tools" / "attestation_samples"


# ------------------------------------------------------------------ minimal DER walker
def _tlv(b: bytes, i: int):
    first = b[i]; i += 1
    cls, constructed, tag = first >> 6, bool(first & 0x20), first & 0x1F
    if tag == 0x1F:                                   # high-tag-number form (e.g. [704])
        tag = 0
        while True:
            c = b[i]; i += 1
            tag = (tag << 7) | (c & 0x7F)
            if not c & 0x80:
                break
    ln = b[i]; i += 1
    if ln & 0x80:
        n = ln & 0x7F
        ln = int.from_bytes(b[i:i + n], "big"); i += n
    return cls, constructed, tag, b[i:i + ln], i + ln


def _children(v: bytes):
    out, i = [], 0
    while i < len(v):
        cls, cons, tag, val, i = _tlv(v, i)
        out.append((cls, cons, tag, val))
    return out


def _int(v: bytes) -> int:
    return int.from_bytes(v, "big", signed=True)


@dataclass
class Attestation:
    security_level: str
    keymaster_security_level: str
    challenge: bytes
    verified_boot_state: str | None
    device_locked: bool | None
    attestation_version: int


def parse_key_description(leaf: x509.Certificate) -> Attestation:
    ext = leaf.extensions.get_extension_for_oid(KEY_DESCRIPTION_OID).value.value
    _, _, _, seq, _ = _tlv(ext, 0)
    f = _children(seq)
    att_version, sec, km_sec = _int(f[0][3]), _int(f[1][3]), _int(f[3][3])
    challenge = f[4][3]
    boot_state = locked = None
    for auth_list in (f[7][3], f[6][3]):              # hardware-enforced first, then software-enforced
        for cls, _, tag, val in _children(auth_list):
            if cls == 2 and tag == TAG_ROOT_OF_TRUST:
                rot = _children(_children(val)[0][3])  # explicit tag wraps a SEQUENCE
                locked = rot[1][3] != b"\x00"
                boot_state = BOOT_STATE.get(_int(rot[2][3]), "unknown")
                break
        if boot_state is not None:
            break
    return Attestation(SECURITY_LEVEL.get(sec, "unknown"), SECURITY_LEVEL.get(km_sec, "unknown"), challenge,
                       boot_state, locked, att_version)


# ------------------------------------------------------------------ chain checks
def google_root_keys(path=SAMPLES / "google_attestation_roots.pem"):
    pem = path.read_text()
    certs = [x509.load_pem_x509_certificate(("-----BEGIN CERTIFICATE-----" + b).encode())
             for b in pem.split("-----BEGIN CERTIFICATE-----")[1:]]
    return {c.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
            for c in certs}


def _signed_by(cert: x509.Certificate, issuer: x509.Certificate) -> bool:
    pub = issuer.public_key()
    try:
        if isinstance(pub, rsa.RSAPublicKey):
            pub.verify(cert.signature, cert.tbs_certificate_bytes, padding.PKCS1v15(), cert.signature_hash_algorithm)
        elif isinstance(pub, ec.EllipticCurvePublicKey):
            pub.verify(cert.signature, cert.tbs_certificate_bytes, ec.ECDSA(cert.signature_hash_algorithm))
        else:
            return False
        return True
    except InvalidSignature:
        return False


@dataclass
class Verdict:
    ok: bool
    reasons: list = field(default_factory=list)
    attestation: Attestation | None = None


def verify(chain_pems: list[bytes], expected_challenge: bytes | None, enrolled_pub_der: bytes | None = None,
           revocation: dict | None = None, roots=None, require_locked=True) -> Verdict:
    reasons = []
    try:
        chain = [x509.load_pem_x509_certificate(p) for p in chain_pems]
    except Exception as e:  # noqa: BLE001
        return Verdict(False, [f"unparseable chain: {type(e).__name__}"])
    if len(chain) < 2:
        return Verdict(False, ["chain too short"])
    for child, parent in zip(chain, chain[1:]):
        if not _signed_by(child, parent):
            reasons.append(f"signature break at '{child.subject.rfc4514_string()[:40]}'")
    root = chain[-1]
    roots = roots if roots is not None else google_root_keys()
    root_spki = root.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    if root_spki not in roots:
        reasons.append("root is not a Google hardware attestation root")
    if revocation:
        for c in chain:
            for s in (format(c.serial_number, "x"), str(c.serial_number)):
                if s in revocation.get("entries", {}):
                    reasons.append(f"certificate {s} revoked ({revocation['entries'][s].get('reason')})")
    try:
        att = parse_key_description(chain[0])
    except Exception as e:  # noqa: BLE001
        return Verdict(False, reasons + [f"no/invalid attestation extension: {type(e).__name__}"])
    if att.security_level not in ("TrustedEnvironment", "StrongBox"):
        reasons.append(f"key not in secure hardware ({att.security_level})")
    if att.verified_boot_state != "Verified":
        reasons.append(f"verified boot state {att.verified_boot_state}")
    if require_locked and att.device_locked is not True:
        reasons.append("bootloader unlocked")
    if expected_challenge is not None and att.challenge != expected_challenge:
        reasons.append("challenge mismatch (replayed or foreign attestation)")
    if enrolled_pub_der is not None:
        leaf_pub = chain[0].public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
        if leaf_pub != enrolled_pub_der:
            reasons.append("attested key is not the key being enrolled")
    return Verdict(not reasons, reasons, att)


def load_sample(name):
    d = SAMPLES / name
    return [(d / f"cert{i}.pem").read_bytes() for i in range(4)]


def load_revocation():
    p = SAMPLES / "revocation_status.json"
    return json.loads(p.read_text()) if p.exists() else None
