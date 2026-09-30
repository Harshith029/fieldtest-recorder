# Competitor and AI-convergence analysis (revision 6)

## Existing products and approaches (state of the art, not blueprints)

| Solution | What it does | Gap vs SIH26231 |
|---|---|---|
| DetectaChem MobileDetect | App reads its own QR-coded pouches; report with time, place and images | Proprietary consumables, not NCB kits; no Indian legal mapping |
| e-Sakshya (MHA/NIC) | Records and hashes search/seizure video; Sakshya Lockers | Doesn't read kits or produce per-package results. **Most likely "competitor" is NIC adding a module**, so we ship an embeddable SDK (ADR-13) |
| eyeWitness (IBA), ProofMode | Verified capture with hashes and signatures | Integrity only; no colour interpretation, no NDPS workflow |
| Academic phone colorimetry (e.g., Choodum & Nic Daeid 2011) | RGB analysis of colour tests | Research, not a field workflow or evidence system; usually JPEG |
| NIJ Std-0604.01 | Documented colour standard for kits (US) | A standard, not software; India lacks an equivalent (Bombay HC, 2021) |

## The strongest public rival: Pranav-error/sih-2026-field-drug-testing (read 29 Sep 2026)
Based on its README and file list; we did not run its code. About 50 commits by one owner.

| Area | Rival | Us (rev 7) | Who is ahead |
|---|---|---|---|
| Working app | Flutter Android app, pipeline runs on the handset, offline | None yet (Python reference only) | **Rival** |
| Tests / second implementation | 398 automated tests; an independent Dart verifier cross-checked on vectors | One Python reference; suites E5/E10/E14/E15/E17 + log | **Rival** |
| Colour measurement | Root-polynomial correction, light-field fit, 28 camera sensitivities, conformal prediction sets | 3×3 correction, RAW tier, 1 DSLR sensor model, band model + blank well | **Rival** on validation breadth; us on RAW and amount handling |
| Liveness | Two-view parallax with a fold-up card tab: prints and screens give ~0 px, real card 28 px (measured) | Colour track from before the drop: staged wells 0%, mid-swaps 0.5% (sim) | Different attacks; **their tab is cheap and physical** |
| Timestamp + GPS in the signed record (required by the PS) | Not signed (argues a device clock proves nothing) | Signed: device + GNSS time, location, mock flag; server countersign; panchnama anchor bounds time | **Us** |
| Completeness (deleted or re-run records) | Hash chain detects forks; tail deletion bounded only by "records not yet witnessed off-device" | Every phone's range + head in the witness-signed panchnama (multi-phone) | **Us** |
| Who vouches for the device's officer | Attestation only | Supervisor-DSC binding under NCB's list + attestation | **Us** |
| Searchable log (required by the PS) | No (CCTNS is the system of record) | On-device log + server search | **Us** |
| NCB's actual kit | Generic kit | NDDK Tests A–E, flow charts, lower-layer reading, colour ranges, narrowing, quantity warning | **Us** |
| NDPS procedure | BSA s.63 certificate (draft) | s.63 data, Form-1 item 5, Rule 10(2) grouping, panchnama anchor, Rule 14 lab loop (design) | **Us** on scope; rival has a built s.63 emitter |
| Real photos / users | None | None | Neither |

**Verdict:**
- **Design:** ours fits the problem statement and Indian NDPS procedure more closely.
- **Execution:** theirs is further along.
- **At the finale:** the final round weighs the complete product from the officer's view, so today they would demo better.

**What to learn (ideas, not code):**
- A fold-up parallax tab on the card for photo/screen replay (it complements our colour-track liveness).
- Calibrated abstention thresholds (conformal) once validation data exists.
- Testing over many camera sensitivities.
- A second, independent verifier (our Kotlin port).

## What 100 AI-assisted teams will probably build

- A Flutter, React Native or web app.
- An OpenCV colour match, or a CNN "drug classifier" trained on synthetic images, with a high accuracy claim.
- SHA-256 of the photo, plus GPS.
- A Firebase or FastAPI + PostgreSQL backend, often with a blockchain "for immutability".
- A React dashboard with maps or heatmaps; an NDPS chatbot; a PDF report; a multilingual UI.

**Evidence from our experiments that this pattern is weak for this problem:**

| Common choice | What we found | Source |
|---|---|---|
| Hash of the photo only | Caught 0 of 6 attacks | E3 |
| ML on uncorrected colours | Up to 5.6% wrong under an unseen light | E7 |
| "Positive for cocaine" | Chemically impossible: cocaine and ephedrine have the identical published colour | E6 |
| JPEG capture (every app's default) | Cobalt thiocyanate, the cocaine test, was 21% wrong because its blues fall outside what a JPEG can store. RAW capture: 0% [0–1.6] | E12, E13 |
| Blockchain | Doesn't stop an officer photographing a staged well or deleting a record before sync. Our phone-signed chains plus the witnessed panchnama anchor do the second (12/12 attacks) | E5 |
| "Server is the source of truth" | An admin can mint devices and records | E5 admin attacks |
| Delete local copy once the server acknowledges | Lost 5 of 16 records after a backup restore | E14 |

## Which of our parts are also generic
Android app, reference card (mandated), colour distance, hashing, GPS, PDF report, PostgreSQL server. Necessary, not differentiating.

## Copy test: what a team could reproduce in 48 hours after seeing our demo
Screens, card, colour distance, hashing, Form-1 text, a dashboard. Also the idea of a colour-group list, and "use RAW", once they hear them.

## What is hard to reproduce quickly
1. **The colour-standard framing:**
   - grounded in the Bombay HC judgment (read in full) and NIJ 0604.01;
   - a parsed 150-row data table;
   - signed kit profiles;
   - a two-level profile checker that says when a kit's categories are too close for a camera, or need RAW.
2. **Evidence:** 16 experiments with 95% intervals, including:
   - published colours;
   - out-of-gamut failure and its fix;
   - handheld night mode;
   - insider attacks;
   - backup-restore loss;
   - staged-capture detection.
3. **The trust model:**
   - supervisor DSC bindings;
   - real Android attestation verification against Google's roots and revocation list;
   - multi-phone anchors in the witnessed panchnama;
   - a server that is not trusted.

   It comes with a working verifier, an attack suite and a tested sync protocol.
4. **Frozen region maps:** learned offline, signed, deterministic and re-runnable. This is a specific answer to "AI or not?".

## Core statements
- **Core insight:** A field colour test identifies a colour group, not a drug, and it only means something against a documented standard. India's courts found that the standard, and a verifiable report, are missing.
- **Core advantage:** Every kit test becomes a verifiable report, interpreted against a published, signed colour standard and reproducible by anyone.
- **Technical differentiator:**
  - RAW-first, card-calibrated measurement: 0–1.6% wrong in simulation across 5 reagents;
  - colour-group output with every consistent substance listed;
  - device-signed, attested, witness-anchored records that catch deletions, re-runs and admin forgery (12/12).
- **Operational differentiator:**
  - It produces the artefacts the NDPS process lacks: a field-test report for the charge sheet, Form-1 item 5, and the Rule 10(2) comparison.
  - It learns kit accuracy from the Rule-14 lab report.
  - It embeds in e-Sakshya rather than competing with it.
- **Why it matters:** Bail and remand decisions before the lab result turn on procedure. This makes the first step of every NDPS case documented, standardised and checkable. After the lab confirms, the lab result carries the case (Delhi HC, 2023), and we say so.
