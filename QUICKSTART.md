# Quick Start

Get the SATB So-Fa Score Reader running locally in about five minutes.

## 1. Prerequisites

- Python 3.10+ (developed on 3.11)
- pip

## 2. Install

```bash
cd satb_solfa_reader
pip install -r requirements.txt
```

The solfège engine and the MusicXML reader are standard-library only.
Streamlit is needed for the UI; `music21`, `pdf2image` and `Pillow` are
optional extras (richer parsing / future OMR work).

## 3. Run the tests

```bash
python tests/test_solfege.py
# or: pytest tests/
```

All tests pass with no extra dependencies installed.

## 4. Launch the app

```bash
streamlit run src/ui/app.py
```

**Windows note:** if `streamlit` is not found on PATH, either activate the
project venv first (`.venv\Scripts\activate`) or call it via its Python:

```powershell
.venv\Scripts\python.exe -m streamlit run src/ui/app.py
```

Then in the browser:

1. Upload a MusicXML file (`.xml` / `.musicxml`). A sample with a
   mid-piece key change ships at
   `tests/sample_data/satb_sample_with_key_change.musicxml`.
2. Pick **Movable-do 首調** or **Fixed-do 固定調** in the sidebar.
3. Toggle which parts (S/A/T/B) to display.
4. Read the annotated preview (HTML above, plain text in the expander).

## Solfa options (sidebar)

| Option | What it does |
|---|---|
| Movable-do / Fixed-do | 首調 (syllables follow the key) vs 固定調 (C is always Do) |
| Minor key: Do-based minor | Tick to anchor "Do" at the minor tonic. Default is **La-based minor** (HK/TW convention): the minor tonic sings "La". |
| Avoid-Si-clash | Spells the raised 5th as "Se" instead of "Si" (avoids clashing with fixed-do Si = B) |
| Sharp/flat detail (fixed-do only) | Shows e.g. `Fa#/Solb` instead of collapsing to `Fa` |

## Scanned PDF scores

The app reads MusicXML, not PDFs. Convert a scanned score first with
[Audiveris](https://github.com/Audiveris/audiveris) — **always use the
two-phase (book round-trip) flow**, not the single inline command:

```bash
# Phase 1: transcribe the PDF and SAVE the .omr book (no export yet)
audiveris -batch -save -output build/ocr_output "assets/scores/your_score.pdf"

# Phase 2: re-open the saved book and export MusicXML from it
audiveris -batch -export build/ocr_output/your_score.omr
```

The produced `.mxl` lands next to the book in `build/ocr_output/`. Upload
that into the app (or call `AudiverisBackend.convert()`, which runs both
phases for you).

**Why two phases?** Audiveris 5.11's inline `-batch -export` on a PDF has
a `PartwiseBuilder` bug: when a page contains hairpins/wedges with
unresolved time offsets it throws NPEs mid-export and the part assembly
gets *shredded* (observed on a real score: a clean 5-part SATB+Piano
engraving exported as 17 garbled parts, with notes migrated between
parts). Saving the book first and exporting from it re-assembles parts
correctly — the same NPEs are logged but non-fatally. See
`docs/OMR_NOTES.md` for the full forensic write-up.

**Always verify OMR output before trusting it**: check the part count
and names, and spot-check a few notes against the printed score. Known
quirks of this flow: measure numbers shift after repeat sections, tenor
pitches are written (not 8vb-sounding), and repeated noteheads are
sometimes merged/dropped. See `README.md` for the full picture and
`docs/ROADMAP.md` for what is still on the way.
