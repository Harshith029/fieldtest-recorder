# Validation and benchmark results

All numbers come from code in this repository. **Every rate carries a 95% Clopper-Pearson interval** (`stats.py`).
"Simulated" = spectral + rendered-photo simulation with a real **DSLR** sensor model (Nikon D5100, NPL data),
CIE light spectra, and published reaction colours (NIJ Std-0604.01). Not measured on a phone yet.
Anything not measured is marked **NOT YET VERIFIED**.

## Integrity, trust and protocol (real code; revision 7 record format)
| Metric | Result | Source |
|---|---|---|
| Tampering attacks detected | **18/18** (12 original + withheld record, re-labelled record, one key as two devices, operator mismatch, value above 2^53, signed record without time/GPS) | `test_integrity.py` |
| Verify one raid without disclosing others | RAID-2 VERIFIED with RAID-1's 7 records withheld (headers only) | `test_integrity.py` |
| Timestamp, GPS (with mock-location flag), operator ID, image hash in every signed test record | required by the verifier and the sync server | `test_integrity.py`, E14 |
| Panchnama code check character | 434/434 single-character errors and 12/13 adjacent swaps detected; typo reported as a typo | `test_integrity.py` |
| Strict attestation policy: bindings without an attestation chain | rejected | `test_integrity.py` |
| Attestation checks (Google's samples + synthetic production-style chain) | 18/18 as expected, **including the success path** end to end | E15 |
| Attestation pass on a real locked production phone | **NOT YET VERIFIED** | E15 |
| Malformed bundles handled cleanly | 13/13 | E10 |
| Hostile images crashing the engine | 0/11 | E10 |
| Sync-protocol failure scenarios | 15/15 pass (incl. malformed records inside a signed envelope; server search) | E14 |
| Records lost after disk loss + restore from older backup | delete-on-any-checkpoint: 5/16 lost; **delete-on-durable-checkpoint: 0/16 lost** | E14 |
| Searchable on-device log | 10/10 checks (text, filters, re-verify on open, tamper flagged) | `test_log.py` |
| Verification throughput | ~8,600–8,800 records/s (Python, laptop) | `test_integrity.py` |
| Sync throughput (reference server, SQLite) | ~5,200 records/s; real need < 1/s | E14 |

## Sample amount and blank well (E17, colour-level simulation, sigma 1.0 per CIELAB channel)
Pooled over 0.5–1.6× amount (Beer-Lambert) and 40–80% partial reaction. Positive-group called positive / others called positive:

| Reagent | Old point rule | Band model (rev 7) |
|---|---|---|
| Marquis | 24.8% / 0.0% | 74.7% / 0.0% |
| Mecke | 27.0% / 0.0% | 66.1% / 0.0% |
| Simon's | 19.3% / **9.2%** [7.0–11.8] | 44.3% / 0.0% [0–0.6] |
| Cobalt thiocyanate | 17.1% / **11.7%** [10.6–12.9] | 29.2% / 0.0% [0–0.1] |

Clear well → "negative, no colour change": 99.0–100% with a blank well. NCB kit bands (chart colours, approximate):
**89.1% [88.0–90.3] correct, 1.7% [1.2–2.2] wrong**, all errors in partially reacted wells.

End to end through rendered photos (`test_blank_pipeline.py`, NCB kit Test A, blank in W2, 40 photos per case):

| Case | JPEG correct | RAW correct | Wrong |
|---|---|---|---|
| opiate range | 86.8% [71.9–95.6] | 100% [90.7–100] | 0 |
| amphetamine range | 73.0% [55.9–86.2] | 100% [90.5–100] | 0 |
| clear sample | 87.2% [72.6–95.7] | 100% [91.0–100] | 0 |

JPEG shortfalls are inconclusive calls: glare, and a bright clear well tripping the glare check (U25).

## Colour reading, held-out, through the real engine path (E12: 3 seeds × 100 photos, glare on; re-run for revision 7)
At the reference sample amount only (see E17 for amount variation). Region maps are rev-7 guarded maps
(outliers removed, 3-reading density, positive only near a documented colour): coverage drops, wrong calls do not rise.

| Reagent | Capture + decision | Correct | Wrong | Inconclusive |
|---|---|---|---|---|
| Marquis | JPEG + rule | 85.8% [82.6–88.5] | 0.0% [0.0–0.6] | 14.2% |
| Marquis | JPEG + guarded map | 78.3% [74.7–81.6] (was 88.0%) | 0.2% [0.0–1.0] | 21.5% |
| Marquis | RAW + rule | 89.4% [86.6–91.8] | 0.0% [0.0–0.6] | 10.6% |
| Mecke | JPEG + rule | 79.2% [75.6–82.4] | 0.3% [0.0–1.2] | 20.5% |
| Mecke | JPEG + guarded map | 86.5% [83.4–89.1] (was 89.2%) | 0.0% [0.0–0.6] | 13.5% |
| Mecke | RAW + rule | 89.4% [86.6–91.8] | 0.0% [0.0–0.6] | 10.6% |
| Simon's | JPEG + rule | 87.2% [84.1–89.8] | 0.0% [0.0–0.6] | 12.8% |
| Simon's | JPEG + guarded map | 89.1% [86.2–91.5] | 0.0% [0.0–0.6] | 10.9% |
| Simon's | RAW + rule | 89.6% [86.8–92.0] | 0.0% [0.0–0.6] | 10.4% |
| Cobalt thiocyanate | JPEG + rule | 39.4% [35.4–43.5] | **21.2% [17.9–24.7]** | 39.4% |
| Cobalt thiocyanate | JPEG + guarded map | 83.2% [79.8–86.1] (was 88.0%) | 0.9% [0.3–2.0] | 16.0% |
| Cobalt thiocyanate | RAW + rule | 90.1% [87.4–92.4] | 1.6% [0.7–2.9] | 8.3% |
| Duquenois-Levine | JPEG + rule | 92.1% [89.6–94.2] | 0.4% [0.0–1.3] | 7.5% |
| Duquenois-Levine | RAW + rule | 92.3% [89.8–94.4] | 0.4% [0.0–1.3] | 7.3% |

True substance present in the "also consistent with" list on positive calls: 100% after the rev-6 fix (E12 recheck).

## Other colour results
| Metric | Result | Source |
|---|---|---|
| RAW vs JPEG, out-of-sRGB colours (cobalt) | error 7.4 → 0.8 ΔE00; wrong 21.9% [16.7–27.9] → 0.0% [0.0–1.6] | E13 |
| E4 illustrative colours, 1,384 wells | 0 wrong → 95% upper bound 0.27% | E4 |
| Frozen region map, per unseen light (~70–100 wells each) | "0% wrong" means only < 3.6–5.1% at 95% | E11 |
| Night, locked linear flash/no-flash, 180 wells | 0 wrong → < 2.0% at 95%; 100% correct | E9 |
| Liveness: pre-reacted well/screen accepted as live | 0.0% [0.0–0.9] | E16 |
| Liveness: mid-capture swap accepted | 0.5% [0.1–1.8] | E16 |
| Liveness: swap timed at the drop / replay | accepted (limit of colour evidence) | E16 |
| Engine time per photo | ~110 ms (1600×1300, laptop, Python) | `time_engine.py` |
| Printable card (150×105 mm, 600 dpi) found by the engine | yes (self-check on the flat print file) | `tools/make_card.py` |
| Real-photo reader on 9 simulated photos (3 cups × phones/lights/variants) | 0 rejected; same-cup spread median 1.8–2.9, 95th pct 3.8–6.4 ΔE00 (JPEG) | `read_photos.py --selftest` |

## Caveats that apply to every colour number
- Training data for region maps and test photos come from the **same simulator** (different seeds), which favours the maps.
- DSLR sensor model, opaque-well rendering; real liquids in wells, phone sensors and phone processing may differ.
- NIJ colours are for pure reference drugs; street samples are mixtures.

## NOT YET VERIFIED
Real phone photos; NCB kits; street samples; phone-side timing; RAW/manual-control support on officers' phones;
attestation on a locked production device; server on PostgreSQL under load; officer time per package; court acceptance.
