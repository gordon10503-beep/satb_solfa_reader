# OMR debugging status (paused 2026-09-18) — Finale-Zhong-Qu-SATB-and-piano

## What we found
1. The `.mxl` in `assets/scores/` is a **corrupted Audiveris export**: 17 parts
   (12 garbled fragments `_m`, `S.`, `A,`, `T,`…, 4 named S/A/T/B, 1 `Piano`
   with stray notes). Tenor P15 m1 read "Re Mi Mi Mi Mi Fa Sol" — wrong.
2. Root cause: Audiveris 5.11.0 `PartwiseBuilder` NPE while sorting wedges
   (`Rational.compareTo ... timeOffset is null`, first hit in page-6 measure),
   during an inline transcription+export over all 14 music sheets → parts got
   shredded across sheets into 17 parts.
3. Ground truth (extracted from PDF page 5 vector glyphs, E major):
   - Tenor pickup (m0): B3 B4 F#4 = **Sol Sol Re** ✔ (user was right)
   - Tenor m1: F#4 F#4 G#4 G#4 G#4 G#4 A4 B4 B4 A4 = Re Re Mi Mi Mi Mi Fa Sol Sol Fa Fa
   - Soprano & Bass have whole rests in system 1 (page 5); choir enters later.
4. **Fix that works**: re-export from the saved `.omr` book WITHOUT re-running OMR:
   ```
   "C:/Program Files/Audiveris/Audiveris.exe" -batch -export -sheets 5-18 \
     -output build/all_export build/ocr_output/Finale-Zhong-Qu-SATB-and-piano.omr
   ```
   (note: `-output` is ignored for book-based export; result lands in
   `build/ocr_output/Finale-Zhong-Qu-SATB-and-piano.mxl`).
   Result: clean 5-part structure — P1..P4 "Voice" + P5 "Piano", measures 1–87
   (pickup renumbered to m1), P3 m1 = B3 B4 F#4 = tenor pickup ✔.
   NPEs still logged (~27) but export completes and structure is intact.
   Old shredded export backed up at `build/seg_s7plus.mxl`; pages 5-6-only
   export was clean of NPEs (sheet 6 = the wedge-problem page 7? — recheck).

## Remaining to do

- [x] Confirm P1..P4 roles: **P1=Soprano** (PDF m14 = C#4 A4 G#4 G#4 G#4 F#4
      F#4 C#5 B4 matched 9/9), **P3=Tenor** (pickup match), **P4=Bass**
      (range MIDI 47–62), **P2=Alto** (elimination + range 56–72).
- [x] Spot-check: system-2 (PDF m5–8) has whole rests in S/A/B — tenor
      solo passage; choir enters PDF m13 (mxl m14 after +1 shift).
- [x] Adopt clean export: `assets/scores/*.mxl` replaced with the clean
      5-part export; shredded original backed up at
      `build/shredded_backup_original.mxl`.
- [x] `AudiverisBackend.convert()` rewritten as two-phase flow with a
      phase-2 retry (see QUICKSTART "why"): Silver Rain's PDF has
      non-music pages (cover/blank) that Audiveris *removes* during
      transcription; the first book export aborts ("Could not export
      since transcription did not complete successfully") because those
      invalid stubs are only resolved during that attempt — a second
      export succeeds. Verified end-to-end: Silver Rain → 5 parts
      (4× Voice + Piano), 62 measures, Eb major, SATB ranges descending.
- [x] App flow re-verified: `assign_satb_roles` maps Voice×4 positionally,
      Piano stays instrumental; `pytest` 10/10.
- [ ] Optional: re-run transcription for the Zhong-Qu wedge page with
      `-force` to eliminate the ~27 logged (non-fatal) NPEs at the source.

## Known quirks of the clean export (Zhong-Qu score)

- Measure numbers shift +1 vs PDF after the m9–13 repeat region.
- Tenor pitches are written (treble-clef reading), not 8vb-sounding.
- Repeated noteheads sometimes merged/dropped (m2: 7 vs 9 noteheads).
