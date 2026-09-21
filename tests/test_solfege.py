import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.score_model import Note, KeySignature, Score, Part, Measure
from src.core import solfege as sf
from src.core.key_tracker import assign_satb_roles, annotate_score, guess_satb_role
from src.core.musicxml_loader import load_musicxml


def test_fixed_do_basic():
    c_major_key = KeySignature(fifths=0)
    note = Note(step="C", alter=0, octave=4)
    assert sf.fixed_do_name(note) == "Do"
    note2 = Note(step="F", alter=1, octave=4)  # F#
    assert sf.fixed_do_name(note2) == "Fa"  # collapsed spelling
    assert sf.fixed_do_name(note2, chromatic_labels=True) == "Fa#/Solb"


def test_movable_do_c_major():
    key = KeySignature(fifths=0, mode="major")
    assert sf.movable_do_name(Note(step="C", octave=4), key) == "Do"
    assert sf.movable_do_name(Note(step="G", octave=4), key) == "Sol"
    assert sf.movable_do_name(Note(step="B", octave=4), key) == "Ti"


def test_movable_do_transposes_with_key():
    # In D major (2 sharps), D is now "Do".
    key_d = KeySignature(fifths=2, mode="major")
    assert sf.movable_do_name(Note(step="D", octave=4), key_d) == "Do"
    assert sf.movable_do_name(Note(step="A", octave=4), key_d) == "Sol"
    # F# is diatonic scale degree 3 (Mi) in D major
    assert sf.movable_do_name(Note(step="F", alter=1, octave=4), key_d) == "Mi"


def test_movable_do_chromatic_raise():
    key_c = KeySignature(fifths=0, mode="major")
    fsharp = Note(step="F", alter=1, octave=4)
    assert sf.movable_do_name(fsharp, key_c) == "Fi"


def test_movable_do_chromatic_lower():
    key_c = KeySignature(fifths=0, mode="major")
    # Flattened notes get the lowered ("e"-ending) names, not raised ones.
    assert sf.movable_do_name(Note(step="B", alter=-1, octave=4), key_c) == "Te"
    assert sf.movable_do_name(Note(step="D", alter=-1, octave=4), key_c) == "Ra"
    assert sf.movable_do_name(Note(step="E", alter=-1, octave=4), key_c) == "Me"
    assert sf.movable_do_name(Note(step="A", alter=-1, octave=4), key_c) == "Le"
    # ... and in a flat key the key-signature flats are plain diatonic
    # degrees: Bb is the 4th of F major ("Fa"), E natural is its 7th ("Ti").
    key_f = KeySignature(fifths=-1, mode="major")
    assert sf.movable_do_name(Note(step="B", alter=-1, octave=4), key_f) == "Fa"
    assert sf.movable_do_name(Note(step="E", octave=4), key_f) == "Ti"
    assert sf.movable_do_name(Note(step="F", octave=4), key_f) == "Do"


def test_movable_do_la_based_minor_default():
    # Default minor handling is La-based: A minor tonic sings "La".
    key_am = KeySignature(fifths=0, mode="minor")
    assert sf.movable_do_name(Note(step="A", octave=4), key_am) == "La"
    assert sf.movable_do_name(Note(step="B", octave=4), key_am) == "Ti"
    assert sf.movable_do_name(Note(step="C", octave=5), key_am) == "Do"
    assert sf.movable_do_name(Note(step="E", octave=4), key_am) == "Mi"
    # Same logic in a flat-side minor key (C minor: relative major Eb,
    # so Eb sings "Do" and the flat-7th Bb sings "Sol").
    key_cm = KeySignature(fifths=-3, mode="minor")
    assert sf.movable_do_name(Note(step="C", octave=4), key_cm) == "La"
    assert sf.movable_do_name(Note(step="E", alter=-1, octave=4), key_cm) == "Do"
    assert sf.movable_do_name(Note(step="B", alter=-1, octave=4), key_cm) == "Sol"


