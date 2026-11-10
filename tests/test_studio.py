"""Regression tests for real notation, timing, safe edits and persistence."""
import io
import json
import threading
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

import pytest

from src.core.musicxml_loader import load_musicxml
from src.core.score_model import Note
from src.studio.document import (append_bar, child, edit_note, engrave, inspect,
                                 new_score, read_xml, replace_bar, xml_bytes)
from src.studio.server import Library, StudioServer


def melody(phrase="C4/q D4/q E4/h", bars=1, **kwargs):
    return replace_bar(new_score(template="melody", bars=bars, tempo=120, **kwargs), 0, 0, phrase)


def test_mxl_rootfile_attribute_and_namespace(tmp_path):
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        z.writestr("META-INF/container.xml", '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="music/main.musicxml" media-type="application/vnd.recordare.musicxml+xml"/></rootfiles></container>')
        z.writestr("wrong.xml", "<not-a-score/>")
        z.writestr("music/main.musicxml", melody())
    assert read_xml(out.getvalue()).tag == "score-partwise"
    path = tmp_path / "score.mxl"
    path.write_bytes(out.getvalue())
    score = load_musicxml(str(path))
    assert [n.duration for n in score.parts[0].measures[0].notes] == [1, 1, 2]


def test_reject_external_entities():
    data = b'<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///secret">]><score-partwise><part>&xxe;</part></score-partwise>'
    with pytest.raises(Exception): read_xml(data)


def test_accidentals_cross_octaves():
    assert Note(step="B", alter=1, octave=4).midi == 72
    assert Note(step="C", alter=-1, octave=4).midi == 59


def test_timing_chords_dots_rests():
    data = melody("[C4,E4,G4]/q. R/e D4/h")
    info = inspect(read_xml(data))
    assert not info["issues"]
    assert [n["offset"] for n in info["notes"].values()] == [0, 0, 0, 1.5, 2]
    result = engrave(data)
    assert result["duration"] == pytest.approx(2)
    assert [e["pitch"] for e in result["events"][:3]] == [60, 64, 67]
    assert all(e["duration"] == pytest.approx(.75) for e in result["events"][:3])
    assert result["events"][-1]["time"] == pytest.approx(1)
    assert "Do" in result["pages"][0]


def test_tied_notes_sustain():
    root = read_xml(melody("C4/h C4/h"))
    notes = root.findall("part/measure/note")
    child(notes[0], "tie", type="start")
    child(child(notes[0], "notations"), "tied", type="start")
    child(notes[1], "tie", type="stop")
    child(child(notes[1], "notations"), "tied", type="stop")
    result = engrave(xml_bytes(root))
    assert len(result["events"]) == 1
    assert result["events"][0]["duration"] == pytest.approx(2)
    assert not result["issues"]
    with pytest.raises(ValueError, match="tied"):
        edit_note(xml_bytes(root), "ss-p0-m0-n0", "D", 0, 4, "")


def test_tempo_changes_and_repeats():
    data = replace_bar(melody("C4/w", bars=2), 0, 1, "D4/w")
    root = read_xml(data)
    bars = root.findall("part/measure")
    direction = ET.Element("direction")
    child(direction, "sound", tempo="60")
    bars[1].insert(0, direction)
    result = engrave(xml_bytes(root))
    assert result["duration"] == pytest.approx(6)
    assert [e["duration"] for e in result["events"]] == pytest.approx([2, 4])
    child(child(bars[0], "barline", location="left"), "repeat", direction="forward")
    child(child(bars[1], "barline", location="right"), "repeat", direction="backward")
    repeated = engrave(xml_bytes(root))
    assert len(repeated["events"]) == 4
    assert repeated["duration"] >= 12


