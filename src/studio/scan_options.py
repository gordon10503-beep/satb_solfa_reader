"""Explicit recognition settings and conservative SATB book assembly."""
import re
import shutil
import zipfile
from xml.etree import ElementTree as ET


def selected_pages(value):
    value = str(value or "").strip()
    if not value:
        return []
    if not re.fullmatch(r"\d+(?:-\d+)?(?:\s*,\s*\d+(?:-\d+)?)*", value):
        raise ValueError("Use page numbers such as 1-4, 6. Leave blank for all pages.")
    pages = set()
    for token in value.split(","):
        bounds = [int(x) for x in token.strip().split("-")]
        start, end = bounds[0], bounds[-1]
        if start < 1 or end < start or end > 10000:
            raise ValueError("Page ranges must be increasing, between 1 and 10000.")
        pages.update(range(start, end + 1))
    return [str(p) for p in sorted(pages)]


def repair_satb_book(path):
    """Only for an explicitly selected five-part SATB + piano layout.

    Refuse mismatched systems rather than deleting or guessing voice content.
    Keep the untouched OMR book for investigation.
    """
    with zipfile.ZipFile(path) as source:
        root = ET.fromstring(source.read("book.xml"))
        systems = root.findall("sheet/page/system")
        if not systems or any([len(p.findall("staff-configuration")) for p in s.findall("part")] != [1,1,1,1,2] for s in systems):
            raise ValueError("SATB + piano preset needs four single-staff voices and one two-staff piano in every system. Retry Automatic, or correct staff grouping in Audiveris.")
        for system in systems:
            for i, part in enumerate(system.findall("part")):
                part.set("logical-id", str(i+1))
        scores = root.findall("score")
        if len(scores) != 1:
            raise ValueError("The SATB preset currently supports a single movement. Use Automatic for this book.")
        score = scores[0]
        for part in score.findall("logical-part"): score.remove(part)
        for i,name in enumerate(("Soprano", "Alto", "Tenor", "Bass", "Piano")):
            count = 2 if i == 4 else 1
            part = ET.Element("logical-part", {"id": str(i+1), "staff-count": str(count), "name": name})
            for _ in range(count): ET.SubElement(part, "staff-configuration", {"line-count": "5"})
            score.insert(i,part)
        temporary = path.with_suffix(".tmp")
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as output:
            for entry in source.infolist():
                output.writestr(entry, ET.tostring(root, encoding="utf-8", xml_declaration=True) if entry.filename == "book.xml" else source.read(entry.filename))
    shutil.copy2(path, path.with_suffix(".original.omr"))
    temporary.replace(path)
