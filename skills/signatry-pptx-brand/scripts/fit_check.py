#!/usr/bin/env python3
"""Text fit check for Signatry decks (design-system.md standard #2).

Measures wrapped text height using the skill's bundled TTFs and asserts it
fits within <=90% of the usable box height. Run BEFORE rendering, for every
dense text block (any block you estimate at >60% of its box).

Usage (as a library):
    from fit_check import check
    ok, pct = check(
        texts=["First paragraph...", "Second..."],   # one string per paragraph/bullet
        font="Mulish",          # Mulish | Mulish-Bold | Lora
        size_pt=14,
        box_w_in=5.7, box_h_in=4.3,
        line_spacing=1.15,      # match lineSpacingMultiple in pptxgenjs
        para_after_pt=10,       # match paraSpaceAfter
        indent_in=0.25,         # bullet/number indent; 0 for plain text
    )

Exit criteria: pct <= 90 passes. On failure: reduce font 1-2pt, widen the box,
or split the slide. Do NOT pass by adding autofit.
"""
import os
from PIL import ImageFont

_HERE = os.path.dirname(os.path.abspath(__file__))
_FONTS = {
    "Mulish": "../assets/fonts/Mulish/Mulish-Regular.ttf",
    "Mulish-Bold": "../assets/fonts/Mulish/Mulish-Bold.ttf",
    "Mulish-SemiBold": "../assets/fonts/Mulish/Mulish-SemiBold.ttf",
    "Lora": "../assets/fonts/Lora/Lora-Regular.ttf",
}

def _px(pt):
    return pt * 96 / 72

def check(texts, font, size_pt, box_w_in, box_h_in,
          line_spacing=1.15, para_after_pt=10, indent_in=0.0,
          inset_lr_in=0.2, inset_tb_in=0.1):
    path = os.path.normpath(os.path.join(_HERE, _FONTS[font]))
    f = ImageFont.truetype(path, int(_px(size_pt)))
    usable_w = (box_w_in - inset_lr_in - indent_in) * 96
    ascent, descent = f.getmetrics()
    line_h = (ascent + descent) * line_spacing
    total = 0.0
    for i, t in enumerate(texts):
        cur, lines = "", 0
        for w in t.split():
            trial = (cur + " " + w).strip()
            if f.getbbox(trial)[2] <= usable_w or not cur:
                cur = trial
            else:
                lines += 1
                cur = w
        lines += 1
        total += lines * line_h
        if i < len(texts) - 1:
            total += _px(para_after_pt)
    usable_h = (box_h_in - inset_tb_in) * 96
    pct = total / usable_h * 100
    return pct <= 90, round(pct)

if __name__ == "__main__":
    ok, pct = check(
        texts=["Example paragraph to demonstrate the checker output."],
        font="Mulish", size_pt=14, box_w_in=5.0, box_h_in=1.0)
    print(f"demo: {pct}% -> {'PASS' if ok else 'FAIL'}")
