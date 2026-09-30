"""Kit profile = the published, signed colour standard for one kit step (reagent).

Contents (all signed together, integers only so canonical bytes match across languages):
  reference   documented colour table: substance, target?, CIELAB (x100), Munsell, colour name, phase
  decision    "rule"       (bootstrap, before validation data exists): group radius R and margin M
              "region_map" (after validation): frozen CIELAB lookup table learned offline, cell size 1 dE
              "band"       (kit charts give RANGES: "colour in the range X to Y"): each outcome is a band of
                           CIELAB points spanning the chart range AND 0.5-1.6x sample amount (Beer-Lambert,
                           computed once at build time by bands.py), so decisions do not hinge on lightness
  read_time_s time after reagent addition at which the final colour is read (kit instructions / NIJ 3.3)
  layout      optional: which card zone holds the reagent-only BLANK well (same photo, same light)
Every decision first compares the sample with the blank: within NO_CHANGE of it is "negative, no colour change"
(the most common real negative). The engine's answer is then a colour group (positive / negative /
inconclusive) plus every substance whose documented colour is consistent with the measurement.
"""
from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass, field

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent / "research"))
import record_core as rc  # noqa: E402
from sim import de  # noqa: E402

GROUP_R_X100 = 600          # substances within 6 dE00 of a target colour belong to the positive colour group
UNRESOLVABLE_X100 = 800     # E6/E8: below ~8 dE00 a phone reading cannot separate two colours -> ERROR
RESOLVABLE_X100 = 1000      # E12: at 8-10 dE00, 0-1.6% wrong (cobalt, RAW) -> WARN, needs validation data
NO_CHANGE_X100 = 600        # sample within 6 dE00 of the blank well = no colour change (negative)
CLEAR_CHANGE_X100 = 800     # a positive call needs the sample at least 8 dE00 away from the blank
MAP_GUARD_X100 = 1200       # a region-map "positive" must lie within 12 dE00 of a documented positive colour


