"""Prepare raster score pages for OMR without changing the library original."""
from pathlib import Path
from statistics import median

import numpy as np
from PIL import Image, ImageOps
import pymupdf


def correction_angle(image):
    """Seek horizontal ink projections supported by evenly spaced staff lines."""
    preview = image.convert("L")
    preview.thumbnail((1100, 1500))
    width, height = preview.size
    if width < 200 or height < 70:
        return 0.0
    votes = []
    for left, right in ((.06, .49), (.51, .94)):
        strip = preview.crop((int(left * width), 0, int(right * width), height))
        def score(angle):
            rotated = strip.rotate(angle, Image.Resampling.BILINEAR, fillcolor=255)
            pixels = np.asarray(rotated)
            # Ignore rotated edges. Long, dark horizontal runs give sharp row peaks.
            margin = max(2, strip.width // 12)
            ink = (pixels[:, margin:-margin] < 155).mean(axis=1)
            best = 0.
            for gap in range(3, min(25, height // 8)):
                length = height - 4 * gap
                aligned = np.minimum.reduce([ink[k*gap:k*gap+length] for k in range(5)])
                best = max(best, float(aligned.max()))
            return best
        baseline = score(0)
        angle, quality = max(((a / 2, score(a / 2)) for a in range(-10, 11)), key=lambda pair: pair[1])
        if quality < .24 or quality < baseline + .09 or abs(angle) < .5:
            return 0.
        refined = max((angle + step / 10 for step in range(-3, 4)), key=score)
        votes.append(refined)
    return median(votes) if abs(votes[0]-votes[1]) <= .4 else 0.


def corrected_image(image):
    angle = correction_angle(image)
    if not angle:
        return None
    return image.convert("RGB").rotate(angle, Image.Resampling.BICUBIC, expand=True, fillcolor="white")


def prepare_for_omr(source, pages=()):
    """Return a derived PDF only when at least one selected page needs correction."""
    import io
    source = Path(source)
    selected = {int(page) for page in pages}
    target = source.with_name("prepared.pdf")
    changed = False
    with pymupdf.open() as output:
        def append_image(image, width, height):
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            page = output.new_page(width=width, height=height)
            page.insert_image(page.rect, stream=buffer.getvalue())

        if source.suffix.lower() == ".pdf":
            with pymupdf.open(source) as document:
                pending = 0
                for index, page in enumerate(document):
                    corrected = None
                    if not selected or index+1 in selected:
                        images = page.get_image_info()
                        area = page.rect.get_area()
                        # Scanned PDFs can have an invisible OCR text layer.
                        # Only process pages dominated by an embedded raster.
                        if area and any(pymupdf.Rect(i["bbox"]).get_area() >= .8*area for i in images):
                            scale = min(300/72, 4200/max(page.rect.width, page.rect.height))
                            preview = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), colorspace=pymupdf.csGRAY, alpha=False)
                            corrected = corrected_image(Image.frombytes("L", (preview.width, preview.height), preview.samples))
                    if corrected is not None:
                        if pending < index:
                            output.insert_pdf(document, from_page=pending, to_page=index-1)
                        append_image(corrected, corrected.width/scale, corrected.height/scale)
                        pending = index + 1
                        changed = True
                if changed and pending < len(document):
                    output.insert_pdf(document, from_page=pending, to_page=len(document)-1)
        else:
            with Image.open(source) as original:
                for index in range(getattr(original, "n_frames", 1)):
                    original.seek(index)
                    image = ImageOps.exif_transpose(original)
                    oriented = original.getexif().get(274, 1) != 1
                    corrected = corrected_image(image) if not selected or index+1 in selected else None
                    changed |= corrected is not None or oriented
                    if not changed and getattr(original, "n_frames", 1) == 1:
                        return source
                    result = corrected if corrected is not None else image
                    dpi = original.info.get("dpi", (300,300))[0]
                    dpi = dpi if 72 <= dpi <= 1200 else 300
                    append_image(result.convert("RGB"), result.width*72/dpi, result.height*72/dpi)
        if changed:
            output.save(target)
            return target
    return source
