# SIH winner pattern analysis

Goal: learn **patterns**, not copy projects. Public information about winners is thin, mostly self-reported,
and suffers from survivorship bias (we rarely see finalists who lost). No judge score sheets are public.
Nothing below proves causation.

## Sources

| # | Year | Source | Type | What it tells us |
|---|---|---|---|---|
| W1 | 2026 | SIH 2026 Guidelines, sih.gov.in | Official | Idea criteria: novelty, complexity, clarity in the prescribed format, feasibility, practicability, sustainability, scale of impact, user experience, future work. 4–5 teams per PS to finale; organisation may declare no winner; ₹1.5 lakh |
| W2 | 2023 | sih.gov.in/sih2023-grand-finale-result | Official | 275 winning entries; MHA had 11 PS winners; some PS had **joint** winners (₹50k each) |
| W3 | 2023 | dev.to/heisdinesh (Team DORA, Govt of Jharkhand, infrastructure monitoring) | Firsthand | **3 judging rounds weighted 20% (idea, feasibility) / 30% (technical execution) / 50% (complete product, end-user view)** + 2 mentoring sessions; 60% of time spent understanding the problem; stakeholder validation; every member explained their part; app broke an hour before the final and was recovered |
| W4 | 2019 | GeeksforGeeks experience (HUL supply chain) | Firsthand | 4 rounds; last "power round" decisive; judges wanted business value, "less on the tech" |
| W5 | 2024 | MathWorks blog (Team Solar Masters, MathWorks PS) | Secondary (sponsor blog) | Working software + hardware + structured presentation; **quantified improvement (20% over fixed panels)** |
| W6 | 2024 | The Bridge Chronicle (AIT Pune, NIA problem) | News | Law-enforcement winner: **Cyber Triage Tool** that "simplifies evidence importation and analysis" for investigators — a workflow tool, not a dashboard |
| W7 | 2024 | sih.gov.in 2024 results (via search) | Official | Two NCB PS winners (drug-trafficking identification); solution details not public |
| W8 | 2025 | K J Somaiya announcement; SkillOutlook | College/news | Railways AI traffic-control winner among 500 teams; evaluators (TCS, Wipro, Verizon…) praised "technical maturity", "real-world deployment", "problem-centric approach" |
| W9 | 2025 | PIB (SIH 2025) | Official | ~72k ideas, ~1,360 finalist teams, 36-hour software finale |
| W10 | 2026 | Reskilll blog | Vendor blog, anecdotal | Solve the PS as written; working prototype beats slides; edge cases; ~3-minute pitch |

## Answers to the 14 questions

1. **Recurring characteristics:** a working end-to-end prototype (W3, W5, W10); visible problem understanding and stakeholder input (W3, W8); a clear end-user workflow (W3 round 3, W6); a quantified result (W5).
2. **What winners built:** complete workflows used by a named operator (site engineer, investigator), not isolated models (W3, W6).
3. **How they showed the problem:** by walking through the user's current process and pain (W3 design thinking).
4. **How they showed impact:** a measured number (W5) or a before/after workflow (W3).
5. **Feasibility:** by the thing running — rounds 2–3 weight execution and the complete product at 80% (W3).
6. **Government deployment:** evaluators explicitly praised "real-world deployment" potential (W8); law-enforcement winners fit investigators' existing evidence workflow (W6).
7. **Different from generic projects:** problem fit over breadth (W10), ownership of a real workflow (W6).
8. **Not the core reason:** tech stacks (W3 used the most common MERN + Flask stack); "AI" appears in winners and losers alike — no evidence it caused wins.
9. **Product thinking:** one operator, one workflow, one measurable change.
10. **Technical execution:** integration across components (W3 round 2 = 30%); recovery from failures on the day (W3).
11. **Validation:** stakeholder validation is mentioned by winners (W3); quantified tests (W5).
12. **Demos:** short and live; progress visible across rounds (W3, W4).
13. **Storytelling:** business/real-world value first, technology second (W4, W8).
14. **Judge questions:** inclusivity and "no user could find fault" in round 1 (W3); every member must be able to answer (W3).

## What this means for us (and where we are weak)
- The **50% final round is about the complete product from the end user's view.** Our strength is depth (trust model, colour science); our weakest area is the officer-facing app, which doesn't exist yet.
- **Stakeholder validation is our biggest gap**: we have not spoken to a single officer, chemist or prosecutor. Winners report doing this.
- **A quantified result**: we have simulated numbers; we need at least one measured number on real phones before the finale.
- Judges will ask every member; the team must understand the trust model and colour pipeline, not just the demo.

## Winning-characteristics model applied to our project

| Area | Status | Why |
|---|---|---|
| Problem understanding | **STRONG** | Legal chain (NDPS Rules), Bombay HC judgment, NIJ standard, cross-reactant insight |
| Technical correctness | STRONG (trust layer) / NEEDS VALIDATION (colour) | E5, E10 in real code; colour only simulated, DSLR sensor model |
| Real-world value | STRONG argument / NEEDS VALIDATION | Directly answers a court's criticism; no officer has confirmed it |
| Innovation | **STRONG** | Documented, signed colour standard + verifiable, complete records + frozen region maps |
| Feasibility | STRONG | Reference implementation runs; Kotlin port pending |
| Robustness | STRONG in simulation / UNKNOWN on phones | E4, E9, E10 |
| Security | STRONG design / NEEDS VALIDATION | Attestation verifier implemented (E15); no locked production phone enrolled yet; liveness limits stated (E16) |
| Scalability | STRONG (by analysis) / NOT YET VERIFIED | Tiny workload; server not built |
| Deployability | NEEDS VALIDATION | APIs, DSCs, device capabilities unknown |
| User experience | **WEAK** | No app, no usability test |
| Measurable impact | **WEAK** | No baseline data from the field |
| Validation | **WEAK** | No real kits, no real phones yet |
| Demo quality | UNKNOWN | Not built |
| Explainability | **STRONG** | Deterministic lookup, published standard, re-runnable in court |
| Government integration | NEEDS VALIDATION | File exports work; APIs unverified |
| Maintainability | STRONG (design) | Shared libraries, tests; unproven over time |

**Highest-leverage weaknesses, in order:** (1) talk to users (officers, a forensic chemist, a prosecutor);
(2) test on real phones with a printed card and safe dyes; (3) build the officer-facing app flow;
(4) measure time per package.
