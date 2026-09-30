"""FieldTest Recorder — reference implementation of the record format and trust model.

This is the executable spec the Kotlin record-core must match (same canonical bytes, same verdicts).
Design rules that keep canonicalisation identical across languages:
  * RFC 8785 (JCS) canonical JSON
  * ASCII-only object keys, no floating-point numbers, integers within +/-(2^53 - 1)
    (JCS writes numbers as IEEE doubles: a larger integer would round, so an edited value could keep its signature)
Record = signed HEADER {device_id, counter, prev, payload_sha256} + PAYLOAD (everything else: kind, operation,
package, operator, device/GNSS time, location, image hash, measurement, decision). The chain runs over headers
only, so one operation can be disclosed with every other case's payload withheld; withheld records reveal only
their counter and a hash, never when, where or what.
Trust chain:  NCB supervisor list  ->  supervisor-signed device binding (officer + device_id + key + attestation)
              ->  device-signed, hash-chained records  +  anchor (every phone's counter range and chain head)
              written into the witness-signed panchnama as a QR and a 14-character code with a check character.
The server is never a trust root.
"""
from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass, field

import jcs
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

GENESIS = "0" * 64
MAX_SAFE_INT = 2**53 - 1


def canon(obj) -> bytes:
    _check_signable(obj)
    return jcs.canonicalize(obj)


def _check_signable(obj, path="$"):
    if isinstance(obj, bool) or obj is None or isinstance(obj, str):
        return
    if isinstance(obj, float):
        raise ValueError(f"float not allowed in signed data at {path}; use scaled integers")
    if isinstance(obj, int):
        if abs(obj) > MAX_SAFE_INT:
            raise ValueError(f"integer beyond +/-(2^53-1) at {path}; it would not survive canonicalisation")
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            if not (isinstance(k, str) and k.isascii()):
                raise ValueError(f"non-ASCII key at {path}")
            _check_signable(v, f"{path}.{k}")
    elif isinstance(obj, (list, tuple)):                 # tuples serialise as JSON arrays
        for i, v in enumerate(obj):
            _check_signable(v, f"{path}[{i}]")
    else:
        raise ValueError(f"unsupported type {type(obj).__name__} at {path}")


def sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def pub_pem(key) -> str:
    return key.public_key().public_bytes(serialization.Encoding.PEM,
                                          serialization.PublicFormat.SubjectPublicKeyInfo).decode()


def load_pub(pem: str):
    return serialization.load_pem_public_key(pem.encode())


def sign(key, data: bytes) -> str:
    return base64.b64encode(key.sign(data, ec.ECDSA(hashes.SHA256()))).decode()


def verify_sig(pem: str, data: bytes, sig_b64: str) -> bool:
    try:
        load_pub(pem).verify(base64.b64decode(sig_b64), data, ec.ECDSA(hashes.SHA256()))
        return True
    except (InvalidSignature, ValueError):
        return False


# ---------------------------------------------------------------- trust roots

def make_supervisor_list(ncb_key, supervisors: dict[str, str], version: int) -> dict:
    """NCB's offline, two-person-signed list of authorised supervisors {officer_id: public_key_pem}."""
    body = {"type": "supervisor_list", "version": version, "supervisors": supervisors}
    return {"body": body, "sig": sign(ncb_key, canon(body))}


def make_binding(supervisor_id: str, supervisor_key, officer_id: str, device_id: str, device_pub_pem: str,
                 valid_from: str, attestation_ok: bool = True, attestation_chain: list | None = None,
                 enrolment_nonce: str | None = None) -> dict:
    """Device binding signed by the supervising officer (DSC in production, test key here).

    Signs officer, device_id AND key together, so one key cannot be presented as a second device.
    Production bindings carry the Android key-attestation chain (PEM strings) and the server's enrolment
    nonce; the verifier checks them with attestation.py. `hw_attested` alone is accepted only in test mode.
    """
    body = {"type": "device_binding", "officer_id": officer_id, "device_id": device_id, "device_pub": device_pub_pem,
            "approved_by": supervisor_id, "valid_from": valid_from, "hw_attested": attestation_ok}
    if attestation_chain is not None:
        body["attestation_chain"] = attestation_chain
        body["enrolment_nonce"] = enrolment_nonce or ""
    return {"body": body, "sig": sign(supervisor_key, canon(body))}


