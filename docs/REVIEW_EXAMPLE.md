# Reviewing 我們都(可以)是天使_粤语粤拼版.pdf

This diagnosis uses the PDF and recognized XML from the local library. The source has 14 pages.

## Fix structure before notes

PDF page 1 shows five parts: Soprano, Alto, Tenor, Bass, and a two-staff Piano. The initial scan created nine parts, splitting full names and abbreviations into different voices. Its opening attributes contain no time signature, so Studio assumes 4/4. The printed opening is 12/8, changing to 6/8 at bar 4 and back to 12/8 at bar 5.

Those failures produce many misleading rhythm warnings. An overfull-bar warning does not necessarily mean a note should be deleted. For example, six quarter-note beats are correct in 12/8, but are reported as overfull if the missing meter is assumed to be 4/4.

## A separate partial repair is in the library

The copy ending **(partial repair)** was made from a separate copy of the saved Audiveris book. All 24 detected systems have the expected staff configuration (1,1,1,1,2). Their logical voice assignments were consolidated and re-exported as five parts. Only the verified 12/8 markings at bar positions 1 and 5 were added to this draft. The original import and original PDF remain available.

This repair is incomplete. Parts still have different bar counts and notes are missing. More accurate meter information can reveal additional short bars, so the warning total is not an accuracy score. Do not use this draft as a reliable rehearsal track yet.

## Controls to use

1. Open the partial repair, select Check score, and keep Compare selected. Original page 1 and recognized notation now start at a common panel baseline.
2. Verify part count and opening meter before inspecting a note. The review guide explains that order.
3. For a missing/wrong meter, expand Correct a time signature. Choose the bar position and numerator/denominator, then Apply meter to all parts. This changes meter context only; it does not invent notes or change durations. Undo in Compose restores the previous document.
4. For a wrong pitch, click the recognized note, change its note/accidental/octave, then Apply note change. Verify against the same source bar.
5. For a simple single-voice bar with missing/wrong rhythms, use the visual bar composer. It replaces the complete bar's notes and lyrics. Linked notation, multiple voices, ties and tuplets need a richer editor such as Audiveris; Studio refuses simple replacement in these cases.

For this particular failed import, finishing the structural/rhythm repairs in Audiveris and re-importing its MusicXML is more practical than changing hundreds of individual warnings. The saved project is under `data/scans/02f2a959757443129893193ebfcafdc4/scan.omr`; keep an untouched copy. The experimental repaired book is under `build/accuracy-review/choir-repaired.omr`.

## Future rescans

Check score now has Rescan with options. For this PDF, select SATB + piano; all pages contain music. The preset refuses systems that do not have four single-staff voices plus two-staff piano, rather than guessing. Page selection is available for other PDFs with covers/text pages. This addresses part assembly, not every notehead, time signature, or lyric-recognition error.

## Opening bars and draft highlighting

Malformed, overlapping/unclosed repeat-ending spans in this scan caused the engraving conversion to drop the opening bars even though playback retained them. Studio now suppresses those broken brackets in the disposable rendering copy and reports a review issue. Saved MusicXML is unchanged. Both sample versions were checked: all 15 opening pitched notes now have rendered IDs.

When parts have different bar-number sequences, the display uses sequential bar positions to match the existing editor/playback. This is explicitly provisional: it does not restore missing bars or establish correct musical alignment across parts. A yellow bar marker and blue playing notes work on unreviewed scores, including Compare mode; the transport shows the current bar position. PDF-coordinate highlighting remains future work.
