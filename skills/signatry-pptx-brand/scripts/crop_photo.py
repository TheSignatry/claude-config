#!/usr/bin/env python3
"""Subject-aware crop for Signatry decks (design-system.md standard #4).

A blind center-crop assumes the subject is horizontally/vertically centered
in the source frame. It often isn't — a person standing left-of-center, a
whiteboard on the right, a face in the upper third. Cropping equally from
both edges in that case can cut straight through the subject.

MANDATORY WORKFLOW for any photo containing a person or a clear focal
subject:
1. View the source photo first (the `view` tool, not this script) and note
   the subject's approximate position as a fraction of width/height —
   e.g. "the man is at roughly x=0.65 (right third), y=0.45".
2. Pass that as center_x/center_y below. Only use the default (0.5, 0.5)
   for photos with no off-center subject (landscapes, textures, evenly
   distributed group shots).
3. After cropping, re-view the OUTPUT file to confirm the subject is fully
   inside the frame and not clipped at an edge — this script places the
   crop box around your stated center but does not verify the subject's
   extent, since it has no subject-detection of its own.

Usage:
    python crop_photo.py IN.jpg OUT.jpg TARGET_W TARGET_H [center_x] [center_y]

    TARGET_W/TARGET_H: target aspect ratio (e.g. 0.74 1.0, or use pixel
    dims like 1600 2160 — only the ratio matters).
    center_x/center_y: fraction (0.0-1.0) of the source image where the
    subject sits. Default 0.5 0.5 (true center — the old blind behavior).

As a library:
    from crop_photo import crop
    crop("in.jpg", "out.jpg", target_w=0.74, target_h=1.0,
         center_x=0.65, center_y=0.45)
"""
import sys
from PIL import Image

def crop(src_path, dst_path, target_w, target_h, center_x=0.5, center_y=0.5):
    img = Image.open(src_path)
    # Convert CMYK to RGB (several template photos are CMYK and render wrong otherwise)
    if img.mode == "CMYK":
        img = img.convert("RGB")
    sw, sh = img.size
    target_ratio = target_w / target_h
    src_ratio = sw / sh

    if src_ratio > target_ratio:
        # source is wider than target -> crop width, keep full height
        crop_h = sh
        crop_w = int(sh * target_ratio)
    else:
        # source is taller than target -> crop height, keep full width
        crop_w = sw
        crop_h = int(sw / target_ratio)

    # Center the crop box on the stated subject position, clamped to bounds
    cx = center_x * sw
    cy = center_y * sh
    left = max(0, min(sw - crop_w, int(cx - crop_w / 2)))
    top = max(0, min(sh - crop_h, int(cy - crop_h / 2)))

    cropped = img.crop((left, top, left + crop_w, top + crop_h))
    cropped.save(dst_path, quality=90)
    return dst_path, (left, top, crop_w, crop_h), (sw, sh)

if __name__ == "__main__":
    if len(sys.argv) not in (5, 7):
        print(__doc__)
        sys.exit(2)
    src, dst = sys.argv[1], sys.argv[2]
    tw, th = float(sys.argv[3]), float(sys.argv[4])
    cx, cy = (float(sys.argv[5]), float(sys.argv[6])) if len(sys.argv) == 7 else (0.5, 0.5)
    if cx == 0.5 and cy == 0.5:
        print("NOTE: using default center (0.5, 0.5). If this photo has an "
              "off-center person or subject, view it first and pass the "
              "actual center_x/center_y instead — see this script's docstring.")
    path, box, (sw, sh) = crop(src, dst, tw, th, cx, cy)
    print(f"source {sw}x{sh} -> crop box {box} -> saved {path}")
    print("Re-view the output to confirm the subject isn't clipped at an edge.")
