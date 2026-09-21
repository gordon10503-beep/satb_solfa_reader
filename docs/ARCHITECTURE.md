# Architecture

```
PDF score (scanned or Finale-exported)
        │
        ▼
┌───────────────────┐
│  src/ocr/          │  OMR backend (Audiveris or oemer)
│  omr_pipeline.py   │  PDF -> MusicXML
└───────────────────┘
        │  MusicXML
        ▼
┌───────────────────┐
│  src/core/          │  load_musicxml() / load_via_music21()
│  musicxml_loader.py │  -> Score (parts, measures, notes, key sigs)
└───────────────────┘
        │
        ▼
┌───────────────────┐
│  src/core/          │  assign_satb_roles() : name -> S/A/T/B
│  key_tracker.py     │  annotate_score()   : per-note solfège, key-aware
└───────────────────┘
        │  Score with note.solfege filled in
        ▼
┌───────────────────┐        ┌───────────────────┐
│  src/render/        │  or   │  src/core/          │
│  text_renderer.py   │       │  musicxml_loader.py  │
│  (HTML/text preview)│       │  write_solfege_as_lyrics (stub)│
└───────────────────┘        └───────────────────┘
        │
        ▼
┌───────────────────┐
│  src/ui/app.py       │  Streamlit: upload, SATB toggles,
│                      │  movable/fixed switch, preview
└───────────────────┘
```

## Design principles

1. **`src/core` has zero required third-party dependencies.** The
   solfège/key-change logic is pure Python (dataclasses + stdlib XML), so
   it's trivially unit-testable and portable. Heavier libraries
   (music21, streamlit, OMR engines) are opt-in, isolated to `src/ocr`,
   `src/ui`, and the optional loader function.

2. **Key changes are modeled as timestamped events**, not a single global
   key. `Score.key_signatures` is a list of `KeySignature(fifths, mode,
   measure_number)`; `Score.key_at_measure(n)` resolves "what key applies
   at measure n" by taking the latest key signature at or before that
   measure. This is what lets movable-do relabel notes automatically after
   a modulation.

3. **OMR is decoupled behind an abstract `OMRBackend`** so you can swap
   Audiveris ⇄ oemer ⇄ a future commercial API without touching the
   solfège logic. `get_backend()` auto-picks whichever is installed.

4. **Part → SATB role mapping is name-based with manual override.** OMR
   output sometimes garbles part names; `guess_satb_role()` does
   best-effort matching against `PART_NAME_ALIASES`, and the UI warns you
   about any parts it couldn't classify so you can fix them.