# ---------------------------------------------------------------- payload schema

LOCATION_UNAVAILABLE = {"status": "unavailable"}


def location_fix(lat: float, lon: float, acc_m: float, mock: bool = False) -> dict:
    """GNSS fix as scaled integers (degrees x 1e7, accuracy in cm) plus Android's Location.isMock() flag."""
    return {"status": "fix", "lat_e7": int(round(lat * 1e7)), "lon_e7": int(round(lon * 1e7)),
            "acc_cm": int(round(acc_m * 100)), "mock": bool(mock)}


def test_payload(operation_id: str, package: str, officer_id: str, device_time_ms: int, location: dict,
                 gnss_time_ms: int | None = None, **extra) -> dict:
    """The fields SIH26231 requires in every test record: timestamp, GPS, operator identifier (+ image hash,
    added by Device.append). GNSS time is recorded when the receiver has it; the server countersigns
    its own receive time at first sync, which bounds how far a record could have been backdated."""
    p = {"operation_id": operation_id, "package": package, "officer_id": officer_id,
         "device_time_ms": device_time_ms, "location": location, **extra}
    if gnss_time_ms is not None:
        p["gnss_time_ms"] = gnss_time_ms
    return p


def payload_problems(p) -> list[str]:
    """Schema of a record payload; empty list = valid."""
    probs = []
    if not isinstance(p, dict):
        return ["payload is not an object"]

    def need(k, t):
        v = p.get(k)
        if not isinstance(v, t) or (t is int and isinstance(v, bool)):
            probs.append(f"'{k}' missing or not {t.__name__}")
            return None
        return v

    kind = need("kind", str)
    need("operation_id", str)
    need("officer_id", str)
    t = need("device_time_ms", int)
    if t is not None and t < 0:
        probs.append("device_time_ms negative")
    if "gnss_time_ms" in p and (not isinstance(p["gnss_time_ms"], int) or isinstance(p["gnss_time_ms"], bool)):
        probs.append("gnss_time_ms not int")
    if kind == "test":
        need("package", str)
        need("image_sha256", str)
        loc = need("location", dict)
        if loc is not None:
            st = loc.get("status")
            if st == "fix":
                for k, lim in (("lat_e7", 900_000_000), ("lon_e7", 1_800_000_000)):
                    v = loc.get(k)
                    if not isinstance(v, int) or isinstance(v, bool) or abs(v) > lim:
                        probs.append(f"location.{k} invalid")
                if not isinstance(loc.get("acc_cm"), int) or loc["acc_cm"] < 0:
                    probs.append("location.acc_cm invalid")
                if not isinstance(loc.get("mock"), bool):
                    probs.append("location.mock missing")
            elif st != "unavailable":
                probs.append("location.status must be 'fix' or 'unavailable'")
    return probs


# ---------------------------------------------------------------- device ledger

@dataclass
class Device:
    device_id: str
    key: ec.EllipticCurvePrivateKey
    counter: int = 0
    head: str = GENESIS
    records: list = field(default_factory=list)

    def append(self, kind: str, payload: dict, image_bytes: bytes | None = None) -> dict:
        self.counter += 1
        pl = {"kind": kind, **payload}
        if image_bytes is not None:
            pl["image_sha256"] = sha256_hex(image_bytes)
        header = {"device_id": self.device_id, "counter": self.counter, "prev": self.head,
                  "payload_sha256": sha256_hex(canon(pl))}
        rec = {"body": header, "sig": sign(self.key, canon(header)), "payload": pl}
        self.head = sha256_hex(canon(header))
        self.records.append(rec)
        return rec


