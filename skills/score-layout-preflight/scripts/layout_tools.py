"""Local PDF preparation, layout validation and reviewed system export.

Requires PyMuPDF. No network/model calls. Outputs go to a new directory.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path


def box(value):
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError('Box must contain four coordinates')
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in value):
        raise ValueError('Coordinates must be finite numbers')
    x0, y0, x1, y1 = value
    if not (0 <= x0 < x1 <= 1000 and 0 <= y0 < y1 <= 1000):
        raise ValueError('Box must be ordered and within 0–1000')
    return value


def validate(data, digest, page_count):
    if data.get('version') != 1 or data.get('source_sha256') != digest:
        raise ValueError('Wrong manifest version or source PDF hash')
    pages = data.get('pages')
    if not isinstance(pages, list) or not pages:
        raise ValueError('At least one inspected page is required')
    seen_pages, seen_systems = set(), set()
    for page in pages:
        number = page['page']
        if type(number) is not int or not 1 <= number <= page_count or number in seen_pages:
            raise ValueError('Invalid or duplicate page')
        seen_pages.add(number)
        if page['classification'] not in ('music', 'nonmusic', 'uncertain'):
            raise ValueError('Invalid page classification')
        systems = page['systems']
        if not isinstance(systems, list):
            raise ValueError('Systems must be a list')
        if page['classification'] == 'music' and not systems:
            raise ValueError('Music page needs a system or uncertain classification')
        bottom = 0
        for system in systems:
            sid = system['id']
            if not isinstance(sid, str) or not sid or sid in seen_systems:
                raise ValueError('System IDs must be unique nonempty strings')
            seen_systems.add(sid)
            x0, y0, x1, y1 = box(system['box'])
            if y0 < bottom:
                raise ValueError('Systems must be top-to-bottom without overlapping boxes')
            bottom = y1
            if type(system['geometry_reviewed']) is not bool:
                raise ValueError('geometry_reviewed must be a boolean')
            boundaries = system['bar_boundaries']
            if not isinstance(boundaries, list) or len(boundaries) == 1:
                raise ValueError('Use zero or at least two boundaries')
            previous = -1
            for boundary in boundaries:
                if type(boundary) not in (int, float) or not math.isfinite(boundary) or not x0 <= boundary <= x1 or boundary <= previous:
                    raise ValueError('Bar boundaries must increase within the system')
                previous = boundary
            if len(system['printed_bar_numbers']) != max(0, len(boundaries)-1):
                raise ValueError('Printed bar numbers must match boundary intervals')
            part_ids = set()
            for part in system['parts']:
                if not isinstance(part['id'], str) or not part['id'] or part['id'] in part_ids or type(part['staff_count']) is not int or part['staff_count'] < 1:
                    raise ValueError('Invalid part ID or staff count')
                part_ids.add(part['id'])
            if not part_ids:
                raise ValueError('Record at least one part, using unknown when unresolved')
            for lyric in system['lyric_regions']:
                a, b, c, d = box(lyric)
                if not (x0 <= a < c <= x1 and y0 <= b < d <= y1):
                    raise ValueError('Lyric region falls outside its system')
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'review', 'export'])
    parser.add_argument('pdf', type=Path)
    parser.add_argument('paths', nargs='+', type=Path, help='prepare: output; review/export: layout.json output')
    args = parser.parse_args()
    expected = 1 if args.command == 'prepare' else 2
    if len(args.paths) != expected:
        parser.error('Wrong number of paths; see --help')
    import pymupdf as pdf
    digest = hashlib.sha256(args.pdf.read_bytes()).hexdigest()
    with pdf.open(args.pdf) as source:
        data = None if args.command == 'prepare' else validate(json.loads(args.paths[0].read_text(encoding='utf-8')), digest, len(source))
        output = args.paths[-1]
        # A new directory prevents accidental replacement of reviewed artifacts.
        output.mkdir(parents=True, exist_ok=False)
        if args.command == 'prepare':
            pages = []
            for i, page in enumerate(source):
                page.get_pixmap(dpi=150).save(output / f'page-{i+1}.png')
                pages.append({'page': i+1, 'width_pt': page.rect.width, 'height_pt': page.rect.height, 'rotation': page.rotation})
            (output / 'source.json').write_text(json.dumps({'source_name': args.pdf.name, 'source_sha256': digest, 'pages': pages}, indent=2), encoding='utf-8')
            return
        review = pdf.open()
        crops = []
        for entry in data['pages']:
            page = source[entry['page']-1]
            width, height = page.rect.width, page.rect.height
            # Flatten the displayed rotation in the derived review/crop only.
            target = review.new_page(width=width, height=height)
            target.insert_image(target.rect, stream=page.get_pixmap(dpi=150).tobytes('png'))
            for index, system in enumerate(entry['systems']):
                x0, y0, x1, y1 = system['box']
                rect = pdf.Rect(x0*width/1000, y0*height/1000, x1*width/1000, y1*height/1000)
                target.draw_rect(rect, color=(0, .35, 1), width=1)
                target.insert_text((rect.x0, max(10, rect.y0-3)), f'System {index+1}', fontsize=9)
                for boundary in system['bar_boundaries']:
                    x = boundary*width/1000
                    target.draw_line((x, rect.y0), (x, rect.y1), color=(1, .25, .2), width=.6)
                if args.command == 'export' and system['geometry_reviewed']:
                    filename = f'page-{entry["page"]}-system-{index+1}.pdf'
                    with pdf.open() as crop:
                        dest = crop.new_page(width=rect.width, height=rect.height)
                        dest.insert_image(dest.rect, stream=page.get_pixmap(dpi=300, clip=rect).tobytes('png'))
                        crop.save(output / filename)
                    crops.append({'file': filename, 'page': entry['page'], 'system_id': system['id'], 'box': system['box'], 'parts': system['parts'], 'bar_boundaries': system['bar_boundaries'], 'context': system.get('context', ''), 'uncertainties': system.get('uncertainties', [])})
        review.save(output / 'layout-review.pdf')
        review.close()
        (output / 'crops.json').write_text(json.dumps({'source_name': args.pdf.name, 'source_sha256': digest, 'crops': crops}, indent=2, ensure_ascii=False), encoding='utf-8')
        print(f'Geometry valid; {len(crops)} reviewed system crops exported. Musical correctness is not validated.')


if __name__ == '__main__':
    main()