def test_first_second_endings_and_pickup():
    data = melody("C4/w", bars=3)
    data = replace_bar(data,0,1,"D4/w")
    data = replace_bar(data,0,2,"E4/w")
    root=read_xml(data)
    bars=root.findall("part/measure")
    child(child(bars[0],"barline",location="left"),"repeat",direction="forward")
    child(child(bars[1],"barline",location="left"),"ending",type="start",number="1")
    line=child(bars[1],"barline",location="right")
    child(line,"ending",type="stop",number="1");child(line,"repeat",direction="backward")
    child(child(bars[2],"barline",location="left"),"ending",type="start",number="2")
    child(child(bars[2],"barline",location="right"),"ending",type="stop",number="2")
    result=engrave(xml_bytes(root))
    assert [e["pitch"] for e in result["events"]] == [60,62,60,64]
    assert result["duration"] == pytest.approx(8)
    root=read_xml(melody("C4/w",bars=2))
    first=root.find("part/measure")
    first.set("implicit","yes")
    first.find("note/duration").text="16"
    first.find("note/type").text="quarter"
    result=engrave(xml_bytes(root))
    assert result["duration"]==pytest.approx(2.5)


def test_tuplets_and_multiple_voices():
    root = read_xml(melody("C4/w"))
    m = root.find("part/measure")
    m.remove(m.find("note"))
    m.find("attributes/divisions").text = "3"
    for pitch in "CDE":
        n = child(m, "note");p = child(n, "pitch");child(p, "step", pitch);child(p, "octave", 4)
        child(n, "duration", 1);child(n, "voice", 1);child(n, "type", "eighth")
        tm = child(n, "time-modification");child(tm, "actual-notes", 3);child(tm, "normal-notes", 2)
    rest = child(m, "note");child(rest, "rest");child(rest, "duration", 9);child(rest, "voice", 1);child(rest, "type", "half");child(rest, "dot")
    child(child(m, "backup"), "duration", 12)
    n = child(m, "note");p=child(n,"pitch");child(p,"step","G");child(p,"octave",3)
    child(n,"duration",12);child(n,"voice",2);child(n,"type","whole")
    info = inspect(root)
    assert not info["issues"]
    assert list(info["notes"].values())[-1]["offset"] == 0
    result = engrave(xml_bytes(root))
    assert result["duration"] == pytest.approx(2)
    assert result["events"][0]["duration"] == pytest.approx(1/6, abs=.002)
    assert 'class="tuplet"' in result["pages"][0]
    with pytest.raises(ValueError, match="voices"):
        replace_bar(xml_bytes(root), 0, 0, "C4/w")


def test_transposing_instrument_and_octave_clef():
    root = read_xml(melody("C4/w"))
    a = root.find("part/measure/attributes")
    transpose = child(a, "transpose");child(transpose, "diatonic", -1);child(transpose, "chromatic", -2)
    result = engrave(xml_bytes(root))
    assert result["events"][0]["pitch"] == 58
    # MusicXML octave-clef pitches already encode their register. Changing
    # the clef changes staff placement, not the stored pitch a second time.
    a.remove(transpose);child(a.find("clef"), "clef-octave-change", -1)
    assert engrave(xml_bytes(root))["events"][0]["pitch"] == 60


def test_key_is_part_local_and_changes():
    data = new_score(bars=2)
    data = replace_bar(data, 0, 0, "D4/w")
    data = replace_bar(data, 1, 0, "D4/w")
    root = read_xml(data)
    root.findall("part")[0].find("measure/attributes/key/fifths").text = "2"
    info = inspect(root)
    assert info["notes"]["ss-p0-m0-n0"]["solfa"] == "Do"
    assert info["notes"]["ss-p1-m0-n0"]["solfa"] == "Re"


def test_edit_preserves_unrelated_notation_and_export():
    root = read_xml(melody())
    n = root.find("part/measure/note")
    child(child(n, "notations"), "fermata")
    child(child(n, "lyric", number="2"), "text", "original second verse")
    edited = read_xml(edit_note(xml_bytes(root), "ss-p0-m0-n0", "F", 1, 5, "Hello"))
    assert edited.findtext("part/measure/note/pitch/step") == "F"
    assert edited.find("part/measure/note/notations/fermata") is not None
    assert edited.findtext("part/measure/note/lyric/text") == "Hello"
    assert edited.findall("part/measure/note")[1].findtext("pitch/step") == "D"


def test_invalid_bar_does_not_mutate_source():
    data = melody()
    with pytest.raises(ValueError, match="needs 4"):
        replace_bar(data, 0, 0, "C4/q")
    assert inspect(read_xml(data))["notes"]["ss-p0-m0-n2"]["step"] == "E"


