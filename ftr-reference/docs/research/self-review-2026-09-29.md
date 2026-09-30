# Self-review against the continuous-investigation brief (29 Sep 2026)

Judged section by section against the brief. PASS = done with evidence; PARTIAL = done but with material gaps;
FAIL = not done. Integrity problems in my own work are listed separately and are not softened.

## Section-by-section

| # | Brief section | Verdict | Evidence | Gap |
|---|---|---|---|---|
| 1 | Don't trust the current solution; re-evaluate everything | PARTIAL | Problem interpretation, classifier, AI/ML, night mode, verifier re-evaluated with experiments | DB design, APIs, data flow, UX, integrations, deployment not re-evaluated this round |
| 2 | Unresolved problem register | PASS | `unresolved-problems.md`, 17 items with required fields; code scan found 3 hidden problems | "Evidence required" and "experiment required" merged into one column; only `.py` files scanned |
| 3 | Continuous experiment mode | PASS | E6–E11 hypothesis → build → measure → decide | Measured accuracy and latency only; no memory/CPU, complexity, usability or cost measurements |
| 4 | Search for better solutions | PARTIAL | Classifier (4 variants), calibration vs ML, night-mode variants, rule vs frozen map | Not tested: record format alternatives, DB model, sync strategy, capture UX alternatives, server-side vs on-device processing |
| 5 | Fresh domain research | PASS (strong finds) / PARTIAL (depth) | NIJ 0604.01, Bombay HC judgment, NCB Vision 2026–29, absence of an Indian app | HC judgment read only via secondary summaries; no primary on phone Camera2 capability share, e-Sakshya API, lab turnaround, any Indian (BIS) kit standard; kit tender search failed |
| 6 | Serious SIH winner research | PARTIAL (weak) | 10 sources, 3 firsthand; 14 questions answered | Thin evidence; no finalist/loser accounts; no per-winner detail on prototype/validation; NCB 2024 winners known only from a search summary; several blogs blocked (403) |
| 7 | Winning-characteristics model | PASS | STRONG/WEAK/UNKNOWN/NEEDS VALIDATION table; highest-leverage weaknesses named | — |
| 8 | Real differentiator | PASS | Colour-standard insight backed by NIJ data + court + E6/E8 | Must still be tested on real judges/users |
| 9 | Attack the product | PARTIAL | Judge simulation; competitor copy test | Missed the strongest attack: **"why won't NIC just add a field-test module to e-Sakshya?"** Answer should be: build the engine, standard and report format as a module/SDK that can live inside e-Sakshya, not only as a standalone app |
| 10 | Attack the technical architecture | PARTIAL | ADR list; removed components | Server/DB/API not re-attacked this round |
| 11 | Worst-case tests | PARTIAL | E10 hostile images and malformed bundles; attack suite; E9 night | System failures (DB, network, storage, auth, deployment) and user failures (abandoned workflows, concurrency, repeats) designed only, not tested — no server/app exists |
| 12 | Measure the system | PARTIAL | Every existing component measured; NOT YET VERIFIED labels used | **No confidence intervals on experiment results** (only on the future plan); single seed per run, no variance across seeds |
| 13 | Validate the product, not just the code | **FAIL** | — | No USER → WORKFLOW → PAIN → INTERVENTION → OUTCOME model with work eliminated / time saved / errors prevented was produced this round; **zero users consulted** |
| 14 | Demo / pilot / production | PARTIAL | Table exists on architecture page (earlier revision) | Not updated for rev-5 decisions (validation data now required for region maps; device capability probe; report) |
| 15 | Experiment until diminishing returns + log | PASS | `experiments.md` | Diminishing returns reached only for *simulation*; the next gains require real phones, kits and people |
| 16 | Don't destroy working components without reason | PASS (process) / **FAIL (follow-through)** | Old classifier kept for comparison; changes evidence-driven | **Accepted design is not in the engine**: `read_capture` still calls the old substance-nearest `classify`; region maps exist only in `e11_region_map.py` |
| 17 | Current vs proposed architecture | PASS | `architecture-decisions.md` with OLD/WHY/NEW/EVIDENCE/BENEFIT/TRADEOFF | — |
| 18 | Hostile judge simulation | PASS | `judge-simulation.md`, 6 personas, 19 questions, weak answers → actions | — |
| 19 | "Would this actually work?" (11 questions) | PARTIAL | 4 of 11 answered in chat | Missing: buzzword removal, 5-year regret, 48 hours, 6 months, copy-the-UI (answered only in competitor file) |
| 20 | Final output A–Z | PARTIAL | Given in chat | Letters merged (L–R, S–T, V–X); M, O, P, Q, R only said "unchanged" instead of restating |
| + | `docs/research/` evidence files | PASS | All 7 requested + judge simulation | — |

