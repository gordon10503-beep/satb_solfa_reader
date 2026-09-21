# Roadmap / TODO

Ordered roughly by priority for a first usable version.

## 1. Get a real OMR conversion working (highest priority)
- [ ] Install Audiveris locally (needs Java 17+). Test on
      `assets/scores/Finale-Zhong-Qu-SATB-and-piano.pdf` first — being a
      Finale-exported PDF, it should OMR cleanly (clean engraving = best
      case for OMR accuracy).
- [ ] Run `python -c "from src.ocr.omr_pipeline import get_backend; ..."`
      end-to-end and confirm the MusicXML output opens correctly and the
      SATB parts + key signature(s) come through intact.
- [ ] For `In Time Of Silver Rain — Choral.pdf` (larger file, possibly a
      photographed/scanned score) check OMR accuracy separately — scans
      are harder than clean engravings; may need image pre-processing
      (deskew, contrast) before OMR.
- [ ] Wire up `OemerBackend.convert()` as a Java-free fallback (render PDF
      pages to PNG via `split_pdf_to_images`, run oemer per page, merge
      per-movement MusicXML).

## 2. Round-trip solfège back into a usable score file
- [ ] Implement `write_solfege_as_lyrics()` in `musicxml_loader.py`: walk
      the *original* XML tree in note order (parallel to how
      `load_musicxml` walks it) and inject a second `<lyric number="2">`
      element per note containing `note.solfege`. This lets the user open
      the annotated file in MuseScore/Finale and see solfège syllables
      as a lyric line under (or, with a style tweak, above) each note.
- [ ] Alternative/complementary: export a simplified "rehearsal view" —
      one line of noteheads + solfège text per part, generated fresh
      (not tied to original engraving) — useful for quick sight-reading
      practice.

## 3. Real staff-image renderer with solfège overlay
- [ ] Option A: use `music21` to parse the OMR'd MusicXML and export to
      Lilypond/MusicXML, then render with a Lilypond install, overlaying
      solfège as `\markup` text above noteheads.
- [ ] Option B: keep the OMR engine's page images (Audiveris exposes glyph
      bounding boxes) and draw solfège text directly onto the page image
      at each notehead's (x, y), which is more visually faithful to the
      original score but requires extracting per-note pixel coordinates
      from Audiveris's internal book/sheet export (its `.omr` project
      file), not just the final MusicXML.
- [ ] Ship a simple SVG/PNG export so results can be printed for
      rehearsal.

## 4. UI polish
- [ ] Add a "part role override" dropdown per part in the sidebar for when
      `guess_satb_role()` fails (e.g. garbled OCR'd part names).
- [ ] Persist last-used settings (mode, visible parts) in `config.yaml` or
      browser local storage.
- [ ] Add a "highlight key-change measures" visual marker in the preview.
- [ ] Batch mode: process all PDFs in `assets/scores/` and cache their
      MusicXML + annotations so re-opening the app is instant.

## 5. Nice-to-haves
- [ ] Support divisi / multi-voice parts (e.g. "Soprano 1/2" within one
      staff) — currently one `Part` = one SATB role assumption.
- [ ] Support `minor_uses_do` and `avoid_si_clash` as per-user saved
      preferences (some choir members will prefer different spelling
      conventions).
- [ ] Add a CLI (`python -m satb_solfa_reader convert score.pdf`) for
      batch processing without the Streamlit UI.
- [ ] Export annotated practice sheets to PDF for printing before
      rehearsals.
