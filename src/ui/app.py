"""
Streamlit UI: SATB So-Fa Score Reader (draft)

Run with:
    streamlit run src/ui/app.py

Features implemented in this draft:
  - Upload a MusicXML (.xml/.musicxml/.mxl) file (output of the OMR step,
    or a hand-made test file) -- see src/ocr/omr_pipeline.py for turning a
    PDF scan into MusicXML first.
  - Per-part ON/OFF toggle buttons for Soprano / Alto / Tenor / Bass.
  - A switch for Movable-do (首調) vs Fixed-do (固定調).
  - Extra switches: Do-based minor solfa, avoid-Si-clash spelling.
  - A text/HTML preview of the annotated score (interim renderer -- see
    docs/ROADMAP.md for the planned staff-image overlay renderer).

This is a draft scaffold: wire in real score-image rendering and the OMR
pipeline call next (see docs/ROADMAP.md).
"""
import sys
import tempfile
from pathlib import Path

# Make src/ importable when run directly via `streamlit run`.
SRC_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SRC_ROOT.parent))

import streamlit as st

from src.core.musicxml_loader import load_musicxml
from src.core.key_tracker import assign_satb_roles, annotate_score
from src.render.text_renderer import render_html, render_text

st.set_page_config(page_title="SATB So-Fa Score Reader", layout="wide")
st.title("🎼 SATB So-Fa Score Reader (draft)")

with st.sidebar:
    st.header("1. Load score")
    uploaded = st.file_uploader(
        "MusicXML file (.xml / .musicxml / .mxl)",
        type=["xml", "musicxml", "mxl"],
        help="For a scanned PDF, run the OMR pipeline first (src/ocr/omr_pipeline.py) "
             "to produce MusicXML, then upload it here.",
    )

    st.header("2. So-fa style")
    mode = st.radio(
        "Solfa system",
        options=["movable", "fixed"],
        format_func=lambda m: "Movable-do 首調" if m == "movable" else "Fixed-do 固定調",
    )
    minor_uses_do = False
    avoid_si_clash = False
    fixed_chromatic = False
    if mode == "movable":
        minor_uses_do = st.checkbox(
            "Minor key: anchor Do at tonic (Do-based minor)",
            value=False,
            help="Untick (default) for La-based minor: the minor tonic sings "
                 "'La', the HK/TW convention. Tick for Do-based minor: the "
                 "minor tonic sings 'Do'.",
        )
        avoid_si_clash = st.checkbox("Use 'Se' instead of 'Si' for raised 5th (avoid fixed-do clash)", value=False)
    else:
        fixed_chromatic = st.checkbox("Show sharp/flat detail (e.g. Do#/Reb)", value=False)

    st.header("3. Parts to display")
    show_s = st.toggle("Soprano (S)", value=True)
    show_a = st.toggle("Alto (A)", value=True)
    show_t = st.toggle("Tenor (T)", value=True)
    show_b = st.toggle("Bass (B)", value=True)

visible_roles = set()
if show_s:
    visible_roles.add("S")
if show_a:
    visible_roles.add("A")
if show_t:
    visible_roles.add("T")
if show_b:
    visible_roles.add("B")

if uploaded is None:
    st.info(
        "Upload a MusicXML file to begin. Test files: "
        "`tests/sample_data/satb_sample_with_key_change.musicxml`."
    )
    st.stop()

tmp_path = Path(tempfile.gettempdir()) / uploaded.name
tmp_path.write_bytes(uploaded.getvalue())

score = load_musicxml(str(tmp_path))
assign_satb_roles(score)
annotate_score(
    score,
    mode=mode,
    minor_uses_do=minor_uses_do,
    fixed_chromatic_labels=fixed_chromatic,
    avoid_si_clash=avoid_si_clash,
)

unassigned = [p.name for p in score.parts if p.satb_role is None]
if unassigned:
    st.warning(
        f"Could not auto-detect SATB role for parts: {unassigned}. "
        "Rename them in the source MusicXML (e.g. 'Soprano', 'Alto', 'Tenor', 'Bass') "
        "or extend PART_NAME_ALIASES in src/core/score_model.py."
    )

st.subheader(f"Preview: {score.title}")
st.components.v1.html(render_html(score, visible_roles=visible_roles), height=600, scrolling=True)

with st.expander("Plain-text view"):
    st.code(render_text(score, visible_roles=visible_roles))

with st.expander("Detected key signatures"):
    for ks in score.key_signatures:
        st.write(f"Measure {ks.measure_number}: {ks.fifths:+d} fifths, mode={ks.mode}")
