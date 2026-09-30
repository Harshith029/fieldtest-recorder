"""FieldTest Recorder: end-to-end demo of the core workflow, using the real reference code.

One seizure, two officers, two phones, three packets, NCB Narcotic Drugs Detection Kit:
  guided test (printed flow chart) -> photo of card + sample well + blank well -> colour reading (RAW tier)
  -> blank-relative colour-band decision -> signed, chained record (time, GPS, officer, image hash)
  -> panchnama anchor code -> searchable log -> offline verification -> tampering attempts caught.

SIMULATED: the photos (rendered with a camera-sensor model; no real reagents are ever used) and the device
keys (software keys; the real app uses Android hardware keys with attestation, tested separately in E15).
Everything else (card detection, colour correction, decisions, records, anchor, log, verifier) is the actual code.

Usage:  python demo/run_demo.py            -> writes demo/output/report.html and report.json
"""
from __future__ import annotations

import base64
import copy
import html
import json
import sys
import time
import warnings
from pathlib import Path

import cv2
import numpy as np
from cryptography.hazmat.primitives.asymmetric import ec

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / "ftr-reference"
sys.path[:0] = [str(REF), str(REF / "research")]

import bands  # noqa: E402
import colour_engine as ce  # noqa: E402
import kit_profile as kp  # noqa: E402
import nddk  # noqa: E402
import nij_colours as nc  # noqa: E402
import photo_sim as ps  # noqa: E402
import record_core as rc  # noqa: E402
import sim  # noqa: E402
from record_log import RecordLog  # noqa: E402

SEED = 2026
T0 = 1_790_730_000_000                                   # 30 Sep 2026, ~11:50 IST (demo clock)
KIT_BATCH = "NDDK-2026-07"
CRIME_NO = "NCB/DZU/112/2026"
OP = "OP-DZU-2026-0931"
DEMO_FIX = (28.6448, 77.2167)                            # demo GNSS position (New Delhi)
CHART = {o[0]: np.array(o[2], float) for outs in nddk.CHART.values() for o in outs}
LIGHT = "White LED torch (LED-B3)"


def load_profiles():
    return {t: kp.KitProfile.from_dict(json.loads((REF / "profiles" / f"nddk-test-{t}.json").read_text()))
            for t in nddk.CHART}


class Phone:
    """An officer's phone: device key, hash-chained records, local searchable log, clock."""

    def __init__(self, device_id, officer_id):
        self.dev = rc.Device(device_id, ec.generate_private_key(ec.SECP256R1()))
        self.officer = officer_id
        self.log = RecordLog(rc.pub_pem(self.dev.key))
        self.clock = T0
        self.images = {}

    def tick(self, seconds):
        self.clock += seconds * 1000
        return self.clock

    def record(self, kind, payload, image_bytes=None):
        rec = self.dev.append(kind, payload, image_bytes)
        if kind == "test":
            self.log.add(rec)
        if image_bytes is not None:
            self.images[rec["payload"]["image_sha256"]] = image_bytes
        return rec


def photo(sample_lab):
    """Render a phone photo: card + SAMPLE well (W1) + reagent-only BLANK well (W2). Returns jpeg array, raw, bytes."""
    wells = np.vstack([ps.jitter(nc.reflectance(sample_lab)), ps.jitter(nc.reflectance(bands.WHITE))])
    jpeg, _, raw = ps.render(sim.ILL[LIGHT], wells, sim.random_conditions(), glare_on=False, noise=0.01, return_raw=True)
    ok, buf = cv2.imencode(".jpg", cv2.cvtColor(jpeg, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 92])
    return jpeg, raw, buf.tobytes()