def verify_record(rec: dict, device_pub_pem: str) -> bool:
    """Single-record check used by the on-device log ('opening a record re-verifies it')."""
    try:
        return (verify_sig(device_pub_pem, canon(rec["body"]), rec["sig"])
                and sha256_hex(canon(rec["payload"])) == rec["body"]["payload_sha256"]
                and not payload_problems(rec["payload"]))
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------- panchnama code

B32 = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"


def _check_char(data: str) -> str:
    """Luhn mod-32 check character: catches every single-character error and most adjacent swaps."""
    factor, total = 2, 0
    for ch in reversed(data):
        add = factor * B32.index(ch)
        factor = 1 if factor == 2 else 2
        total += add // 32 + add % 32
    return B32[(32 - total % 32) % 32]


def b32_code(hex_hash: str, chars: int = 13) -> str:
    """Human-writable code: first 65 bits of the anchor digest (RFC 4648 base32) + 1 check character."""
    data = base64.b32encode(bytes.fromhex(hex_hash)).decode()[:chars]
    return data + _check_char(data)


def normalise_code(code: str) -> str:
    """Accept what a person copies from paper: spaces/hyphens, lower case, 0/1/8 for O/I/B."""
    return code.upper().replace(" ", "").replace("-", "").translate(str.maketrans("018", "OIB"))


def code_well_formed(code: str) -> bool:
    c = normalise_code(code)
    return len(c) == 14 and all(ch in B32 for ch in c) and _check_char(c[:13]) == c[13]


def format_code(code: str) -> str:
    return f"{code[:5]}-{code[5:10]}-{code[10:]}"


def make_anchor(operation_id: str, devices: list[Device]) -> dict:
    """Every phone's counter range for this operation and its chain head at close."""
    heads = []
    for d in devices:
        first = min((r["body"]["counter"] for r in d.records if r["payload"].get("operation_id") == operation_id),
                    default=d.counter)
        heads.append({"device_id": d.device_id, "first_counter": first, "last_counter": d.counter, "head": d.head})
    heads.sort(key=lambda h: h["device_id"])
    body = {"type": "anchor", "operation_id": operation_id, "heads": heads}
    digest = sha256_hex(canon(body))
    return {"qr": body, "digest": digest, "handwritten_code": b32_code(digest)}


def disclose(records: list, operation_id: str) -> list:
    """Bundle view for one operation: other cases' records keep only header + signature (payload withheld)."""
    return [r if r["payload"].get("operation_id") == operation_id else {"body": r["body"], "sig": r["sig"]}
            for r in records]


# ---------------------------------------------------------------- offline verifier

class VerificationError(Exception):
    pass


MAX_RECORDS = 200_000
MAX_IMAGE_BYTES = 25_000_000


