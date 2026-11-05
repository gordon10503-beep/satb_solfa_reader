# Portable score-reader foundation

## Current implementation

The browser uses original PDF bytes rendered locally with PDF.js, plus a separate MusicXML document for engraving and timed playback. A selectable comparison layout shows both. Imported names, including extensions, are stored in `sourceFileName` and retained through notation edits. Newly imported PDFs are retained even if recognition fails or Audiveris is unavailable. Recognition completion updates the musical document without replacing annotations.

Pen and highlight strokes are normalized page coordinates (0–1000 per axis), keyed by source page, stored in the score metadata. They remain independent of canvas pixel density and responsive size. Undo mark removes the most recent stroke on the displayed page. These marks are currently stored in the local SQLite library; annotated PDF export and cross-device sync are not implemented.

Playback now uses bundled FluidR3 GM MP3 samples for piano, flute, strings, organ and bells. Attribution is in `static/sounds/LICENSE.txt`. Samples are decoded on demand per instrument and cached for the session. Long notes beyond a sample's recorded tail are not seamlessly looped. The existing oscillator is retained for metronome clicks. Real-device memory, output loudness and iOS audio interruption testing remain necessary.

The optional conductor camera requests rear-facing video, never audio, only after a button press. It displays locally in a draggable floating window, never records or uploads, and stops on close, navigation away, or backgrounding. HTTPS (or localhost) is required. Camera permission, rear-camera selection, Apple Pencil behavior and battery use need testing on physical tablets. Rear-camera preference is not a guarantee on every device.

## Web first, packaging later

Keep browser rendering/audio/annotations separate from the recognition service:

1. Browser client: PDF.js, Pointer Events annotations, Web Audio and responsive score controls.
2. Document service: original PDF, recognized MusicXML, normalized annotations, bookmarks and revisions.
3. Recognition worker: Audiveris/Java receives queued scan jobs and publishes results. Keep recognition off the HTTP request thread and retain the original on every failure.
4. Optional alignment data: source page + normalized rectangle + stable musical location, with provenance and confidence.

The current Python server is loopback-only and is **not a public hosting server**. Before hosting: add account authentication, per-user authorization, upload quotas, isolated recognition workers, a durable queue/job status, object storage, database migrations, backups and HTTPS. Do not simply expose its current port. Recognition uses server CPU/RAM and can take minutes; a static hosting site alone cannot run the current Java scanner.

A PWA is a sensible first distribution target: Safari users can use the website without App Store distribution. Add a manifest, offline app-shell caching and IndexedDB document storage after the authenticated API boundary is in place. Offline reading/annotations can work on previously downloaded documents; first-time recognition still requires a server or desktop companion. No PWA installation or offline synchronization is claimed by this revision.

Future iOS/Android shells can reuse the web UI through Capacitor, with native file, Pencil and lifecycle adapters. Windows/macOS can use a desktop shell and a bundled local recognition worker. This is architectural preparation, not a packaged application or store submission. Capacitor officially targets web/iOS/Android; desktop packaging requires a separate runtime decision.

## PDF playback alignment

PDF display and annotation are straightforward compared with reliable automatic note highlighting. Do not infer coordinates from re-engraved MusicXML: page breaks, spacing, lyrics and voices may change. Extract source-page staff/bar/note coordinates from recognition output, preserve IDs across conversion, and validate mappings against repeated sections and multiple voices. Start with manually adjustable bar rectangles and measure-level highlighting; add note-level tracking only after confidence checks. Until then, original-PDF mode deliberately has no automatic musical playhead or automatic page turns. Digital notation retains its existing highlighting and scrolling.

## References

- PDF.js: https://mozilla.github.io/pdf.js/
- Capacitor targets: https://capacitorjs.com/docs/getting-started/environment-setup
- Sound samples and attribution: https://github.com/gleitz/midi-js-soundfonts

## Known prototype limits

The PDF viewer renders one page at a time for tablet memory use. Recognition job status is currently in process memory and is lost on server restart. A failed import retains a readable PDF but retry UI is not yet available. The annotation overlay is saved in metadata with optimistic revisions; concurrent editing in multiple browser windows must be resolved before re-saving. There is no PDF-to-note alignment, real-time conductor video sharing, annotated PDF export, or iPad hardware certification yet.
