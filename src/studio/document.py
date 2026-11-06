"""Lossless MusicXML storage, targeted edits and a disposable engraving copy.

The original XML is the document. Never round-trip saved scores through MEI:
engravers support different subsets of MusicXML.
"""
from __future__ import annotations

import io
import re
import threading
import zipfile
import xml.etree.ElementTree as ET
from fractions import Fraction
from pathlib import Path

from defusedxml.ElementTree import fromstring

from src.core.score_model import KeySignature, Note
from src.core.solfege import annotate_note
from .playback import build_playback

MAX_BYTES = 40 * 1024 * 1024
RENDER_LOCK = threading.Lock()
DURATIONS = {"whole": 4, "half": 2, "quarter": 1, "eighth": .5,
             "16th": .25, "32nd": .125, "64th": .0625}
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
MEI = "http://www.music-encoding.org/ns/mei"
ET.register_namespace("", MEI)


def read_xml(data: bytes) -> ET.Element:
    if len(data) > MAX_BYTES:
        raise ValueError("Score exceeds the 40 MB import limit.")
    if data.startswith(b"PK"):
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            if sum(i.file_size for i in z.infolist()) > MAX_BYTES:
                raise ValueError("Expanded MusicXML exceeds 40 MB.")
            container = fromstring(z.read("META-INF/container.xml"))
            entry = next((e.get("full-path") for e in container.iter()
                          if e.tag.split("}")[-1] == "rootfile" and
                          e.get("media-type", "application/vnd.recordare.musicxml+xml")
                          == "application/vnd.recordare.musicxml+xml"), None)
            if not entry:
                raise ValueError("Compressed score has no MusicXML rootfile.")
            data = z.read(entry)
    root = fromstring(data)
    # MusicXML commonly has no namespace; normalize namespaced variants.
    for e in root.iter():
        e.tag = e.tag.split("}")[-1]
    if root.tag != "score-partwise" or not root.findall("part"):
        raise ValueError("Please import a score-partwise MusicXML file (.musicxml, .xml or .mxl).")
    if sum(1 for _ in root.iter("note")) > 60000:
        raise ValueError("This score exceeds the 60,000-note limit.")
    return root


def xml_bytes(root):
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def child(parent, tag, value=None, **attrs):
    el = ET.SubElement(parent, tag, attrs)
    if value is not None:
        el.text = str(value)
    return el


def duration_type(duration):
    for name, value in DURATIONS.items():
        for dots in range(3):
            if abs(value * sum(.5 ** i for i in range(dots + 1)) - duration) < 1e-6:
                return name, dots
    return None


