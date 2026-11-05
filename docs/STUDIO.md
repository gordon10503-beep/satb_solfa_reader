# Solfa Studio

Recent additions: sampled FluidR3 instruments; original-PDF and side-by-side comparison modes; saved pen/highlighter overlays; exact imported filenames; and an optional local rear-camera conductor preview. See [platform plan and current limitations](PLATFORM.md). Original PDF viewing is available before recognition completes. Automatic musical highlighting/page following applies only to digital notation until source-coordinate alignment is implemented.

Solfa Studio is the new local browser-based music workspace. The previous Streamlit reader remains available separately.

## Launch

On Windows, double-click **Start Studio.cmd** in the project folder. It installs the two Studio dependencies on first launch and opens http://127.0.0.1:8873. Python must be installed. After installation, notation and synthesized playback work offline.

Manual launch:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-studio.txt
.venv\Scripts\python.exe -m src.studio.server
```

Use `--port 8874` if the default port is occupied, or `--data-dir PATH` for another library location. Close the server with Ctrl+C.

## Read and rehearse

- Import MusicXML, XML or compressed MXL. PDF, PNG, JPEG and TIFF imports run local Audiveris recognition in the background.
- Choose movable-do or fixed-do labels above the staves. Minor keys default to La-based minor; select Minor: Do for Do-based minor.
- Click instrument chips to layer Piano, Flute, Strings, Organ or Bell tones on each part. M mutes and S solos. These are synthesized practice sounds, not sampled orchestral instruments.
- Space starts/pauses playback; the transport provides seek, tempo and master volume. Tempo changes scale the score's internal tempo map proportionally.
- Follow the music scrolls to the current measure. Set my own duration scrolls over the chosen number of seconds. Scroll without sound works independently.
- The metronome uses quarter-note pulses. During playback it follows the tempo map and accents measure starts; standalone it accents every four pulses.
- Use collection + to assign the open score to a named collection. Bookmark saves the current/selected bar; its label opens that bar later.

## Compose

Create SATB, a melody, or a single-staff piano sketch with a key, meter and tempo. Click a pitched note to change pitch, accidental, octave or lyric. To write a bar, choose its part and bar number, open the keyboard, enable Add played keys to the phrase, and choose note lengths. Rest adds a rest. Apply the complete phrase with Replace bar with phrase.

Typed entry also works: `C4/q D4/q E4/h`. Durations: w whole, h half, q quarter, e eighth, s sixteenth; a trailing dot makes a dotted note. `R/q` is a rest and `[C4,E4,G4]/h` is a chord. The phrase must fill the bar. Octaves use MusicXML pitch values; octave clefs affect staff placement, not a second playback transposition.

Simple bar replacement intentionally refuses bars with multiple voices, ties, tuplets or linked notation. Use the advanced MusicXML editor for these cases. Saved XML retains unrelated notation; the engraving copy is disposable. MusicXML export preserves the score, while Print includes displayed sol-fa labels. Changes and metadata have a persistent 50-step Undo history.

## Scan review and accuracy

Audiveris is detected on PATH or in the standard Windows installation folder. Set `AUDIVERIS_CMD` to its executable if needed. Recognition uses save-book then export, retains logs and the original scan, and marks its result unreviewed. Open Check score to view the original and review flagged bars. Recognition is not guaranteed accurate, especially handwriting, low-quality scans, lyrics, part assembly and unusual notation.

Checks include overfull/short bars, duration-versus-note-symbol mismatches, invalid pitches, differing part lengths and missing engraved notes. These checks cannot establish that a pitch matches a printed source. Mark reviewed only after comparison; musical edits reset it.

Playback reads exact source durations, chords, rests, voices, tuplets, transposition, ties, tempo changes, pickups, ordinary repeats and numbered endings. D.C./D.S./coda, nested repeats and expressive timing require manual navigation/review. Grace notes are displayed but omitted from timed playback. Dynamics, pedal and articulations are not yet interpreted by the synthesizer. Verovio supports a subset of MusicXML notation; advanced imports must be checked visually.

This is a working first version, not yet a full desktop engraving suite: no packaged installer, freehand handwriting recognition, grand-staff creation wizard, MIDI-device input, sampled sound library, or complete graphical symbol palette.

## Storage and verification

The library, scans and revision history live under `data/` in the project, excluded from Git. Stop Studio and back up that directory to preserve the library. Original imported files are not overwritten. The server binds only to loopback and checks origin and mutation tokens.

Run `.venv\Scripts\python.exe -m pytest tests -q` and `node --check src/studio/static/app.js`. The suite covers sol-fa, compressed imports, timing, ties, tempo changes, repeats/endings, tuplets, transposition, pitch boundaries, safe edits, persistence, undo, stale revisions and local HTTP access. A real Audiveris image conversion and browser composition/pitch-edit workflows were also exercised during development.

## Implementation

- `src/studio/document.py`: original MusicXML, validation, targeted editing and Verovio engraving.
- `src/studio/playback.py`: source-based timing and repeat expansion.
- `src/studio/server.py`: SQLite library, local HTTP API and background recognition.
- `src/studio/static/`: responsive interface and Web Audio practice tools.

Reference: [Verovio documentation](https://book.verovio.org/) and [MusicXML notation](https://www.w3.org/2021/06/musicxml40/tutorial/notation-basics/). Verovio is installed as a dependency with its bundled fonts; preserve its license notices when distributing an application bundle.

## Focused pages and pitch labels

Studio opens at the Library. Open a score, then choose Read (uncluttered score), Practice (collapsible instruments, scrolling and bookmarks), Compose (bar entry and expandable note editor), or Check score. Under Note labels, choose Note names for scientific pitch spelling such as C4, F♯4 or B♭3. These are the source MusicXML pitches, not concert-pitch conversion for transposing instruments. Turn Labels off for plain notation.

## PDF layouts and scan status

PDF imports default to side-by-side comparison. Both source PDF and recognized notation scroll vertically in Compare view. Original-PDF view has independent selectors for one/two pages per spread and horizontal/vertical scrolling. Pages render lazily near the viewport. These layouts do not imply automatic musical alignment between source and recognition.

The scan panel shows real workflow stages and elapsed time, plus the current Audiveris recognition step where available. Its bar represents completed stages, not estimated runtime percentage. Scans can be rediscovered after a browser refresh while the same server remains running; server restart still loses in-memory job status.
