#!/usr/bin/env python3
"""Layout lint for Signatry decks (design-system.md standard #3).

Reads a built .pptx and flags:
  1. Text boxes whose rectangles intersect pictures or other text boxes
     (gap < 0.3" also reported, as a warning)
  2. Any non-tab element entering the corner-tab zone (11.5,6.1)-(13.33,7.5)
     on slides that have a corner tab

Full-bleed/background photos (covering >=85% of the slide) and full-bleed
overlay rectangles are ignored — text is expected to sit on those.

Usage: python3 layout_lint.py deck.pptx
Exit code 1 if any ERROR found.
"""
import sys, re, zipfile
from lxml import etree

NS = {'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
      'p': 'http://schemas.openxmlformats.org/presentationml/2006/main'}
EMU = 914400.0
SLIDE_W, SLIDE_H = 13.333, 7.5
TAB_ZONE = (11.5, 6.1, 13.333, 7.5)
GAP_IN = 0.15  # warn threshold; kicker+headline pairs stack tighter by design

def shapes(slide_xml):
    tree = etree.fromstring(slide_xml)
    out = []
    for el in tree.iter():
        tag = etree.QName(el).localname
        if tag not in ('sp', 'pic'):
            continue
        nv = el.find(f'{{{NS["p"]}}}nvSpPr') if tag == 'sp' else el.find(f'{{{NS["p"]}}}nvPicPr')
        name = nv.find(f'{{{NS["p"]}}}cNvPr').get('name') if nv is not None else '?'
        spPr = el.find(f'{{{NS["p"]}}}spPr')
        xfrm = spPr.find(f'{{{NS["a"]}}}xfrm') if spPr is not None else None
        if xfrm is None:
            continue
        off, ext = xfrm.find(f'{{{NS["a"]}}}off'), xfrm.find(f'{{{NS["a"]}}}ext')
        x, y = int(off.get('x'))/EMU, int(off.get('y'))/EMU
        w, h = int(ext.get('cx'))/EMU, int(ext.get('cy'))/EMU
        has_text = tag == 'sp' and any((t.text or '').strip() for t in el.iter(f'{{{NS["a"]}}}t'))
        # a filled sp with no text is a decorative rect (card/panel/overlay)
        out.append(dict(name=name, kind=tag, x=x, y=y, w=w, h=h, text=has_text))
    return out

def rect(s): return (s['x'], s['y'], s['x']+s['w'], s['y']+s['h'])

def gap_between(a, b):
    ax1, ay1, ax2, ay2 = rect(a); bx1, by1, bx2, by2 = rect(b)
    dx = max(bx1-ax2, ax1-bx2, 0)
    dy = max(by1-ay2, ay1-by2, 0)
    if dx == 0 and dy == 0:
        return -1  # intersecting
    return max(dx, dy) if (dx == 0 or dy == 0) else (dx**2+dy**2)**0.5

def is_fullbleed(s):
    return s['w']*s['h'] >= 0.85*SLIDE_W*SLIDE_H

def is_tab(s):
    return s['kind'] == 'pic' and abs(s['x']-11.7) < 0.15 and abs(s['y']-6.36) < 0.15

def contains(outer, inner, tol=0.05):
    ox1,oy1,ox2,oy2 = rect(outer); ix1,iy1,ix2,iy2 = rect(inner)
    return ix1 >= ox1-tol and iy1 >= oy1-tol and ix2 <= ox2+tol and iy2 <= oy2+tol

def main(path):
    z = zipfile.ZipFile(path)
    slide_names = sorted([n for n in z.namelist()
                          if re.match(r'ppt/slides/slide\d+\.xml$', n)],
                         key=lambda n: int(re.search(r'(\d+)', n).group()))
    errors = warnings = 0
    for n in slide_names:
        ss = shapes(z.read(n))
        sn = re.search(r'(\d+)', n).group()
        tabs = [s for s in ss if is_tab(s)]
        texts = [s for s in ss if s['text']]
        solids = [s for s in ss if not s['text'] and not is_fullbleed(s) and not is_tab(s)]
        for t in texts:
            for o in texts + solids:
                if o is t:
                    continue
                # text placed INSIDE a card/panel is intentional
                if not o['text'] and contains(o, t):
                    continue
                g = gap_between(t, o)
                if g < 0:
                    print(f"ERROR slide {sn}: text '{t['name']}' intersects {'text' if o['text'] else o['kind']} '{o['name']}'")
                    errors += 1
                elif g < GAP_IN:
                    print(f"WARN  slide {sn}: gap {g:.2f}\" < {GAP_IN}\" between '{t['name']}' and '{o['name']}'")
                    warnings += 1
        if tabs:
            zx1, zy1, zx2, zy2 = TAB_ZONE
            zone = dict(x=zx1, y=zy1, w=zx2-zx1, h=zy2-zy1)
            for s in ss:
                if is_tab(s) or is_fullbleed(s):
                    continue
                if gap_between(s, zone) < 0:
                    print(f"ERROR slide {sn}: '{s['name']}' enters the corner-tab zone")
                    errors += 1
    print(f"\n{errors} error(s), {warnings} warning(s)")
    return 1 if errors else 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1]))