def inspect(root, mode="movable", minor_do=False):
    names = {p.get("id"): p.findtext("part-name", p.get("id"))
             for p in root.findall("part-list/score-part")}
    parts, notes, issues = [], {}, []
    for pi, part in enumerate(root.findall("part")):
        if part.find("measure/attributes/time") is None:
            issues.append({"part": pi, "measure": 0, "code": "missing-meter", "message": "Opening time signature was not recognized. The app currently assumes 4/4. Check the printed meter before correcting bar lengths."})
        divisions, beats, beat_type, key = 1., 4, 4, KeySignature(0)
        transpositions = {"1": 0}
        measures = []
        for mi, measure in enumerate(part.findall("measure")):
            cursor, last_start, extent = 0., 0., 0.
            voices, tempos = {}, []
            ni = 0
            for el in measure:
                if el.tag == "attributes":
                    divisions = float(el.findtext("divisions", str(divisions)))
                    if divisions <= 0:
                        raise ValueError("MusicXML divisions must be positive.")
                    if el.find("time/beats") is not None:
                        beats = sum(int(x) for x in el.findtext("time/beats").split("+"))
                        beat_type = int(el.findtext("time/beat-type"))
                    if beat_type <= 0 or beats <= 0:
                        raise ValueError("Time signature must be positive.")
                    if el.find("key/fifths") is not None:
                        key = KeySignature(int(el.findtext("key/fifths")), el.findtext("key/mode", "major"))
                    for tr in el.findall("transpose"):
                        transpositions[tr.get("number", "1")] = float(tr.findtext("chromatic", "0")) + 12 * int(tr.findtext("octave-change", "0"))
                elif el.tag in ("direction", "sound"):
                    sound = el if el.tag == "sound" else el.find("sound")
                    bpm = sound.get("tempo") if sound is not None else None
                    met = el.find("direction-type/metronome")
                    if bpm is None and met is not None:
                        try:
                            bpm = float(met.findtext("per-minute")) * DURATIONS.get(met.findtext("beat-unit"), 1) * sum(.5**d for d in range(len(met.findall("beat-unit-dot"))+1))
                        except (TypeError, ValueError): bpm = None
                    if bpm is not None and 0 < float(bpm) <= 1000:
                        tempos.append({"offset": cursor + float(el.findtext("offset", "0")) / divisions, "bpm": float(bpm)})
                elif el.tag in ("backup", "forward"):
                    cursor += float(el.findtext("duration", "0")) / divisions * (-1 if el.tag == "backup" else 1)
                    if cursor < -1e-5:
                        issues.append({"part": pi, "measure": mi, "message": "A voice moves before the start of its bar. Correct its backup duration."})
                elif el.tag == "note":
                    nid = f"ss-p{pi}-m{mi}-n{ni}"
                    ni += 1
                    dur = float(el.findtext("duration", "0")) / divisions
                    chord = el.find("chord") is not None
                    grace = el.find("grace") is not None
                    start = last_start if chord else cursor
                    if not chord:
                        last_start = start
                        if not grace:
                            cursor += dur
                    extent = max(extent, start + dur)
                    voice = el.findtext("voice", "1")
                    voices[voice] = max(voices.get(voice, 0), start + dur)
                    pitch = el.find("pitch")
                    step = el.findtext("pitch/step", "C")
                    alter = float(el.findtext("pitch/alter", "0"))
                    octave = int(el.findtext("pitch/octave", "4"))
                    if pitch is not None and (step not in "CDEFGAB" or len(step) != 1 or not -1 <= octave <= 9):
                        raise ValueError(f"Invalid pitch in part {pi + 1}, measure {mi + 1}.")
                    if dur < 0:
                        raise ValueError("Negative note duration.")
                    solfa = ""
                    if pitch is not None and alter == int(alter):
                        n = Note(step=step, alter=int(alter), octave=octave)
                        annotate_note(n, key, mode="movable" if mode == "pitch" else mode, minor_uses_do=minor_do)
                        solfa = (step + {-2: "𝄫", -1: "♭", 0: "", 1: "♯", 2: "𝄪"}.get(int(alter), str(alter)) + str(octave)) if mode == "pitch" else n.solfege
                    if pitch is None and el.find("rest") is None:
                        issues.append({"part": pi, "measure": mi, "message": "Unpitched notation: check percussion playback manually."})
                    notes[nid] = {"id": nid, "part": pi, "measure": mi, "index": ni - 1,
                                  "step": step, "alter": alter, "octave": octave,
                                  "rest": el.find("rest") is not None, "pitched": pitch is not None,
                                  "duration": dur, "offset": start, "voice": voice,
                                  "staff": el.findtext("staff", "1"), "solfa": solfa,
                                  "lyric": el.findtext("lyric/text", ""), "grace": grace,
                                  "tieStart": el.find("tie[@type='start']") is not None or el.find("notations/tied[@type='start']") is not None,
                                  "tieStop": el.find("tie[@type='stop']") is not None or el.find("notations/tied[@type='stop']") is not None,
                                  "midi": 12 * (octave + 1) + Note.STEP_TO_PC.get(step, 0) + alter + transpositions.get(el.findtext("staff", "1"), transpositions.get("1", 0))}
                    if grace:
                        issues.append({"part": pi, "measure": mi, "message": "Grace note is displayed but omitted from timed playback; interpret its timing manually."})
                    if not grace and dur == 0:
                        issues.append({"part": pi, "measure": mi, "message": "A note has no duration; check the source."})
                    written_type = el.findtext("type")
                    if written_type in DURATIONS and not grace and el.find("rest[@measure='yes']") is None:
                        written = DURATIONS[written_type] * sum(.5 ** i for i in range(len(el.findall("dot")) + 1))
                        tm = el.find("time-modification")
                        if tm is not None:
                            actual = float(tm.findtext("actual-notes", "1"))
                            normal = float(tm.findtext("normal-notes", "1"))
                            if actual <= 0 or normal <= 0: raise ValueError("Invalid tuplet ratio.")
                            written *= normal / actual
                        if abs(written - dur) > 1e-5:
                            issues.append({"part": pi, "measure": mi, "message": f"Rhythm mismatch: note symbol is {written:g} quarter beats but duration is {dur:g}. Correct before trusting playback."})
            expected = beats * 4 / beat_type
            if extent > expected + 1e-5:
                issues.append({"part": pi, "measure": mi, "message": f"Overfull bar: {extent:g} quarter beats; expected {expected:g}."})
            elif extent < expected - 1e-5 and mi != 0 and measure.get("implicit") != "yes":
                issues.append({"part": pi, "measure": mi, "message": f"Short bar: {extent:g} quarter beats; expected {expected:g}. Check pickup or missing notes."})
            measures.append({"number": measure.get("number", str(mi + 1)), "beats": beats,
                             "beatType": beat_type, "length": expected, "divisions": divisions,
                             "fifths": key.fifths, "mode": key.mode, "extent": extent,
                             "implicit": measure.get("implicit") == "yes", "tempos": tempos})
        parts.append({"id": part.get("id"), "name": names.get(part.get("id"), f"Part {pi+1}"), "measures": measures})
    for tag, message in [("segno", "Navigation marks: verify D.S./D.C. playback against the score."),
                         ("coda", "Coda navigation requires manual checking."),
                         ("fermata", "Fermata lengths are expressive; use a slower tempo or pause as needed.")]:
        if message and root.find(f".//{tag}") is not None:
            issues.append({"message": message})
    from src.core.key_tracker import guess_satb_role
    roles = [guess_satb_role(p["name"]) for p in parts]
    duplicates = [role for role in ("S", "A", "T", "B") if roles.count(role) > 1]
    if duplicates:
        issues.insert(0, {"code": "part-assembly", "message": "The scan split choir voices into duplicate parts (" + ", ".join(duplicates) + "). Repair the part assignments in Audiveris before trying to fix individual notes. Do not delete a duplicate: it may contain music from other systems."})
    if len({len(p["measures"]) for p in parts}) > 1:
        issues.append({"message": "Parts contain different numbers of bars. Check OMR part assembly before playback."})
    if any(s.get("dacapo") or s.get("dalsegno") or s.get("tocoda") for s in root.iter("sound")):
        issues.append({"message": "D.C./D.S./coda instructions are displayed but not followed by playback. Use bookmarks to navigate."})
    depth = 0
    for repeat in root.find("part").iter("repeat"):
        if repeat.get("direction") == "forward":
            depth += 1
            if depth > 1:
                issues.append({"message": "Nested repeats require manual playback navigation. Unroll the repeat in MusicXML for accurate timing."})
        else: depth = max(0, depth - 1)
    return {"title": root.findtext("work/work-title") or root.findtext("movement-title") or "Untitled score",
            "composer": root.findtext("identification/creator", ""), "parts": parts, "notes": notes, "issues": issues}


