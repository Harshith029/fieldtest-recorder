# FieldTest Recorder

**SIH 2026 · SIH26231 · Digital Companion for Field Drug Testing (Narcotics Control Bureau, MHA)**

![tests](https://github.com/Harshith029/fieldtest-recorder/actions/workflows/ci.yml/badge.svg)

A guided, measured and signed field test for NCB's **Narcotic Drugs Detection Kit**. It works offline on the officer's phone:
- it follows the kit's printed Tests A–E;
- it photographs each reaction beside a reagent-only blank well on a reference colour card;
- it reads the colour against a signed colour standard;
- it turns every result into a tamper-evident record with time, GPS, officer and image hash.

An independent expert can verify those records offline.

> **Status.** This repository holds the working reference implementation (Python) of the whole core. It is the executable specification the Android app must match. **The Android app is not built yet.** Colour results are from simulated photos; nothing has been measured on a real phone or a real NCB reaction. Every claim below is labelled accordingly.

![Every capture in the demo and the engine's decision](docs/img/demo-captures.png)

## The problem

1. Officers test every seized packet with the kit and judge the colour **by eye** against a printed chart. They write the result in the panchnama ("dark brown").
2. That result drives the NDPS procedure before any lab report exists:
   - classification (Rule 3);
   - Form-1 within 48 h;
   - which packets are sampled together (Rule 10(2));
   - remand and bail.
3. Nothing proves the test happened at that place and time. The Bombay High Court found that NCB "has not prescribed the standards" and called field testing "arbitrary" (*Sagar Parshuram Joshi*, 2021).
4. A colour test identifies a **group** of drugs, not one drug. NCB's own chart says Test E's blue means "cocaine or methaqualone". Wrongly naming the drug changes the NDPS quantity category, as in the Anuraj case, where alleged MDMA was methamphetamine.

## Try it (Python 3.11)

```bash
pip install -r requirements.txt
python demo/run_demo.py          # full workflow in ~15 s -> demo/output/report.html
pytest                           # 47 tests, ~30 s
```

**The demo** (a pre-generated copy is in [`docs/demo/report.html`](docs/demo/report.html); download and open it) covers one seizure with two officers, two phones and three packets:
1. **P-1:** the flow chart picks Test A. The reading is positive against the blank, consistent with codeine, heroin or morphine, and the app warns that the NDPS quantity category can't be decided in the field.
2. **P-2:** no colour change on Test A, then Test B, then "stop testing" exactly as the printed flow chart says.
3. **P-3:** tablet, amphetamine range. Test C is marked *inconclusive*, because its chart isn't printed in the guide; the app does not guess.
4. **Signing:** every capture is signed and chained, and the phones' ranges become a 14-character panchnama code with a check character.
5. **Offline verification:** the raid is **VERIFIED** while an earlier, unrelated case on the same phone stays hidden.
6. **Tampering:** four tampering attempts are **caught**; a one-character typo in the code is reported as a typo; the search log finds records and re-verifies them when opened.

## What is built, and how we know

| Part | Status | Evidence |
|---|---|---|
| Record format: signed header + payload with time, GNSS time, GPS + mock-location flag, officer, image hash; hash chain | **Proven in code** | 18/18 tampering attacks caught (`ftr-reference/test_integrity.py`) |
| Trust model: NCB supervisor list → supervisor-signed phone binding → attested hardware key; our server is never trusted | **Proven in code** | Insider-admin forgery caught; attestation accept + reject paths 19/19 (`e15_attestation.py`) |
| Panchnama anchor: every phone's record range + chain head; code with check character | **Proven in code** | Deleted/re-run records caught; 434/434 single-character typos detected |
| Verify one raid without disclosing other cases | **Proven in code** | Other cases disclosed as hashes only |
| Sync protocol: idempotent, fork/replay detection, durable checkpoints, search | **Proven in code** (SQLite reference server) | 15/15 failure scenarios (`e14_failures.py`) |
| Searchable offline log that re-verifies on open | **Proven in code** | 10/10 checks (`test_log.py`) |
| NCB kit as a signed guided protocol: Tests A–E, flow charts, lower-layer reading, narrowing across tests, NDPS quantity warning | **Built** | Colours sampled from the scanned printed chart: approximate |
| Colour engine: card detection, correction, RAW tier, **blank well**, colour bands across sample amount | **Simulated** | 0.0% false positives across 0.5–1.6× sample amount (old point rule: up to 11.7%); NCB-kit bands 89% correct, 1.7% wrong (E17) |
| Android app (Kotlin), Spring Boot server, real-phone and real-kit validation | **Not built yet** | Planned for the finale |

The full evidence trail covers 17 experiments with 95% intervals, the decisions they forced, an unresolved-problem register, and an external review we verified claim by claim. It's in [`ftr-reference/docs/research/`](ftr-reference/docs/research/); start with [`validation-results.md`](ftr-reference/docs/research/validation-results.md).

## How it works

```mermaid
flowchart LR
  A["Guided NDDK test<br/>(printed flow chart)"] --> B["Photo: card + sample well<br/>+ reagent-only blank well"]
  B --> C["Colour engine<br/>card fit, RAW, CIELAB"]
  C --> D["Colour bands vs blank<br/>positive / no change / inconclusive<br/>+ every drug it fits"]
  D --> E["Signed record<br/>time, GPS, officer, image hash<br/>hash-chained on the phone"]
  E --> F["Panchnama code<br/>signed by witnesses"]
  E --> G["Searchable log,<br/>Field Test Memo, Form-1 item 5"]
  F --> H["Offline verifier<br/>(court expert)"]
```

**Design choices:**
- **No neural network:** a colour test cannot identify a drug, and a court must be able to re-run the reading. Decisions use colour bands computed from the kit's own chart and published physics.
- **No blockchain:** phone-signed chains plus the witnessed panchnama do the job, and even our own server admin cannot forge a record.

The full architecture is in [`docs/pages/FieldTest-Recorder-Architecture.html`](docs/pages/FieldTest-Recorder-Architecture.html) (download and open; diagrams render in browsers with Mermaid support).

## Honest limitations

- **Colour accuracy** is simulated with a camera-sensor model and chart colours from a scanned book. Real phones and real NCB reactions are untested.
- **Kit gaps:** Tests C and D aren't printed in the guide, so they return "inconclusive" until NCB's kit sheet is added.
- **Remaining errors:** partially reacted wells cause the remaining simulated errors. With JPEG only, a bright clear well sometimes reads as glare and comes back inconclusive.
- **Staged samples:** a sample swapped exactly at the reagent drop, or a replayed video, can't be caught from colour alone.
- **Attestation:** hardware attestation is proven with test certificates, not yet on a real locked phone.
- **Users:** no officers, chemists or prosecutors have been interviewed yet.

## Repository map

| Path | What it is |
|---|---|
| `ftr-reference/` | Reference implementation, experiments E1–E17, signed profiles, tools ([its README](ftr-reference/README.md)) |
| `demo/run_demo.py` | End-to-end demo |
| `tests/` | Test suite run by CI |
| `ftr-reference/docs/research/` | Evidence trail |
| `ftr-reference/docs/validation/` | Real-phone test protocol and printable reference card |
| `docs/deck/` | SIH idea presentation (PDF) and its build script |
| `docs/sources/SOURCES.md` | Primary sources with links |

## Safety and legal

- **No narcotics:** the team never handles narcotics. Colour work uses published colours, the kit chart and safe dyes; real-kit validation is designed for NCB or CFSL chemists.
- **Test keys only:** the signing keys in this repository are **TEST-ONLY**. Production keys belong to NCB and never leave its hardware.
- **Presumptive only:** results are presumptive. They never replace the laboratory report.

© 2026 the team. All rights reserved; licence to be decided by the team.