def capture_and_sign(phone, profiles, package, test, sample_lab, captures):
    """Capture (retake if the card is not found), read, decide, sign. Rejected shots stay in the chain."""
    for attempt in range(1, 4):
        jpeg, raw, jpg_bytes = photo(sample_lab)
        res = ce.read_capture_linear(jpeg, raw, profiles[test]) if test in profiles else None
        t = phone.tick(45)
        base = rc.test_payload(OP, package, phone.officer, t, rc.location_fix(*DEMO_FIX, 6.5), gnss_time_ms=t,
                               crime_no=CRIME_NO, kit_batch=KIT_BATCH, test=test, capture_tier="raw",
                               place_note="Paharganj godown, New Delhi (demo)")
        if res is not None and not res.accepted:
            rec = phone.record("test", {**base, "outcome": "inconclusive", "reason": f"capture_rejected:{res.reason}",
                                        "retake": attempt}, jpg_bytes)
            captures.append(dict(package=package, test=test, attempt=attempt, jpeg=jpeg, outcome="retake needed",
                                 reason=res.reason, consistent=[], lab=None, blank=None, counter=rec["body"]["counter"],
                                 device=phone.dev.device_id))
            continue
        if res is None:                                      # Test C/D: chart not printed in the guide
            outcome, reason, cons = nddk.classify_step(profiles, test, None, None)
            lab = blank = None
            fit = None
        else:
            w1, w2 = res.wells
            outcome, reason, cons = w1.outcome, w1.reason, w1.consistent_with or []
            lab, blank, fit = w1.lab, w2.lab, res.card_fit_de
        payload = {**base, "outcome": outcome, "reason": reason, "consistent_with": cons,
                   "profile": f"nddk-test-{test}@v1" if test in profiles else "none"}
        if lab is not None:
            payload["lab_x100"] = [int(round(v * 100)) for v in lab]
            payload["blank_lab_x100"] = [int(round(v * 100)) for v in blank]
            payload["card_fit_x100"] = int(round(fit * 100))
        rec = phone.record("test", payload, jpg_bytes)
        captures.append(dict(package=package, test=test, attempt=attempt, jpeg=jpeg, outcome=outcome, reason=reason,
                             consistent=cons, lab=lab, blank=blank, counter=rec["body"]["counter"], device=phone.dev.device_id))
        return outcome, reason, cons
    return "inconclusive", "capture failed 3 times", []