def prepare_render_structure(root, info):
    """Contain broken scan structure in the disposable rendering copy only."""
    parts = root.findall("part")
    sequences = [[m.get("number") for m in p.findall("measure")] for p in parts]
    if any(sequence != sequences[0] for sequence in sequences[1:]):
        # Playback/editor use source positions. Do not let the engraver silently
        # join different positions by inconsistent OCR measure numbers.
        for p in parts:
            for mi, m in enumerate(p.findall("measure")):
                m.set("number", str(mi + 1))
        info["issues"].append({"code": "bar-alignment", "message": "Parts have inconsistent bar numbers or counts. Display and playback use bar positions provisionally; missing bars must be repaired against the PDF. Original numbering is preserved in the saved MusicXML."})
    broken = False
    for p in parts:
        opened = None
        for ending in p.findall("measure/barline/ending"):
            kind, number = ending.get("type"), ending.get("number")
            if kind == "start":
                if opened is not None: broken = True
                opened = number
            else:
                if opened is None or opened != number: broken = True
                opened = None
        if opened is not None: broken = True
    if broken:
        # Unclosed/nested ending spans can make Verovio discard preceding bars.
        for barline in root.findall("part/measure/barline"):
            for ending in barline.findall("ending"):
                barline.remove(ending)
        info["issues"].append({"code": "broken-endings", "message": "Recognition produced incomplete or overlapping repeat endings. Their brackets are hidden in the display to keep opening bars visible. Saved notation is unchanged; repeat playback still needs review."})


