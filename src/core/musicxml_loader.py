"""
Minimal MusicXML (score-partwise) reader/writer built on the standard
library's xml.etree, so the core pipeline has zero heavy dependencies.

This intentionally supports a practical subset of MusicXML sufficient for
SATB choral scores: parts, measures, key signatures (incl. changes),
notes/rests/chords, and writing solfege syllables back as <lyric> text
(and/or as separate <words> attached directions above the staff).

For real OCR'd scores, first convert PDF -> MusicXML using an OMR engine
(see src/ocr/omr_pipeline.py) then feed the resulting .xml/.musicxml file
into `load_musicxml()`.

If `music21` is installed in your environment, you can alternatively use
`load_via_music21()` below, which is more robust for edge cases (grace
notes, tuplets, multi-voice parts) at the cost of an extra dependency.
"""
from __future__ import annotations
import io
import os
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Optional

from .score_model import Score, Part, Measure, Note, KeySignature


def _text(el, tag, default=None):
    child = el.find(tag)
    return child.text if child is not None and child.text is not None else default


def _parse_root(path: str) -> ET.Element:
    """Parse a MusicXML file, transparently handling .mxl ZIP containers
    (which hold the score at META-INF/container.xml-referenced rootfile,
    by convention a top-level *.xml)."""
    with open(path, "rb") as f:
        head = f.read(4)
    if head[:2] == b"PK":
        with zipfile.ZipFile(path) as zf:
            container = zf.read("META-INF/container.xml")
            rootfile = next((el.get("full-path") for el in ET.fromstring(container).iter()
                             if el.tag.split("}")[-1] == "rootfile"), "score.xml")
            rootfile = (rootfile or "score.xml").lstrip("/")
            try:
                data = zf.read(rootfile)
            except KeyError:
                # Fallback: first .xml member that is not the container.
                data = zf.read(
                    next(n for n in zf.namelist()
                         if n.lower().endswith(".xml")
                         and not n.startswith("META-INF/"))
                )
            return ET.fromstring(data)
    return ET.parse(path).getroot()


def load_musicxml(path: str) -> Score:
    root = _parse_root(path)

    title = "Untitled"
    work = root.find("work/work-title")
    if work is not None and work.text:
        title = work.text
    else:
        movement_title = root.find("movement-title")
        if movement_title is not None and movement_title.text:
            title = movement_title.text

    # part-list gives id -> display name
    id_to_name = {}
    part_list = root.find("part-list")
    if part_list is not None:
        for score_part in part_list.findall("score-part"):
            pid = score_part.get("id")
            name_el = score_part.find("part-name")
            id_to_name[pid] = name_el.text if name_el is not None and name_el.text else pid

    score = Score(title=title)
    key_signatures = []

    for part_el in root.findall("part"):
        pid = part_el.get("id")
        part = Part(part_id=pid, name=id_to_name.get(pid, pid))
        # Staff-relative clef octave shifts (MusicXML <clef-octave-change>):
        # a tenor staff uses treble clef with octave change -1, so its
        # written pitches sound one octave lower. Audiveris exports tenor
        # notes at their WRITTEN octave, so we must apply the shift to get
        # sounding pitches. Tracked per staff number (piano = 2 staves).
        staff_octave_shift = {1: 0}
        default_shift = 0
        divisions = 1.0

        for measure_el in part_el.findall("measure"):
            mnum_raw = measure_el.get("number", "0")
            try:
                mnum = int(mnum_raw)
            except ValueError:
                mnum = 0
            measure = Measure(number=mnum)

            attributes = measure_el.find("attributes")
            if attributes is not None:
                divisions = float(_text(attributes, "divisions", str(divisions)))
                if divisions <= 0:
                    raise ValueError("MusicXML divisions must be positive")
                key_el = attributes.find("key")
                if key_el is not None:
                    fifths_txt = _text(key_el, "fifths", "0")
                    mode_txt = _text(key_el, "mode", "major") or "major"
                    fifths = int(fifths_txt)
                    ks = KeySignature(fifths=fifths, mode=mode_txt, measure_number=mnum)
                    key_signatures.append(ks)
                    measure.key = ks

                for clef_el in attributes.findall("clef"):
                    staff = int(clef_el.get("number", "1") or 1)
                    change = clef_el.find("clef-octave-change")
                    shift = int(change.text or 0) if change is not None else 0
                    staff_octave_shift[staff] = shift
                    if staff == 1:
                        default_shift = shift

            for note_el in measure_el.findall("note"):
                is_rest = note_el.find("rest") is not None
                if is_rest:
                    note = Note(is_rest=True)
                else:
                    pitch_el = note_el.find("pitch")
                    if pitch_el is None:
                        continue  # skip grace/percussion edge cases in this minimal reader
                    step = _text(pitch_el, "step", "C")
                    alter = int(_text(pitch_el, "alter", "0") or 0)
                    octave = int(_text(pitch_el, "octave", "4") or 4)
                    staff_el = note_el.find("staff")
                    staff = int(staff_el.text or 1) if staff_el is not None else 1
                    shift = staff_octave_shift.get(staff, default_shift)
                    note = Note(step=step, alter=alter,
                                octave=octave + shift, is_rest=False)

                lyric_el = note_el.find("lyric/text")
                if lyric_el is not None and lyric_el.text:
                    note.lyric = lyric_el.text

                dur_txt = _text(note_el, "duration")
                if dur_txt is not None:
                    note.duration = float(dur_txt) / divisions

                measure.notes.append(note)

            part.measures.append(measure)
        score.parts.append(part)

    score.key_signatures = key_signatures or [KeySignature(fifths=0, mode="major", measure_number=1)]
    return score


