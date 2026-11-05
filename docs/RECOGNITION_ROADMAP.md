# Recognition improvement roadmap

## Implemented

The backend is still Audiveris. Selectable music pages and an explicit SATB + piano assembly preset help prevent cover-page input and split logical voices. Meter, part-count, bar-length and rendering checks expose failures; they do not improve notehead classification. No custom model has been trained and no accuracy gain has been measured on a held-out collection.

## Proposed layout assistance (not implemented)

Use a vision model as an optional layout adviser, combined with deterministic image geometry:

1. Rasterize each PDF page without changing the source PDF.
2. Detect staff lines, full systems, braces, part labels and lyric regions. Retain all simultaneous staves (SATB plus piano) in each system.
3. Propose barline coordinates across the system; distinguish barlines from stems using staff-span geometry and agreement across staves. Show editable boxes over the original PDF.
4. Validate bounds, reading order, overlaps and coverage. Retain page/system/part/bar IDs and original PDF coordinates.
5. First test full-system crops with the existing backend. For bar-level retries, carry clefs, key, meter, part identity and neighboring tie/slur context; arbitrary isolated crops are not a drop-in improvement for Audiveris.
6. Reassemble recognized fragments using explicit IDs and verify rhythm totals and simultaneous bar alignment. Keep uncertain regions visible for manual correction.

Preserve lyrics on the original PDF and maintain a separate text/lyric layer. Never erase text from the user's source or regenerate the score image with an LLM. Crop recognition should remain an experiment until measured against full-page recognition.

A model prompt or skill can orchestrate this workflow, but does not itself improve the backend or guarantee accurate crop coordinates. Remote-model use would require an explicit provider integration and user choice about uploading pages. Local processing should remain available.

## Alternatives and evaluation

- homr: https://github.com/liebharc/homr
- Oemer: https://github.com/BreezeWhite/oemer
- Full-page Sheet Music Transformer research: https://arxiv.org/abs/2405.12105
- Audiveris measure-stack data: https://github.com/Audiveris/audiveris/wiki/sheet%23N-xml

Benchmark candidates on the same permission-cleared choir pages with manually verified MusicXML and page coordinates. Measure bar/staff grouping, missing/extra notes, pitch, duration, lyric association and manual repair time separately. Piano benchmarks alone do not establish SATB + Chinese/Jyutping lyric accuracy.

Fine-tuning a pretrained layout or recognition model may help with this repertoire once enough verified examples exist. Start with layout and part association; compare on held-out entire scores/publishers, not random crops from training scores. User corrections can become training examples only after verification and explicit dataset opt-in. Automatically training on unverified scans risks reinforcing their mistakes. Training from scratch is not the first recommended experiment.

## Reusable assistant skill

`skills/score-layout-preflight/SKILL.md` now supplies an assistant-driven layout workflow for arbitrary ensembles, including orchestral systems. Its local PyMuPDF helper renders page images, validates a model-proposed layout manifest, produces review overlays, and exports visually checked complete-system crops with source coordinates. Invoke it as `$score-layout-preflight` in a compatible assistant after installing that folder in its skills directory.

This is not yet an automatic Studio scanner option. No API client or paid model call is included, and recognition accuracy has not been benchmarked. Geometry/helper checks pass; arbitrary ensemble presets, interactive box editing in Studio, staff-group crop reassembly and PDF playback mapping remain future application work. The dated model recommendation and assumed-token cost calculation live in the skill's references/model-notes.md.