@dataclass
class KitProfile:
    profile_id: str
    version: int
    reagent: str
    reference: list                       # dicts: substance, target, lab_x100 [3], munsell, colour_name, phase
    decision: dict                        # {"type": "rule"|"region_map"|"band", ...}
    read_time_s: int = 60
    signature: str | None = None
    layout: dict | None = None            # e.g. {"blank_well": "W2"}
    blank_lab_x100: list | None = None    # documented reagent-blank colour, if the kit sheet gives one
    _grid: np.ndarray | None = field(default=None, repr=False, compare=False)
    _bands: list | None = field(default=None, repr=False, compare=False)

    # ---------------- serialisation / signing
    def body(self) -> dict:
        b = {"type": "kit_profile", "profile_id": self.profile_id, "version": self.version, "reagent": self.reagent,
             "reference": self.reference, "decision": self.decision, "read_time_s": self.read_time_s}
        if self.layout is not None:
            b["layout"] = self.layout
        if self.blank_lab_x100 is not None:
            b["blank_lab_x100"] = self.blank_lab_x100
        return b

    def sign(self, key):
        self.signature = rc.sign(key, rc.canon(self.body()))
        return self

    def verify(self, authority_pub_pem: str) -> bool:
        return self.signature is not None and rc.verify_sig(authority_pub_pem, rc.canon(self.body()), self.signature)

    def to_dict(self):
        return {"body": self.body(), "sig": self.signature}

    @classmethod
    def from_dict(cls, d):
        b = d["body"]
        return cls(b["profile_id"], b["version"], b["reagent"], b["reference"], b["decision"], b["read_time_s"], d.get("sig"),
                   b.get("layout"), b.get("blank_lab_x100"))

    # ---------------- helpers
    def labs(self):
        return np.array([r["lab_x100"] for r in self.reference], float) / 100.0

    def targets(self):
        return np.array([r["target"] for r in self.reference], bool)

    def positive_group(self):
        """Target colours plus every reference colour within the group radius of a target (cross-reactants)."""
        labs, tgt = self.labs(), self.targets()
        R = GROUP_R_X100 / 100
        in_group = np.array([any(float(de(L, labs[j])) <= R for j in np.where(tgt)[0]) for L in labs])
        return in_group

    # ---------------- the decision
    def group_members(self, positive: bool):
        grp = self.positive_group()
        return sorted({r["substance"] for r, g in zip(self.reference, grp) if g == positive})

    def _consistent(self, outcome, d_all):
        """Substances to report as 'also consistent with'.

        E12 finding: on JPEG captures, out-of-gamut colours are read with a bias of ~8 dE00, so a list built
        only from distances can miss the true substance even when the decision is right. The list therefore
        comes from the profile's documented colour group (what the kit cannot tell apart); close distance
        matches are only used to narrow it, never to replace it.
        """
        R = GROUP_R_X100 / 100
        if outcome == "positive":
            return self.group_members(True)        # the kit cannot tell these apart: always list them all
        return sorted({self.reference[i]["substance"] for i in np.where(d_all <= R)[0]})

    def classify(self, L, blank_L=None):
        """Returns (outcome, reason, consistent_with).

        blank_L: the reagent-only well measured in the same photo. Without it, the documented blank colour is used
        if the profile has one; otherwise a clear well cannot be called negative and returns inconclusive.
        """
        L = np.asarray(L, float)
        if blank_L is None and self.blank_lab_x100 is not None:
            blank_L = np.array(self.blank_lab_x100, float) / 100
        d_blank = float(de(L, np.asarray(blank_L, float))) if blank_L is not None else None
        if d_blank is not None and d_blank <= NO_CHANGE_X100 / 100:
            return "negative", "no_colour_change", []
        out, reason, cons = self._decide(L)
        if out == "positive" and d_blank is not None and d_blank < CLEAR_CHANGE_X100 / 100:
            return "inconclusive", "weak_change_from_blank", cons
        if out == "inconclusive" and reason in ("unknown_colour", "outside_validated_colours") and d_blank is None:
            return "inconclusive", "no_blank_in_frame", cons
        return out, reason, cons

    def _decide(self, L):
        labs = self.labs()
        d_all = np.array([float(de(L, x)) for x in labs])
        if self.decision["type"] == "band":
            return self._band(L)
        if self.decision["type"] == "region_map":
            out = self._lookup(L)
            if out == -2:
                return "inconclusive", "outside_validated_colours", self._consistent("inconclusive", d_all)
            if out == -1:
                return "inconclusive", "uncertain_region", self._consistent("inconclusive", d_all)
            if out == 1:
                # guard (review finding): a learned map may only say positive near a documented positive colour
                if d_all[self.positive_group()].min() > MAP_GUARD_X100 / 100:
                    return "inconclusive", "map_disagrees_with_standard", self._consistent("inconclusive", d_all)
                return "positive", "in_positive_colour_group", self._consistent("positive", d_all)
            return "negative", "outside_positive_colour_group", self._consistent("negative", d_all)
        r, m = self.decision["r_x100"] / 100, self.decision["m_x100"] / 100
        grp = self.positive_group()
        d_pos = d_all[grp].min()
        d_oth = d_all[~grp].min() if (~grp).any() else 99.0
        if d_pos <= r and d_oth - d_pos >= m:
            return "positive", "in_positive_colour_group", self._consistent("positive", d_all)
        if d_oth <= r and d_pos - d_oth >= m:
            return "negative", "outside_positive_colour_group", self._consistent("negative", d_all)
        if min(d_pos, d_oth) > 2 * r:
            return "inconclusive", "unknown_colour", self._consistent("inconclusive", d_all)
        return "inconclusive", "between_groups", self._consistent("inconclusive", d_all)

    def _band(self, L):
        """Range model: inside a positive band (and not a non-target band) -> positive, listing every substance
        whose band contains the reading; overlapping positive and non-target bands -> inconclusive."""
        d = self.decision
        if self._bands is None:
            self._bands = [(o, np.array(o["points_x100"], float) / 100) for o in d["outcomes"]]
        tol, m = d["tol_x100"] / 100, d["margin_x100"] / 100
        dist = [(o, float(np.min(de(np.broadcast_to(L, pts.shape), pts)))) for o, pts in self._bands]
        pos = [(o, x) for o, x in dist if o["positive"] and x <= tol]
        neg = [(o, x) for o, x in dist if not o["positive"] and x <= tol]
        # the list errs on inclusion: every outcome within tol + margin (what the kit cannot tell apart here)
        near = lambda positive: sorted({s for o, x in dist if o["positive"] == positive and x <= tol + m
                                        for s in o["substances"]})
        dneg = min((x for o, x in dist if not o["positive"]), default=99.0)
        dpos = min((x for o, x in dist if o["positive"]), default=99.0)
        if pos and dneg - min(x for _, x in pos) >= m:
            return "positive", "in_documented_positive_range", near(True)
        if neg and dpos - min(x for _, x in neg) >= m:
            return "negative", "in_documented_non_target_range", near(False)
        if pos or neg:
            return "inconclusive", "overlapping_ranges", sorted(set(near(True)) | set(near(False)))
        return "inconclusive", "outside_documented_ranges", []

    def _lookup(self, L):
        d = self.decision
        if self._grid is None:
            raw = base64.b64decode(d["cells_b64"])
            if hashlib.sha256(raw).hexdigest() != d["cells_sha256"]:
                raise ValueError("region map corrupted")
            self._grid = np.frombuffer(raw, np.int8).reshape(d["shape"])
        idx = np.rint(np.asarray(L)).astype(int) - np.array(d["lo"])
        if np.any(idx < 0) or np.any(idx >= np.array(d["shape"])):
            return -2
        return int(self._grid[tuple(idx)])


