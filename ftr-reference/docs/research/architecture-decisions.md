# Architecture decisions (ADR log) and current-vs-proposed comparison

Status: **Accepted** (evidence supports it), **Proposed** (evidence partial), **Superseded**.

## Current (revision 4) vs proposed (revision 5)

| Area | OLD (rev 4) | Why insufficient | NEW (rev 5) | Evidence | Expected benefit | Tradeoff |
|---|---|---|---|---|---|---|
| What the app outputs | positive / negative / inconclusive per target drug | Real colour tests are class-level; many substances share colours (cocaine = ephedrine; morphine = MDA) | **Colour group + "also consistent with" list** of substances known to give that colour; still reported as positive / negative / inconclusive for the kit's positive pattern | E6, E8, NIJ Table 1 | Honest, matches the standard, still meets the PS categories | Officers see a list, not a single name |
| Decision rule | Global hand-set ΔE00 thresholds | Best thresholds differ per reagent; rule abstains too much on clustered dark colours (Mecke 32%) | **Signed CIELAB region map per kit profile**, learned offline from validation reactions and frozen; conservative rule only until validation data exists | E7, E11 | Mecke correct 68% → 87–97% at ≤1% wrong; deterministic, re-runnable | Needs validation data; region maps must be governed |
| Kit profile | Config of expected colours | Court found no documented colour standards in India | **Published, signed colour standard** modelled on NIJ 0604.01 (reagent × substance × Munsell/Lab × read time × layout × region map) | Domain D1, D2 | Answers the court's criticism directly | NCB must own and publish it |
| Profile safety | none | Fine categories below camera resolution cause wrong calls | **Profile linter**: rejects categories closer than the measured resolvable distance (~8–10 ΔE00) | E6, E8 (cobalt) | Prevents impossible profiles | Some kits get coarser categories |
| Night mode | Flash/no-flash, device-agnostic | Fails completely with auto processing | **Tiered by device capability**: locked + linear flash/no-flash → single flash frame → reject/torch | E9 | 100% vs 87% vs rejected, never wrong | Device capability probe needed |
| Card | 80-unit markers, 4 required | 64% detection under blur | 120-unit (~18 mm) markers, 3 of 4, matte laminate; fit error doubles as card-authenticity check | E4, E10 | ~96% detection; fake cards rejected | Slightly larger card |
| Well reading | Median of well | Partial glare biases colour | Darker-half estimator + live glare warning | E4 | Fewer glare-induced errors | — |
| Verifier input handling | Assumed well-formed | 5 crash paths on malformed bundles | Strict schema, size caps, fail-closed | E10 | 0 unhandled; still 12/12 attacks | — |
| Field-test report | Implied by documents | Court noted no field-test report was filed | **Printable signed Field Test Report** (per package: photo, colour, group, cross-reactants, profile version, hash, QR) for the charge sheet | D1 | Direct procedural value | — |

## Revision 6 changes (this round, all evidence-driven)