def load_via_music21(path: str) -> Score:
    """Optional, richer loader using music21 (pip install music21).

    Differences from the minimal ET-based loader:
    - finds notes inside <voice> containers (music21 groups notes into
      Voice streams even when the XML has a single voice, so a flat
      measure.notesAndRests walk misses them -- use recurse());
    - returns SOUNDING pitches: music21 applies <clef-octave-change>
      itself, so a tenor on treble-8vb comes out an octave lower, no
      manual shift needed;
    - splits multi-staff parts (piano) into one Part per staff.

    Kept separate so the minimal loader has zero dependencies.
    """
    import music21  # noqa: F401  (imported lazily; not a hard dependency)
    from music21 import converter, stream

    m21_score = converter.parse(path)
    score = Score(
        title=(m21_score.metadata.title if m21_score.metadata else None) or "Untitled"
    )
    key_signatures = []

    for m21_part in m21_score.parts:
        part = Part(part_id=str(m21_part.id), name=m21_part.partName or str(m21_part.id))
        for m21_measure in m21_part.getElementsByClass(stream.Measure):
            measure = Measure(number=m21_measure.number)
            ks = m21_measure.keySignature
            if ks is not None:
                fifths = ks.sharps
                mode = getattr(ks, "mode", "major") or "major"
                key_obj = KeySignature(fifths=fifths, mode=mode, measure_number=measure.number)
                key_signatures.append(key_obj)
                measure.key = key_obj
            for el in m21_measure.recurse().notesAndRests:
                if el.isRest:
                    note = Note(is_rest=True, duration=float(el.quarterLength))
                else:
                    p = el.pitch if hasattr(el, "pitch") else el.pitches[0]
                    note = Note(
                        step=p.step, alter=int(p.alter or 0), octave=p.octave,
                        is_rest=False, duration=float(el.quarterLength),
                    )
                    if el.lyric:
                        note.lyric = el.lyric
                measure.notes.append(note)
            part.measures.append(measure)
        score.parts.append(part)

    score.key_signatures = key_signatures or [KeySignature(fifths=0, mode="major", measure_number=1)]
    return score


