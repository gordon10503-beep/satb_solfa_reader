# Solfa Studio / SATB So-Fa Score Reader

**The new local workspace is ready to try:** double-click `Start Studio.cmd`, or run `.venv\Scripts\python.exe -m src.studio.server`. It opens on port 8873 with real notation, scan import, sol-fa, composition, layered playback, scrolling, metronome, keyboard, collections and bookmarks. See [Studio guide](docs/STUDIO.md) for installation, workflows and current limitations.

The text below documents the original Streamlit scaffold, which remains available.

A tool for choir members to read SATB scores with **so-fa (solfège) names**
printed above the staff, with:

- ✅ Per-part show/hide toggles (Soprano / Alto / Tenor / Bass)
- ✅ A switch between **Movable-do 首調** and **Fixed-do 固定調**
- ✅ Automatic handling of **key changes** mid-piece
- ✅ OCR/OMR pipeline hook to turn a scanned/exported PDF score into
  MusicXML, which the solfège engine then annotates

This is a **draft scaffold** meant to be continued by you + your coding
agent. The music-theory core (solfège engine, key-change tracking, SATB
role detection) is fully implemented and unit-tested. The OCR step and the
graphical score renderer are stubbed out with clear interfaces, because
this sandbox has no internet/Java to run real OMR engines -- see
`docs/ROADMAP.md`.

## What's already working

| Component | Status | File |
|---|---|---|
| Fixed-do / Movable-do syllable engine | ✅ Done, tested | `src/core/solfege.py` |
| Key-change tracking across measures | ✅ Done, tested | `src/core/score_model.py`, `src/core/key_tracker.py` |
| SATB part-name auto-detection | ✅ Done, tested | `src/core/key_tracker.py::guess_satb_role` |
| Minimal MusicXML reader (stdlib only) | ✅ Done, tested | `src/core/musicxml_loader.py` |
| Optional music21-based reader | 🟡 Stub (needs `pip install music21`) | `src/core/musicxml_loader.py::load_via_music21` |
| OMR pipeline (PDF → MusicXML) | 🟡 Interface + adapters written, needs Audiveris/oemer installed | `src/ocr/omr_pipeline.py` |
| Streamlit UI (toggles + switches + preview) | ✅ Draft working (text/HTML preview) | `src/ui/app.py` |
| Real staff-image / notation renderer with overlay | ❌ Not started | see `docs/ROADMAP.md` |
| Round-trip: write solfège back into MusicXML as lyrics | ❌ Stub only | `src/core/musicxml_loader.py::write_solfege_as_lyrics` |

## Quick start

```bash
cd satb_solfa_reader
pip install -r requirements.txt

# Run the unit tests for the solfège/key-change engine (no extra deps needed)
python tests/test_solfege.py

# Launch the draft UI (uses the bundled sample MusicXML, or upload your own)
streamlit run src/ui/app.py
```

The UI currently accepts **MusicXML** input. Your uploaded PDF scores are
stored in `assets/scores/` for OCR pipeline testing:

- `assets/scores/Finale-Zhong-Qu-SATB-and-piano.pdf`
- `assets/scores/In Time Of Silver Rain — Choral.pdf`

To turn one of these into MusicXML you'll need an OMR engine installed on
your machine (not possible inside this drafting sandbox — no internet/Java
here). Recommended: install [Audiveris](https://github.com/Audiveris/audiveris)
(free, Java-based, best accuracy for engraved/Finale-exported scores) and
run it via the **two-phase book round-trip** (see QUICKSTART.md for why —
the inline one-step export can corrupt part assembly):

```bash
audiveris -batch -save  -output build/ocr_output "assets/scores/Finale-Zhong-Qu-SATB-and-piano.pdf"
audiveris -batch -export build/ocr_output/Finale-Zhong-Qu-SATB-and-piano.omr
```

Or equivalently, from Python, `AudiverisBackend.convert()` runs both
phases (`src/ocr/omr_pipeline.py`). That produces a `.mxl`/`.xml` file you
can upload straight into the Streamlit app.

### OMR output caveats (learned the hard way)

- **Always verify before trusting**: open the `.mxl` and check the part
  count/names, then spot-check a few notes per part against the PDF.
  A PDF-vector ground-truth checker pattern is described in
  `docs/OMR_NOTES.md`.
- Audiveris 5.11 writes garbled part names for OCR'd labels (`S.`, `A,`,
  `_m`, ...). The app's `assign_satb_roles()` handles this: OCR'd
  fragments like `A,`/`T.` still resolve via name aliases, four
  generically-named parts get positional S/A/T/B, and piano-ish parts
  are excluded from the fallback.
