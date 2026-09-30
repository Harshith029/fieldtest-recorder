# Hostile judge simulation (revision 6)

Format per question: **Answer** (strongest honest answer) · **Evidence** · **Weak spot** · **Action**.

## Government domain expert (NDPS / NCB)
1. *"The field test isn't evidence. Why digitise it?"*
   - **Answer:** Right, identity is the lab's job, and once the lab confirms, a missing field test doesn't sink the case (Delhi HC, 2023). But before the lab report, the field test drives:
     - classification (Rule 3(1));
     - sampling lots (Rule 10(2));
     - Form-1 item 5;
     - remand and bail.

     The Bombay HC granted bail partly because the field test was undocumented, no standard existed, and a "bare reference" in the panchnama was not enough.
   - **Evidence:** GSR 899(E); *Sagar Parshuram Joshi* (2021), read in full; *Masibur Khan* (2023).
   - **Weak:** no prosecutor has confirmed the value.
   - **Action:** prosecutor interview.
2. *"Our kits aren't the ones in your NIJ table."*
   - **Answer:** Agreed. NIJ is the only published colour data, and the design takes any kit through a signed profile. The profile checker tells NCB which of its categories a camera can and can't separate.
   - **Evidence:** E6, E12.
   - **Weak:** no NCB kit data.
   - **Action:** Phase-0 validation (U1).
3. *"Officers won't add steps during a raid."*
   - **Answer:** It removes steps: the Form-1 text, panchnama paragraph, field-test report and grouping table are generated.
   - **Weak:** time not measured.
   - **Action:** stopwatch study (U6, `product-validation.md`).
4. *"Why not just ask NIC to add this to e-Sakshya?"*
   - **Answer:** Please do. We ship the engine, the colour standard and the report format as an SDK that e-Sakshya can embed. Our app is the reference host that works today.
   - **Evidence:** ADR-13.
   - **Weak:** no NIC contact.
   - **Action:** ask the mentor or nodal officer.

## Senior software architect
5. *"Why not a web app?"*
   - **Answer:** A browser can't give us three things we need:
     - hardware-backed, attested keys;
     - RAW or locked-linear capture, which E13 and E9 showed is needed;
     - reliable offline use.
   - **Weak:** none significant.
6. *"Why a server at all?"*
   - **Answer:** Device enrolment, durable storage, the lab loop and checkpoints. Records verify without it.
   - **Evidence:** reference sync protocol, 13/13 failure scenarios (E14).
   - **Weak:** not yet on PostgreSQL.
   - **Action:** M4 + load test.
7. *"What breaks first at 10×?"*
   - **Answer:** QA aggregate queries, not ingestion. The reference protocol syncs about 5,600 records/s; the real need is under 1/s.
   - **Weak:** SQLite, not PostgreSQL.
   - **Action:** load test.
8. *"You restore from backup and records are gone."*
   - **Answer:** Phones delete their copy only after a durable (post-backup) checkpoint. We found this by testing: deleting after any checkpoint lost 5 of 16 records.
   - **Evidence:** E14.
   - **Weak:** none in the reference.

## Cybersecurity expert
9. *"An admin can edit your database."*
   - **Answer:** Records are signed on phones. Admins hold no device or supervisor keys. Checkpoints are copied to phones and HQ.
   - **Evidence:** E5 admin attacks caught.
   - **Weak:** none in the reference implementation.
10. *"I root a phone and extract the key."*
    - **Answer:** The key lives in hardware. At enrolment we verify Google's attestation chain against Google's roots and revocation list, and we require secure hardware, verified boot, a locked bootloader, our challenge and the enrolled key.
    - **Evidence:** E15, 13/13 cases, including tampered, revoked and forged-root chains.
    - **Weak:** we haven't yet enrolled a real locked production phone.
    - **Action:** enrol one.
11. *"I photograph a pre-reacted well."*
    - **Answer:** Capture starts before the reagent drop. A well that is already coloured is rejected, and so is an abrupt colour jump.
    - **Evidence:** E16: staged 0.0% [0–0.9] accepted; mid-capture swap 0.5% [0.1–1.8].
    - **Weak:** a swap exactly at the drop, or a replayed video, passes colour checks.
    - **Action:** package-label tracking plus a cross-link to the s.105 video; say this limit openly.
