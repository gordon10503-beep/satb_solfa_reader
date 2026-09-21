"""
OCR / OMR (Optical Music Recognition) pipeline.

OCR (text) is not enough for a music score -- we need OMR to recognise
noteheads, staves, clefs, key/time signatures, etc. There is no
lightweight pure-Python OMR engine that runs fully offline out of the box,
so this module defines a pluggable backend interface and two concrete
adapters you can install later:

  1. AudiverisBackend  - Audiveris (https://github.com/Audiveris/audiveris)
     Free, open-source, Java-based OMR. Best accuracy for printed/engraved
     scores like the Finale-exported PDFs in assets/scores/. Runs as a
     CLI: `audiveris -batch -export -output <dir> <input.pdf>` producing
     MusicXML.

  2. OemerBackend - `pip install oemer` (https://github.com/BreezeWhite/oemer)
     Pure Python + deep learning OMR, no Java required, but needs to
     download model weights on first run (needs internet once).

Both backends output MusicXML, which core/musicxml_loader.py then parses
into our Score model. This module does NOT call any network/OMR engine
right now (this dev sandbox has no internet/Java) -- wire up whichever
backend is available in your actual dev machine / CI, and keep this
interface stable so core/ never needs to change.
"""
from __future__ import annotations
import subprocess
import shutil
from abc import ABC, abstractmethod
from pathlib import Path


class OMRBackend(ABC):
    name: str = "base"

    @abstractmethod
    def is_available(self) -> bool:
        ...

    @abstractmethod
    def convert(self, pdf_path: str, output_dir: str) -> str:
        """Convert a PDF score to MusicXML. Returns the output .xml/.musicxml path."""
        ...


class AudiverisBackend(OMRBackend):
    """Audiveris 5.x OMR backend using the two-phase (book round-trip) flow.

    Why two phases? Audiveris 5.11's inline transcription+export (single
    `audiveris -batch -export file.pdf` run) has a PartwiseBuilder bug:
    when a page contains hairpins/wedges with unresolved time offsets it
    throws a NullPointerException mid-export and the part assembly gets
    shredded (observed: a 5-part score exported as 17 garbled parts).

    Phase 1 transcribes the PDF and SAVES the .omr book (-save). Phase 2
    re-opens the saved book and re-exports from the persisted, already
    transcribed data (no OMR re-run). The book round-trip re-assembles
    parts cleanly, so the export survives the same NPEs (they are logged
    as non-fatal warnings) with an intact part structure.

    Verify any output before trusting it: part count, part names, and a
    few known notes against the printed score.
    """

    def __init__(self, audiveris_cmd: str = "audiveris"):
        self.audiveris_cmd = audiveris_cmd

    def is_available(self) -> bool:
        return shutil.which(self.audiveris_cmd) is not None

    def convert(self, pdf_path: str, output_dir: str) -> str:
        """Convert a PDF score to MusicXML via the two-phase flow.

        Returns the path of the exported .mxl (falling back to .xml).
        """
        pdf_path = Path(pdf_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        stem = pdf_path.stem
        book_path = output_dir / f"{stem}.omr"

        # Phase 1: transcribe + save the .omr book (no inline export).
        cmd1 = [self.audiveris_cmd, "-batch", "-save",
                "-output", str(output_dir), str(pdf_path)]
        subprocess.run(cmd1, check=True)

        # Phase 2: re-open the saved book and re-export MusicXML from it.
        # NOTE: for a book-based input Audiveris ignores -output and writes
        # the .mxl next to the book, i.e. into output_dir itself.
        #
        # Known quirk: when the PDF has non-music pages (cover, blank or
        # text-only pages), Audiveris REMOVES those sheets during
        # transcription, and a first export of the freshly-saved book then
        # aborts with "Could not export since transcription did not
        # complete successfully" (exit 1) because those invalid stubs are
        # only resolved DURING that export attempt. The book is re-stored
        # with the stubs resolved, so a second export succeeds. Hence the
        # retry below.
        cmd2 = [self.audiveris_cmd, "-batch", "-export", str(book_path)]
        # Remove stale exports from previous runs so the retry loop only
        # ever returns a file produced by THIS call.
        for name in (f"{stem}.mxl", f"{stem}.xml"):
            stale = output_dir / name
            if stale.exists():
                stale.unlink()
        candidate = None
        last_rc = None
        for _attempt in (1, 2):
            proc = subprocess.run(cmd2, check=False)
            last_rc = proc.returncode
            candidate = self._find_export(output_dir, stem)
            if candidate is not None:
                return candidate
        raise FileNotFoundError(
            f"Audiveris export failed after 2 attempts (last exit code "
            f"{last_rc}); no .mxl/.xml produced in {output_dir}"
        )

    @staticmethod
    def _find_export(output_dir: Path, stem: str):
        for name in (f"{stem}.mxl", f"{stem}.xml"):
            candidate = output_dir / name
            if candidate.exists():
                return str(candidate)
        return None


class OemerBackend(OMRBackend):
    name = "oemer"

    def is_available(self) -> bool:
        try:
            import oemer  # noqa: F401
            return True
        except ImportError:
            return False

    def convert(self, pdf_path: str, output_dir: str) -> str:
        # oemer works on images (png/jpg), not multi-page PDFs directly.
        # Typical flow: render each PDF page to PNG (see split_pdf_to_images
        # below), run oemer per page, then stitch/merge per movement.
        # Left as an integration task -- see docs/ROADMAP.md.
        raise NotImplementedError(
            "OemerBackend.convert: render PDF pages to PNG first (pdf2image), "
            "then call oemer's `python -m oemer <page.png>` per page and merge."
        )


def split_pdf_to_images(pdf_path: str, output_dir: str, dpi: int = 300) -> list:
    """Utility used ahead of image-based OMR backends (e.g. oemer)."""
    from pdf2image import convert_from_path
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    pages = convert_from_path(pdf_path, dpi=dpi)
    paths = []
    for i, page in enumerate(pages, start=1):
        out = str(Path(output_dir) / f"page_{i:02d}.png")
        page.save(out, "PNG")
        paths.append(out)
    return paths


def get_backend(preferred: str = "audiveris") -> OMRBackend:
    backends = {"audiveris": AudiverisBackend(), "oemer": OemerBackend()}
    chosen = backends.get(preferred)
    if chosen and chosen.is_available():
        return chosen
    for b in backends.values():
        if b.is_available():
            return b
    raise RuntimeError(
        "No OMR backend available. Install Audiveris (Java) or `pip install "
        "oemer`, see src/ocr/omr_pipeline.py docstring."
    )