def test_rhythm_mismatch_is_flagged():
    root = read_xml(melody())
    root.find("part/measure/note/type").text = "whole"
    assert any("Rhythm mismatch" in i["message"] for i in inspect(root)["issues"])


def test_library_reopen_undo_and_stale_revision(tmp_path):
    path = tmp_path / "library.sqlite3"
    lib = Library(path)
    original = melody()
    sid = lib.add(original)
    updated = lib.update(sid, 1, metadata={"group": "Concert", "bookmarks": [{"measure": 0, "label": "Opening"}]})
    assert updated["revision"] == 2
    with pytest.raises(ValueError, match="another window"):
        lib.update(sid, 1, metadata={"group": "Lost update"})
    lib = Library(path)
    assert lib.get(sid)["meta"]["group"] == "Concert"
    changed = append_bar(original)
    lib.update(sid, 2, data=changed)
    assert len(read_xml(lib.get(sid)["xml"]).findall("part/measure")) == 2
    restored = lib.update(sid, 3, undo=True)
    assert restored["xml"] == original
    assert restored["meta"]["bookmarks"][0]["label"] == "Opening"


def test_original_filename_and_annotations_survive_music_edits(tmp_path):
    lib = Library(tmp_path / "library.sqlite3")
    name = "Choir rehearsal 01 (Final).pdf"
    sid = lib.add(melody(), {"title": name, "sourceFileName": name}, b"original bytes", "application/pdf")
    marks = [{"page": 2, "tool": "highlight", "points": [[10, 20], [300, 20]]}]
    lib.update(sid, 1, metadata={"annotations": marks})
    lib.update(sid, 2, data=melody("F4/w"))
    row = Library(lib.path).get(sid)
    assert row["meta"]["title"] == name
    assert row["meta"]["annotations"] == marks
    assert row["source"] == b"original bytes"


def test_bundled_sample_banks_are_distinct():
    from pathlib import Path
    import base64
    folder = Path(__file__).parents[1] / "src/studio/static/sounds"
    samples = []
    for name in ("Piano", "Flute", "Strings", "Organ", "Bell"):
        bank = json.loads((folder / f"{name}.json").read_text())
        assert len(bank) == 88
        data = base64.b64decode(bank["C4"].split(",")[1])
        assert len(data) > 1000
        samples.append(data)
    assert len(set(samples)) == 5


def test_scan_progress_uses_real_steps_and_stops_elapsed_time(tmp_path):
    from types import SimpleNamespace
    from src.studio.server import scan_status
    lib = Library(tmp_path / "library.sqlite3")
    server = SimpleNamespace(library=lib, jobs={"abc": {"status": "running", "stage": 1, "started": 100}})
    folder = tmp_path / "scans/abc"
    folder.mkdir(parents=True)
    (folder / "recognition.log").write_text("INFO StepMonitoring 98 | HEADS\nINFO StepMonitoring 98 | RHYTHMS\n")
    result = scan_status(server, "abc")
    assert result["detail"] == "Recognizing: rhythms"
    assert result["stage"] == 1
    assert "detail" not in server.jobs["abc"]
    server.jobs["abc"].update(status="done", stage=4, finished=125)
    assert scan_status(server, "abc")["elapsed"] == 25


def test_second_launch_reuses_only_the_same_studio_library(tmp_path, monkeypatch):
    from src.studio.server import start_or_reuse
    lib = Library(tmp_path / "one.sqlite3")
    server = StudioServer(("127.0.0.1", 0), lib)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    opened = []
    monkeypatch.setattr("src.studio.server.webbrowser.open", opened.append)
    port = server.server_address[1]
    try:
        assert start_or_reuse(port, lib) is None
        assert opened == [f"http://127.0.0.1:{port}"]
        assert start_or_reuse(port, lib, open_browser=False) is None
        assert len(opened) == 1
        with pytest.raises(RuntimeError, match="different Studio library"):
            start_or_reuse(port, Library(tmp_path / "two.sqlite3"))
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_meter_correction_preserves_notes_and_flags_missing_meter():
    from src.studio.document import edit_meter
    root = read_xml(melody())
    a = root.find("part/measure/attributes")
    a.remove(a.find("time"))
    before = xml_bytes(root)
    assert any(i.get("code") == "missing-meter" for i in inspect(root)["issues"])
    corrected = read_xml(edit_meter(before, 0, 12, 8))
    assert corrected.findtext("part/measure/attributes/time/beats") == "12"
    assert [ET.tostring(n) for n in corrected.findall("part/measure/note")] == [ET.tostring(n) for n in root.findall("part/measure/note")]
    assert not any(i.get("code") == "missing-meter" for i in inspect(corrected)["issues"])


