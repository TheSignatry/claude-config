#!/usr/bin/env python3
"""Set font substitution fallbacks for Signatry decks.

OOXML has no per-run font stack, so a hard "fallback to Georgia" cannot be
declared. The supported mechanism is the `panose` attribute on <a:latin>/<a:ea>/
<a:cs>: when the named typeface is missing (and embedded fonts are not honored),
PowerPoint's substitution engine picks the installed font whose PANOSE
classification is closest. Writing Georgia's PANOSE onto every Lora reference
steers substitution to Georgia — a strong steer on systems where Georgia is
installed (all Windows/macOS Office installs), not an absolute guarantee.

Fallback map:
  Lora   -> Georgia PANOSE 2 4 5 2 5 4 5 2 3 3  (hex 02040502050405020303)
  Mulish -> Arial   PANOSE 2 11 6 4 2 2 2 2 2 4 (hex 020B0604020202020204)

Run BEFORE embed_fonts.py. Usage: python3 apply_font_fallbacks.py deck.pptx
"""
import sys, zipfile, shutil, re

PANOSE = {
    'Lora': '02040502050405020303',   # Georgia
    'Mulish': '020B0604020202020204', # Arial (confirmed against this deck's own
                                       # original Arial buFont references)
}

def main(path):
    tmp = path + '.tmp'
    zin = zipfile.ZipFile(path)
    zout = zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED)
    n_set = 0
    for name in zin.namelist():
        data = zin.read(name)
        if re.match(r'ppt/(slides|slideLayouts|slideMasters|notesSlides)/[^/]+\.xml$', name) \
           or re.match(r'ppt/theme/theme\d+\.xml$', name):
            xml = data.decode('utf-8')
            for face, panose in PANOSE.items():
                # add panose to any latin/ea/cs element naming this face, if absent
                pattern = re.compile(r'(<a:(?:latin|ea|cs) typeface="%s")(?![^>]*panose=)' % re.escape(face))
                xml, k = pattern.subn(r'\1 panose="%s"' % panose, xml)
                n_set += k
                # replace an existing (wrong/native) panose on this face
                pattern2 = re.compile(r'(<a:(?:latin|ea|cs) typeface="%s"[^>]*panose=")[0-9A-Fa-f]+(")' % re.escape(face))
                xml, k2 = pattern2.subn(r'\g<1>%s\g<2>' % panose, xml)
                n_set += k2
            data = xml.encode('utf-8')
        zout.writestr(name, data)
    zout.close(); zin.close()
    shutil.move(tmp, path)
    print(f'set fallback PANOSE on {n_set} font reference(s) in {path}')
    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1]))
