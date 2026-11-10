"""Recover an omitted opening meter from embedded SMuFL symbols in a PDF."""
from collections import defaultdict
from .document import edit_meter, read_xml


def opening_meter(page):
    import pymupdf
    clefs, signatures, attacks = [], [], []
    for block in page.get_text("rawdict", flags=pymupdf.TEXTFLAGS_RAWDICT & ~pymupdf.TEXT_PRESERVE_IMAGES)["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                if span["font"].split("+")[-1] not in {"Leland", "Bravura"}:
                    continue
                rows = defaultdict(list)
                for char in span["chars"]:
                    value = ord(char["c"])
                    x, y = char["origin"]
                    if value in (0xE050, 0xE05C, 0xE062):
                        clefs.append((x, y, span["size"]))
                    if 0xE0A0 <= value <= 0xE0BF or 0xE4E1 <= value <= 0xE4EF:
                        attacks.append((x, y))
                    if 0xE080 <= value <= 0xE089:
                        rows[round(y, 1)].append((x, str(value - 0xE080)))
                if len(rows) != 2:
                    continue
                upper, lower = (sorted(rows[y]) for y in sorted(rows))
                if max(len(upper), len(lower)) > 2:
                    continue
                beats, unit = (int("".join(d for _, d in row)) for row in (upper, lower))
                if 1 <= beats <= 32 and unit in (1, 2, 4, 8, 16, 32):
                    signatures.append((upper[0][0], min(rows), (beats, unit)))
    if not clefs:
        return None
    left, top, size = min(clefs, key=lambda c: c[1])
    # Only consider the first two adjacent, left-aligned staff starts.
    starts = sorted((c for c in clefs if abs(c[0]-left) < size/2), key=lambda c:c[1])[:2]
    if len(starts) != 2 or starts[1][1]-top > 8*size:
        return None
    votes = []
    for x, y, scale in starts:
        matches = [(sx, meter) for sx, sy, meter in signatures
                   if x < sx < x+4*scale and abs(sy-y) < scale
                   and not any(x < ax < sx and abs(ay-y) < scale for ax, ay in attacks)]
        if len(matches) != 1:
            return None
        votes.append(matches[0])
    if votes[0][1] == votes[1][1] and abs(votes[0][0]-votes[1][0]) < size/4:
        return votes[0][1]
    return None


def recover_opening_meter(output, pdf_data, page_number=1):
    parts = read_xml(output).findall("part")
    first = [part.find("measure") for part in parts]
    if not first or any(m is None or m.find("attributes/time") is not None for m in first):
        return output, None
    import pymupdf
    try:
        with pymupdf.open(stream=pdf_data, filetype="pdf") as pdf:
            meter = opening_meter(pdf[page_number-1])
    except (RuntimeError, ValueError, IndexError):
        return output, None
    if meter is None:
        return output, None
    return edit_meter(output, 0, *meter), meter