def test_scan_page_ranges_and_satb_guard(tmp_path):
    from src.studio.scan_options import selected_pages, repair_satb_book
    assert selected_pages("1-3, 5") == ["1", "2", "3", "5"]
    for value in ("0", "4-2", "-batch", "1;2"):
        with pytest.raises(ValueError): selected_pages(value)
    book = tmp_path / "bad.omr"
    with zipfile.ZipFile(book, "w") as z:
        z.writestr("book.xml", '<book><sheet><page><system><part><staff-configuration/></part></system></page></sheet><score/></book>')
    before = book.read_bytes()
    with pytest.raises(ValueError, match="Selected ensemble"):
        repair_satb_book(book)
    assert book.read_bytes() == before


def test_local_http_import_edit_export_and_origin_checks(tmp_path):
    server = StudioServer(("127.0.0.1", 0), Library(tmp_path / "db.sqlite3"))
    thread = threading.Thread(target=server.serve_forever, daemon=True);thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    def request(path, payload=None, headers=None):
        data = json.dumps(payload).encode() if payload is not None else None
        h = {"Content-Type": "application/json", "X-Studio-Token": server.token, **(headers or {})}
        return urllib.request.urlopen(urllib.request.Request(base+path, data=data, headers=h))
    try:
        sid = json.load(request("/api/new", {"title": "Round trip", "bars": 1, "template": "melody"}))["id"]
        result = json.load(request(f"/api/score/{sid}"))
        assert result["title"] == "Round trip"
        copy_id = json.load(request("/api/duplicate", {"id": sid, "revision": 1}))["id"]
        assert copy_id != sid
        assert json.load(request(f"/api/score/{copy_id}"))["title"] == "Round trip (copy)"
        json.load(request("/api/meta", {"id": copy_id, "revision": 1, "meta": {"title": "Renamed", "group": "Concert", "trashed": True}}))
        copied = server.library.get(copy_id)
        assert copied["meta"]["trashed"] and copied["meta"]["group"] == "Concert"
        json.load(request("/api/meta", {"id": copy_id, "revision": 2, "meta": {"trashed": False}}))
        assert not server.library.get(copy_id)["meta"]["trashed"]
        assert server.library.get(sid)["meta"]["title"] == "Round trip"
        assert "font-src 'self' data:" in request("/").headers["Content-Security-Policy"]
        json.load(request("/api/edit", {"id": sid, "revision": 1, "action": "bar", "values": {"part": 0, "measure": 0, "phrase": "C4/w"}}))
        assert read_xml(request(f"/api/xml/{sid}").read()).findtext("part/measure/note/pitch/step") == "C"
        with pytest.raises(urllib.error.HTTPError) as e:
            request("/api/new", {}, {"Origin": "https://unrelated.example"})
        assert e.value.code == 403
        with pytest.raises(urllib.error.HTTPError) as e:
            request("/api/new", {}, {"X-Studio-Token": "wrong"})
        assert e.value.code == 403
    finally:
        server.shutdown();server.server_close();thread.join()

def test_broken_endings_do_not_hide_opening_bars():
    root = read_xml(new_score(template='satb', bars=4))
    root = read_xml(replace_bar(xml_bytes(root), 0, 0, 'C4/q D4/q E4/h'))
    bars = root.findall('part')[1].findall('measure')
    child(child(bars[1], 'barline', location='left'), 'ending', number='1', type='start')
    child(child(bars[2], 'barline', location='left'), 'ending', number='1', type='start')
    original = xml_bytes(root)
    result = engrave(original)
    svg = ''.join(result['pages'])
    assert 'id="ss-p0-m0-n0"' in result['pages'][0]
    assert 'id="ss-measure-0"' in svg
    assert any(i.get('code') == 'broken-endings' for i in result['issues'])
    assert len(read_xml(original).findall('part/measure/barline/ending')) == 2


