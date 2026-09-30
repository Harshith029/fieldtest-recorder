# FieldTest Recorder — reference implementation (SIH26231)

This is an executable specification for the parts that decide whether the solution works:
- the **record and trust layer**;
- the **colour engine and signed kit profiles**;
- the **sync protocol**.

The Kotlin SDK, app, server and verifier must reproduce these files' outputs exactly: the same canonical bytes, the same verdicts, and the same colour decisions.

Reaction colours come from the published US standard (NIJ Std-0604.01), not from NCB's kits. Every colour result is **simulated**: a DSLR sensor model and CIE light spectra, not a real phone yet.

## Core modules

| File | What it is |
|---|---|
| `record_core.py` | Canonical JSON (RFC 8785, ASCII keys, no floats, integers within ±2^53−1); ECDSA P-256; records = signed header (device, counter, prev, payload hash) + payload (time, GNSS time, GPS + mock flag, operator, image hash, result); per-device hash chains; supervisor-signed bindings (officer + device_id + key + attestation); panchnama anchor (QR + 14-char code with check character, per-phone counter ranges); one-raid disclosure; fail-closed offline verifier |
| `attestation.py` | Android key attestation. Full chain to Google's roots, revocation list, key-description extension (TEE/StrongBox, verified boot, locked bootloader, challenge, key match) |
| `colour_engine.py` | ArUco card detection (3 of 4 markers, sub-pixel), homography, blur/card-fit/glare gates, grey-ramp + 3×3 correction, CIELAB, CIEDE2000. `read_capture` handles the JPEG tier and `read_capture_linear` the RAW tier |
| `kit_profile.py` | Signed kit profile = documented colour standard. Decision is a **band** (chart range × sample amount), a rule, or a guarded region map. Every sample is judged against the **blank well** first ("no colour change" = negative). Returns the outcome plus every substance consistent with it. Two-level profile checker |
| `bands.py` | Builds colour bands: chart range × 0.5–1.6× amount via Beer-Lambert (build time only) |
| `nddk.py` | NCB Narcotic Drugs Detection Kit as a signed protocol: Tests A–E, flow charts I/II, lower-layer reading, band profiles from the chart (approximate), narrowing across tests, NDPS quantity warning |
| `record_log.py` | On-device searchable log (SQLite FTS); re-verifies a record when opened |
| `nij_colours.py` | NIJ Munsell targets → CIELAB D65 (Bradford), reflectance for the simulator |
| `build_profiles.py` | Builds and signs the demo profiles in `profiles/` with the **TEST-ONLY** key; rejects a tampered profile |
| `sync_server.py` | Reference sync protocol: enrolment, idempotent sync, fork freeze, gaps, replay nonces, hash-chained ledger, signed receipts, durable checkpoints, backup and restore |
| `stats.py` | Clopper-Pearson 95% intervals used by every experiment |
| `photo_sim.py` | Renders realistic photos of the card (spectral light × sensor, tilt, blur, glare, uneven light, JPEG); optional 12-bit linear RAW |
| `read_photos.py` | Reads real phone photos (JPEG or DNG) through the engine; writes a CSV and a reproducibility summary. `--selftest` runs on simulated photos |

## Tools

| File | What it is |
|---|---|
| `tools/make_card.py` | Prints the 150×105 mm test card (600-dpi PNG + lossless A4 PDF with crop marks) into `docs/validation/card/`, and self-checks that the engine finds it |
| `tools/parse_nij.py` | Parses NIJ Table 1 into `docs/research/data/nij0604_table1.csv` (150 rows) |
| `tools/attestation_samples/` | Google's sample attestation chains, Google's published roots, a snapshot of the revocation list |

## Experiments (question → result → decision in `docs/research/experiments.md`)

| File | Experiment |
|---|---|
| `research/` | E1 calibration, E1b bad light, E2 same-photo comparison, E3 integrity logic |
| `e4_pipeline.py` | E4 full engine on rendered photos |
| `test_integrity.py` | E5 12 tampering attacks + strict attestation policy |
| `e6_nij_colours.py` | E6 published NIJ colours |
| `e7_threshold_and_ml.py` | E7 thresholds; ML with/without the card |
| `e8_region_vs_substance.py` | E8 colour group vs substance-nearest |
| `e9_flash_handheld.py` | E9 handheld night mode |
| `e10_fuzz.py` | E10 hostile images and malformed bundles |
| `e11_region_map.py` | E11 frozen region maps |
| `e12_heldout.py` | E12 held-out photos through the real engine, 3 seeds, JPEG/map/RAW |
| `e13_gamut_raw.py` | E13 RAW vs JPEG for out-of-sRGB colours |
| `e14_failures.py` | E14 13 sync and user-failure scenarios |
| `e15_attestation.py` | E15 attestation verification |
| `e16_liveness.py` | E16 staged-capture detection |
| `e17_amount.py` | E17 sample amount + blank well: point rule vs band model; NCB kit bands; flow charts |
| `test_log.py` | Searchable log checks |
| `test_blank_pipeline.py` | Blank-well path end to end through rendered photos (JPEG and RAW) with the NCB kit Test A profile |
| `time_engine.py`, `validation_power.py` | Engine timing; sample sizes for NCB validation |

## Run

```bash
pip install colour-science scipy numpy opencv-python-headless jcs cryptography pillow scikit-learn
python build_profiles.py
python nddk.py
python test_integrity.py
python test_log.py
python e17_amount.py
python e12_heldout.py
python e14_failures.py
python e15_attestation.py
python e16_liveness.py
python tools/make_card.py
python read_photos.py --selftest
```

To read real photos (protocol in `docs/validation/real-phone-capture-protocol.md`):

```bash
python read_photos.py --photos path/to/photos --profile profiles/marquis_rule.json --out results/real.csv
```

## Headline results (95% intervals; full tables in `docs/research/validation-results.md`)

- **Integrity** (real code):
  - 18/18 attacks caught;
  - 13/13 malformed bundles rejected cleanly;
  - 15/15 sync failure scenarios behave as designed;
  - 18/18 attestation cases behave as expected, including the accept path;
  - one raid verifies with other cases withheld.
- **Colour** (simulated, held out, glare on): RAW capture gives 85–92% correct and 0.0–1.6% wrong across 5 reagents, **at the reference sample amount only**.
- **Sample amount** (E17): the point rule fails off the reference amount. The band model with a blank well gives 0.0% false positives and 29–75% sensitivity. NCB kit bands: 89.1% correct, 1.7% wrong.
- **JPEG only:** cobalt thiocyanate is 21.2% wrong with the rule, so it needs RAW or the region map.
- **Liveness:**
  - staged pre-reacted wells accepted 0.0% [0–0.9];
  - mid-capture swaps accepted 0.5% [0.1–1.8];
  - a swap timed at the drop, and replays, are not caught by colour.
- **Not yet verified:**
  - real phones and NCB kits;
  - a locked production phone's attestation;
  - the server on PostgreSQL;
  - officer time.
