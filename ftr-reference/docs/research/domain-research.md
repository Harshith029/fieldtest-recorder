# Domain research — what could change the architecture

Primary sources first. "Secondary" = news/blog/legal summary. Retrieved 24–29 Sep 2026.

## Findings that changed the design

| # | Finding | Source | Type | Architectural consequence |
|---|---|---|---|---|
| D1 | Bombay High Court (Justice Sandeep K. Shinde), *Sagar Parshuram Joshi v. State of Maharashtra*, Bail Application (ST) No. 4761/2020, 15 Jan 2021 (AIRONLINE 2021 BOM 151): field testing is "left to the experience, knowledge and perception of Law Enforcement Officer"; the process "is arbitrary" because, unlike NIJ standards in the US, no Indian colour-test standard was produced; a "bare reference of field test being conducted… in the panchanama is not 'sufficient material'"; test memos not filed. Bail granted under NDPS s.36A(4) (charge sheet incomplete without the chemical analyser's report). 65 g amphetamine | https://indiankanoon.org/doc/90970274/ | **Primary** (judgment text) | Two product requirements: (1) a **documented colour standard** per kit; (2) a **printable field-test report** for the charge sheet |
| D1b | Delhi High Court (Justice Amit Sharma), *Masibur Khan v. State*, 31 May 2023, citing D1: field test is "only indicative"; natural drugs (ganja, charas, opium) identifiable by colour, texture, smell; **absence of a field test does not vitiate the procedure when the FSL confirms** | https://indiankanoon.org/doc/91398841/ | Primary (judgment text) | **Narrows our legal claim:** field-test records matter most at the **pre-lab stage** (seizure, remand, bail, charge-sheet completeness, Rule 10(2) sampling, reasonable belief), not for conviction once the lab confirms |
| D2 | NIJ Standard-0604.01 (2000) defines colour-test reagents/kits: final colours given as **Munsell notation** + ISCC-NIST names; "final colour" generally within 1–2 min after intermediates disappear; kits must state drugs detected and time for final colour; 12 common reagents with a table of outcomes | https://www.ojp.gov/pdffiles1/nij/183258.pdf | Primary (US standard) | Kit profile modelled on this structure (reagent × substance × colour × read time). Gave us real reaction colours for E6–E11 |
| D3 | Many substances give the same colour with a reagent (e.g., cobalt thiocyanate: cocaine, ephedrine, methadone, pseudoephedrine… all "greenish blue"; Marquis: heroin ≈ chlorpromazine; Mecke: morphine = codeine = MDA) | Same NIJ table | Primary | Output must be a **colour group + known cross-reactants**, not a drug identity (E6, E8) |
| D4 | NDPS Rules 2022: kit result drives classification (Rule 3(1)), grouping for sampling (Rule 10(2)), Form-1 item 5; lab reports to Magistrate and IO within 15 days (Rule 14) | GSR 899(E) | Primary | Unchanged: legal hooks for records and lab loop |
| D5 | NCB handbook: test every package; record in panchnama; field test not evidence of identity; good-faith defence if lab negative | narcoticsindia.nic.in/DLEA/1.pdf | Primary | Unchanged: record = proof of procedure |
| D6 | NCB uses "DD kits" for prima facie determination | MHA RS USQ 3259, 24 Mar 2021 | Primary | Confirms kits exist and are the target |
| D7 | UNODC field kits contain test tubes, spot plate, pipettes, glass rod, spatula; many commercial kits use glass ampoules in tubettes | UNODC kit page (search summary; page later 404), vendor pages | Secondary | Capture layouts must support spot plates AND tubes/ampoules (profile-defined) |
| D8 | NCB Vision Document 2026–2029 (released 27 Jun 2026): modernisation, synthetic drugs, precursors, AI profiling, surveillance | https://vajiramandravi.com/current-affairs/drug-control-in-india/ | Secondary | Synthetic drugs and new substances are often outside classic colour tests → "not covered" outcome matters; precursor kit (PCDK) relevance grows |
| D9 | No Indian government app for digital field-test recording found in searches (2021–2026) | Web searches, 24–29 Sep 2026 | Absence of evidence (not proof) | Not solving an already-solved problem, as far as public sources show |
| D10 | Class 3 DSCs are legally recognised signatures (IT Act ss.3, 5); CCA runs an offline root | CCA / e-Gov guidelines | Primary | Supervisor-signed device bindings |
| D11 | BNSS s.105 video; BSA s.63 certificate with hash; BPR&D SOP: hash on phone | BPR&D SOP | Primary | Certificate data output |
| D12 | SIMS: every NDPS case entered on Form F within 48 h of FIR | Millennium Post (2020) | Secondary | Pre-fill / export, not replace |

## Have we misunderstood the real-world process?
- **Partly, yes (corrected).** We treated "classification" as deciding drug identity. The standards (D2, D3) and the court (D1) show the real gap is *documented, reproducible interpretation of a colour against a published standard*, plus *a report that exists*. Identity is the lab's job.
- **Deeper problem behind the stated one:** India lacks a published colour-test standard for field kits (D1). Our kit profiles, if NCB publishes them, would be that standard. This is the strongest government-relevance argument we have.
- **Constraint not in the statement:** interpretation must be defensible in bail hearings — reports must be attachable to charge sheets (D1).
- **Existing systems to integrate, not replace:** e-Sakshya (video), SIMS (case data), panchnama (paper, witnessed).

## Still unknown
Kit physical format and reagent list for NCB's NDDK/PCDK/KDK; read times; whether NCB wants to publish a standard; API access.