def _require(cond, msg):
    if not cond:
        raise VerificationError(f"malformed bundle: {msg}")


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _validate_structure(b):
    """Strict shape check before any cryptography (E10: malformed input must fail closed with a reason)."""
    _require(isinstance(b, dict), "bundle is not an object")
    for k, t in (("supervisor_list", dict), ("bindings", dict), ("records", list), ("images", dict), ("anchor_qr", dict)):
        _require(isinstance(b.get(k), t), f"'{k}' missing or not a {t.__name__}")
    _require(len(b["records"]) <= MAX_RECORDS, f"more than {MAX_RECORDS} records")
    sl = b["supervisor_list"]
    _require(isinstance(sl.get("body"), dict) and isinstance(sl.get("sig"), str), "supervisor_list shape")
    _require(isinstance(sl["body"].get("supervisors"), dict), "supervisor_list.supervisors")
    for dev, bd in b["bindings"].items():
        _require(isinstance(bd, dict) and isinstance(bd.get("body"), dict) and isinstance(bd.get("sig"), str), f"binding {dev}")
        for f in ("approved_by", "device_pub", "device_id", "officer_id", "hw_attested"):
            _require(f in bd["body"], f"binding {dev} lacks {f}")
    for i, r in enumerate(b["records"]):
        _require(isinstance(r, dict) and isinstance(r.get("body"), dict) and isinstance(r.get("sig"), str), f"record {i}")
        body = r["body"]
        _require(set(body) == {"device_id", "counter", "prev", "payload_sha256"}, f"record {i} header fields")
        _require(isinstance(body["device_id"], str), f"record {i} device_id")
        _require(_is_int(body["counter"]) and body["counter"] >= 1, f"record {i} counter")
        _require(isinstance(body["prev"], str) and isinstance(body["payload_sha256"], str), f"record {i} hashes")
        _require("payload" not in r or isinstance(r["payload"], dict), f"record {i} payload")
    for h, img in b["images"].items():
        _require(isinstance(img, (bytes, bytearray)) and len(img) <= MAX_IMAGE_BYTES, f"image {h[:12]}")
    heads = b["anchor_qr"].get("heads")
    _require(isinstance(heads, list) and all(
        isinstance(h, dict) and {"device_id", "first_counter", "last_counter", "head"} <= h.keys()
        and _is_int(h["first_counter"]) and _is_int(h["last_counter"]) for h in heads), "anchor heads")
    _require(isinstance(b["anchor_qr"].get("operation_id"), str), "anchor operation_id")


def verify_bundle(bundle: dict, ncb_pub_pem: str, panchnama_code: str, attestation_policy: str = "strict",
                  attestation_roots=None) -> dict:
    """Checks everything an independent expert needs, trusting only NCB's key and the paper panchnama.

    bundle = {"supervisor_list", "bindings": {device_id: binding}, "records": [...], "images": {sha: bytes},
              "anchor_qr": body}
    Records outside the anchored operation may be headers only (payload withheld): the chain still verifies,
    and nothing about those cases is disclosed.
    attestation_policy: "strict" (default) requires a valid Android attestation chain in every binding;
                        "test-flag" accepts the hw_attested flag (reference tests only, never production).
    attestation_roots:  None = Google's published roots; a set of root SPKIs only in tests.
    """
    _validate_structure(bundle)
    try:
        return _verify(bundle, ncb_pub_pem, panchnama_code, attestation_policy, attestation_roots)
    except VerificationError:
        raise
    except Exception as e:  # noqa: BLE001  any residual surprise is a rejection, never an acceptance
        raise VerificationError(f"malformed bundle: {type(e).__name__}") from e


def _check_attestation(dev_id, body, policy, roots):
    if "attestation_chain" in body:
        import attestation
        from cryptography.hazmat.primitives import serialization as _ser
        pub_der = load_pub(body["device_pub"]).public_bytes(_ser.Encoding.DER, _ser.PublicFormat.SubjectPublicKeyInfo)
        v = attestation.verify([p.encode() for p in body["attestation_chain"]], body["enrolment_nonce"].encode(),
                               enrolled_pub_der=pub_der, revocation=attestation.load_revocation(), roots=roots)
        if not v.ok:
            raise VerificationError(f"device {dev_id} attestation failed: {'; '.join(v.reasons)}")
        return
    if policy == "test-flag" and body["hw_attested"]:
        return
    raise VerificationError(f"device {dev_id} has no hardware attestation chain")


