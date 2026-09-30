# Verification of the external review (29 Sep 2026)

Each claim was checked against the current code, the documents in `docs/sources/`, and primary web sources.
- **CONFIRMED:** reproduced or read in the source.
- **STALE:** true when the review was written; fixed earlier today.
- **NOT RE-RUN:** the reviewer's own experiment; the principle was checked but not the number.
- **WRONG / NOT IN SOURCE:** the claim doesn't hold as stated.

The code checks are in a script run against `ftr-reference/` (not kept in the project).

## Code and design defects

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| 1 | A clear well (no colour change) never comes out "negative" | **CONFIRMED** | Clear well → inconclusive in all 9 demo profiles; the NIJ table has no blank or no-reaction rows |
| 2 | Simon's region map calls a white well positive | **CONFIRMED** | L* 88–95 neutral → positive. Cause: 1 training row labelled MDMA at L* 92.1 (glare). Cobalt has 2 such rows at L* 86–88. |
| 3 | Lightness decides substance; the rule works at only one sample amount | **CONFIRMED** (own model: reflectance^k) | Cobalt: k=0.8 (20% less) → 0/7 group positive; k=1.4 → 6/10 other blues called positive. Marquis/Mecke drop to 3/6 and 1/6 at k=0.8 and 1.4. Dimethoxy-meth (Simon's deep blue, a secondary amine) is labelled non-target. |
| 4 | Records carry no timestamp or GPS | **CONFIRMED** | Signed body = device_id, counter, prev, kind, payload, image hash; nothing requires time or GPS. The architecture page's "Meets" was a design claim, not code. |
| 5 | No searchable log in code | **CONFIRMED** | No search or query path in `sync_server.py` or anywhere else |
| 6 | Verifying one raid needs every earlier record on the phone | **CONFIRMED** | RAID-2-only bundle → "chain broken at counter 4" |
| 7 | "Also consistent with" misses the true substance on JPEG | **STALE** | Fixed in rev 6: positive calls list the whole documented group (`kit_profile._consistent`) |
| 8 | Attestation success path never exercised | **CONFIRMED** | E15 passes only by rejecting development-device samples. The "root list out of date" point was withdrawn by the reviewer and agrees with our E15. |
| 9a | Binding doesn't sign `device_id` | **CONFIRMED** | A binding copied under a second device_id verifies, so one key can present two chains |
| 9b | Panchnama code has no check character | **CONFIRMED** | A 1-character typo gives the same message as tampering |
| 9c | README missing scikit-learn | **STALE** | Fixed today |
| 9d | Not a git repo; on OneDrive | **CONFIRMED** | — |
| T1 | Integers above 2^53 can be edited and still verify | **CONFIRMED** | `canon(2^53+1) == canon(2^53)`, so the same signature covers both. Java disagreement: not checked. 2^53 ns = 104.2 days (arithmetic correct). |
| T2 | Sync server crashes on a malformed record inside a signed envelope | **CONFIRMED** | Record without body / body without counter / string record → unhandled KeyError, KeyError, TypeError |
| D | Docs say attestation is a placeholder; page has 5 stacked revisions | **STALE** | Fixed today (single rev-6 page, docs updated) |
| D2 | Earlier dossier's reagent blank and "officer reads first" were dropped | **CONFIRMED** (blank); **PARTLY** (officer-first kept for the pilot only) | Dossier D1, D2 |
| L | Card assumes two fixed wells | **CONFIRMED** | `colour_engine.py:27` |

## Domain and legal claims

| Claim | Verdict | Evidence |
|---|---|---|
| NCB's kit is the Narcotic Drugs Detection Kit, Tests A–E in flow-chart order | **CONFIRMED** | NICFS guide Figs 8.12–8.16, rendered from `docs/sources/`:<br>- A = A1 + A2 on a spot plate (opium; morphine/codeine/heroin; amphetamines/mescaline);<br>- B = cannabis in a tube, read the **lower layer**;<br>- C = methamphetamine/methylphenidate;<br>- D = barbiturates;<br>- E = blue for cocaine **or** methaqualone, then E3/E4 separate them.<br>Positives are **colour ranges**. The spot plate has 3 wells. |
| Test B is Fast Blue B (UNODC Test 5) | **PLAUSIBLE** | The procedure matches (solid reagent, 25 + 25 drops, lower layer red). The chart doesn't name reagents, and the UNODC manual is scanned and wasn't checked page by page. |
| Our NIJ profiles don't match; Duquenois-Levine isn't the Indian cannabis test | **CONFIRMED** | Only Test A (≈Marquis-type) and Test E (cobalt-type) overlap with our demo reagents |
| Bombay HC: NCB "has not prescribed the standards"; "arbitrary"; "dark brown"; no test memos | **CONFIRMED** | Judgment text, indiankanoon doc 90970274 |
| "which sugar also gives" (dark brown) | **NOT IN THE JUDGMENT** | The reviewer's chemistry note; don't attribute it to the court |
| Default-bail reasoning is before a larger SC bench | **CONFIRMED** | *Hanif Ansari v. State (NCT of Delhi)*, referred April 2024; no final ruling found. Also: Sagar Joshi bail was under CrPC s.167(2), read with NDPS s.36A(4). |
| MDMA 0.5 g / 10 g; methamphetamine 2 g / 50 g | **CONFIRMED** | S.O. 1055(E), 19 Oct 2001 |
| Anuraj case: alleged MDMA turned out to be methamphetamine | **CONFIRMED** | Kerala HC 2024: commercial-quantity MDMA alleged, lab found intermediate-quantity methamphetamine |
| Portal: ≤ 6 slides including title, PDF, idea title + description; nomination and submission close 30 Sep; 33/500 ideas; 4–5 teams per PS | **CONFIRMED** | Template slide 7; SIH 2026 Guidelines; our saved PS data |
| 9 public repos; one has a phone app, real card photos, hardware signing, s.63 | **PARTLY** | GitHub shows 5 repos tagged SIH26231. *Pranav-error/sih-2026-field-drug-testing* has a Flutter app, a printed ArUco card, StrongBox/TEE signing with attestation, a draft s.63 certificate and liveness. None of those opened mention the panchnama, Rule 10(2), the NCB kit tests or the lab loop. |
| Blank well 24/24 vs 14/24; range model 97–100% across 0.5–1.4× amount | **NOT RE-RUN** | The principle is sound; our amount test supports the need for it |
| Header/payload split fixes disclosure (5/5 attacks) | **NOT RE-RUN**, one refinement | If the signed header carries time, GPS or operation, withheld cases still leak when and where other raids happened. The header should hold only device, counter, prev and payload hash; everything else goes in the payload. |

## Fixes applied (same day, revision 7), each with its test

| Finding | Fix | Test result |
|---|---|---|
| 1 Clear well never negative | Blank (reagent-only) well in every photo, zone W2 on card v2. Within 6 ΔE00 of the blank = "negative, no colour change". Without a blank → inconclusive "no blank in frame". | Clear well → negative 99.0–100% on every profile (E17) |
| 2 Simon's map: white = positive | Training readings > 20 ΔE00 from their documented colour dropped. A map cell needs 3 readings within 6 ΔE00. A map "positive" must lie within 12 ΔE00 of a documented positive colour. | White/grey L* 88–95 → not positive (E17) |
| 3 Amount / lightness | **Band model**: each outcome = chart range × 0.5–1.6× amount (Beer-Lambert vs the blank); positives need clear separation from the blank and from non-target bands. | False positives 0.0% on all 4 NIJ reagents (rule: up to 11.7%); positive-group sensitivity 17–27% → 29–75% (E17). Same-hue substances overlap → inconclusive. |
| NCB kit | `nddk.py`: Tests A–E as a signed protocol (reagent order, drops, vessel, lower layer for B, flow charts I/II), bands from the chart swatches (approximate), results combined across tests, NDPS quantity warning | NDDK bands: 89.1% correct, 1.7% [1.2–2.2] wrong (all errors in partially reacted wells). Flow-chart scenarios behave as printed. Tests C, D: chart not printed → inconclusive. |
| 4 No time/GPS | Payload requires `device_time_ms`, location (fix: lat/lon ×1e7, accuracy cm, mock flag; or "unavailable"), operator ID matched to the binding. GNSS time when available. Server countersigns receive time. | Signed record without time/GPS rejected; mock location flagged (E5) |
| 5 No searchable log | `record_log.py` (on device, SQLite FTS, re-verifies on open) + `Server.search` | 10/10 log checks; server search by case + result (E14 #14) |
| 6 One raid discloses all | Signed header = device, counter, prev, payload hash only; anchor holds each phone's counter range; other cases disclosed as headers only | RAID-2 verifies with RAID-1's 7 records withheld; withholding a record of the anchored raid is caught (E5) |
| 8 Attestation success path | Synthetic production-style chain under a test root | Accepted by `attestation.py` and end to end by the strict verifier; same chain rejected against Google's roots; unlocked and software-key variants rejected (E15) |
| 9a device_id unsigned | Binding signs `device_id`; verifier checks it | One key as two devices caught (E5) |
| 9b No check character | 14-char code with Luhn mod-32 check; typos reported as typos; 0/1/8 read as O/I/B | 434/434 single-character errors, 12/13 adjacent swaps caught |
| T1 > 2^53 | Signer and verifier reject integers beyond ±(2^53−1) | Caught at signing and verification (E5, E10) |
| T2 Sync crash | Each record validated inside a signed envelope | 5 malformed records rejected one by one, good record kept (E14 #13) |

Attack suite: 18/18 caught (12 original + 6 new). E10: 13 malformed bundles rejected cleanly, 0 unhandled. E14: 15/15. E15: 18/18.

## What this changes in our own claims
1. **"0–1.6% wrong" holds only at exactly the NIJ chip depth.** Our simulation never varied sample amount. With ±20–40% amount, the point-distance rule fails.
2. **"Kit format unknown" was wrong.** NCB's kit chart was in our own sources folder as an image, and we missed it.
3. **The requirement check claimed "Meets"** for timestamp, GPS and the searchable log. The reference code has none of these yet.
4. **Region maps trained on simulated NIJ readings should be paused.** The Simon's map shows how one bad label becomes a signed false positive.