def write_solfege_as_lyrics(
    score: Score,
    input_path: str,
    output_path: str,
    verse_number: int = 2,
    skip_rests: bool = True,
) -> None:
    """Write an annotated copy of the original MusicXML with each note's
    `.solfege` value (computed by key_tracker.annotate_score on `score`)
    injected as an extra lyric verse, so the file opens in MuseScore /
    Finale / Sibelius with solfège text under (or above, restyled) the
    staff.

    The `score` object MUST come from load_musicxml(input_path) on the
    same file (plus assign_satb_roles / annotate_score): this function
    walks the raw XML in exactly the same order the loader walked it --
    per part, per measure, per <note> -- skipping the same elements the
    loader skips (notes without <pitch>, i.e. grace/unpitched), so the
    two walks stay in lockstep.

    verse_number: which <lyric number> slot to use (1 = original lyrics;
                  2 = the solfège line; raises if the slot is taken).
    skip_rests:   don't attach lyrics to rests (MusicXML permits it but
                  engravers render stray dashes).
    """
    tmp_xml = None
    with open(input_path, "rb") as f:
        head = f.read(4)
    if head[:2] == b"PK":
        # .mxl container: extract the inner score XML to a temp file and
        # process that, so callers can pass the same path they loaded.
        import tempfile
        import zipfile

        with zipfile.ZipFile(input_path) as zf:
            container = zf.read("META-INF/container.xml")
            rootfile = next((el.get("full-path") for el in ET.fromstring(container).iter()
                             if el.tag.split("}")[-1] == "rootfile"), "score.xml")
            rootfile = (rootfile or "score.xml").lstrip("/")
            try:
                data = zf.read(rootfile)
            except KeyError:
                data = zf.read(
                    next(n for n in zf.namelist()
                         if n.lower().endswith(".xml")
                         and not n.startswith("META-INF/"))
                )
        fd = tempfile.NamedTemporaryFile(
            suffix=".xml", delete=False, dir=str(Path(output_path).parent)
        )
        fd.write(data)
        fd.close()
        tmp_xml = fd.name
        input_path = tmp_xml

    tree = ET.parse(input_path)
    root = tree.getroot()

    # Sanity: the XML must have the same parts, in order, as the Score.
    xml_part_ids = [p.get("id") for p in root.findall("part")]
    score_part_ids = [p.part_id for p in score.parts]
    if xml_part_ids != score_part_ids:
        raise ValueError(
            f"Score/XML mismatch: xml parts {xml_part_ids} != "
            f"score parts {score_part_ids}. Re-load the score from the "
            "same input file before writing lyrics."
        )
    # Refuse to clobber an existing verse.
    for note_el in root.iter("note"):
        for lyric_el in note_el.findall("lyric"):
            if lyric_el.get("number") == str(verse_number):
                raise ValueError(
                    f"lyric number={verse_number} already exists in the "
                    "source; choose another verse number."
                )

    notes_iter = (
        note
        for part in score.parts
        for measure in part.measures
        for note in measure.notes
    )

    part_count = 0
    for part_el in root.findall("part"):
        part_count += 1
        for measure_el in part_el.findall("measure"):
            for note_el in measure_el.findall("note"):
                is_rest_el = note_el.find("rest") is not None
                has_pitch = note_el.find("pitch") is not None
                if not is_rest_el and not has_pitch:
                    continue  # grace/unpitched: loader skipped these too
                # NOTE: rests must consume an iterator item even when
                # skip_rests=True -- the loader created Note(is_rest=True)
                # for them, and dropping them here would desync the two
                # walks from the first rest onward.
                note = next(notes_iter, None)
                if note is None:
                    raise ValueError(
                        "Score ran out of notes before the XML did -- "
                        "the Score object was not loaded from this file."
                    )
                if (skip_rests and note.is_rest) or not note.solfege:
                    continue
                lyric_el = ET.SubElement(note_el, "lyric")
                lyric_el.set("number", str(verse_number))
                syllabic = ET.SubElement(lyric_el, "syllabic")
                syllabic.text = "single"
                text = ET.SubElement(lyric_el, "text")
                text.text = note.solfege

    if tmp_xml:
        os.unlink(tmp_xml)
    tree.write(output_path, encoding="utf-8", xml_declaration=True)