def _verify(bundle, ncb_pub_pem, panchnama_code, attestation_policy="strict", attestation_roots=None):
    sl = bundle["supervisor_list"]
    if not verify_sig(ncb_pub_pem, canon(sl["body"]), sl["sig"]):
        raise VerificationError("supervisor list not signed by NCB")
    supervisors = sl["body"]["supervisors"]

    device_keys, device_officer = {}, {}
    for dev_id, b in bundle["bindings"].items():
        sup = b["body"]["approved_by"]
        if sup not in supervisors:
            raise VerificationError(f"binding for {dev_id} approved by non-authorised {sup}")
        if not verify_sig(supervisors[sup], canon(b["body"]), b["sig"]):
            raise VerificationError(f"binding for {dev_id} has invalid supervisor signature")
        if b["body"]["device_id"] != dev_id:
            raise VerificationError(f"binding signed for device {b['body']['device_id']} presented as {dev_id}")
        _check_attestation(dev_id, b["body"], attestation_policy, attestation_roots)
        device_keys[dev_id] = b["body"]["device_pub"]
        device_officer[dev_id] = b["body"]["officer_id"]

    # anchor: QR must match the handwritten code in the witness-signed panchnama
    if not code_well_formed(panchnama_code):
        raise VerificationError("panchnama code mistyped: check character does not match (re-read the paper)")
    op = bundle["anchor_qr"]["operation_id"]
    anchor_digest = sha256_hex(canon(bundle["anchor_qr"]))
    if b32_code(anchor_digest) != normalise_code(panchnama_code):
        raise VerificationError("anchor QR does not match the panchnama code")
    expected = {h["device_id"]: h for h in bundle["anchor_qr"]["heads"]}

    per_dev: dict[str, list] = {}
    for r in bundle["records"]:
        per_dev.setdefault(r["body"]["device_id"], []).append(r)
    if set(per_dev) != set(expected):
        raise VerificationError("devices in records differ from devices in anchor")

    flags, disclosed, withheld = [], 0, 0
    for dev_id, recs in per_dev.items():
        if dev_id not in device_keys:
            raise VerificationError(f"no valid binding for {dev_id}")
        lo, hi = expected[dev_id]["first_counter"], expected[dev_id]["last_counter"]
        prev, n = GENESIS, 0
        for r in recs:
            body = r["body"]
            n += 1
            if not verify_sig(device_keys[dev_id], canon(body), r["sig"]):
                raise VerificationError(f"{dev_id}#{body['counter']}: bad signature")
            if body["counter"] != n or body["prev"] != prev:
                raise VerificationError(f"{dev_id}: chain broken at counter {body['counter']}")
            in_op = lo <= n <= hi
            if "payload" not in r:
                if in_op:
                    raise VerificationError(f"{dev_id}#{n}: record of the anchored operation withheld")
                withheld += 1
            else:
                pl = r["payload"]
                if sha256_hex(canon(pl)) != body["payload_sha256"]:
                    raise VerificationError(f"{dev_id}#{n}: payload altered (hash does not match signed header)")
                probs = payload_problems(pl)
                if probs:
                    raise VerificationError(f"{dev_id}#{n}: payload invalid: {'; '.join(probs)}")
                if pl["officer_id"] != device_officer[dev_id]:
                    raise VerificationError(f"{dev_id}#{n}: operator {pl['officer_id']} is not the officer bound to this device")
                if in_op and pl["operation_id"] != op:
                    raise VerificationError(f"{dev_id}#{n}: record inside the anchored range belongs to another operation")
                if "image_sha256" in pl:
                    img = bundle["images"].get(pl["image_sha256"])
                    if img is None or sha256_hex(img) != pl["image_sha256"]:
                        raise VerificationError(f"{dev_id}#{n}: image missing or altered")
                if pl.get("kind") == "test" and pl["location"].get("mock"):
                    flags.append(f"{dev_id}#{n}: location reported by a mock-location provider")
                if pl.get("kind") == "test" and pl["location"]["status"] == "unavailable":
                    flags.append(f"{dev_id}#{n}: no GNSS fix at capture")
                disclosed += 1
            prev = sha256_hex(canon(body))
        if n != hi or prev != expected[dev_id]["head"]:
            raise VerificationError(f"{dev_id}: records incomplete or replaced (anchor mismatch)")
    return {"devices": len(per_dev), "records": disclosed + withheld, "disclosed": disclosed,
            "withheld_other_cases": withheld, "flags": flags, "status": "VERIFIED"}
