"""
Text-based score renderer (interim, dependency-free preview).

Until a real graphical score renderer is wired in (e.g. music21 + Lilypond,
or a MusicXML.js web viewer), this module produces a readable text/HTML
layout of the solfege annotations, organised by measure, so you can sanity
-check OMR + solfege output immediately without extra installs.

Real score-image rendering with overlayed solfege text is tracked in
docs/ROADMAP.md ("Score image overlay renderer").
"""
from __future__ import annotations
from typing import Iterable, Set, Optional
from ..core.score_model import Score


def render_text(score: Score, visible_roles: Optional[Set[str]] = None) -> str:
    """Return a plain-text grid: rows = SATB parts, columns = measures."""
    lines = [f"Score: {score.title}", ""]
    for part in score.parts:
        if visible_roles is not None and part.satb_role not in visible_roles:
            continue
        role_label = part.satb_role or "?"
        lines.append(f"=== {part.name} [{role_label}] ===")
        for measure in part.measures:
            key = score.key_at_measure(measure.number)
            syllables = [
                n.solfege or ("rest" if n.is_rest else "?")
                for n in measure.notes
            ]
            pitches = [
                ("rest" if n.is_rest else
                 f"{n.step}{'#' * max(n.alter, 0)}{'b' * max(-n.alter, 0)}{n.octave}")
                for n in measure.notes
            ]
            key_tag = f"(key: {key.fifths:+d} fifths, {key.mode})" if measure.key else ""
            lines.append(f"  m{measure.number:>3} {key_tag}: {' '.join(syllables)}")
            lines.append(f"        pitches: {' '.join(pitches)}")
        lines.append("")
    return "\n".join(lines)


def render_html(score: Score, visible_roles: Optional[Set[str]] = None) -> str:
    """Return a minimal standalone HTML page with the same info as
    render_text, styled as a simple table -- handy for the Streamlit UI's
    'preview' pane before real staff rendering is implemented.
    """
    rows = []
    for part in score.parts:
        if visible_roles is not None and part.satb_role not in visible_roles:
            continue
        role_label = part.satb_role or "?"
        cells = []
        for measure in part.measures:
            syllables = [n.solfege or ("·" if n.is_rest else "?") for n in measure.notes]
            pitches = [
                ("rest" if n.is_rest else f"{n.step}{'#' * max(n.alter, 0)}{'b' * max(-n.alter, 0)}{n.octave}")
                for n in measure.notes
            ]
            cells.append(
                f"<td><div class='m'>m{measure.number}</div>"
                f"{' '.join(syllables)}<br><span class='p'>{' '.join(pitches)}</span></td>"
            )
        rows.append(f"<tr><th>{part.name}<br>[{role_label}]</th>{''.join(cells)}</tr>")

    html = f"""<!doctype html>
<html><head><meta charset='utf-8'>
<style>
  body {{ font-family: sans-serif; }}
  table {{ border-collapse: collapse; }}
  td, th {{ border: 1px solid #ccc; padding: 6px 10px; text-align: center; vertical-align: top; }}
  .m {{ font-size: 10px; color: #888; }}
  .p {{ font-size: 11px; color: #4a7fb5; }}
</style></head><body>
<h2>{score.title}</h2>
<table>{''.join(rows)}</table>
</body></html>"""
    return html
