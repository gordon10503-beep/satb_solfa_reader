"""
Solfege (so-fa) name engine.

Implements both:
  - Fixed-do (固定調): the syllable is tied to the absolute pitch class,
    C=Do, D=Re, E=Mi, F=Fa, G=Sol, A=La, B=Si, independent of key.
  - Movable-do (首調): the syllable is tied to the scale degree relative
    to the current key's tonic, so "Do" always means the tonic. Chromatic
    (out-of-scale) notes get the standard raised/lowered chromatic solfa
    names (Di, Ri, Fi, Si, Li / Ra, Me, Se, Le, Te). Which of the pair
    applies is chosen from the note's spelling: a sharpened diatonic step
    takes the raised name, a flattened one the lowered name (F# = "Fi"
    but Bb = "Te" in C major).

Minor keys in movable-do:
  - Default is La-based minor (the HK/TW choir convention): the minor
    tonic itself is sung "La" (Do sits on the relative major's tonic), so
    A-minor naturals sing La Ti Do Re Mi Fa Sol.
  - minor_uses_do=True switches to Do-based minor: the minor tonic is
    sung "Do", with natural-minor degrees Me/Le/Te and ascending
    chromatic degrees Di/Mi/Fi/Li/Ti. (Enharmonic spellings are not
    distinguished in this mode: the syllable follows the pitch class.)
"""
from __future__ import annotations
from typing import Dict
from .score_model import Note, KeySignature

# ---------------------------------------------------------------------------
# Fixed-do: absolute pitch class -> syllable. Sharps/flats keep the same
# base syllable (common convention); pass chromatic_labels=True to get
# sharp/flat aware labels instead of collapsing.
# ---------------------------------------------------------------------------
FIXED_DO_BASE = {
    0: "Do", 1: "Do", 2: "Re", 3: "Re", 4: "Mi", 5: "Fa",
    6: "Fa", 7: "Sol", 8: "Sol", 9: "La", 10: "La", 11: "Si",
}

FIXED_DO_CHROMATIC = {
    0: "Do", 1: "Do#/Reb", 2: "Re", 3: "Re#/Mib", 4: "Mi", 5: "Fa",
    6: "Fa#/Solb", 7: "Sol", 8: "Sol#/Lab", 9: "La", 10: "La#/Sib", 11: "Si",
}

# ---------------------------------------------------------------------------
# Movable-do: scale degree (semitone distance from tonic, 0-11) -> syllable.
# Diatonic major-scale degrees are Do Re Mi Fa Sol La Ti; chromatic
# alterations use the standard "raise ends in i / lower ends in e" system.
# ---------------------------------------------------------------------------
MAJOR_DIATONIC_SLOTS = frozenset((0, 2, 4, 5, 7, 9, 11))

# Raised ("i"-ending) chromatic spellings.
MOVABLE_DO_MAJOR = {
    0: "Do", 1: "Di", 2: "Re", 3: "Ri", 4: "Mi", 5: "Fa",
    6: "Fi", 7: "Sol", 8: "Si", 9: "La", 10: "Li", 11: "Ti",
}
# Lowered ("e"-ending) chromatic spellings; diatonic slots are identical.
MOVABLE_DO_MAJOR_LOWERED = {
    0: "Do", 1: "Ra", 2: "Re", 3: "Me", 4: "Mi", 5: "Fa",
    6: "Se", 7: "Sol", 8: "Le", 9: "La", 10: "Te", 11: "Ti",
}
# Do-based minor (minor_uses_do=True): the minor tonic sings "Do".
# Natural-minor degrees are Do Re Me Fa Sol Le Te; the remaining slots use
# the ascending melodic-minor names. Enharmonics are not distinguished:
# e.g. G#/Ab both land on the "Le" slot.
MOVABLE_DO_MINOR = {
    0: "Do", 1: "Di", 2: "Re", 3: "Me", 4: "Mi", 5: "Fa",
    6: "Fi", 7: "Sol", 8: "Le", 9: "Li", 10: "Te", 11: "Ti",
}
# Alternative spelling some HK choirs use for the raised 5th degree
# ("Si" clashes with fixed-do Si/B). Note: this doubles with the lowered
# Sol name "Se" from MOVABLE_DO_MAJOR_LOWERED -- a known ambiguity of the
# convention, kept because it is the existing toggle behaviour.
MOVABLE_DO_MAJOR_ALT_SHARP5 = dict(MOVABLE_DO_MAJOR)
MOVABLE_DO_MAJOR_ALT_SHARP5[8] = "Se"  # avoids clashing with fixed-do "Si"

