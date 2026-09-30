# Final output: continuous-investigation brief (29 Sep 2026, updated to revision 7)

Revision 7 applied an external review; every claim was re-checked first (`review-verification-2026-09-29.md`). The corrections are made in place below.

This answers Sections 19 and 20 of the brief in full, one letter per section, with nothing merged.
- Numbers come from code in this repository, with 95% Clopper-Pearson intervals.
- "Simulated" means a DSLR sensor model (Nikon D5100), CIE light spectra and published NIJ reaction colours. It does **not** mean a phone.
- Details live in the other files in `docs/research/`.

---

## Section 19: "Would this actually work?"

| # | Question | Honest answer |
|---|---|---|
| 1 | Remove the UI: does the core still solve the problem? | **Yes.** The core is four things: the record format, signing and chain, the colour engine with signed profiles, and the offline verifier. All run with no UI (`record_core.py`, `colour_engine.py`, `kit_profile.py`). This is why it ships as an SDK (ADR-13). |
| 2 | Remove AI: does the product still have value? | **Yes, fully.** RAW + deterministic rule reaches 0–1.6% wrong with no learned component (E12). ML is used only offline, to draw region maps for JPEG-only phones. Remove it and those phones return "inconclusive" more often on saturated colours; nothing else changes. |
| 3 | Remove every buzzword: is it still strong? | **Yes.** What's left: a printed card, a colour measurement, a published standard, a signature, a hash chain, and a code written into the witnessed panchnama. Each one answers a specific gap: in the problem statement, in the NDPS Rules, or in the Bombay HC judgment. |
| 4 | Another team copies our UI: what stays hard? | Six things stay hard to copy:<br>1. The **colour-standard framing**, and knowing that cocaine = ephedrine by colour.<br>2. **RAW-first capture**, backed by the out-of-gamut evidence.<br>3. The **trust model**: supervisor DSC bindings, attestation, multi-phone panchnama anchor, an untrusted server.<br>4. **Durable checkpoints.**<br>5. The evidence behind all of it: **16 experiments with intervals**.<br>6. The **profile checker** that says which kit categories a camera can't separate. |
| 5 | Government deploys tomorrow: what breaks first? | **Colour bands on real reactions.** NCB's kit is now encoded (Tests A–E, flow charts), but its colours come from a scanned chart, and Tests C and D aren't printed. Next: partially reacted wells, then phones without RAW, supervisors without DSCs, and API access. The trust layer would not be the first thing to break. |
| 6 | Maintain for five years: what would we regret? | Two regrets are likely:<br>- **The colour engine drifting from the verifier** across versions. Mitigation: one shared library plus golden-image tests.<br>- **Letting profiles become app config** instead of NCB-governed, signed releases.<br>We might also regret the portal UI (keep it minimal) and depending on Google's attestation roots (the Android platform ties us to them; revocation-list caching is needed). |
| 7 | Only 48 hours: what do we build? | The Android capture → colour group → sign → chain → anchor loop on real phones, plus the offline verifier CLI and a live tamper demo. Use one reagent profile (Marquis, rule) and the printed card with safe dyes. No server: export bundles over USB. |
| 8 | Six months: what do we improve? | 1. NCB kit validation (real profiles).<br>2. A phone capability survey and a real RAW pipeline.<br>3. Server on PostgreSQL with a load test.<br>4. A 12-week pilot in one zonal unit with a stopwatch study.<br>5. Label tracking and the s.105 video cross-link, to close swap-at-drop and replay.<br>6. SIMS and e-Sakshya integration if access is granted.<br>7. A security audit. |
| 9 | Biggest weakness now? | **No app and no real-world contact.** A public rival already has a working Flutter app. No officer, chemist or prosecutor consulted. No real phone photo. Colour accuracy is simulated. |
| 10 | Biggest unknown? | **How NCB's real reactions compare with the printed chart**, at realistic sample amounts, plus Tests C and D. Second: whether officers' phones support RAW. |
| 11 | Most valuable next experiment? | **The real-phone test.** Print the card, photograph safe dyes (pH indicators, food colours, plus saturated blue and green dyes) on 3 phones under 4 lights, and run `read_photos.py`. It takes about an afternoon. It tests the whole simulation chain at once: markers, correction, reproducibility across phones, and JPEG vs RAW. After that come the interviews (`product-validation.md`). |

