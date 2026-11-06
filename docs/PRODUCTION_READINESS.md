# Production-readiness work using MuseScore as a workflow reference

Reference workflows: [note input](https://handbook.musescore.org/basics/entering-notes-and-rests), [palettes](https://musescore.org/en/handbook/4/using-palettes), and [instrument layout](https://handbook.musescore.org/notation/instruments-staves-and-systems/instruments-and-system-markings).

Studio remains a prototype. These are acceptance criteria, not implemented-feature claims:

1. Selection-based editing: separate note/rest selection, input mode and properties; show the target part, staff, voice and bar. Symbol palettes must apply only to valid selected objects, with undo for every edit.
2. Instrument layout: an ordered instrument list with add/remove/reorder, staff grouping and transposition. Distinguish parts from staves and voices; support hidden empty orchestral staves without changing identity.
3. Recognition review: page/system/bar overlays, editable grouping, preserved PDF coordinates and explicit unresolved regions. Never infer score accuracy from warning count alone.
4. Editing fidelity: round-trip fixtures covering multiple voices, ties, slurs, tuplets, repeats, lyrics, percussion and transposition. Unsupported edits must explain the limitation and preserve original XML.
5. Reliability: persistence/undo recovery, interrupted-scan handling, build-version visibility, large-score responsiveness, keyboard accessibility and real tablet/touch validation.
6. Release criteria: representative verified score corpus, end-to-end editing/playback tests, performance budgets, packaging/update strategy, dependency-license audit and platform-specific tests. No production-ready label until these gates are met.

Current increment: clickable scan ensemble cards with guarded staff grouping; launch avoids silently reusing an outdated backend; a controlled full-page versus system-crop recognition trial. Full interactive layout editing and the broader notation palette remain unimplemented.