def test_valid_endings_and_consistent_numbers_preserved():
    from src.studio.document import prepare_render_structure
    root = read_xml(new_score(template='melody', bars=3))
    bars = root.find('part').findall('measure')
    child(child(bars[1], 'barline', location='left'), 'ending', number='1', type='start')
    child(child(bars[2], 'barline', location='right'), 'ending', number='1', type='stop')
    before = xml_bytes(root)
    info = {'issues': []}
    prepare_render_structure(root, info)
    assert xml_bytes(root) == before
    assert not info['issues']


def test_inconsistent_part_numbers_use_explicit_provisional_positions():
    from src.studio.document import prepare_render_structure
    root = read_xml(new_score(template='satb', bars=3))
    root.findall('part')[1].findall('measure')[1].set('number', '9')
    info = {'issues': []}
    prepare_render_structure(root, info)
    assert all([m.get('number') for m in p.findall('measure')] == ['1', '2', '3'] for p in root.findall('part'))
    assert info['issues'][0]['code'] == 'bar-alignment'


@pytest.mark.parametrize("layout,counts", [("satb", [1,1,1,1]), ("piano", [2]), ("satb-piano", [1,1,1,1,2])])
def test_ensemble_presets_preserve_staff_counts(tmp_path, layout, counts):
    from src.studio.scan_options import repair_satb_book
    book = tmp_path / "ensemble.omr"
    parts = ''.join('<part>' + '<staff-configuration/>' * n + '</part>' for n in counts)
    with zipfile.ZipFile(book, 'w') as z:
        z.writestr('book.xml', '<book><sheet><page><system>' + parts + '</system></page></sheet><score/></book>')
    repair_satb_book(book, layout)
    with zipfile.ZipFile(book) as z:
        root = ET.fromstring(z.read('book.xml'))
    assert [int(p.get('staff-count')) for p in root.findall('score/logical-part')] == counts
    assert book.with_suffix('.original.omr').exists()

@pytest.mark.parametrize('symbol', ['staccato', 'tenuto', 'accent', 'fermata'])
def test_symbol_toggle_preserves_timing_and_lyrics(symbol):
    from src.studio.document import edit_symbol
    original = melody()
    root = read_xml(original)
    note = root.find('part/measure/note')
    child(child(note, 'lyric'), 'text', 'hello')
    child(child(note, 'notations'), 'slur', type='start', number='1')
    original = xml_bytes(root)
    edited = edit_symbol(original, 'ss-p0-m0-n0', symbol)
    changed = read_xml(edited).find('part/measure/note')
    assert changed.findtext('duration') == note.findtext('duration')
    assert changed.findtext('lyric/text') == 'hello'
    assert changed.find('notations/slur') is not None
    assert changed.find('.//' + symbol) is not None
    reverted = read_xml(edit_symbol(edited, 'ss-p0-m0-n0', symbol))
    assert reverted.find('.//' + symbol) is None
    assert reverted.find('.//slur') is not None


def test_rename_preserves_part_identity_and_undo(tmp_path):
    from src.studio.document import rename_part
    lib = Library(tmp_path / 'rename.sqlite3')
    original = melody()
    sid = lib.add(original)
    row = lib.get(sid)
    edited = rename_part(row['xml'], 0, 'Solo flute')
    assert ET.tostring(read_xml(edited).find('part')) == ET.tostring(read_xml(row['xml']).find('part'))
    saved = lib.update(sid, row['revision'], data=edited)
    assert inspect(read_xml(saved['xml']))['parts'][0]['name'] == 'Solo flute'
    restored = lib.update(sid, saved['revision'], undo=True)
    assert restored['xml'] == row['xml']

def test_move_part_preserves_music_and_definition_order():
    from src.studio.document import move_part
    original = new_score(template="satb", bars=2)
    parts = read_xml(original).findall("part")
    moved = read_xml(move_part(original, 1, -1))
    expected = [parts[1], parts[0], *parts[2:]]
    assert [ET.tostring(p) for p in moved.findall("part")] == [ET.tostring(p) for p in expected]
    assert [p.get("id") for p in moved.findall("part-list/score-part")] == [p.get("id") for p in expected]
