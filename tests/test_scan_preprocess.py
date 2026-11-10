import io
import hashlib

import pymupdf
from PIL import Image, ImageDraw

from src.studio.scan_preprocess import correction_angle, prepare_for_omr


def staff():
    image = Image.new("L", (820, 610), 255)
    pen = ImageDraw.Draw(image)
    for top in (120, 240, 400):
        for line in range(5):
            pen.line((30, top+line*8, 775, top+line*8), fill=0, width=2)
        for x in range(60, 735, 37):
            pen.ellipse((x, top+12, x+9, top+18), fill=0)
    return image


def test_staff_consensus_and_abstention():
    page = staff()
    for angle in (-3, 2):
        skew = page.rotate(angle, Image.Resampling.BICUBIC, fillcolor=255)
        assert abs(correction_angle(skew) + angle) <= .4
    assert correction_angle(page) == 0
    assert correction_angle(Image.new("L", page.size, 255)) == 0


def test_mixed_pdf_pages_and_selection(tmp_path):
    path = tmp_path / "scan.pdf"
    with pymupdf.open() as doc:
        doc.new_page().insert_text((50, 50), "Digital page")
        img = staff().rotate(2, fillcolor=255)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        page = doc.new_page(width=820,height=610)
        page.insert_image(page.rect,stream=buf.getvalue())
        doc.save(path)
    before = hashlib.sha256(path.read_bytes()).digest()
    assert prepare_for_omr(path, [1]) == path
    derived = prepare_for_omr(path, [2])
    assert derived != path
    with pymupdf.open(derived) as doc:
        assert len(doc) == 2 and "Digital page" in doc[0].get_text()
        pix = doc[1].get_pixmap(colorspace=pymupdf.csGRAY)
        assert correction_angle(Image.frombytes("L",(pix.width,pix.height),pix.samples)) == 0
    assert hashlib.sha256(path.read_bytes()).digest() == before