---

## Section 20: final output A–Z

### A. Executive summary
FieldTest Recorder is an offline Android tool, built as an embeddable SDK, for **NCB's Narcotic Drugs Detection Kit**.
- It guides the officer through Tests A–E in the printed flow-chart order.
- It photographs each reaction beside a reagent-only **blank well** on a reference card, preferably as a RAW capture.
- It reads the colour against **signed colour bands** built from the kit's own ranges. It reports positive, "negative, no colour change", or inconclusive, plus every substance consistent with the colour.
- It combines results across tests and warns when the NDPS quantity category can't be told.

Each test becomes a device-signed, hash-chained record carrying time, GPS and officer. The record is bound to the numbered package and to a code written into the witness-signed panchnama. One raid can be verified offline without disclosing other cases.

The trust layer and sync protocol are proven in code (18/18 attacks, 15/15 failure scenarios). Colour decisions are simulated: 0.0% false positives across sample amounts, and 89.1% correct / 1.7% wrong on NCB-kit bands. Real reactions, phones and users remain untested, and the app isn't built.

### B. Actual problem
The field kit test decides:
- classification (Rule 3(1));
- sampling lots (Rule 10(2));
- Form-1 item 5;
- remand and bail before the lab report.

Yet it leaves no verifiable, standardised record. The Bombay HC (*Sagar Parshuram Joshi*, 2021) called field testing "arbitrary" because India has no documented colour standard, and held that a bare mention in the panchnama is not sufficient. The Delhi HC (*Masibur Khan*, 2023) held that the field test is only indicative once the lab confirms. So the need sits at the **pre-lab stage**.

### C. Root cause
Three things combine:
- The record is made apart from the event.
- The colour is judged by eye against no documented standard, under uncontrolled light.
- Nothing binds the result to the package, the witnesses or the time.

On top of this, no lab result flows back to measure kit accuracy.

### D. Current solution status

| Part | Status |
|---|---|
| Record, trust and verifier | **Done in reference code:** E5 12/12, E10 fail-closed |
| Sync protocol | **Done in reference code:** E14 13/13, durable checkpoints |
| Attestation verifier | **Done:** E15. No locked production phone enrolled yet |
| Colour engine and signed profiles | **Done in reference code**, simulated only (E12, E13) |
| Liveness | **Done:** E16, with stated limits |
| Printable card and real-photo reader | **Done;** not yet used on real phones |
| Kotlin app and SDK | **Not built** |
| Spring Boot server | **Not built** |
| Deck | **Not started** (on hold by instruction) |

### E. Unresolved problems
The full register is in `unresolved-problems.md` (U1–U20). The ones that matter:

| ID | Problem |
|---|---|
| U1 | NCB kit data |
| U2 | Real-phone photos |
| U3 | RAW support on officers' phones |
| U4 | Attestation on a locked production phone |
| U5 | Swap at the drop, and replay |
| U6 | Officer time and adoption |
| U7 | Court and prosecutor view |
| U8 | API access |
| U10 | Mixtures |
| U13 | Server on PostgreSQL |

### F. Research findings
Detail is in `domain-research.md`. The findings that changed the design:
- **D1 Bombay HC (primary, read in full):** the standard and the report are missing.
- **D1b Delhi HC:** narrows the legal claim to the pre-lab stage.
- **D2/D3 NIJ 0604.01:** the colour-standard model; many substances share a colour, so output is a colour group.
- **D4/D5 NDPS Rules and NCB handbook:** the legal hooks, and the officer's good-faith defence.
- **D9:** no Indian app for digital field-test recording found in public sources (absence of evidence, not proof).
- **D10/D11:** DSCs, BSA s.63 hash certificate, BPR&D SOP.

