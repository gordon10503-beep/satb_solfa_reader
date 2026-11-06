# First-page layout trial — 2026-11-06

Source: the user's 14-page choir PDF, page 1 only. The original library score was not changed. Audiveris ran in a separate trial library under ignored `build/layout-trial/`.

| Input | Detected parts | Bars per part | Parsed note/rest elements | Structural warnings |
|---|---:|---|---:|---:|
| Original first page | 9 | 6 each | 116 | 28 |
| First complete system crop | 5 | 3 each | 59 | 20 |
| Second complete system crop | 5 | 3 each | 43 | 8 |

Visual source inspection shows five parts and two systems of three bars. Cropping fixed the duplicated-part structure on this page. The second system retained generic Voice names and Pno.; persistent instrument identity still needs to be carried from the first system. Note/rest totals are not accuracy scores, and differ partly because duplicated parts contain extra rests. No note-level ground-truth accuracy was calculated. Meter/rhythm recognition still has failures. The two crops took more total processing time than the single page.

This was an assistant-guided layout trial, not an API benchmark of GPT-5.4 mini. Crops were inspected from the rendered source and made at 300 DPI, preserving all six staves and the lyrics. Neither crop was merged into the main score. Separate cropped recognition must carry inherited clef/key/meter and part IDs before it is safe for automatic reassembly.

Local artifacts: `build/layout-trial/baseline.pdf`, `system-1.pdf`, `system-2.pdf`, `results.json`, and saved Audiveris books/logs under `scans/`. These private score artifacts are excluded from Git.