def engrave(data, mode="movable", minor_do=False, solfa=True):
    import verovio
    root = read_xml(data)
    info = inspect(root, mode, minor_do)
    playback = build_playback(root, info)
    prepare_render_structure(root, info)
    # Supply omitted note types for otherwise valid duration-only MusicXML.
    for pi, p in enumerate(root.findall("part")):
        for mi, m in enumerate(p.findall("measure")):
            tuplet_run = []
            for ni, n in enumerate(m.findall("note")):
                nid = f"ss-p{pi}-m{mi}-n{ni}"
                n.set("id", nid)
                if n.find("type") is None and not info["notes"][nid]["grace"]:
                    dt = duration_type(info["notes"][nid]["duration"])
                    if dt:
                        child(n, "type", dt[0])
                        for _ in range(dt[1]):
                            child(n, "dot")
                    else:
                        info["issues"].append({"part": pi, "measure": mi, "message": "Missing rhythmic type for a tuplet or unusual duration. Correct MusicXML before relying on playback."})
                # MusicXML allows a tuplet ratio without explicit bracket
                # notation. Supply complete simple groups in the render copy.
                tm = n.find("time-modification")
                if tm is not None and n.find("notations/tuplet") is None and n.find("chord") is None:
                    signature = (tm.findtext("actual-notes"), tm.findtext("normal-notes"), n.findtext("voice", "1"), n.findtext("type"))
                    if tuplet_run and tuplet_run[0][0] != signature: tuplet_run = []
                    tuplet_run.append((signature, n))
                    if len(tuplet_run) == int(signature[0]):
                        for which, node in (("start", tuplet_run[0][1]), ("stop", tuplet_run[-1][1])):
                            notation = node.find("notations")
                            if notation is None: notation = child(node, "notations")
                            child(notation, "tuplet", type=which, number="1")
                        tuplet_run = []
                else: tuplet_run = []
    with RENDER_LOCK:
        verovio.setDefaultResourcePath(str(Path(verovio.__file__).parent / "data"))
        tk = verovio.toolkit()
        tk.setOptions({"pageWidth": 2100, "pageHeight": 2600, "scale": 45,
                       "adjustPageHeight": True, "breaks": "auto", "footer": "none",
                       "header": "none", "spacingStaff": 16, "spacingSystem": 12})
        if not tk.loadData(xml_bytes(root).decode()):
            raise ValueError("The engraving engine could not read this score. Check MusicXML notation.")
        logs = [tk.getLog().strip()]
        mei = fromstring(tk.getMEI())
        staff_by_note = {n.get(XML_ID): staff.get("n", "1")
                         for staff in mei.iter(f"{{{MEI}}}staff")
                         for n in staff.iter(f"{{{MEI}}}note")}
        for mi, measure in enumerate(mei.iter(f"{{{MEI}}}measure")):
            measure.set(XML_ID, f"ss-measure-{mi}")
            if solfa:
                for note in list(measure.iter(f"{{{MEI}}}note")):
                    nid = note.get(XML_ID)
                    source = info["notes"].get(nid)
                    if source and source["solfa"]:
                        direction = ET.SubElement(measure, f"{{{MEI}}}dir", {
                            "startid": f"#{nid}", "place": "above", "staff": staff_by_note[nid],
                            "color": "#537667", XML_ID: f"solfa-{nid}"})
                        direction.text = source["solfa"]
        if not tk.loadData(ET.tostring(mei, encoding="unicode")):
            raise ValueError("Could not engrave the score.")
        logs.append(tk.getLog().strip())
        pages = [tk.renderToSVG(i) for i in range(1, tk.getPageCount() + 1)]
        rendered_ids = {el.get(XML_ID) for el in mei.iter()}
        missing = [n for nid, n in info["notes"].items() if n["pitched"] and nid not in rendered_ids]
        if missing:
            info["issues"].append({"message": f"{len(missing)} pitched notes could not be engraved. Review the import before rehearsing."})
        logs.append(tk.getLog().strip())
        log = "\n".join(s for s in logs if s)
        if log:
            info["engravingLog"] = log[:5000]
            info["issues"].append({"message": "The engraving engine reported notation notices. Review its notices below and compare the source."})
        return {**info, "pages": pages, **playback}