### G. SIH winner pattern findings
Detail is in `sih-winner-analysis.md`.
- A firsthand SIH 2023 account reports three rounds weighted 20/30/50, with the last round judging the **complete product from the end user's view**.
- Winners showed three things: a working end-to-end workflow for a named operator, stakeholder validation, and at least one quantified result.
- The tech stack and "AI" appear in winners and losers alike; there is no evidence either caused wins.
- Our model: STRONG on problem understanding, innovation and explainability. WEAK on user experience, measurable impact and validation.

### H. Competitive / AI convergence analysis
Detail is in `competitor-analysis.md`. Most teams will likely build:
- a Flutter or web app with a CNN "drug classifier" on JPEG photos;
- SHA-256 + GPS;
- Firebase or FastAPI;
- often a blockchain, a dashboard and a chatbot.

Our experiments show why that pattern fails here:

| Common choice | What we found |
|---|---|
| Hash only | 0/6 attacks caught (E3) |
| ML without the card | up to 5.6% wrong (E7) |
| "Cocaine" output | chemically impossible (E6) |
| JPEG capture | 21% wrong on the cocaine test (E12) |
| Delete once acknowledged | loses records on restore (E14) |

### I. Alternative solutions investigated

| Area | Alternatives tested | Outcome |
|---|---|---|
| Overall approach | signed capture with human reading; server-side or remote expert reading; handheld spectrometers; blockchain ledger | calibrated measurement on the phone chosen (Phase 3) |
| Classification | substance-nearest vs colour group | colour group (E8) |
| Calibration | ML without the card vs card calibration | card (E7) |
| Decision | global thresholds vs learned boundary | rule, with a frozen map as fallback (E7, E11) |
| Capture | JPEG vs RAW | RAW (E13) |
| Night mode | flash/no-flash locked vs auto vs single flash | tiered (E9) |
| Integrity | hash vs chain vs chain + anchor | chain + anchor (E3) |
| Device trust | server-issued vs supervisor-signed bindings | supervisor-signed (E5) |
| Attestation | flag vs full chain verification | full chain (E15) |
| Deletion | on any checkpoint vs durable checkpoint | durable (E14) |
| Liveness | raw vs smoothed colour track | smoothed (E16) |
| Deployment | standalone app vs SDK | SDK (ADR-13) |

### J. Experiments performed
16 experiments: E1–E3 (research), E4–E16. Each is logged as question → hypothesis → implementation → result → decision in `experiments.md`, with raw outputs in `results/`.

### K. Results

| Result | Source |
|---|---|
| 12/12 attacks caught | E5 |
| Malformed bundles: 0 unhandled | E10 |
| 13/13 sync failure scenarios | E14 |
| 16/16 records recovered after restore with durable checkpoints, vs 11/16 without | E14 |
| 13/13 attestation cases as expected | E15 |
| RAW + rule: 85–92% correct, 0.0–1.6% wrong across Marquis, Mecke, Simon's, cobalt thiocyanate and Duquenois-Levine | E12 |
| JPEG + rule on cobalt: 21.2% [17.9–24.7] wrong, fixed by RAW (0.0% [0–1.6]) | E12, E13 |
| Staged wells accepted: 0.0% [0–0.9] | E16 |
| Mid-capture swaps accepted: 0.5% [0.1–1.8] | E16 |
| Printed card found by the engine | `tools/make_card.py` |
| Same cup read across simulated phones and lights: median 1.8–2.9 ΔE00 | `read_photos.py` self-test |

### L. Final recommended architecture
The components:
- **FieldTest Engine SDK (Kotlin):**
  - capture (RAW first, JPEG fallback, starting before the drop);
  - colour engine (card fit, CIELAB, ΔE00);
  - signed kit profile (colour groups; rule or frozen map);
  - record core (RFC 8785, SHA-256, ECDSA P-256, chain);
  - anchor and report generator.
- **Reference Android app** hosting the SDK.
- **One Spring Boot server:** enrolment with attestation and supervisor DSC, idempotent sync, ledger, durable checkpoints, lab results, QA.
- **Storage:** PostgreSQL and S3 with object lock.
- **Offline verifier** built on the same record core.

