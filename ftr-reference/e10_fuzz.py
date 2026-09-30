"""E10: malicious / corrupt inputs. Nothing may crash; everything must fail closed with a clear reason.

Part 1: colour engine with hostile images. Part 2: offline verifier with malformed bundles.
"""
import copy
import random
import sys
import traceback
import warnings
from pathlib import Path

import cv2
import numpy as np

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).parent / "research"))
import colour_engine as ce  # noqa: E402
import record_core as rc  # noqa: E402

PROFILE = [("violet", "positive", np.array([30.0, 40.0, -45.0])), ("no change", "negative", np.array([92.0, 0.0, 6.0]))]
rs = np.random.default_rng(5)


def card_image(shuffle_markers=False, grey_patches=False):
    img = np.full((ce.CARD_H, ce.CARD_W, 3), 230, np.uint8)
    ids = [0, 1, 2, 3]
    if shuffle_markers:
        ids = [3, 2, 1, 0]
    for pos_id, mid in zip(ce.MARKERS, ids):
        x, y = ce.MARKERS[pos_id]
        m = cv2.aruco.generateImageMarker(ce.ARUCO, mid, ce.MARKER)
        img[y:y + ce.MARKER, x:x + ce.MARKER] = m[..., None]
    for i in range(24):
        x, y, w, h = ce.patch_rect(i)
        img[y:y + h, x:x + w] = 128 if grey_patches else rs.integers(0, 255, 3)
    return cv2.copyMakeBorder(img, 100, 100, 100, 100, cv2.BORDER_CONSTANT, value=(40, 40, 40))


hostile_images = {
    "random noise": rs.integers(0, 256, (1200, 1600, 3), dtype=np.uint8),
    "all black": np.zeros((1200, 1600, 3), np.uint8),
    "all white (overexposed)": np.full((1200, 1600, 3), 255, np.uint8),
    "1x1 pixel": np.zeros((1, 1, 3), np.uint8),
    "very large 4000x3000": rs.integers(0, 256, (3000, 4000, 3), dtype=np.uint8),
    "markers in wrong corners (forged/misprinted card)": card_image(shuffle_markers=True),
    "card with grey patches (fake/faded card)": card_image(grey_patches=True),
    "card with random patch colours": card_image(),
}
print("Part 1: colour engine vs hostile images")
crashes = 0
for name, img in hostile_images.items():
    try:
        r = ce.read_capture(img, PROFILE)
        verdict = f"accepted={r.accepted} reason={r.reason}" + (f" fit={r.card_fit_de}" if r.card_fit_de else "")
    except Exception as e:  # noqa: BLE001
        crashes += 1
        verdict = f"CRASH {type(e).__name__}: {e}"
    print(f"  {name:48s} -> {verdict}")
for name, data in {"truncated JPEG": cv2.imencode(".jpg", hostile_images["random noise"])[1].tobytes()[:5000],
                   "not an image (text)": b"GIF89a; <script>alert(1)</script>", "empty bytes": b""}.items():
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR) if data else None
    print(f"  {name:48s} -> decoder returned {'None (rejected before the engine)' if img is None else img.shape}")

# ---------------- Part 2: verifier with malformed bundles
print("\nPart 2: offline verifier vs malformed bundles")
import test_integrity as ti  # builds a valid scenario  # noqa: E402

good = ti.S["bundle"]; code = ti.S["code"]; ncb = ti.NCB_PUB
mutations = {
    "missing supervisor_list": lambda b: b.pop("supervisor_list"),
    "records is not a list": lambda b: b.__setitem__("records", "oops"),
    "record without body": lambda b: b["records"][0].pop("body"),
    "counter is a string": lambda b: b["records"][0]["body"].__setitem__("counter", "1"),
    "signature not base64": lambda b: b["records"][0].__setitem__("sig", "%%%notb64%%%"),
    "binding with garbage public key": lambda b: b["bindings"]["DEV-1"]["body"].__setitem__("device_pub", "-----BEGIN PUBLIC KEY-----\nAAAA\n-----END PUBLIC KEY-----\n"),
    "anchor heads missing": lambda b: b["anchor_qr"].pop("heads"),
    "image entry is not bytes": lambda b: b["images"].__setitem__(next(iter(b["images"])), 12345),
    "10,000 junk records (DoS attempt)": lambda b: b["records"].extend([{"body": {"device_id": "DEV-1"}, "sig": "x"}] * 10_000),
    "payload is not an object": lambda b: b["records"][-1].__setitem__("payload", ["x"]),
    "extra field in signed header": lambda b: b["records"][0]["body"].__setitem__("note", "x"),
    "integer above 2^53 in header": lambda b: b["records"][0]["body"].__setitem__("counter", 2**53 + 1),
    "anchor range is a string": lambda b: b["anchor_qr"]["heads"][0].__setitem__("first_counter", "1"),
}
unhandled = 0
for name, mut in mutations.items():
    b = copy.deepcopy(good)
    mut(b)
    try:
        rc.verify_bundle(b, ncb, code, attestation_policy="test-flag")
        res = "ACCEPTED (bad!)"
    except rc.VerificationError as e:
        res = f"rejected cleanly: {e}"
    except Exception as e:  # noqa: BLE001
        unhandled += 1
        res = f"UNHANDLED {type(e).__name__}: {e}"
    print(f"  {name:36s} -> {res[:110]}")
print(f"\nengine crashes: {crashes}; verifier unhandled exceptions: {unhandled}")