def new_score(title="Untitled composition", composer="", template="satb", bars=8, beats=4, beat_type=4, fifths=0, tempo=96):
    if not 1 <= bars <= 128 or beats not in range(1, 13) or beat_type not in (2, 4, 8, 16) or not -7 <= fifths <= 7 or not 20 <= tempo <= 300:
        raise ValueError("Choose 1–128 bars, a valid meter/key and a tempo of 20–300.")
    root = ET.Element("score-partwise", version="4.0")
    child(child(root, "work"), "work-title", title[:200])
    child(child(root, "identification"), "creator", composer[:200], type="composer")
    pl = child(root, "part-list")
    names = ["Soprano", "Alto", "Tenor", "Bass"] if template == "satb" else ["Piano" if template == "piano" else "Melody"]
    for i, name in enumerate(names):
        child(child(pl, "score-part", id=f"P{i+1}"), "part-name", name)
    for i, name in enumerate(names):
        p = child(root, "part", id=f"P{i+1}")
        for bar in range(bars):
            m = child(p, "measure", number=str(bar+1))
            if bar == 0:
                a = child(m, "attributes")
                child(a, "divisions", 16)
                k = child(a, "key"); child(k, "fifths", fifths); child(k, "mode", "major")
                t = child(a, "time"); child(t, "beats", beats); child(t, "beat-type", beat_type)
                c = child(a, "clef"); child(c, "sign", "F" if name == "Bass" else "G"); child(c, "line", 4 if name == "Bass" else 2)
                if name == "Tenor": child(c, "clef-octave-change", -1)
                if i == 0:
                    d = child(m, "direction", placement="above")
                    met = child(child(d, "direction-type"), "metronome")
                    child(met, "beat-unit", "quarter"); child(met, "per-minute", tempo)
                    child(d, "sound", tempo=str(tempo))
            n = child(m, "note"); child(n, "rest", measure="yes"); child(n, "duration", int(beats * 4 / beat_type * 16))
    return xml_bytes(root)


def edit_note(data, nid, step, alter, octave, lyric):
    root = read_xml(data)
    info = inspect(root)
    if nid not in info["notes"]:
        raise ValueError("That note no longer exists. Select it again.")
    src = info["notes"][nid]
    if not src["pitched"]:
        raise ValueError("Use the bar composer to replace a rest or unpitched note.")
    if step not in list("CDEFGAB") or alter not in (-2, -1, 0, 1, 2) or not 0 <= octave <= 8:
        raise ValueError("Choose a valid pitch.")
    note = root.findall("part")[src["part"]].findall("measure")[src["measure"]].findall("note")[src["index"]]
    if note.find("tie") is not None or note.find("notations/tied") is not None:
        raise ValueError("This note is tied. Edit both ends together in MusicXML to preserve the tie.")
    pitch = note.find("pitch")
    pitch.clear(); child(pitch, "step", step)
    if alter: child(pitch, "alter", alter)
    child(pitch, "octave", octave)
    for accidental in note.findall("accidental"):
        note.remove(accidental)
    existing = note.find("lyric")
    if existing is not None:
        text = existing.find("text")
        if text is None: text = child(existing, "text")
        text.text = lyric[:500]
    elif lyric:
        child(child(note, "lyric", number="1"), "text", lyric[:500])
    return xml_bytes(root)


def replace_bar(data, part, measure, phrase):
    """Explicitly replace one simple bar with a single-voice phrase.

    Grammar: C4/q D#4/e R/h [C4,E4,G4]/h, optional trailing dot.
    Multi-voice/staff, ties and tuplets are refused to avoid destroying links.
    """
    root = read_xml(data)
    info = inspect(root)
    p = root.findall("part")[part]
    m = p.findall("measure")[measure]
    details = info["parts"][part]["measures"][measure]
    ns = m.findall("note")
    if m.find("backup") is not None or any(n.find("tie") is not None or n.find("notations") is not None or n.find("time-modification") is not None for n in ns) or len({n.findtext("staff", "1") for n in ns}) > 1:
        raise ValueError("This bar contains voices, ties, tuplets or linked symbols. Use MusicXML editing to preserve them.")
    units = {"w": 4, "h": 2, "q": 1, "e": .5, "s": .25}
    generated, total = [], Fraction(0)
    for token in phrase.split():
        match = re.fullmatch(r"(R|[A-G](?:bb|##|b|#)?[0-8]|\[[A-G0-8b#,]+\])/([whqes])(\.?)", token)
        if not match:
            raise ValueError(f"Cannot read '{token}'. Example: C4/q D4/q E4/h. Rest: R/q. Chord: [C4,E4,G4]/h.")
        pitches, unit, dot = match.groups()
        dur = Fraction(units[unit]) * (Fraction(3, 2) if dot else 1)
        total += dur
        ticks = dur * Fraction(str(details["divisions"]))
        if ticks.denominator != 1:
            raise ValueError("This score's rhythmic resolution is too low for that duration. Use MusicXML to increase divisions.")
        for ci, pitch in enumerate(pitches.strip("[]").split(",")):
            n = ET.Element("note")
            if ci: child(n, "chord")
            if pitch == "R": child(n, "rest")
            else:
                pm = re.fullmatch(r"([A-G])(bb|##|b|#)?([0-8])", pitch)
                if not pm: raise ValueError("Invalid chord pitch.")
                step, acc, octave = pm.groups()
                pe = child(n, "pitch"); child(pe, "step", step)
                if acc: child(pe, "alter", {"bb": -2, "b": -1, "#": 1, "##": 2}[acc])
                child(pe, "octave", octave)
            child(n, "duration", int(ticks)); child(n, "voice", "1")
            child(n, "type", duration_type(float(dur))[0])
            if dot: child(n, "dot")
            generated.append(n)
    if abs(float(total) - details["length"]) > 1e-6:
        raise ValueError(f"The phrase uses {float(total):g} quarter beats. This bar needs {details['length']:g}.")
    for n in list(m):
        if n.tag in ("note", "forward"): m.remove(n)
    insert = next((i for i, el in enumerate(m) if el.tag == "barline"), len(m))
    for n in generated:
        m.insert(insert, n); insert += 1
    return xml_bytes(root)


