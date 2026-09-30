"""Run the colour engine on REAL phone photos of the printed card (real-phone capture protocol).

  python read_photos.py --photos <folder> --profile profiles/demo-marquis-rule.json --out results/real_phone.csv
  python read_photos.py --selftest            # renders synthetic photos and runs the same path (install check)

JPEG/PNG go through the JPEG path; .dng files go through the RAW/linear path if `rawpy` is installed.
File names following <phone>_<light>_<cupA>-<cupB>_<variant>.<ext> also get a reproducibility summary:
for each cup, the spread (dE00) of its readings across phones, lights and variants.
"""
import argparse
import csv
import itertools
import json
import re
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE / "research"))
import colour_engine as ce  # noqa: E402
import kit_profile as kp  # noqa: E402
from sim import de, srgb_encode  # noqa: E402

NAME_RX = re.compile(r"^(?P<phone>[^_]+)_(?P<light>[^_]+)_(?P<a>[^-_]+)-(?P<b>[^_]+)_(?P<variant>[^.]+)$")


def load_dng(path):
    try:
        import rawpy
    except ImportError:
        return None, "rawpy not installed (pip install rawpy) - DNG skipped"
    with rawpy.imread(str(path)) as r:
        lin = r.postprocess(gamma=(1, 1), no_auto_bright=True, output_bps=16, use_camera_wb=True).astype(np.float32) / 65535
    preview = (np.clip(srgb_encode(lin / max(lin.max(), 1e-6)), 0, 1) * 255).astype(np.uint8)
    return (preview, lin), None


def read(path, profile):
    if path.suffix.lower() == ".dng":
        data, err = load_dng(path)
        if data is None:
            return None, err
        return ce.read_capture_linear(data[0], data[1], profile), "RAW"
    bgr = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if bgr is None:
        return None, "not a readable image"
    return ce.read_capture(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB), profile), "JPEG"


def run(photos: Path, profile_path: Path, out: Path):
    profile = kp.KitProfile.from_dict(json.loads(profile_path.read_text()))
    rows, cups = [], defaultdict(list)
    files = sorted(p for p in photos.iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".dng"))
    for f in files:
        res, mode = read(f, profile)
        if res is None:
            rows.append([f.name, "", "error", mode] + [""] * 9); continue
        m = NAME_RX.match(f.stem)
        if not res.accepted:
            rows.append([f.name, mode, "rejected", res.reason, res.card_fit_de, res.sharpness] + [""] * 7); continue
        for w, cup in zip(res.wells, (m.group("a"), m.group("b")) if m else ("", "")):
            L = w.lab or ("", "", "")
            rows.append([f.name, mode, "ok", "", res.card_fit_de, res.sharpness, w.well, cup, *L, w.outcome,
                         w.reason + (" | also consistent with: " + ", ".join(w.consistent_with) if w.consistent_with else "")])
            if cup and w.lab:
                cups[(cup, mode)].append(np.array(w.lab))
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as fh:
        wr = csv.writer(fh)
        wr.writerow(["file", "mode", "status", "reject_reason", "card_fit_dE", "sharpness", "well", "cup",
                     "L", "a", "b", "outcome", "reason"])
        wr.writerows(rows)
    ok = sum(1 for r in rows if r[2] == "ok")
    print(f"{len(files)} photos, {ok} well readings -> {out}")
    rej = defaultdict(int)
    for r in rows:
        if r[2] == "rejected":
            rej[r[3]] += 1
    print("rejected photos by reason:", dict(rej) or "none")
    if cups:
        print("reproducibility (same cup across phones/lights/variants), dE00 median / 95th:")
        for (cup, mode), labs in sorted(cups.items()):
            if len(labs) > 1:
                d = [float(de(a, b)) for a, b in itertools.combinations(labs, 2)]
                print(f"  {cup:6s} {mode:4s} n={len(labs):3d}  {np.median(d):5.1f} / {np.percentile(d, 95):5.1f}")


def selftest():
    import photo_sim as ps
    import sim
    import nij_colours as nc
    tmp = Path(tempfile.mkdtemp())
    ref = nc.reference("Marquis")
    picks = [0, 5, 11]
    for n, light in enumerate(["Daylight (D65)", "Tube light (FL2)", "White LED torch (LED-B3)"]):
        for k in range(3):
            a, b = picks[k % 3], picks[(k + 1) % 3]
            wells = np.vstack([ps.jitter(nc.reflectance(ref[i]["lab"])) for i in (a, b)])
            img, _ = ps.render(sim.ILL[light], wells, sim.random_conditions(), glare_on=False, noise=0.01)
            cv2.imwrite(str(tmp / f"sim{k}_{light.split(' ')[0].lower()}_C{a:02d}-C{b:02d}_normal.jpg"),
                        cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
    run(tmp, HERE / "profiles" / "demo-marquis-rule.json", HERE / "results" / "read_photos_selftest.csv")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--photos", type=Path)
    ap.add_argument("--profile", type=Path, default=HERE / "profiles" / "demo-marquis-rule.json")
    ap.add_argument("--out", type=Path, default=HERE / "results" / "real_phone.csv")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    selftest() if a.selftest else run(a.photos, a.profile, a.out)