## Integrity problems in my own work

1. **Overstated certainty.** "0% wrong" on 70–100 readings per light (E11) only proves < 3.6–5.1% at 95% confidence. E4's 0/1,384 proves < 0.27%. E8 Marquis 7/412 = 1.7% has a 95% CI of 0.7–3.5%. These bounds were not reported.
2. **Docs ahead of code.** ADR-07/08 are "Accepted", but the reference engine still uses the superseded classifier.
3. **Undisclosed data gap.** NIJ parse got 0 of 4 Duquenois-Levine rows (the cannabis test) and missed a few others.
4. **Optimistic evaluation.** E7/E11 train and test on the same simulator, so learned boundaries fit the simulator's own noise. Stated once as a caveat; should be on every result.
5. **Secondary sources carrying key claims.** The Bombay HC finding is now central to the pitch but was read only via a news summary and a law-firm note.
6. **Documentation sprawl.** The architecture page has five stacked revisions with a banner saying later ones supersede earlier ones. A team member reading top to bottom meets contradictions (e.g., older "no model to train" text vs rev-5 learned region maps).
7. **Recommended actions I could have prepared but didn't:** a printable card file, a script to run the engine on real phone photos, an interview guide. All three are within my capability.

## Strategic miss

The SIH idea PDF is due **30 Sep 2026** and does not exist. Without it, none of this work reaches a judge.

## Fixes, in order of leverage
1. Build the 6-slide idea PDF on the rev-5 insight (deadline).
2. Wire colour groups + region-map lookup into `read_capture`; profile-driven thresholds; re-run E4/E6 through the real path.
3. Report 95% bounds on every result; re-run key experiments over several seeds.
4. Generate the printable card (150 × 105 mm, 18 mm ArUco) + a `read_photos.py` CLI + capture protocol, so the real-phone test can happen this week.
5. Interview guide for officers / forensic chemist / prosecutor; product-validation model (Section 13).
6. Fetch the primary HC judgment; fix the NIJ parser (Duquenois-Levine).
7. Consolidate the architecture page into one clean current version.
8. Position the engine + standard + report as an e-Sakshya-embeddable module.

## Follow-up: round 3 (same day)

At the user's instruction, the deck (fix 1) is deliberately **on hold until the solution is judged confident**. The rest:

| Fix | Status | Where |
|---|---|---|
| 2. Accepted design in the engine | DONE | `kit_profile.py` (rule + region map, colour groups, consistent-with list), wired into `read_capture` and `read_capture_linear`; E12 runs through it |
| 3. Intervals and seeds | DONE | `stats.py`; every rate in `validation-results.md` has a 95% interval; E12 pooled over 3 seeds |
| 4. Card + real-photo reader + protocol | DONE (card PNG generated; PDF writer fixed to lossless) | `tools/make_card.py`, `read_photos.py`, `docs/validation/real-phone-capture-protocol.md` |
| 5. Product-validation model + interview guide | DONE (model); interviews NOT DONE | `product-validation.md` |
| 6. Primary judgment; NIJ parser | DONE | D1 now read from the judgment text; D1b Delhi HC narrows the legal claim; `tools/parse_nij.py` gets all 10 D-L rows |
| 7. One clean architecture page | DONE | `docs/pages/FieldTest-Recorder-Architecture.html`, revision 6 only |
| 8. e-Sakshya-embeddable SDK | DONE (design) | ADR-13 |

Gaps from the section table, re-checked:

- **§11 system and user failures:** now tested on a reference server. E14 covers 13 scenarios, including restore from an older backup, which exposed a real evidence-loss bug (fixed with durable checkpoints).
- **§4 alternatives:**
  - capture tier: JPEG vs RAW (E13);
  - checkpoint policy (E14);
  - liveness designs (E16 v1 vs v2);
  - attestation "flag" vs full chain (E15).
- **§12 measurement:** memory and CPU on a phone are still unmeasured; they can't be measured without the Kotlin build.
- **§13:** still **zero users consulted**. This remains the biggest gap and cannot be closed by me.

New problems the fixes surfaced:
- E12: JPEG misreads out-of-sRGB colours (cobalt 21% wrong). Fixed by RAW capture (E13).
- E12: the "also consistent with" list missed the true substance. Fixed by listing the whole group.
- E14: evidence loss on restore. Fixed.
- E16: noise let 29.5% of mid-capture swaps through. Fixed, now 0.5%.
- E15: Google's samples are development devices, so a real locked-phone pass is still unshown.
