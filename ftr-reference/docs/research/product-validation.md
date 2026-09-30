# Product validation model (brief §13) and stakeholder interviews

Numbers marked **ESTIMATE** are our assumptions, to be replaced by the stopwatch study and interviews below.
Legal facts are from primary sources (see `domain-research.md`).

## 1. Seizing officer (NCB DLEO / state ANTF / police)
| Step | Today | With FieldTest Recorder |
|---|---|---|
| Test each package | Drop reagent, compare to printed chart by eye, any light | Same kit; phone guides the step, timer starts itself, card calibrates light |
| Record the result | Writes "field test indicated X" in the panchnama | Signed per-package record: photo, colour, colour group, substances the kit can't tell apart, profile version |
| Grouping for sampling (Rule 10(2)) | Judges "identical results" by eye, often later before the Magistrate | Same-photo comparison flags packages that differ |
| Form-1 item 5 (48 h) | Hand-copied | Generated from the records |
| Charge sheet | Bombay HC: "bare reference" in the panchnama is not sufficient material | Printable, signed Field Test Report per package |
| Lab result (Rule 14) | Arrives; nobody compares it with the field result | Entered once; accuracy per kit batch becomes visible |

**Pain removed:** undocumented, non-standard, unverifiable field results (primary: Bombay HC 2021).
**Work added (ESTIMATE):** ~20–40 s per package for framing the card, partly offset by generated paperwork.
**Work removed (ESTIMATE):** re-writing results into Form-1, test memos, and later explanations in court.
**Errors prevented:** misreading under bad light (E1/E9: bad light is rejected, never guessed); undetected
grouping of different substances (E2); later alteration or deletion of results (E3/E5).
**Decisions made easier:** reasonable belief at seizure; sampling lots; bail/remand arguments before the lab report.
**New information:** field-vs-lab agreement per kit batch and per officer (does not exist today).

## 2. Supervisor / zonal unit
Today: signs off panchnamas; no view of field-test quality. New: enrols devices (DSC), sees inconclusive rates,
disagreements and anchors; revokes compromised phones.

## 3. NCB HQ (profile authority / forensic advisers)
Today: supplies kits; no data on how often they give false positives (NCB handbook: lab negatives "often possible").
New: publishes the documented colour standard (signed kit profiles); monitors field-vs-lab agreement per batch;
retires a bad batch with evidence.

## 4. Court / defence / prosecution
Today: the field test is "only indicative" (Delhi HC 2023, Bombay HC 2021) and at the bail stage undocumented.
New: an offline-verifiable report showing what was tested, when, how the colour was read against a published
standard, and every substance that gives the same colour. The record helps whichever side the facts favour.

## Measurable outcomes (to be measured, not claimed)
| Outcome | Baseline source | How we measure |
|---|---|---|
| Time per package | Stopwatch: paper vs app, 6 packages, 5 volunteers | Median seconds |
| Reader agreement | Volunteers read the same proxy reactions by eye | Fleiss' κ, human vs app |
| Documentation completeness | Sample of panchnamas (if NCB permits) | Share with a verifiable per-package record |
| Field-vs-lab agreement | None exists today | Pilot: agreement per kit batch with 95% CI |

## 5. Interview guide (30 minutes each; 3–5 people)
**Who:** a serving or retired NDPS seizing officer; a supervising officer; a forensic chemist (FSL/CRCL);
a public prosecutor or defence lawyer with NDPS bail experience.
Introduce: student project for SIH, no confidential case details needed, notes only with consent.

Officers
1. Walk me through the last seizure where you used a kit. What did you write, where, when?
2. What light were you working in? Were you ever unsure about a colour? What did you do?
3. How many packages in a typical seizure? How long does testing take?
4. Which kits do you carry (narcotic drugs, precursor, ketamine)? Tubes, spot plate or ampoules? Reading time?
5. Has a lab result ever contradicted your field test? What happened?
6. What would make you refuse to use a phone for this? What would make you want to?
7. Do you use an official phone? Which model? Is e-Sakshya installed?

Forensic chemist
1. Which colour tests does the field kit use? Known false positives in Indian street samples?
2. Would a documented colour standard (like NIJ 0604.01) be useful? Who would own it?
3. Could your lab run a one-day validation of kits against reference standards?

Prosecutor / defence
1. At bail, how is the field test argued today? What is missing?
2. Would a signed per-package field-test report change that? What would make you distrust it?
3. What certificate would a court expect (BSA s.63)?

**Record:** what surprised us; what contradicts our design; the exact words used for pain points.
**Decision rule:** if two of three officer interviews say the time cost is unacceptable, redesign the flow before building more.