def append_bar(data):
    root = read_xml(data)
    info = inspect(root)
    for pi, p in enumerate(root.findall("part")):
        last = info["parts"][pi]["measures"][-1]
        previous = p.findall("measure")[-1]
        m = child(p, "measure", number=str(len(p.findall("measure"))+1))
        n = child(m, "note"); child(n, "rest", measure="yes")
        child(n, "duration", round(last["length"] * last["divisions"]))
        for line in previous.findall("barline"):
            if line.findtext("bar-style") == "light-heavy" and line.find("repeat") is None:
                previous.remove(line); m.append(line)
    return xml_bytes(root)


def edit_meter(data, measure, beats, beat_type, part=0, all_parts=True):
    if not 1 <= beats <= 32 or beat_type not in (1, 2, 4, 8, 16, 32):
        raise ValueError("Choose a valid time signature.")
    root = read_xml(data)
    parts = root.findall("part") if all_parts else [root.findall("part")[part]]
    for p in parts:
        bars = p.findall("measure")
        if not 0 <= measure < len(bars):
            raise ValueError("This bar does not exist in every selected part. Repair part assembly first.")
        m = bars[measure]
        a = m.find("attributes")
        if a is None:
            a = ET.Element("attributes"); m.insert(0, a)
        for t in a.findall("time"): a.remove(t)
        t = ET.Element("time"); child(t, "beats", beats); child(t, "beat-type", beat_type)
        index = next((i for i,e in enumerate(a) if e.tag not in ("divisions", "key")), len(a))
        a.insert(index, t)
    return xml_bytes(root)


def edit_symbol(data, nid, symbol):
    root = read_xml(data)
    source = inspect(root)["notes"].get(nid)
    if source is None: raise ValueError("Select a note first.")
    if symbol not in ("staccato", "tenuto", "accent", "fermata"):
        raise ValueError("Unsupported symbol.")
    note = root.findall("part")[source["part"]].findall("measure")[source["measure"]].findall("note")[source["index"]]
    if not source["pitched"] and symbol != "fermata":
        raise ValueError("This articulation needs a pitched note.")
    notation = note.find("notations")
    if notation is None: notation = child(note, "notations")
    parent = notation
    if symbol != "fermata":
        parent = notation.find("articulations")
        if parent is None: parent = child(notation, "articulations")
    existing = parent.findall(symbol)
    if existing:
        for item in existing: parent.remove(item)
    else: child(parent, symbol)
    return xml_bytes(root)


def rename_part(data, part, name):
    name = str(name).strip()
    if not name or len(name) > 100: raise ValueError("Use a part name between 1 and 100 characters.")
    root = read_xml(data)
    parts = root.findall("part")
    if not 0 <= part < len(parts): raise ValueError("Part not found.")
    definition = next(p for p in root.findall("part-list/score-part") if p.get("id") == parts[part].get("id"))
    label = definition.find("part-name")
    if label is None: label = child(definition, "part-name")
    label.text = name
    for abbreviation in definition.findall("part-abbreviation"): abbreviation.text = name
    return xml_bytes(root)
