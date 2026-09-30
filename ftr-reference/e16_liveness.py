"""E16: reaction liveness — can the app tell a live reaction from a staged one? (U5)

Protocol requirement being tested: capture starts BEFORE the reagent drop (the app sees the sample in the well),
continues through the reaction to the read time (NIJ: final colour generally within 1-2 min).
A genuine test shows: sample colour -> (intermediate colours) -> final colour, with the change starting after
the drop. Attacks:
  STATIC      photograph of a pre-reacted well / a screen showing one (colour constant from frame 0)
  PRE-DROP    reagent already added before capture started (colour already final at frame 0)
  SWAP        well replaced mid-capture (abrupt jump between two frames, no reaction curve)
  REPLAY      a recording of an earlier genuine reaction played back (passes colour checks -> needs other controls)
Frames: 1 fps for 90 s; per-frame measurement noise from E4/E12 (~1.5 dE00, heavier with glare);
reaction speeds 1-40 s time constants (instant to slow), incl. NIJ-style intermediate colours.
Liveness rule (deterministic): pre-drop frames match the sample colour; after the drop the colour moves
>= 8 dE00 away from it; no single-frame jump > 70% of the total change unless the reaction is fast.
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent / "research"))
import nij_colours as nc  # noqa: E402
from sim import de  # noqa: E402
from stats import fmt  # noqa: E402

rng = np.random.default_rng(1616)
N = 400
T = 90
SAMPLE = np.array([88.0, 1.0, 8.0])            # typical off-white powder in a white well
REF = [r["lab"] for r in nc.reference("Marquis") + nc.reference("Mecke") + nc.reference("Simon's")]


def noisy(L, glare=False):
    return L + rng.normal(0, 1.5 if not glare else 3.0, 3)


def genuine(fast=False):
    final = REF[rng.integers(len(REF))]
    inter = REF[rng.integers(len(REF))] if rng.random() < 0.3 else None        # intermediate colour
    drop = int(rng.integers(5, 15)); tau = rng.uniform(0.5, 2) if fast else rng.uniform(2, 40)
    seq = []
    for t in range(T):
        if t < drop:
            L = SAMPLE
        else:
            k = 1 - np.exp(-(t - drop) / tau)
            L = SAMPLE + k * (final - SAMPLE)
            if inter is not None and k < 0.6:
                L = L + np.sin(np.pi * k / 0.6) * 0.4 * (inter - L)
        seq.append(noisy(L, glare=rng.random() < 0.1))
    return np.array(seq), drop


def static():
    final = REF[rng.integers(len(REF))]
    return np.array([noisy(final) for _ in range(T)]), int(rng.integers(5, 15))


def swap(at_drop=False):
    s, drop = static()
    t = drop + 1 if at_drop else int(rng.integers(20, 60))
    s[:t] = [noisy(SAMPLE) for _ in range(t)]
    return s, drop


def is_live(seq, drop, fast_ok=True):
    pre = seq[:drop]
    if np.median([float(de(p, SAMPLE)) for p in pre]) > 6:
        return False, "no sample colour before the drop"
    raw_d = np.array([float(de(p, SAMPLE)) for p in seq])
    # v2: 3-frame rolling median so single noisy frames cannot fake an early "change start" (v1 bug, 29.5% swaps passed)
    d = np.array([np.median(raw_d[max(0, i - 1):i + 2]) for i in range(len(raw_d))])
    final_move = np.median(d[-10:])
    if final_move < 8:
        return True, "no colour change (negative result; liveness not applicable)"
    jumps = np.abs(np.diff(d))
    change_start = drop + int(np.argmax(d[drop:] > 6))
    if change_start < drop:
        return False, "change before the drop"
    if jumps.max() > 0.7 * final_move and not (fast_ok and change_start - drop <= 3):
        return False, "abrupt jump mid-capture (swap)"
    return True, "reaction observed after the drop"


cases = {"genuine (slow/normal)": lambda: genuine(False), "genuine (near-instant)": lambda: genuine(True),
         "STATIC pre-reacted well / screen": static, "SWAP well mid-capture": lambda: swap(False),
         "SWAP timed exactly at the drop": lambda: swap(True)}
print(f"E16 liveness, {N} sequences per case, 1 fps x {T} s\n")
for name, gen in cases.items():
    accepted = coloured = 0
    for _ in range(N):
        seq, drop = gen()
        ok, why = is_live(seq, drop)
        moved = np.median([float(de(p, SAMPLE)) for p in seq[-10:]]) >= 8
        coloured += moved
        accepted += ok and moved                    # what matters: a coloured (e.g. positive) result accepted as live
    label = "genuine coloured reactions accepted" if name.startswith("genuine") else "FAKE coloured results accepted"
    print(f"  {name:34s} {label}: {fmt(accepted, coloured)}")
print("\n  REPLAY of a genuine recording: passes by construction -> needs non-colour controls "
      "(device-signed capture session, sensor timestamps, video cross-link)")
