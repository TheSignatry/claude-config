#!/usr/bin/env python3
"""Embed Lora + Mulish into a .pptx (design-system.md standard #10).

PPTX supports native font embedding: TTF bytes stored as ppt/fonts/fontN.fntdata
parts, declared in presentation.xml via <p:embeddedFontLst> with
embedTrueTypeFonts="1". PowerPoint and LibreOffice both honor this, so the deck
renders in the correct fonts on machines where Lora/Mulish are not installed.

Both fonts are SIL Open Font License — embedding is permitted.

Usage: python3 embed_fonts.py deck.pptx   (modifies in place)
"""
import sys, os, zipfile, shutil
from lxml import etree

P = 'http://schemas.openxmlformats.org/presentationml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
CT = 'http://schemas.openxmlformats.org/package/2006/content-types'
REL = 'http://schemas.openxmlformats.org/package/2006/relationships'
FONT_REL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/font'

_HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = [
    # (typeface, style-element, ttf path relative to skill)
    ('Lora',   'regular', '../assets/fonts/Lora/Lora-Regular.ttf'),
    ('Mulish', 'regular', '../assets/fonts/Mulish/Mulish-Regular.ttf'),
    ('Mulish', 'bold',    '../assets/fonts/Mulish/Mulish-Bold.ttf'),
]
# insertion order constraint: embeddedFontLst must follow notesSz in CT_Presentation
AFTER = ['notesSz', 'sldSz', 'sldIdLst', 'handoutMasterIdLst', 'notesMasterIdLst', 'sldMasterIdLst']

def main(path):
    tmp = path + '.tmp'
    zin = zipfile.ZipFile(path)
    names = zin.namelist()
    if any(n.startswith('ppt/fonts/') for n in names):
        print('fonts already embedded; nothing to do')
        return 0

    pres = etree.fromstring(zin.read('ppt/presentation.xml'))
    rels = etree.fromstring(zin.read('ppt/_rels/presentation.xml.rels'))
    ctypes = etree.fromstring(zin.read('[Content_Types].xml'))

    # next free rId
    used = {rel.get('Id') for rel in rels}
    def next_rid():
        i = 1
        while f'rId{i}' in used:
            i += 1
        used.add(f'rId{i}')
        return f'rId{i}'

    # group ttfs per typeface
    grouped = {}
    font_parts = []  # (partname, bytes)
    for i, (face, style, rel) in enumerate(FONTS, 1):
        data = open(os.path.normpath(os.path.join(_HERE, rel)), 'rb').read()
        part = f'fonts/font{i}.fntdata'
        font_parts.append((f'ppt/{part}', data))
        rid = next_rid()
        r = etree.SubElement(rels, f'{{{REL}}}Relationship')
        r.set('Id', rid); r.set('Type', FONT_REL); r.set('Target', part)
        grouped.setdefault(face, []).append((style, rid))

    lst = etree.Element(f'{{{P}}}embeddedFontLst')
    for face, entries in grouped.items():
        ef = etree.SubElement(lst, f'{{{P}}}embeddedFont')
        fo = etree.SubElement(ef, f'{{{P}}}font')
        fo.set('typeface', face)
        for style, rid in entries:
            se = etree.SubElement(ef, f'{{{P}}}{style}')
            se.set(f'{{{R}}}id', rid)

    # insert after the last-present anchor element
    anchor = None
    for tag in AFTER:
        found = pres.find(f'{{{P}}}{tag}')
        if found is not None:
            anchor = found
            break
    if anchor is None:
        pres.insert(0, lst)
    else:
        anchor.addnext(lst)
    pres.set('embedTrueTypeFonts', '1')

    # content type default for fntdata
    if not any(d.get('Extension') == 'fntdata' for d in ctypes
               if etree.QName(d).localname == 'Default'):
        d = etree.SubElement(ctypes, f'{{{CT}}}Default')
        d.set('Extension', 'fntdata'); d.set('ContentType', 'application/x-fontdata')

    zout = zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED)
    for n in names:
        if n == 'ppt/presentation.xml':
            zout.writestr(n, etree.tostring(pres, xml_declaration=True, encoding='UTF-8', standalone=True))
        elif n == 'ppt/_rels/presentation.xml.rels':
            zout.writestr(n, etree.tostring(rels, xml_declaration=True, encoding='UTF-8', standalone=True))
        elif n == '[Content_Types].xml':
            zout.writestr(n, etree.tostring(ctypes, xml_declaration=True, encoding='UTF-8', standalone=True))
        else:
            zout.writestr(n, zin.read(n))
    for part, data in font_parts:
        zout.writestr(part, data)
    zout.close(); zin.close()
    shutil.move(tmp, path)
    print(f'embedded {len(font_parts)} font file(s) into {path}')
    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1]))