_SHARP_ORDER = "FCGDAEB"   # order in which sharps appear as fifths grows
_FLAT_ORDER = "BEADGCF"    # order in which flats appear as fifths drops


def _diatonic_alters(fifths: int) -> Dict[str, int]:
    """Return {step: alter} that the key signature implies for A-G."""
    alters = {s: 0 for s in "CDEFGAB"}
    for i in range(min(fifths, 7)):
        alters[_SHARP_ORDER[i]] = 1
    for i in range(min(-fifths, 7)):
        alters[_FLAT_ORDER[i]] = -1
    return alters


def semitone_from_tonic(pitch_class: int, tonic_pc: int) -> int:
    return (pitch_class - tonic_pc) % 12


def fixed_do_name(note: Note, chromatic_labels: bool = False) -> str:
    if note.is_rest:
        return ""
    table = FIXED_DO_CHROMATIC if chromatic_labels else FIXED_DO_BASE
    return table[note.pitch_class]


def movable_do_name(
    note: Note,
    key: KeySignature,
    minor_uses_do: bool = False,
    avoid_si_clash: bool = False,
) -> str:
    """Return the movable-do syllable for `note` given the active `key`.

    minor_uses_do: if True and key.mode == 'minor', anchor "Do" at the
                    minor tonic (Do-based minor). The default is La-based
                    minor: the minor tonic sings "La" (Do anchored at the
                    relative major's tonic), the HK/TW convention.
    """
    if note.is_rest:
        return ""

    # tonic_pitch_class already returns the *relative major's* tonic for
    # minor keys, which is exactly the Do anchor for La-based minor.
    tonic_pc = key.tonic_pitch_class
    if key.mode == "minor" and minor_uses_do:
        # Do-based minor: the minor tonic sits a minor 3rd below the
        # relative-major tonic that tonic_pitch_class returns.
        tonic_pc = (tonic_pc - 3) % 12
        return MOVABLE_DO_MINOR[(note.pitch_class - tonic_pc) % 12]

    degree = (note.pitch_class - tonic_pc) % 12
    if degree in MAJOR_DIATONIC_SLOTS:
        table = MOVABLE_DO_MAJOR_ALT_SHARP5 if avoid_si_clash else MOVABLE_DO_MAJOR
        return table[degree]

    # Chromatic slot: pick the raised vs lowered name from the spelling
    # (sharpened diatonic step -> "i" name, flattened step -> "e" name).
    diatonic_alter = _diatonic_alters(key.fifths).get(note.step.upper(), 0)
    raised = MOVABLE_DO_MAJOR_ALT_SHARP5 if avoid_si_clash else MOVABLE_DO_MAJOR
    table = raised if note.alter - diatonic_alter > 0 else MOVABLE_DO_MAJOR_LOWERED
    return table[degree]


def annotate_note(
    note: Note,
    key: KeySignature,
    mode: str = "movable",
    minor_uses_do: bool = False,
    fixed_chromatic_labels: bool = False,
    avoid_si_clash: bool = False,
) -> str:
    """Compute and also cache (note.solfege) the syllable for one note."""
    if mode == "fixed":
        name = fixed_do_name(note, chromatic_labels=fixed_chromatic_labels)
    else:
        name = movable_do_name(
            note, key, minor_uses_do=minor_uses_do, avoid_si_clash=avoid_si_clash
        )
    note.solfege = name
    return name