No blockchain, LLM, queue, cache, search cluster or microservices. The live page has the diagrams: <https://claude.ai/artifact/WG34iCaHAWKBcfoXPAvfUy>.

### M. Product workflow
1. Open the operation. Team phones join by QR.
2. Place the card, vessel and package label; start capture before the reagent drop.
3. The app follows the reaction to read time and runs quality and liveness gates.
4. The officer records what they see; the app shows the colour group and consistent substances.
5. Sign and chain the record.
6. Same-photo comparison supports Rule 10(2).
7. Close: the anchor code goes into the panchnama and the witnesses sign.
8. Generate the field-test report, Form-1 item 5 text and s.63 data.
9. Sync; phones delete only after a durable checkpoint.
10. The lab result is entered later and compared.

### N. Tech stack

| Layer | Choice |
|---|---|
| Phone | Kotlin; Camera2 (RAW/DNG) / CameraX; OpenCV ArUco; Android Keystore + key attestation; Room + SQLCipher |
| Record format | RFC 8785 JCS, SHA-256, ECDSA P-256 |
| Server | Spring Boot (Kotlin); PostgreSQL 16; S3-compatible storage with object lock (MinIO on-premises) |
| Portal | Server-rendered Thymeleaf + htmx |
| Identity | Parichay; supervisor Class 3 DSC |
| Deployment | Containers on NIC or empanelled cloud |

Reference implementation: Python with OpenCV, colour-science, cryptography and jcs.

### O. Data architecture
- **Immutable, self-verifying records.** The key is the hash of the canonical body. Corrections are amendment records that point to the original.
- **Media are content-addressed** and stored write-once.
- **Profiles** are signed, versioned and approved by two people.
- **The ledger** is hash-chained, with durable checkpoints copied to phones and HQ.
- **Lab results** need two-person entry.
- **Retention:** records kept until case disposal plus appeals, with legal hold (policy to confirm with NCB).
- **Access:** role and unit scoping.

Schema: architecture page, Phase 7.

### P. Security architecture
- **Trust roots:** NCB's supervisor list (offline, two-person) and Google's attestation roots. The server is never a trust root.
- **Device binding:** a hardware key per device, bound to the officer by the supervisor's DSC. Strict attestation checks the chain, revocation list, TEE/StrongBox, verified boot, locked bootloader and challenge.
- **Records:** signed and chained on the phone; anchored in the panchnama.
- **Sync:** signed envelopes with a replay nonce; forks freeze the device.
- **Other controls:** STRIDE per trust boundary; OWASP MASVS for the app, ASVS L2 for the server, GIGW for the portal.
- **Stated limits:** a hardware-level exploit, a swap exactly at the drop, and a replayed video.

### Q. Failure handling
Every failure mode has detection, recovery and a fallback (architecture page, Phase 10). The rules behind them:
- Field work never depends on the network or the server.
- Phones are the recovery source until a durable checkpoint.
- Bad capture gives "inconclusive" plus the officer's reading, never a guess.
- The verifier fails closed.

Tested so far: 13 E14 scenarios and 11 hostile images (E10).

### R. Scalability
- **Estimated load:** 7–20 lakh records a year; under 1 record/s on average and under 10 requests/s at peak.
- **Reference protocol:** about 5,600 records/s on SQLite.
- **Design:** one monolith with two instances, a PostgreSQL primary and replica; year partitions at 10× and read replicas at 100×. The first thing to strain would be QA queries.
- **Not yet verified:** a load test on PostgreSQL.

### S. SIH MVP
**Must be real:**
- signing on real phones, chain, anchor;
- offline verifier and live tamper demo;
- card calibration and colour group for one or two reagents on safe dyes;
- RAW where the demo phone supports it;
- liveness;
- the searchable log;
- the field-test report.

**Mocked, and labelled:** NCB profiles (proxy chemistry, marked SYNTHETIC), SSO, SIMS, e-Sakshya, lab results.

**Order of work:** M0 format → M1 phone ledger → M2 measurement → M3 night mode and grouping → M4 server if time allows.