def region_map_decision(cells: np.ndarray, lo, trained_on: str, conf_x100: int) -> dict:
    raw = cells.astype(np.int8).tobytes()
    return {"type": "region_map", "lo": [int(v) for v in lo], "shape": [int(v) for v in cells.shape],
            "cells_b64": base64.b64encode(raw).decode(), "cells_sha256": hashlib.sha256(raw).hexdigest(),
            "conf_x100": conf_x100, "trained_on": trained_on}


def lint(profile: KitProfile, resolvable_x100: int = RESOLVABLE_X100):
    """Profile checker: flags colour boundaries a phone camera cannot resolve.

    ERROR   a NON-group colour lies closer than the resolvable distance to a positive-group colour
            (readings near that boundary cannot be trusted) -> merge it into the group or accept wide abstention
    INFO    cross-reactants merged into the positive group (reported to officers as 'also consistent with')
    """
    labs, grp = profile.labs(), profile.positive_group()
    names = [r["substance"] for r in profile.reference]
    issues = []
    for i in np.where(grp)[0]:
        for j in np.where(~grp)[0]:
            dd = float(de(labs[i], labs[j]))
            if dd < UNRESOLVABLE_X100 / 100:
                issues.append(("ERROR", f"{names[j]} is {dd:.1f} dE00 from positive-group colour {names[i]} "
                                        f"(< {UNRESOLVABLE_X100 / 100:.0f}): not separable by camera; merge or drop"))
            elif dd < resolvable_x100 / 100:
                issues.append(("WARN", f"{names[j]} is {dd:.1f} dE00 from positive-group colour {names[i]} "
                                       f"({UNRESOLVABLE_X100 / 100:.0f}-{resolvable_x100 / 100:.0f}): validate before relying on it"))
    try:
        import colour
        for r, L in zip(profile.reference, labs):
            rgb = colour.XYZ_to_sRGB(colour.Lab_to_XYZ(L, colour.CCS_ILLUMINANTS["CIE 1931 2 Degree Standard Observer"]["D65"]))
            if max(0, -rgb.min(), rgb.max() - 1) > 0.02:
                issues.append(("WARN", f"{r['substance']} colour is outside sRGB: requires RAW/linear capture (E13)"))
    except ImportError:
        pass
    tgt = profile.targets()
    for j in np.where(grp & ~tgt)[0]:
        issues.append(("INFO", f"cross-reactant in positive group: {names[j]}"))
    return issues
