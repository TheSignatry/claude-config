#!/usr/bin/env python3
"""Image aspect-ratio check for Signatry decks (design-system.md standard #4).

Reads a built .pptx, finds every placed picture, reads that image's NATIVE
pixel width/height straight from the embedded file, and compares the native
aspect ratio to the placed w/h aspect ratio (the xfrm ext in the slide XML).
Flags anything off by more than a small tolerance.

This exists because logos, icons, and pre-cropped photos are all supposed
to be placed at their native aspect ratio (see standard #4 — "never place
an image at a w/h that differs from its native aspect ratio without
cropping first"). That's currently enforced only by the builder remembering
to check each time. This script checks mechanically instead, for every
image in the file, not just the ones that look off at a glance.

Usage: python3 image_ratio_check.py deck.pptx
Exit code 1 if any ERROR found (ratio off by > TOLERANCE).
"""
import sys, re, zipfile, io
from lxml import etree
from PIL import Image

NS = {'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
      'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
      'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
EMU = 914400.0
TOLERANCE = 0.02  # 2% relative difference in aspect ratio before flagging

def rels_for(z, slide_name):
    """Map r:id -> media path for a given ppt/slides/slideN.xml."""
    rels_name = slide_name.replace('slides/', 'slides/_rels/') + '.rels'
    if rels_name not in z.namelist():
        return {}
    tree = etree.fromstring(z.read(rels_name))
    out = {}
    for rel in tree.iter('{http://schemas.openxmlformats.org/package/2006/relationships}Relationship'):
        rid = rel.get('Id')
        target = rel.get('Target')
        if target and target.startswith('../'):
            target = 'ppt/' + target[3:]
        out[rid] = target
    return out

def pictures(slide_xml):
    tree = etree.fromstring(slide_xml)
    out = []
    for el in tree.iter(f'{{{NS["p"]}}}pic'):
        nv = el.find(f'{{{NS["p"]}}}nvPicPr')
        name = nv.find(f'{{{NS["p"]}}}cNvPr').get('name') if nv is not None else '?'
        spPr = el.find(f'{{{NS["p"]}}}spPr')
        xfrm = spPr.find(f'{{{NS["a"]}}}xfrm') if spPr is not None else None
        if xfrm is None:
            continue
        off, ext = xfrm.find(f'{{{NS["a"]}}}off'), xfrm.find(f'{{{NS["a"]}}}ext')
        w, h = int(ext.get('cx'))/EMU, int(ext.get('cy'))/EMU
        blip = el.find(f'.//{{{NS["a"]}}}blip')
        rid = blip.get(f'{{{NS["r"]}}}embed') if blip is not None else None
        out.append(dict(name=name, w=w, h=h, rid=rid))
    return out

def main(path):
    z = zipfile.ZipFile(path)
    slide_names = sorted([n for n in z.namelist()
                          if re.match(r'ppt/slides/slide\d+\.xml$', n)],
                         key=lambda n: int(re.search(r'(\d+)', n).group()))
    errors = 0
    checked = 0
    for n in slide_names:
        sn = re.search(r'(\d+)', n).group()
        rels = rels_for(z, n)
        for pic in pictures(z.read(n)):
            if not pic['rid'] or pic['rid'] not in rels:
                continue
            media_path = rels[pic['rid']]
            if media_path not in z.namelist():
                print(f"WARN  slide {sn}: '{pic['name']}' references missing media {media_path}")
                continue
            try:
                img = Image.open(io.BytesIO(z.read(media_path)))
                nw, nh = img.size
            except Exception as e:
                print(f"WARN  slide {sn}: couldn't read {media_path} ({e})")
                continue
            checked += 1
            native_ratio = nw / nh
            placed_ratio = pic['w'] / pic['h']
            diff = abs(placed_ratio / native_ratio - 1)
            if diff > TOLERANCE:
                print(f"ERROR slide {sn}: '{pic['name']}' distorted — "
                      f"native {nw}x{nh} (ratio {native_ratio:.3f}) vs placed "
                      f"{pic['w']:.2f}\"x{pic['h']:.2f}\" (ratio {placed_ratio:.3f}), "
                      f"{diff*100:.1f}% off")
                errors += 1
    print(f"\n{checked} image(s) checked, {errors} error(s)")
    return 1 if errors else 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1]))
