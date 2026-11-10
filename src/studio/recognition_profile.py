"""Choose Audiveris recognition settings from notation visible in the input."""
from collections import Counter

import pymupdf


def mixed_note_sizes(sizes):
    """Require repeated evidence of two note sizes within one staff-sized band."""
    if not sizes:
        return False
    normal, count = sizes.most_common(1)[0]
    return count >= 6 and sum(n for size, n in sizes.items()
                              if .55 * normal <= size <= .82 * normal) >= 3


def pdf_has_small_heads(data, pages):
    # Only use fonts whose private-use characters are known SMuFL noteheads.
    with pymupdf.open(stream=data, filetype="pdf") as pdf:
        for number in pages or range(1, len(pdf) + 1):
            page = pdf[int(number)-1]
            bands = {}
            for block in page.get_text("dict", flags=pymupdf.TEXTFLAGS_DICT & ~pymupdf.TEXT_PRESERVE_IMAGES)["blocks"]:
                for line in block.get("lines", []):
                    for span in line["spans"]:
                        if span["font"].split("+")[-1] not in ("Leland", "Bravura"):
                            continue
                        count = sum(0xE0A2 <= ord(ch) <= 0xE0A4 for ch in span["text"])
                        if count:
                            y = span["origin"][1]
                            # Overlap windows to avoid a hard cut through a staff.
                            for offset in (0, 12):
                                band = (offset, int((y+offset)//24))
                                bands.setdefault(band, Counter())[round(span["size"], 1)] += count
            if any(mixed_note_sizes(sizes) for sizes in bands.values()):
                return True
    return False


def recognition_flags(mode, data, ext, pages):
    if mode == "auto":
        try:
            enabled = ext == ".pdf" and pdf_has_small_heads(data, pages)
        except (ValueError, RuntimeError, IndexError):
            enabled = False
    else:
        enabled = mode == "on"
    if enabled:
        return ["-constant", "org.audiveris.omr.sheet.ProcessingSwitches.smallHeads=true"]
    if mode == "off":
        return ["-constant", "org.audiveris.omr.sheet.ProcessingSwitches.smallHeads=false"]
    return []