def thumb(jpeg, width=360):
    h, w = jpeg.shape[:2]
    small = cv2.resize(jpeg, (width, int(h * width / w)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", cv2.cvtColor(small, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 85])
    return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode()


def run(out_dir: Path = ROOT / "demo" / "output", seed: int = SEED, write=True) -> dict:
    ps.reseed(seed)
    sim.rng = np.random.default_rng(seed)
    profiles = load_profiles()
    t_start = time.perf_counter()

    # --- trust roots: NCB signs the supervisor list; the supervisor binds officer + device + key
    ncb, sup = ec.generate_private_key(ec.SECP256R1()), ec.generate_private_key(ec.SECP256R1())
    slist = rc.make_supervisor_list(ncb, {"SUP-DZU-01": rc.pub_pem(sup)}, version=1)
    phone_a, phone_b = Phone("PHONE-A", "OFF-101"), Phone("PHONE-B", "OFF-102")
    bindings = {p.dev.device_id: rc.make_binding("SUP-DZU-01", sup, p.officer, p.dev.device_id, rc.pub_pem(p.dev.key),
                                                 "2026-09-01T00:00:00+05:30") for p in (phone_a, phone_b)}

    # --- an earlier, unrelated case on phone A (must stay private when this raid goes to court)
    phone_a.record("open", {"operation_id": "OP-DZU-2026-0870", "officer_id": "OFF-101", "device_time_ms": T0 - 9 * 86_400_000})
    _, _, earlier = photo(bands.WHITE)
    phone_a.record("test", rc.test_payload("OP-DZU-2026-0870", "P-1", "OFF-101", T0 - 9 * 86_400_000 + 60_000,
                                           rc.location_fix(28.70, 77.10, 8.0), crime_no="NCB/DZU/098/2026",
                                           outcome="negative", reason="no_colour_change", test="A"), earlier)
    phone_a.record("close", {"operation_id": "OP-DZU-2026-0870", "officer_id": "OFF-101", "device_time_ms": T0 - 9 * 86_400_000 + 600_000})

    # --- this raid
    for p in (phone_a, phone_b):
        p.record("open", {"operation_id": OP, "officer_id": p.officer, "crime_no": CRIME_NO, "device_time_ms": p.tick(0)})
    packets = [  # (phone, package, nature of material, truth: sample colour per test; None = no reaction)
        (phone_a, "P-1", "resin or powder (opiate suspected)", {"A": bands.amount_series(CHART["morphine"], 1.2)}),
        (phone_a, "P-2", "resin or powder (opiate suspected)", {}),
        (phone_b, "P-3", "tablets, capsules, powders, liquids", {"A": bands.amount_series(CHART["amphetamines"], 1.0)}),
    ]
    captures, per_packet = [], []
    for phone, pkg, nature, truth in packets:
        flow = nddk.run_flow(nature, lambda test: capture_and_sign(phone, profiles, pkg, test,
                                                                   truth.get(test, bands.WHITE), captures))
        per_packet.append(dict(package=pkg, device=phone.dev.device_id, nature=nature, path=flow["path"],
                               candidates=flow["candidates"], quantity_warning=flow["quantity_warning"]))
    for p in (phone_a, phone_b):
        p.record("close", {"operation_id": OP, "officer_id": p.officer, "crime_no": CRIME_NO, "device_time_ms": p.tick(120)})

    # --- close: anchor into the witness-signed panchnama
    anchor = rc.make_anchor(OP, [phone_a.dev, phone_b.dev])
    code = anchor["handwritten_code"]
    bundle = {"supervisor_list": slist, "bindings": bindings,
              "records": rc.disclose(phone_a.dev.records, OP) + rc.disclose(phone_b.dev.records, OP),
              "images": {**phone_a.images, **phone_b.images}, "anchor_qr": anchor["qr"]}
    ncb_pub = rc.pub_pem(ncb)
    # only this raid's photos travel with the bundle
    op_hashes = {r["payload"]["image_sha256"] for r in bundle["records"] if "payload" in r and "image_sha256" in r["payload"]}
    bundle["images"] = {h: b for h, b in bundle["images"].items() if h in op_hashes}

    # --- offline verification (software demo keys -> test-flag attestation; E15 covers real attestation chains)
    verdict = rc.verify_bundle(bundle, ncb_pub, rc.format_code(code), attestation_policy="test-flag")

    # --- tampering attempts
    def attempt(name, mutate, use_code=None):
        b = copy.deepcopy(bundle)
        mutate(b)
        try:
            rc.verify_bundle(b, ncb_pub, use_code or code, attestation_policy="test-flag")
            return {"attack": name, "result": "NOT CAUGHT"}
        except rc.VerificationError as e:
            return {"attack": name, "result": "caught", "why": str(e)}

    def first_positive(b):
        return next(r for r in b["records"] if r.get("payload", {}).get("outcome") == "positive")

    tamper = [
        attempt("Change a positive result to negative", lambda b: first_positive(b)["payload"].__setitem__("outcome", "negative")),
        attempt("Delete the no-reaction record of P-2", lambda b: b["records"].remove(
            next(r for r in b["records"] if r.get("payload", {}).get("package") == "P-2"
                 and r["payload"].get("outcome") == "negative"))),
        attempt("Replace the photo of a test", lambda b: first_positive(b)["payload"].__setitem__(
            "image_sha256", rc.sha256_hex(b"another photo"))),
        attempt("Hide phone B's records", lambda b: b.__setitem__("records", [r for r in b["records"] if r["body"]["device_id"] != "PHONE-B"])),
    ]
    typo = code[:4] + ("A" if code[4] != "A" else "B") + code[5:]
    try:
        rc.verify_bundle(bundle, ncb_pub, typo, attestation_policy="test-flag")
        typo_msg = "NOT CAUGHT"
    except rc.VerificationError as e:
        typo_msg = str(e)

    # --- the officer's searchable log (on phone A)
    searches = {q: [(h["package"], h.get("test"), h["outcome"]) for h in phone_a.log.search(**q_args)]
                for q, q_args in {"heroin": {"text": "heroin"}, "Paharganj": {"text": "Paharganj"},
                                  "outcome = negative": {"outcome": "negative"}}.items()}
    opened = phone_a.log.open(phone_a.log.search(outcome="positive")[0]["hash"])

    summary = {
        "operation": OP, "crime_no": CRIME_NO, "kit_batch": KIT_BATCH, "light": LIGHT, "seed": seed,
        "captures": [{k: (v if k != "jpeg" else None) for k, v in c.items() if k != "jpeg"} for c in captures],
        "packets": per_packet, "panchnama_code": rc.format_code(code), "verification": verdict,
        "tampering": tamper, "typo_in_code": typo_msg, "searches": searches,
        "log_open_reverifies": opened["verified"], "records_on_phones": {"PHONE-A": phone_a.dev.counter, "PHONE-B": phone_b.dev.counter},
        "seconds": round(time.perf_counter() - t_start, 1),
    }
    for c in summary["captures"]:
        for k in ("lab", "blank"):
            if c[k] is not None:
                c[k] = [round(float(v), 1) for v in c[k]]
    if write:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "report.json").write_text(json.dumps(summary, indent=1, default=str))
        (out_dir / "report.html").write_text(render_html(summary, captures), encoding="utf-8")
        cv2.imwrite(str(out_dir / "captures.png"), cv2.cvtColor(contact_sheet(captures, summary), cv2.COLOR_RGB2BGR))
    return summary


def contact_sheet(captures, s, tile_w=420):
    """One image with every capture and what the engine decided (for the README; generated, not drawn by hand)."""
    colour = {"positive": (179, 38, 30), "negative": (27, 122, 77)}
    tiles = []
    for c in captures:
        h, w = c["jpeg"].shape[:2]
        img = cv2.resize(c["jpeg"], (tile_w, int(h * tile_w / w)), interpolation=cv2.INTER_AREA)
        band = np.full((96, tile_w, 3), 255, np.uint8)
        col = colour.get(c["outcome"], (138, 90, 0))
        cv2.putText(band, f"{c['package']}  Test {c['test']}  ({c['device']} #{c['counter']})", (10, 24),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (28, 36, 48), 1, cv2.LINE_AA)
        cv2.putText(band, f"{c['outcome'].upper()}  {c['reason']}", (10, 52), cv2.FONT_HERSHEY_SIMPLEX, 0.55, col, 2, cv2.LINE_AA)
        cons = ", ".join(c["consistent"]) or "-"
        cv2.putText(band, f"consistent with: {cons}"[:58], (10, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (93, 104, 117), 1, cv2.LINE_AA)
        tiles.append(np.vstack([img, band]))
    th = max(t.shape[0] for t in tiles)
    tiles = [np.vstack([t, np.full((th - t.shape[0], tile_w, 3), 255, np.uint8)]) for t in tiles]
    cols = 3
    while len(tiles) % cols:
        tiles.append(np.full((th, tile_w, 3), 245, np.uint8))
    rows = [np.hstack(tiles[i:i + cols]) for i in range(0, len(tiles), cols)]
    sheet = np.vstack(rows)
    head = np.full((70, sheet.shape[1], 3), 255, np.uint8)
    cv2.putText(head, f"FieldTest Recorder demo: {s['operation']}  |  panchnama code {s['panchnama_code']}  |  "
                      f"offline verification: {s['verification']['status']}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (31, 78, 140), 2, cv2.LINE_AA)
    cv2.putText(head, "SIMULATED photos (camera-sensor model); decisions, signatures and verification are the real reference code",
                (10, 58), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (138, 90, 0), 1, cv2.LINE_AA)
    return np.vstack([head, sheet])


def render_html(s, captures):
    e = html.escape
    pill = lambda o: {"positive": "pos", "negative": "neg"}.get(o, "inc")
    rows = "".join(
        f"<tr><td>{e(c['device'])} #{c['counter']}</td><td>{e(c['package'])}</td><td>Test {e(c['test'])}"
        f"{' (retake ' + str(c['attempt']) + ')' if c['outcome'] == 'retake needed' else ''}</td>"
        f"<td><img src='{thumb(c['jpeg'])}' alt='simulated photo of {e(c['package'])} test {e(c['test'])}'></td>"
        f"<td>{'' if c['lab'] is None else 'L* {:.1f}  a* {:.1f}  b* {:.1f}'.format(*c['lab'])}<br>"
        f"<span class='mute'>{'' if c['blank'] is None else 'blank: L* {:.1f}  a* {:.1f}  b* {:.1f}'.format(*c['blank'])}</span></td>"
        f"<td><span class='pill {pill(c['outcome'])}'>{e(c['outcome'])}</span><br><span class='mute'>{e(c['reason'])}</span></td>"
        f"<td>{e(', '.join(c['consistent'])) or '—'}</td></tr>" for c in captures)
    packets = "".join(
        f"<tr><td>{e(p['package'])}</td><td>{e(p['nature'])}</td>"
        f"<td>{' → '.join(e(f'Test {t}: {o}') for _, t, o in p['path'] if t)} → <b>{e(p['path'][-1][0])}</b></td>"
        f"<td>{e(', '.join(p['candidates'])) or '—'}</td><td>{e(p['quantity_warning'] or 'category decidable')}</td></tr>"
        for p in s["packets"])
    tam = "".join(f"<tr><td>{e(t['attack'])}</td><td><span class='pill {'pos' if t['result'] == 'caught' else 'neg'}'>{e(t['result'])}</span></td>"
                  f"<td class='mute'>{e(t.get('why', ''))}</td></tr>" for t in s["tampering"])
    srch = "".join(f"<tr><td>{e(q)}</td><td>{e('; '.join(f'{a} Test {b}: {c}' for a, b, c in r)) or 'no match'}</td></tr>"
                   for q, r in s["searches"].items())
    v = s["verification"]
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>FieldTest Recorder demo report</title>
<style>
:root{{--ink:#1c2430;--mute:#5d6875;--line:#d5dbe3;--bg:#f5f7fa;--card:#fff;--blue:#1f4e8c;--pos:#b3261e;--neg:#1b7a4d;--inc:#8a5a00}}
body{{font:14px/1.5 system-ui,-apple-system,Segoe UI,Arial,sans-serif;color:var(--ink);background:var(--bg);margin:0;padding:24px 16px}}
main{{max-width:1100px;margin:auto;display:grid;gap:18px}}
h1{{margin:0;font-size:26px}} h2{{margin:0 0 8px;font-size:18px;color:var(--blue)}}
section{{background:var(--card);border:1px solid var(--line);border-radius:6px;padding:16px;overflow-x:auto}}
table{{border-collapse:collapse;width:100%;min-width:720px}} td,th{{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}}
th{{font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--mute)}} img{{width:180px;border-radius:4px}}
.mute{{color:var(--mute);font-size:12px}} .pill{{display:inline-block;padding:0 8px;border-radius:999px;color:#fff;font-size:12px}}
.pos{{background:var(--pos)}} .neg{{background:var(--neg)}} .inc{{background:var(--inc)}}
.code{{font:600 28px/1.2 ui-monospace,Consolas,monospace;letter-spacing:.08em}} .note{{border-left:4px solid var(--inc);padding-left:10px}}
</style></head><body><main>
<header><h1>FieldTest Recorder: end-to-end demo</h1>
<p class="mute">Operation {e(s['operation'])} · {e(s['crime_no'])} · NCB Narcotic Drugs Detection Kit batch {e(s['kit_batch'])} · light: {e(s['light'])} · seed {s['seed']} · ran in {s['seconds']} s</p>
<p class="note"><b>What is simulated:</b> the photos (rendered with a camera-sensor model; the team never handles drugs) and the device keys (software keys; the app uses Android hardware keys, verified separately in E15). Chart colours for the kit come from a scanned printed chart and are approximate. <b>Everything else is the real reference code:</b> card detection, colour correction, blank-relative colour bands, the printed flow chart, signing, chaining, anchor, search and the offline verifier.</p></header>
<section><h2>1. Every capture, as read by the engine (sample well W1 vs blank well W2)</h2><table>
<tr><th>Record</th><th>Packet</th><th>Test</th><th>Photo (simulated)</th><th>Reading (CIELAB)</th><th>Result</th><th>Consistent with</th></tr>{rows}</table></section>
<section><h2>2. Per packet: printed flow chart, combined candidates, NDPS quantity check</h2><table>
<tr><th>Packet</th><th>Material</th><th>Path followed</th><th>Candidates</th><th>Quantity category</th></tr>{packets}</table></section>
<section><h2>3. Panchnama code (written in and signed by the witnesses)</h2><p class="code">{e(s['panchnama_code'])}</p>
<p class="mute">65 bits of the anchor digest plus a check character. It fixes every phone's record range and chain head for this operation.</p></section>
<section><h2>4. Offline verification (what a court expert runs)</h2>
<p><span class="pill neg">{e(v['status'])}</span> {v['devices']} phones · {v['disclosed']} records of this operation disclosed · {v['withheld_other_cases']} records of another case withheld (hashes only) · flags: {e('; '.join(v['flags']) or 'none')}</p>
<p class="mute">A one-character typo in the code: {e(s['typo_in_code'])}</p></section>
<section><h2>5. Tampering attempts on the same bundle</h2><table><tr><th>Attempt</th><th>Result</th><th>Why</th></tr>{tam}</table></section>
<section><h2>6. Searchable log on phone A (offline)</h2><table><tr><th>Query</th><th>Results</th></tr>{srch}</table>
<p class="mute">Opening a record re-verifies its signature and hash: {e(str(s['log_open_reverifies']))}</p></section>
</main></body></html>"""


if __name__ == "__main__":
    s = run()
    print(f"operation {s['operation']}: {len(s['captures'])} captures, records on phones {s['records_on_phones']}")
    for p in s["packets"]:
        print(f"  {p['package']}: {' -> '.join(f'{t}:{o}' for _, t, o in p['path'] if t)} -> {p['path'][-1][0]} | "
              f"candidates {p['candidates']} | {p['quantity_warning'] or 'quantity category decidable'}")
    print(f"panchnama code {s['panchnama_code']}; verification {s['verification']['status']} "
          f"({s['verification']['disclosed']} disclosed, {s['verification']['withheld_other_cases']} withheld)")
    for t in s["tampering"]:
        print(f"  tamper: {t['attack']}: {t['result']}")
    print(f"  typo in code: {s['typo_in_code']}")
    print(f"report: {ROOT / 'demo' / 'output' / 'report.html'} ({s['seconds']} s)")
