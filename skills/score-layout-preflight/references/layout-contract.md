# Layout manifest v1

Coordinates are normalized to 0–1000 in the displayed PDF page after its stored page rotation, origin top-left; boxes are `[left, top, right, bottom]`. Use `page.rect` width/height to map to PDF coordinates. Do not add a further rotation or deskew without an explicit inverse transform. `prepare` supplies the SHA-256 hash. IDs are unique across the document; page numbers are original and 1-based. An absent bar number is null, not a guessed sequence.

```json
{
  "version": 1,
  "source_sha256": "COPY THE HASH FROM source.json",
  "pages": [
    {
      "page": 1,
      "classification": "music",
      "systems": [
        {
          "id": "p1-s1",
          "box": [60, 180, 950, 830],
          "geometry_reviewed": false,
          "parts": [
            {"id": "soprano", "label": "Soprano", "staff_count": 1},
            {"id": "piano", "label": "Piano", "staff_count": 2}
          ],
          "bar_boundaries": [160, 420, 690, 945],
          "printed_bar_numbers": [null, null, null],
          "lyric_regions": [[170, 290, 940, 340]],
          "context": "Opening clefs and key included; meter unclear.",
          "uncertainties": ["Check the second boundary against the piano staff."]
        }
      ]
    }
  ]
}
```

This is a format illustration, not a score template: replace all geometry and part assignments with observed data. Bar boundaries are x coordinates in page space, including left/right edges of the measured music span (not necessarily the system box, which includes labels). Their intervals span all simultaneous staves. Use an empty list if unresolved. `printed_bar_numbers` has one entry per interval when boundaries exist. Page classification is `music`, `nonmusic`, or `uncertain`. Empty systems on nonmusic/uncertain pages are allowed; record unresolved context in a `notes` string. Partial page lists mean only those pages were inspected, not that other pages contain no music.

Required output evidence: source identity, inspected page range, visible overlay, unresolved regions, and whether full-page-versus-crop recognition was actually compared. A geometry-reviewed system can still contain uncertain internal bar boundaries; those boundaries must not be treated as verified PDF playhead positions.
