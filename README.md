# Solfa Studio

A local, browser-based music workspace for reading, checking, composing and rehearsing scores. Solfa Studio combines editable MusicXML notation with the original imported PDF, so lyrics and markings remain visible while you review recognition.

## Get started

On Windows, install Python and double-click **Start Studio.cmd**. The launcher creates a virtual environment, installs the Studio dependencies and opens the local workspace at `http://127.0.0.1:8873`.

To install and run manually from PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-studio.txt
.venv\Scripts\python.exe -m src.studio.server
```

Use `--port 8874` to choose another port or `--data-dir PATH` to use another library. MusicXML reading and playback work locally. PDF and image recognition additionally require [Audiveris](https://github.com/Audiveris/audiveris) installed and available on PATH, or configured using `AUDIVERIS_CMD`.

## Features

- **Read:** import MusicXML/MXL and scanned PDFs or images; show movable-do, fixed-do or note names such as C4 above the digital notation. View the original PDF alongside the recognition, with one- or two-page layouts and selectable scrolling direction.
- **Practice:** play individual parts with layered sampled Piano, Flute, Strings, Organ or Bell sounds; adjust mix, tempo and volume; follow the current digital bar; use the metronome and scrollable keyboard.
- **Compose:** start a score, enter notes with the visual composer, and edit supported notes and bars. Advanced MusicXML editing and export are also available.
- **Check score:** compare the original and recognized notation, inspect structural warnings, and mark a score reviewed. Original PDFs retain their filenames and support saved pen and highlighter annotations.
- **Organize:** group scores into collections, bookmark bars, and use the score menu or right-click to rename, duplicate, export, share, or move scores to trash.
- **Conductor preview:** optionally show a local camera window during practice.

## Scanning and accuracy

Recognition is a draft: check parts, bar alignment, time signatures, notes, rhythms and lyrics against the original before relying on playback. Select music pages to skip covers. The optional SATB + piano preset consolidates compatible part assignments; use Automatic for other layouts. Structural checks flag possible problems but cannot establish that every note is correct. Playback highlighting currently applies to the **digital notation**, not to matching locations on the original PDF.

The optional [`score-layout-preflight` skill](skills/score-layout-preflight/SKILL.md) helps an assistant map systems and parts, review proposed boundaries and export checked system crops. It supports arbitrary ensembles, including orchestral layouts. It is not connected to the Studio Scan button, and its effect on recognition accuracy has not yet been benchmarked. See the [recognition roadmap](docs/RECOGNITION_ROADMAP.md).

## Local data and limitations

Scores, original imports, annotations and history are stored under `data/`, which is excluded from Git. Back up that directory to preserve your library. The server listens on the local computer; this prototype is not yet a hosted service or packaged iOS/Android app. Some complex notation, repeat navigation and expressive playback require manual review. See the [Studio guide](docs/STUDIO.md) and [platform plan](docs/PLATFORM.md) for details.

## Tests and project structure

```powershell
.venv\Scripts\python.exe -m pytest tests -q
node tests/test_sampled_audio.cjs
```

- `src/studio/` — local server, library, notation, playback and interface
- `src/core/` — solfège and MusicXML logic
- `skills/score-layout-preflight/` — optional layout-assistance skill
- `tests/` — notation, timing, persistence and audio-loading checks
- `src/ui/` and `src/ocr/` — earlier Streamlit reader and OMR adapters

The earlier Streamlit prototype remains available separately; see [QUICKSTART.md](QUICKSTART.md). Bundled audio and PDF viewer components retain their license notices in `src/studio/static/`.
