"""E3: which tampering does each integrity design catch?

Designs:
  A  hash of image only (what most SIH repos do)
  B  signed record + hash chain + counter (our v2 plan)
  C  B + 'anchor': chain head (counter + hash) written into the paper panchnama / shown on the s.105 video
Attacks on an operation that produced 6 records (P-1..P-6):
  edit a result, delete a middle record, delete the LAST record (tail truncation),
  replace everything with a freshly signed fake sequence, re-order records.
"""
import hashlib, json, copy
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes
from cryptography.exceptions import InvalidSignature

KEY = ec.generate_private_key(ec.SECP256R1())  # stands in for the Android Keystore key
PUB = KEY.public_key()
H = lambda b: hashlib.sha256(b).hexdigest()
canon = lambda d: json.dumps(d, sort_keys=True, separators=(",", ":")).encode()


def make_records(n=6, results=None):
    recs, prev = [], "0" * 64
    for i in range(n):
        img = f"image-bytes-P{i+1}".encode()
        body = {"counter": i + 1, "package": f"P-{i+1}", "result": (results or ["violet"] * n)[i],
                "image_sha256": H(img), "prev": prev}
        sig = KEY.sign(canon(body), ec.ECDSA(hashes.SHA256())).hex()
        rec = {"body": body, "sig": sig, "image": img}
        prev = H(canon(body))
        recs.append(rec)
    return recs


def anchor(recs):
    return {"last_counter": recs[-1]["body"]["counter"], "head": H(canon(recs[-1]["body"]))}


def check_A(recs, _anchor):
    return all(r["body"]["image_sha256"] == H(r["image"]) for r in recs)


def check_B(recs, _anchor):
    prev = "0" * 64
    for k, r in enumerate(recs):
        try:
            PUB.verify(bytes.fromhex(r["sig"]), canon(r["body"]), ec.ECDSA(hashes.SHA256()))
        except InvalidSignature:
            return False
        if r["body"]["prev"] != prev or r["body"]["counter"] != k + 1 or r["body"]["image_sha256"] != H(r["image"]):
            return False
        prev = H(canon(r["body"]))
    return True


def check_C(recs, anc):
    return check_B(recs, anc) and anchor(recs) == anc


orig = make_records()
anc = anchor(orig)

attacks = {}
a = copy.deepcopy(orig); a[2]["body"]["result"] = "no change"; attacks["edit a result (P-3)"] = a
a = copy.deepcopy(orig); a[2]["image"] = b"other-photo"; a[2]["body"]["image_sha256"] = H(b"other-photo"); attacks["swap photo + fix its hash"] = a
a = copy.deepcopy(orig); del a[2]; attacks["delete a middle record (P-3)"] = a
a = copy.deepcopy(orig)[:-1]; attacks["delete the LAST record (P-6)"] = a
a = copy.deepcopy(orig); a[1], a[2] = a[2], a[1]; attacks["re-order two records"] = a
attacks["re-run whole sequence with the device key"] = make_records(results=["violet"] * 5 + ["no change"])

print(f"{'attack':44s} {'A: hash only':>13s} {'B: signed chain':>16s} {'C: chain + anchor':>18s}")
for name, recs in attacks.items():
    res = [("caught" if not f(recs, anc) else "MISSED") for f in (check_A, check_B, check_C)]
    print(f"{name:44s} {res[0]:>13s} {res[1]:>16s} {res[2]:>18s}")
print("\nuntampered original passes all checks:", all(f(orig, anc) for f in (check_A, check_B, check_C)))
