"""
Core in-memory data model for a parsed choral score.

This model is deliberately independent of any particular OCR/OMR engine or
XML library, so the rest of the pipeline (solfege conversion, rendering,
UI) never has to know whether the data came from Audiveris, oemer, or a
hand-written MusicXML file.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional


# Standard part names we care about. OMR engines / MusicXML files often use
# different labels ("Soprano I", "S.", "Sop", etc.) -- see PART_NAME_ALIASES
# in key_tracker.py / musicxml_loader.py for the normalisation step.
SATB_ORDER = ["S", "A", "T", "B"]

PART_NAME_ALIASES = {
    "S": ["soprano", "sop", "s", "s.", "descant", "treble", "mezzo"],
    "A": ["alto", "alt", "a", "a.", "contralto"],
    "T": ["tenor", "ten", "t", "t."],
    "B": ["bass", "bar", "baritone", "b", "b."],
}


@dataclass
class KeySignature:
    """A key signature / key change event, MusicXML-style.

    fifths: number of sharps (+) or flats (-) in the key signature
            (0 = C major / A minor, 1 = G major, -1 = F major, ...)
    mode:   "major" or "minor" (best-effort; defaults to "major")
    measure_number: the measure in which this key becomes active
    """
    fifths: int
    mode: str = "major"
    measure_number: int = 1

    @property
    def tonic_pitch_class(self) -> int:
        """Return tonic as a pitch class 0-11 (C=0) for major keys, or the
        relative major's tonic if mode == 'minor' is handled by the caller.
        """
        # Circle of fifths starting at C=0, going sharp-wise (+7 semitones
        # mod 12 per fifth) or flat-wise (-7 semitones mod 12 per fifth).
        return (7 * self.fifths) % 12


@dataclass
class Note:
    """A single notated pitch.

    step: 'C','D','E','F','G','A','B'
    alter: -2..2 (double flat .. double sharp), 0 = natural
    octave: MusicXML octave number (4 = middle C octave)
    is_rest: True if this is a rest (step/alter/octave are ignored)
    tie_start / tie_stop: for future rendering use
    """
    step: str = "C"
    alter: int = 0
    octave: int = 4
    is_rest: bool = False
    duration: float = 1.0  # in quarter notes
    lyric: Optional[str] = None  # original lyric text, if any
    solfege: Optional[str] = None  # filled in by the solfege engine

    STEP_TO_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}

    @property
    def pitch_class(self) -> int:
        return (self.STEP_TO_PC[self.step] + self.alter) % 12

    @property
    def midi(self) -> int:
        # Do not wrap the accidental at octave boundaries: B#4 is C5,
        # whereas Cb4 is B3.
        return 12 * (self.octave + 1) + self.STEP_TO_PC[self.step] + self.alter


@dataclass
class Measure:
    number: int
    notes: List[Note] = field(default_factory=list)
    key: Optional[KeySignature] = None  # set if a key change starts here


@dataclass
class Part:
    part_id: str
    name: str
    satb_role: Optional[str] = None  # one of "S","A","T","B" or None
    measures: List[Measure] = field(default_factory=list)


@dataclass
class Score:
    title: str = "Untitled"
    parts: List[Part] = field(default_factory=list)
    key_signatures: List[KeySignature] = field(default_factory=list)

    def part_by_role(self, role: str) -> Optional[Part]:
        for p in self.parts:
            if p.satb_role == role:
                return p
        return None

    def key_at_measure(self, measure_number: int) -> KeySignature:
        """Return the key signature in effect at a given measure number."""
        active = KeySignature(fifths=0, mode="major", measure_number=1)
        for ks in sorted(self.key_signatures, key=lambda k: k.measure_number):
            if ks.measure_number <= measure_number:
                active = ks
            else:
                break
        return active
