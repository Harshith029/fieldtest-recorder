# Unresolved problem register (updated 29 Sep 2026, round 3)

Status: OPEN, PARTLY RESOLVED (by experiment/code; residual stated), RESOLVED (in the reference implementation).
Confidence = our confidence that the current design handles it.

| ID | Problem | Why it matters | Current solution | Status after round 3 | Evidence required | Experiment required | Confidence | Next action |
|---|---|---|---|---|---|---|---|---|
| U1 | NCB's real kits: reagents, format, read times, colours | Everything in the colour engine depends on it | **Found in our own sources (round 4):** NCB's Narcotic Drugs Detection Kit, Tests A–E, flow charts, colour ranges, 3-well spot plate + tubes; encoded in `nddk.py`. Colours sampled from a scanned chart (approximate); Tests C and D not printed; read times mostly not printed | PARTLY RESOLVED | NCB kit sheet (reagents, C/D, read times), measured chart colours | Phase-0 lab validation with amount/purity levels | Medium | Ask via SIH mentor / NCB nodal officer |
| U2 | Simulation realism (DSLR sensor, opaque wells) | All colour numbers are simulated | Printed card + `read_photos.py` + capture protocol ready | OPEN (tools ready) | Real photos | `docs/validation/real-phone-capture-protocol.md` | Medium | Run this week |
| U3 | Officers' phones: RAW and manual-control support | RAW tier (E13) and night tier 1 (E9) need it | Capability probe planned; JPEG + region-map fallback exists | OPEN | Device survey | Probe on 3+ typical phones | Unknown | Part of U2 test |
| U4 | Android key attestation | Fake devices | `attestation.py`: full chain, roots, revocation, extension; strict by default; accept path proven with a production-style test chain (E15 v2) | PARTLY RESOLVED | A chain from a locked production phone | Enrol one real phone | Medium-high | Build Android enrolment (M1) |
| U5 | Staged or replayed capture | Fabricated positives | Capture from before the drop + liveness rule (E16) | PARTLY RESOLVED: staged 0%, mid-swap 0.5% | — | Real videos (U2) | Medium | Add continuous-capture + package-label tracking; rely on s.105 video for swap-at-drop and replay |
| U6 | Officer time and adoption | If slower than paper, it won't be used | Batch mode, generated paperwork | OPEN | Stopwatch study | `product-validation.md` | Unknown | Interviews + timing |
| U7 | Court treatment of the record | Core value | BSA s.63 data, verifier, published standard; legal claim narrowed to pre-lab stage (D1b) | OPEN | Prosecutor / lawyer view | Interviews | Medium | — |
| U8 | Integration with SIMS, e-Sakshya, Parichay | Duplicate entry | File exports; SDK shape (ADR-13) | OPEN | API access | — | Low | Ask NCB |
| U9 | Supervisors' DSCs | Trust model | Test CA; fallback NCB tokens | OPEN | — | — | Medium | Ask NCB |
| U10 | Mixtures / cutting agents | Street samples | Abstain band; colour groups | OPEN | Lab data | Phase-0 with mixtures | Low | — |
| U11 | Fine categories below camera resolution | Wrong calls | Two-level checker (ERROR < 8, WARN 8–10 ΔE00) | RESOLVED in reference | — | — | High | — |
| U12 | Rule 10(2) grouping on real reactions | Sampling decision | Same-photo comparison | OPEN | Real photos | Part of U2 | Medium | — |
| U13 | Server under real load | Pilot readiness | Reference protocol tested (E14) on SQLite | PARTLY RESOLVED | PostgreSQL build | Load test on Spring Boot | Medium | M4 |
| U14 | Data retention period | Compliance | Configurable, legal hold | OPEN | NCB policy | — | Unknown | Ask NCB |
| U15 | Owner of the colour standard | Governance | Two-person signing | OPEN | — | — | Unknown | Ask NCB |
| U16 | Weak flash + sodium light, no manual control | 12% rejected | Reject + torch | OPEN | Real night photos | Part of U2 | Medium | — |
| U17 | New psychoactive substances not covered | Growing | "Not covered" outcome | RESOLVED (honest handling) | — | — | High | — |
| U18 | **Out-of-sRGB reaction colours** (new) | JPEG misreads them (cobalt 21% wrong) | RAW tier; checker flags "needs RAW"; region map as JPEG fallback | PARTLY RESOLVED (sim) | Real RAW photos | Part of U2 | Medium | Include saturated blue/green dyes in U2 |
| U19 | **Evidence loss on backup restore** (new) | Phones deleting too early | Durable checkpoints (E14) | RESOLVED in reference | — | — | High | Port to Kotlin |
| U20 | Accepted design not in code (self-review) | Docs ahead of code | `kit_profile.py` wired into `read_capture`, `read_capture_linear` | RESOLVED in reference | — | E12 through real path | High | — |
| U21 | **Sample amount and purity change colour** (review) | The point rule failed off the chip's exact depth | Band model + blank well (E17): false positives 0%, sensitivity 29–75% | PARTLY RESOLVED (sim) | Real reactions at several amounts | Phase-0 with 0.5/1/2 match-head amounts and cut samples | Medium | Add amount levels to the validation plan |
| U22 | Partially reacted wells | All remaining NCB-kit errors in E17 (1.7%) | Read the darker core; burst capture across the read window | OPEN | Real photos | Part of U2 | Medium | Test with the dye protocol |
| U23 | NCB kit Tests C and D | Not printed in the guide | App records photo + officer reading; classification "chart not available" | OPEN | NCB kit sheet | — | Low | Ask NCB |
| U25 | JPEG tier: a bright clear well can trip the glare check | Clear samples and blank wells read "glare"/"blank unreadable" in 5–15% of JPEG photos (never wrong, only inconclusive); RAW unaffected | `test_blank_pipeline.py` | OPEN | Real photos | Part of U2 | Medium | Separate "white" from "clipped highlight" in the JPEG glare test |
| U26 | Strict X.509 parsers refuse some genuine attestation certificates (found by CI) | cryptography 50+ cannot parse Google's own sample certificates (non-DER signature-algorithm encoding); real phones may emit the same, and a strict server would then refuse genuine devices | Verifier fails closed ("unparseable chain"); library pinned to 48.x in the reference | OPEN | Chains from several real phone models | Enrol real phones (M1) | Medium | Production verifier (JVM) must parse leniently but re-verify signatures over the exact bytes |
| U24 | Chart colours from a scan | Printed chart ≠ reaction colours; dark ends washed out | Dark ends modelled as higher amount, not grey | OPEN | Measured reaction colours | Phase-0 | Low | Replace with measured values |