def test_movable_do_do_based_minor():
    # minor_uses_do=True anchors Do at the minor tonic (Do-based minor).
    # A natural minor: A B C D E F G -> Do Re Me Fa Sol Le Te.
    key_am = KeySignature(fifths=0, mode="minor")
    assert sf.movable_do_name(Note(step="A", octave=4), key_am, minor_uses_do=True) == "Do"
    assert sf.movable_do_name(Note(step="B", octave=4), key_am, minor_uses_do=True) == "Re"
    assert sf.movable_do_name(Note(step="C", octave=5), key_am, minor_uses_do=True) == "Me"
    assert sf.movable_do_name(Note(step="D", octave=4), key_am, minor_uses_do=True) == "Fa"
    assert sf.movable_do_name(Note(step="E", octave=4), key_am, minor_uses_do=True) == "Sol"
    assert sf.movable_do_name(Note(step="F", octave=4), key_am, minor_uses_do=True) == "Le"
    assert sf.movable_do_name(Note(step="G", octave=4), key_am, minor_uses_do=True) == "Te"
    # C minor: tonic C = Do, Eb = Me, F = Fa, Bb = Te.
    key_cm = KeySignature(fifths=-3, mode="minor")
    assert sf.movable_do_name(Note(step="C", octave=4), key_cm, minor_uses_do=True) == "Do"
    assert sf.movable_do_name(Note(step="E", alter=-1, octave=4), key_cm, minor_uses_do=True) == "Me"
    assert sf.movable_do_name(Note(step="F", octave=4), key_cm, minor_uses_do=True) == "Fa"
    assert sf.movable_do_name(Note(step="B", alter=-1, octave=4), key_cm, minor_uses_do=True) == "Te"


def test_guess_satb_role():
    assert guess_satb_role("Soprano") == "S"
    assert guess_satb_role("Alto I") == "A"
    assert guess_satb_role("Ten.") == "T"
    assert guess_satb_role("Bass") == "B"
    assert guess_satb_role("Piano") is None
    # Token-based matching: modifiers/quantifiers must not hijack the role.
    assert guess_satb_role("Second Alto") == "A"
    assert guess_satb_role("Soprano II") == "S"
    assert guess_satb_role("Basses") == "B"
    assert guess_satb_role("Alto 2") == "A"
    # Extended aliases.
    assert guess_satb_role("Treble") == "S"
    assert guess_satb_role("Contralto") == "A"
    assert guess_satb_role("Mezzo-Soprano") == "S"
    # Non-matching / empty names.
    assert guess_satb_role("") is None
    assert guess_satb_role("Organ") is None


def test_key_at_measure_change():
    score = Score(key_signatures=[
        KeySignature(fifths=0, measure_number=1),
        KeySignature(fifths=2, measure_number=3),
    ])
    assert score.key_at_measure(1).fifths == 0
    assert score.key_at_measure(2).fifths == 0
    assert score.key_at_measure(3).fifths == 2
    assert score.key_at_measure(10).fifths == 2


def test_load_sample_musicxml_and_annotate():
    path = str(Path(__file__).parent / "sample_data" / "satb_sample_with_key_change.musicxml")
    score = load_musicxml(path)
    assign_satb_roles(score)
    roles = {p.name: p.satb_role for p in score.parts}
    assert roles == {"Soprano": "S", "Alto": "A", "Tenor": "T", "Bass": "B"}

    annotate_score(score, mode="movable")
    soprano = score.part_by_role("S")
    # measure 1: C in C major -> Do ; measure 3 (key change to D major): D -> Do
    assert soprano.measures[0].notes[0].solfege == "Do"
    assert soprano.measures[2].notes[0].solfege == "Do"

    tenor = score.part_by_role("T")
    # measure 2: F# in C major context is chromatic raised 4th -> Fi
    assert tenor.measures[1].notes[0].solfege == "Fi"
    # measure 3: after key change to D major, G# is the raised 4th of D major -> Fi
    assert tenor.measures[2].notes[0].solfege == "Fi"

    annotate_score(score, mode="fixed")
    assert soprano.measures[0].notes[0].solfege == "Do"  # C is always Do in fixed-do
    assert soprano.measures[2].notes[0].solfege == "Re"  # D is always Re in fixed-do


if __name__ == "__main__":
    import traceback
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_")]
    passed, failed = 0, 0
    for t in tests:
        try:
            t()
            print(f"PASS: {t.__name__}")
            passed += 1
        except Exception:
            print(f"FAIL: {t.__name__}")
            traceback.print_exc()
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