- Measure numbers shift by +1 after repeat sections (pickup renumbered),
  tenor pitches are exported as written (treble-clef reading, not
  8vb-sounding), and repeated noteheads are sometimes merged/dropped.

## How the solfège logic works

- **Fixed-do 固定調** (`src/core/solfege.py::fixed_do_name`): the syllable
  is tied to the absolute pitch — C is always Do, G is always Sol —
  regardless of key. Enable "show sharp/flat detail" to see e.g. `Fa#/Solb`
  instead of collapsing to the natural-note syllable.
- **Movable-do 首調** (`::movable_do_name`): the syllable is relative to
  the *current key's tonic*, which is looked up per-measure via
  `Score.key_at_measure()`. So if the key changes from C major to D major
  partway through, the note D switches from being sung "Re" to being sung
  "Do" automatically. Chromatic (non-diatonic) notes get the standard
  raised/lowered solfa names (Fi, Di, Ri, Si, Li / Te, Le, Se, Me, Ra).
- Minor keys default to **La-based minor** (the HK/TW convention): the
  minor tonic itself is sung "La" — in A minor the naturals sing
  La Ti Do Re Mi Fa Sol. Tick the "Do-based minor" checkbox in the UI
  (`minor_uses_do=True`) to anchor **Do** at the minor tonic instead.
- Flat notes get their proper lowered names: B♭ in C major is "Te"
  (not "Li"), D♭ is "Ra". Raised notes keep the "i"-ending names
  (F# = "Fi"). The direction is chosen from each note's spelling
  relative to the key signature.

This logic is exercised end-to-end in `tests/test_solfege.py` against a
hand-built sample score with a mid-piece key change
(`tests/sample_data/satb_sample_with_key_change.musicxml`) — all 10 tests
pass.

## Project layout

```
satb_solfa_reader/
├── assets/scores/          # your uploaded PDF scores, for OCR pipeline testing
├── config.yaml             # defaults for OMR backend, solfa mode, visible parts
├── requirements.txt
├── src/
│   ├── core/                # pure music-theory logic (no heavy deps)
│   │   ├── score_model.py     # Score / Part / Measure / Note / KeySignature dataclasses
│   │   ├── solfege.py          # fixed-do / movable-do syllable engine
│   │   ├── key_tracker.py      # SATB role detection + per-note annotation pass
│   │   └── musicxml_loader.py  # stdlib MusicXML reader (+ optional music21 loader)
│   ├── ocr/
│   │   └── omr_pipeline.py     # OMR backend interface: Audiveris / oemer adapters
│   ├── render/
│   │   └── text_renderer.py    # interim text/HTML preview (real staff renderer = TODO)
│   └── ui/
│       └── app.py              # Streamlit app: SATB toggles, movable/fixed switch
├── tests/
│   ├── test_solfege.py
│   └── sample_data/satb_sample_with_key_change.musicxml
└── docs/
    ├── ARCHITECTURE.md
    └── ROADMAP.md
```

## Next steps for you / your agent

See `docs/ROADMAP.md` for a prioritized list — the two biggest remaining
pieces are (1) actually running an OMR engine on your real scores and
(2) rendering solfège text visually positioned above noteheads on the
score image, rather than the current text/HTML table preview.
