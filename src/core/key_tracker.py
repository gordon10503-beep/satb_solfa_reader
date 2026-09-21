"""
Utilities for detecting/normalising part names to SATB roles, and for
walking a Score to compute the annotated solfege for every note while
respecting key changes that happen mid-piece.
"""
from __future__ import annotations
import re
from typing import List, Optional, Tuple

from .score_model import Score, SATB_ORDER, PART_NAME_ALIASES
from . import solfege as sf

# (alias, role) pairs flattened from PART_NAME_ALIASES (the single source
# of truth, in score_model.py -- extend it there, not here), longest alias
# first so that e.g. "soprano" wins over its "sop"/"s" prefixes.
_ALIAS_TOKENS: List[Tuple[str, str]] = sorted(
    (
        (token, role)
        for role, aliases in PART_NAME_ALIASES.items()
        for alias in aliases
        for token in re.split(r"[^a-z]+", alias.lower())
        if token
    ),
    key=lambda pair: len(pair[0]),
    reverse=True,
)


def guess_satb_role(part_name: str) -> Optional[str]:
    """Best-effort SATB role guess from a part name.

    Matching is token-based ("Second Alto" -> A, "Basses" -> B), so OCR
    quirks and plurals resolve instead of being hijacked by short
    prefixes; single-letter aliases ("S", "A", ...) only match a whole
    token, so "Treble" maps to S rather than T.
    """
    name = (part_name or "").strip().lower()
    if not name:
        return None
    for token in re.split(r"[^a-z]+", name):
        if not token:
            continue
        for alias, role in _ALIAS_TOKENS:
            if token == alias or (len(alias) >= 3 and token.startswith(alias)):
                return role
    return None


def _looks_instrumental(name: str) -> bool:
    """True for names that clearly denote an instrument, not a voice."""
    lowered = name.lower()
    return any(
        token in lowered
        for token in ("piano", "organ", "keys", "guitar", "violin", "viola",
                      "cello", "flute", "clarinet", "trumpet", "sax", "harp")
    )


def assign_satb_roles(score: Score, positional_fallback: bool = True) -> None:
    """Mutates score.parts[*].satb_role in place based on best-effort name
    matching. If OCR produced garbled names, the UI should let the user
    manually override the role for each part before annotating.

    positional_fallback: when OCR emits identical generic names (e.g.
    four parts all called "Voice"), assign S/A/T/B by part order instead
    of leaving every role None. Only fires when there are exactly four
    unassigned, non-instrumental parts.
    """
    for part in score.parts:
        part.satb_role = guess_satb_role(part.name)

    if positional_fallback:
        unassigned = [
            p for p in score.parts
            if p.satb_role is None
            and not _looks_instrumental(p.name)
        ]
        if len(unassigned) == 4:
            for part, role in zip(unassigned, SATB_ORDER):
                part.satb_role = role


def annotate_score(
    score: Score,
    mode: str = "movable",
    minor_uses_do: bool = False,
    fixed_chromatic_labels: bool = False,
    avoid_si_clash: bool = False,
) -> None:
    """Walk every part/measure/note and fill in note.solfege, using the
    key signature that is active at that measure (so key changes mid-score
    are handled automatically).
    """
    for part in score.parts:
        for measure in part.measures:
            key = score.key_at_measure(measure.number)
            for note in measure.notes:
                sf.annotate_note(
                    note,
                    key,
                    mode=mode,
                    minor_uses_do=minor_uses_do,
                    fixed_chromatic_labels=fixed_chromatic_labels,
                    avoid_si_clash=avoid_si_clash,
                )