### T. Production roadmap
1. SIH finale.
2. Phase-0 kit validation with NCB (1,296 captures).
3. A 12-week pilot in one zonal unit, with a stopwatch study and field-vs-lab accuracy.
4. Security audit.
5. Hosting on NIC.
6. SIMS and e-Sakshya integration.
7. The kit supplier prints the characterised card into kits.
8. National rollout, with NCB owning keys and profiles.

### U. Validation / benchmark results
The full tables are in `validation-results.md`. Every rate there has a 95% interval, and items not yet measured are marked NOT YET VERIFIED.

### V. Biggest risks
1. NCB kits behave differently from the NIJ table.
2. Officers' phones lack RAW, so saturated colours fall back to region maps, which are trained only on simulation.
3. Officers see it as extra work; time is unmeasured.
4. No access to NCB for data or feedback before the finale.
5. A judge asks for real-phone numbers and we have none.

### W. Biggest assumptions
- NCB will share kit sheets and run a validation.
- Kit colours are close to NIJ's.
- Supervisors have, or can get, DSCs.
- NCB wants records the defence can also use.
- The kit supplier can print a colour-controlled card.
- Officers carry phones that pass attestation.

### X. What we still don't know
- NCB kit format, reagents and read times.
- Which phones officers use, and their RAW support.
- Time per package today.
- How prosecutors and courts would treat the report.
- API access to SIMS, e-Sakshya and Parichay.
- The retention policy.
- Who at NCB would own the colour standard.

### Y. Next experiments
1. Real-phone test with the printed card and safe dyes (U2, U3, U12, U16, U18).
2. 3–5 interviews: officer, chemist, prosecutor (U6, U7).
3. Enrol one locked production phone (U4).
4. Kotlin record core on the test vectors (M0).
5. Stopwatch timing of paper vs app on a mock seizure.
6. PostgreSQL load test (U13).

### Z. Why this solution is genuinely different
Most solutions to this statement will claim to identify a drug from a photo. **The chemistry doesn't allow that:** cocaine and ephedrine give the identical colour. **A JPEG can't even store that colour correctly.** We built what the court said was missing: a published colour standard per kit, read with calibrated (preferably RAW) capture, reported honestly as a colour group, and bound into a record that neither the officer, the server admin nor our team can quietly change. Every claim in that sentence has an experiment behind it.

---

## Revision 7 corrections to the letters above
- **D/K/U:**
  - integrity is now E5 18/18, E10 13/13, E14 15/15, E15 18/18 (accept path included);
  - the searchable log passes 10/10;
  - E17 adds the sample-amount results;
  - E12's "0–1.6% wrong" holds only at the reference sample amount.
- **E:** U1 is partly resolved (NCB kit found). New entries: U21 (amount), U22 (partial reaction), U23 (Tests C/D), U24 (scanned chart colours).
- **F:** NCB's kit, from the NICFS guide Figs 8.12–8.16, changed the product's target kit. The "sugar" claim is not in the Bombay HC judgment. Default bail there was under CrPC s.167(2).
- **H:** a public rival (Pranav-error) has a working app. Comparison in `competitor-analysis.md`.
- **L/N/O:**
  - record = signed header + payload;
  - bindings sign the device ID;
  - 14-character code with a check character;
  - colour bands + blank well;
  - NDDK protocol;
  - region maps paused for NCB's kit.
- **S:** the MVP adds the guided NDDK protocol, blank well and search.
- **V/X:** the biggest gaps are now the app, real reactions, partial reaction, and Tests C/D.

## Confidence verdict

- **Design and trust layer: confident.** Each part exists for a reason, alternatives were tested and lost, and the failure modes are tested.
- **Colour accuracy: not established.** It is simulated on a DSLR sensor model and needs one afternoon with real phones to begin to confirm.
- **Product fit: unknown.** No user has been consulted.

More design work would add little. The remaining unknowns can only be closed by real phones, NCB and people. **Recommendation:** start the deck now, because the idea-submission portal closes 30 Sep 2026. Run the real-phone test in parallel, and present the colour numbers as "simulated, with a validation plan ready".
