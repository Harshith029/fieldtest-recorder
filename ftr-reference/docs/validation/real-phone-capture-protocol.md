# Real-phone capture protocol (answers U2: "does the simulation hold on real phones?")

Purpose: measure, on real phones and a printed card, the numbers we have so far only simulated:
card detection, calibration error, colour-reading error, JPEG vs RAW, glare, night mode.
**No drugs, no kit reagents.** Only food-safe colours. Everything is labelled SYNTHETIC.

## Materials
- Printed card: `docs/validation/card/ftr-card-150x105mm.pdf` at 100% scale (no "fit to page"), on matte paper,
  matte-laminated if possible (gloss causes glare). Check with a ruler: markers must be 18 mm.
- Optional: an X-Rite ColorChecker Classic (certified reference) placed beside the printed card in a few shots,
  to characterise the print (see "Card characterisation").
- White ceramic spot plate or small white cups (the "wells"), 2 per photo, placed on the two circles.
- Safe colour sources:
  - Food colours (red, blue, green, yellow) diluted to several strengths and mixed.
  - Red-cabbage indicator (boil red cabbage, keep the water) + vinegar (turns pink) / baking soda (turns blue-green):
    a real colour-change reaction.
  - Iodine clock (vitamin C tablet + tincture of iodine + 3% hydrogen peroxide + starch): colourless → dark blue after
    a delay; a safe stand-in for a timed reaction. Do it with an adult supervisor; don't drink anything.
- 3 different Android phones (one budget, one mid-range, one recent). Note the model and Android version.

## Lighting conditions (photograph every sample under each)
1. Daylight in shade (not direct sun).
2. Indoor tube light.
3. White LED torch held by a second person.
4. Warm incandescent / warm-white LED bulb.
5. Night under a sodium (orange) street lamp: once without flash, once with the phone's flash.

## Procedure
1. For each phone, run the Camera2 capability check (in the Android prototype: `Settings > Device capability`;
   until then, the free app "Camera2 API Probe") and write down: hardware level, RAW support, manual sensor, manual post-processing.
2. Prepare 10 colour mixes. Measure nothing yet; just number the cups C01–C10.
3. For each light × phone: place 2 cups on the card, frame the whole card, take:
   - one normal photo (JPEG),
   - one RAW (DNG) photo if the phone supports it (Open Camera app → Settings → Camera API: Camera2 → RAW),
   - one photo tilted ~20°, one deliberately slightly out of focus, one with a visible reflection on a cup.
4. Timed reaction: for the cabbage and iodine-clock reactions, start video before adding the second liquid, record 90 s.
5. File names: `<phone>_<light>_<cupA>-<cupB>_<variant>.<jpg|dng|mp4>`, e.g. `redmi9_tube_C03-C07_tilt.jpg`.

Expected volume: 3 phones × 5 lights × 5 cup pairs × 5 variants ≈ 375 photos + 30 videos. One afternoon for two people.

## Card characterisation (so the "truth" is known)
Printed colours differ from the design file. Pick one:
- **Best:** photograph the printed card next to a certified ColorChecker in daylight shade with the best phone in RAW;
  `tools/characterise_card.py` (to be written) fits the printed patches' true values from the certified chart.
- **Acceptable for a first test:** use the design values and accept a larger calibration error; report it.

## Analysis
```bash
python read_photos.py --photos <folder> --profile profiles/demo-marquis-rule.json --out results/real_phone.csv
```
The script reports per photo: card found (and markers seen), calibration fit error, blur, glare, well colours (CIELAB),
decision and reason. Compare the reading of the same cup across phones and lights:
- **Reproducibility:** ΔE00 between readings of the same cup across phones/lights (median, 95th).
- **Detection:** share of photos where the card is found; failure reasons.
- **Bad-light gate:** share of sodium-lamp photos rejected without flash; accepted with flash.
- **JPEG vs RAW:** reproducibility difference for saturated blues/greens (E13 predicts RAW is much better).
- **Liveness:** colour trajectory from the videos (E16 predicts a clear sample → final change after the drop).

## What would change our design
| Result | Consequence |
|---|---|
| Card found < 90% | Larger markers or a different marker family |
| Same-cup reproducibility > 5 ΔE00 on JPEG in normal light | Region maps / RAW become mandatory, not optional |
| Budget phones lack RAW and manual controls | Night mode tier 1 and out-of-gamut kits unavailable on them; device list needed |
| Sodium + flash still rejected | Recommend an external torch; keep "reject" behaviour |