| Area | OLD (rev 5) | Why insufficient | NEW (rev 6) | Evidence |
|---|---|---|---|---|
| Accepted design in code | Docs said colour groups + region maps; engine still used the old classifier | Docs ahead of code | `kit_profile.py` (signed profile, rule or frozen map, checker) wired into `read_capture` | E12 through the real path |
| Capture tier | JPEG everywhere; RAW only for night mode | Saturated reaction colours (cobalt blues, some Mecke/Simon's) lie outside sRGB; JPEG misreads them by ~8 ΔE00; cobalt 21% wrong | **RAW/linear capture is the primary tier**; JPEG + region map is the fallback; profiles flag colours that need RAW | E13, E12 |
| Region maps | Core of the decision | With RAW, the simple rule already reaches ~89–92% correct, 0–1.6% wrong | Region maps become a **JPEG-fallback component**, not the core | E12 |
| "Also consistent with" list | Built from distances | On JPEG, biased readings dropped the true substance (cobalt 3/251) | Positive calls list the **whole documented colour group**; 100% contain the true substance | E12 recheck |
| Profile checker | One threshold (8 ΔE00) | Cobalt neighbours at 8–10 ΔE00 still gave 1.6% wrong | ERROR < 8, WARN 8–10, WARN "needs RAW" for out-of-gamut colours | E6/E8/E12/E13 |
| Phone deletes local copies | After receipt + any checkpoint | Disk loss + restore from an older backup permanently lost 5/16 records | Only after a **durable** checkpoint (taken after a backup) — 16/16 recovered | E14 |
| Device attestation | Boolean flag in the binding | Placeholder | Bindings carry the Android attestation chain + enrolment nonce; verifier checks chain → Google roots, revocation list, hardware level, verified boot, locked bootloader, challenge, key match; strict by default | E15 |
| Staged captures | Timed capture + video cross-link (untested) | No evidence | **Capture starts before the drop**; liveness rule on the colour track: staged/pre-reacted wells 0% accepted, mid-capture swaps 0.5%; swaps timed at the drop and replays still pass → need non-colour controls | E16 |
| Deployment shape | Standalone app | Hostile question: "why won't NIC add this to e-Sakshya?" | **FieldTest Engine as an embeddable SDK** (capture + colour engine + record format + profiles + report) with our app as reference host; e-Sakshya/NCB apps can embed it | ADR-13 |

## Decisions

- **ADR-01 Offline native Android capture.** Accepted. Hardware-backed keys, camera control, no network in the field.
- **ADR-02 Device-signed, hash-chained records + panchnama anchor.** Accepted (E3, E5).
- **ADR-03 Supervisor-signed device bindings (DSC); server is never a trust root.** Accepted (E5 admin attacks).
- **ADR-04 RFC 8785 JSON, ASCII keys, no floats, SHA-256, ECDSA P-256.** Accepted (E5).
- **ADR-05 Reference card with ArUco markers, grey-ramp + 3×3 correction.** Accepted (E1, E4). Root-polynomial not needed so far.
- **ADR-06 Card is required; no "AI instead of the card".** Accepted (E7: ML on raw colours up to 5.6% wrong under unseen lights).
- **ADR-07 Colour-group output with cross-reactant list.** Accepted (E6, E8).
- **ADR-08 Decision = signed, frozen CIELAB region map learned offline.** Proposed → Accepted pending real validation data (E7, E11).
- **ADR-09 Tiered night mode.** Accepted (E9); device mix unknown (U3).
- **ADR-10 Thin Spring Boot monolith + PostgreSQL + S3 object lock; no queue/cache/search cluster.** Accepted by analysis; load NOT YET VERIFIED.
- **ADR-11 No blockchain, no LLM, no online ML.** Accepted: no requirement justifies them; E7 shows the value comes from calibration and data-fitted boundaries, not online models.
- **ADR-12 File exports as the integration baseline.** Accepted (API access unverified).
- **ADR-13 Ship the engine as an embeddable SDK; our app is the reference host.** Accepted. The durable value is the record format, colour standard, engine and verifier, not the UI. If NIC/MHA prefer to extend e-Sakshya, the SDK drops in; if not, the standalone app works. Reduces the "why not extend an existing portal?" risk.
- **ADR-14 RAW/linear capture is the primary tier; JPEG + region map is the fallback.** Accepted (E13, E12). Device support is unverified (U3).
- **ADR-15 Delete local copies only after a durable (post-backup) checkpoint.** Accepted (E14).
- **ADR-16 Strict attestation by default; flag only in test mode.** Accepted (E15). A pass on a real locked production phone is not yet demonstrated.
- **ADR-17 Capture from before the reagent drop; liveness check on the colour track.** Accepted (E16) with stated limits.
- **ADR-08 amended:** region maps are the JPEG fallback, not the core decision.
- **ADR-18 Record = signed header {device, counter, prev, payload hash} + payload.** Accepted (E5 v2). The payload carries kind, operation, package, operator (must match the binding), device time, GNSS time, location with mock flag, image hash. The anchor holds each phone's counter range, so one raid can be disclosed with other cases withheld. Also: `device_id` signed into bindings; integers limited to ±(2^53−1); a 14-character panchnama code with a check character; the server countersigns receive time.
- **ADR-19 Band decision model + blank well replace point distances.** Accepted (E17). Outcomes are ranges (as kit charts print them), extended over 0.5–1.6× sample amount by Beer-Lambert. Every photo has a reagent-only blank well; within 6 ΔE00 of it = "no colour change". The "consistent with" list includes every band within tolerance + margin.
- **ADR-20 Build around NCB's Narcotic Drugs Detection Kit.** Accepted (NICFS guide Figs 8.12–8.16). Tests A–E as a signed guided protocol following the printed flow charts; results combined across tests; NDPS quantity warning when candidates differ. NIJ reagents remain only as a second, published colour dataset for testing.
- **ADR-21 Region maps guarded and paused for NCB profiles.** Outliers removed, 3-reading density, "positive" only near a documented positive colour. No maps for the NCB kit until NCB/CFSL validation data exists.
- **Superseded in round 4:** point-distance rule as the primary decision (rev 6); records without time/GPS (rev 6); whole-history disclosure (rev 6); unsigned device_id (rev 6); a code without a check character (rev 6); NIJ reagents as the product's target kit (rev 6).
- **Superseded:** Merkle transparency log (rev 2), C2PA (rev 2), "AI colour-curve classifier" (rev 2), server-issued bindings (rev 2), substance-nearest classification (rev 4), global thresholds (rev 4), distance-only cross-reactant lists (rev 5), delete-on-any-checkpoint (rev 5), `hw_attested` flag as trust (rev 5).

## Removed because they had no strong reason to exist
Blockchain, microservices, Kubernetes, Redis, Elasticsearch, message queues, chatbots, vector databases,
decorative dashboards, online model retraining.
