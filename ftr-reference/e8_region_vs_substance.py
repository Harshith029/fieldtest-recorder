"""E8: substance-nearest classifier (old) vs colour-group classifier (new), same rendered photos.

Ground truth for the colour-group question: is the substance's REFERENCE colour inside the positive colour
group (within R of a target's colour)? Substances that are chemically indistinguishable from the target
(e.g. ephedrine vs cocaine with cobalt thiocyanate) are truly "positive pattern" -- that is the kit's
limitation, which the app must report as 'also consistent with', not hide.
Also saves per-well features (raw well RGB, raw card patches, corrected Lab) for E7 (ML vs card).
"""
import csv
import sys
import warnings
from collections import Counter
from pathlib import Path

import numpy as np

warnings.filterwarnings("ignore")
sys.argv += [] if len(sys.argv) > 1 else ["Marquis"]
REAGENT = sys.argv[1]
N = int(sys.argv[2]) if len(sys.argv) > 2 else 200
R = float(sys.argv[3]) if len(sys.argv) > 3 else 6.0

import importlib.util  # noqa: E402

spec = importlib.util.spec_from_file_location("e6", Path(__file__).parent / "e6_nij_colours.py")
# reuse E6's data loading (Munsell -> Lab, reflectances) without running its photo loop
src = open(Path(__file__).parent / "e6_nij_colours.py", encoding="utf-8").read().split("out_dir = ")[0]
g = {"__name__": "e6data", "__file__": str(Path(__file__).parent / "e6_nij_colours.py")}
sys.argv = [sys.argv[0], REAGENT, "0"]
exec(compile(src, "e6_nij_colours.py", "exec"), g)
outcomes, REFL, PROFILE, pos, neg = g["outcomes"], g["REFL"], g["PROFILE"], g["pos"], g["neg"]
sim, ce, photo_sim = g["sim"], g["ce"], g["photo_sim"]
photo_sim.reseed(7 + hash(REAGENT) % 1000)

REF = [(a, cls == "positive", L) for a, cls, L, _, _ in outcomes]
pos_labs = [L for a, t, L in REF if t]
truth_group = {a: ("positive" if min(float(sim.de(L, p)) for p in pos_labs) <= R else "negative") for a, t, L in REF}
cross = sorted(a for a, t, L in REF if not t and truth_group[a] == "positive")
print(f"== {REAGENT}: R={R}; known cross-reactants in the positive colour group: {cross or 'none'}")

LIGHTS = [l for l in sim.ILL if "Sodium" not in l]
feats = []
old, new = Counter(), Counter()
attrib_ok = attrib_n = 0
yy, xx = photo_sim.yy, photo_sim.xx
for n in range(N):
    light = LIGHTS[n % len(LIGHTS)]
    truth = [(pos if photo_sim.rng.random() < 0.5 else neg) for _ in range(2)]
    truth = [grp[photo_sim.rng.integers(0, len(grp))] for grp in truth]
    wells = np.vstack([photo_sim.jitter(REFL[t[0]]) for t in truth])
    img, _ = photo_sim.render(sim.ILL[light], wells, sim.random_conditions(), glare_on=photo_sim.rng.random() < 0.2, noise=0.01)
    res = ce.read_capture(img, PROFILE)
    if not res.accepted:
        continue
    card = ce.rectify(img)
    patches = np.array([np.median(card[y + h // 4:y + 3 * h // 4, x + w // 4:x + 3 * w // 4].reshape(-1, 3), 0)
                        for x, y, w, h in (ce.patch_rect(i) for i in range(24))]) / 255.0
    for w, t in zip(res.wells, truth):
        substance, subst_cls = t[0], t[1]
        g_truth = truth_group[substance]
        # OLD: substance-nearest, judged against the substance's class
        o = w.outcome
        old["inconclusive" if o == "inconclusive" else ("correct" if o == subst_cls else "wrong")] += 1
        # NEW: colour group, judged against the colour-group truth
        if w.lab is None:
            new["inconclusive"] += 1
            continue
        L = np.array(w.lab)
        out, reason, consistent, dp, do = ce.classify_region(L, REF, R=R)
        new["inconclusive" if out == "inconclusive" else ("correct" if out == g_truth else "wrong")] += 1
        if out == "positive":
            attrib_n += 1
            attrib_ok += substance in consistent
        cx, cy = ce.WELLS[w.well]
        m = (xx - cx) ** 2 + (yy - cy) ** 2 <= (0.6 * ce.WELL_R) ** 2
        raw = np.median(card[m].astype(float), 0) / 255.0
        feats.append([light, substance, g_truth, *raw, *patches.flatten(), *L])

for name, c in (("OLD substance-nearest (vs substance class)", old), ("NEW colour group (vs colour-group truth)", new)):
    t = sum(c.values())
    print(f"  {name:44s} correct {100 * c['correct'] / t:5.1f}%  inconclusive {100 * c['inconclusive'] / t:5.1f}%  wrong {100 * c['wrong'] / t:5.1f}%  (n={t})")
if attrib_n:
    print(f"  positive calls whose 'also consistent with' list contains the true substance: {attrib_ok}/{attrib_n}")
out = Path(__file__).parent / "results" / f"e8_features_{REAGENT.replace(' ', '_').replace(chr(39), '')}.csv"
with open(out, "w", newline="", encoding="utf-8") as f:
    csv.writer(f).writerows(feats)