12. *"I feed your verifier garbage."*
    - **Answer:** Strict schema and fail-closed handling.
    - **Evidence:** E10, 0 unhandled.
    - **Weak:** none known.

## AI/ML expert
13. *"Why not train a CNN on photos?"*
    - **Answer:** We tested the idea. ML on uncorrected colours made up to 5.6% wrong calls under an unseen light; the card fixes the physics. A CNN also wouldn't be reproducible in court.
    - **Evidence:** E7.
    - **Weak:** a CNN on real data might do better, but we have no real data.
14. *"Your region map is a random forest, so that's ML."*
    - **Answer:** Yes. It is learned offline, then frozen into a signed lookup table. It's used only when RAW isn't available. The phone runs no model, and anyone can re-run the lookup.
    - **Evidence:** E11, E12.
    - **Weak:** trained on simulated data.
    - **Action:** train on Phase-0 data.
15. *"How do you know it's accurate?"*
    - **Answer:** It is simulated only: held-out photos, 3 seeds, 95% intervals.
      - RAW: 85–92% correct, 0–1.6% wrong.
      - The real-phone protocol, printed card and reader are ready.
    - **Weak:** this is the biggest honest gap.
16. *"Isn't your simulator just agreeing with itself?"*
    - **Answer:** Partly, for the region maps, which are trained and tested on the same simulator with different seeds. That's why RAW + rule, which is fitted on no simulated data, is the primary path.
    - **Weak:** the DSLR sensor model isn't a phone.
    - **Action:** real photos.

## Product expert
17. *"Who uses it daily and why would they want to?"*
    - **Answer:** Seizing officers. It produces paperwork they must write anyway and protects their good-faith defence.
    - **Weak:** no officer has confirmed.
    - **Action:** interviews.
18. *"What's the measurable benefit?"*
    - **Answer:**
      - a documented report per package (today there is none, per the court case);
      - an objective, reproducible reading;
      - field-vs-lab accuracy per kit batch (today there is none).
    - **Weak:** no time-saved or error-reduction numbers from the field.
19. *"What if NCB already plans this?"*
    - **Answer:** There is no public evidence of it (D9). The SDK shape means we help either way.
    - **Weak:** absence of evidence isn't proof.

## Hackathon judge
20. *"Show me it working."*
    - **Answer (plan):**
      1. Live capture starting before the drop.
      2. Colour group plus consistent substances.
      3. Signed record.
      4. Tamper demo.
      5. Offline verifier.
      6. Restore demo.
    - **Weak:** the app isn't built yet.
    - **Action:** Kotlin M0–M2 before the finale.
21. *"What did you validate?"*
    - **Answer:** 16 experiments with 95% intervals, including published colours, out-of-gamut failure, insider attacks, restore loss and staged capture.
    - **Weak:** none on real phones.
    - **Action:** printed-card phone test this week.
22. *"Why is this different from the other teams?"*
    - **Answer:** A colour test can't say "cocaine", because ephedrine gives the identical colour. Ordinary phone photos also can't even store that blue correctly. So we built a published colour standard with RAW capture and an evidence trail: what the Bombay HC said India lacks.
    - **Weak:** it must be told simply, in under 30 seconds.

## Answers that are still weak → what to build or research
| Weak answer | Fix | Status |
|---|---|---|
| No real-kit data (Q2, Q15) | Phase-0 validation request to NCB | Open |
| No real-phone numbers (Q15, Q21) | Printed card + dyes + 3 phones | Tools ready |
| No officer or prosecutor input (Q1, Q3, Q17) | 3–5 interviews | Guide ready |
| Attestation (Q10) | Enrol a locked production phone | Verifier done |
| Swap at drop / replay (Q11) | Label tracking + s.105 video link | Open, limit stated |
| No working app (Q20) | Build M0–M2 | Open |
