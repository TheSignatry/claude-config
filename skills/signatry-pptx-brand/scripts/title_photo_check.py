#!/usr/bin/env python3
"""Title-slide photo color check (design-system.md archetype A).

The archetype A overlay is Legacy teal at 60% opacity. A green-dominant
photo (foliage, hills, grass) compounds with that overlay and collapses
contrast for the logo. This check is MANDATORY, not advisory — run it on
every candidate title-slide photo BEFORE building slide 1, not just during
final visual QA. It is step 1 of Definition of done in SKILL.md.

Usage:
    python title_photo_check.py path/to/photo.jpg

Exit code 0 = safe for the Legacy overlay.
Exit code 1 = green-dominant; do not use with the Legacy overlay. Either
pick a different photo, or use the Midnight overlay fallback documented
in archetype A.

As a library:
    from title_photo_check import check
    ok, means = check("photo.jpg")   # means = (r, g, b) 0-255
"""
import sys
from PIL import Image

GREEN_MARGIN = 10  # G must exceed max(R,B) by this much to count as "green-dominant"

def check(path):
    img = Image.open(path).convert("RGB")
    img = img.resize((100, 100))  # downsample; only need the average, not detail
    pixels = list(img.getdata())
    n = len(pixels)
    r = sum(p[0] for p in pixels) / n
    g = sum(p[1] for p in pixels) / n
    b = sum(p[2] for p in pixels) / n
    green_dominant = g - max(r, b) > GREEN_MARGIN
    return not green_dominant, (round(r), round(g), round(b))

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python title_photo_check.py path/to/photo.jpg")
        sys.exit(2)
    ok, (r, g, b) = check(sys.argv[1])
    print(f"mean RGB: ({r}, {g}, {b})")
    if ok:
        print("PASS — safe for the Legacy overlay.")
        sys.exit(0)
    else:
        print("FAIL — green-dominant. Do not pair with the Legacy overlay.")
        print("Fix: choose a different title photo, or switch this slide's overlay to Midnight (see archetype A).")
        sys.exit(1)
