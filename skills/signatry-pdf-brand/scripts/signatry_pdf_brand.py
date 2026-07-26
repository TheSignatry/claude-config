"""
Signatry brand helpers for reportlab PDFs.

Usage:
    import sys
    sys.path.insert(0, "<this-skill-dir>/scripts")
    from signatry_pdf_brand import register_signatry_fonts, SIGNATRY_COLORS

    register_signatry_fonts()  # registers Mulish/Lora + bold/italic family mappings
    styles["Normal"].fontName = "Mulish"
    styles["Heading1"].fontName = "Lora"  # Regular only for headlines, per brand rule
"""
import os
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors

_SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MULISH_DIR = os.path.join(_SKILL_DIR, "assets", "fonts", "Mulish")
_LORA_DIR = os.path.join(_SKILL_DIR, "assets", "fonts", "Lora")

# Canonical palette — mirrored from signatry-brand-core. If these values change,
# update signatry-brand-core/SKILL.md first, then update this dict to match.
SIGNATRY_COLORS = {
    "legacy": colors.HexColor("#2b7a78"),
    "glacier": colors.HexColor("#37a49f"),
    "ice": colors.HexColor("#def2f1"),
    "midnight": colors.HexColor("#17242a"),
    "dusk": colors.HexColor("#d77900"),
    "dawn": colors.HexColor("#f2a65a"),
    # Additional accents, usable sparingly in any context (confirmed with Ben, July 2026).
    "jubilee": colors.HexColor("#8a1e41"),
    "heartfelt": colors.HexColor("#fd4a5c"),
    # Audience-specific accents (confirmed with Ben, July 2026) — use only for
    # content whose audience is specifically nonprofits or advisors, not as
    # general-purpose substitutes for the primary palette above.
    "passage": colors.HexColor("#595378"),  # nonprofit content
    "mist": colors.HexColor("#8c88a3"),     # nonprofit content
    "soar": colors.HexColor("#68a269"),     # advisor content
    "arctic": colors.HexColor("#8cb7c9"),   # advisor content
}

_registered = False


def tint(base_hex, percent):
    """
    Return a reportlab Color object for `base_hex` (e.g. "2b7a78" or "#2b7a78")
    tinted to `percent` (0-100). 100 = the base color unchanged, 0 = white.
    Matches the tint formula documented in signatry-brand-core (mix with white,
    percent = proportion of base color retained). This is an opaque lighter
    color, not an alpha/transparency effect.
    """
    h = base_hex.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    p = percent / 100
    r2 = round(255 + (r - 255) * p)
    g2 = round(255 + (g - 255) * p)
    b2 = round(255 + (b - 255) * p)
    return colors.Color(r2 / 255, g2 / 255, b2 / 255)


def register_signatry_fonts():
    """
    Register Mulish and Lora weights with reportlab and map font families so that
    Paragraph markup (<b>, <i>) and style.fontName="Mulish"/"Lora" resolve to the
    right weight automatically. Safe to call more than once (no-ops after the first).

    Registering via TTFont causes reportlab to embed a subset of the font directly
    in the generated PDF — no separate "embed fonts" step is needed, unlike pptx.
    """
    global _registered
    if _registered:
        return
    pdfmetrics.registerFont(TTFont("Mulish", os.path.join(_MULISH_DIR, "Mulish-Regular.ttf")))
    pdfmetrics.registerFont(TTFont("Mulish-Medium", os.path.join(_MULISH_DIR, "Mulish-Medium.ttf")))
    pdfmetrics.registerFont(TTFont("Mulish-SemiBold", os.path.join(_MULISH_DIR, "Mulish-SemiBold.ttf")))
    pdfmetrics.registerFont(TTFont("Mulish-Bold", os.path.join(_MULISH_DIR, "Mulish-Bold.ttf")))
    pdfmetrics.registerFont(TTFont("Mulish-ExtraBold", os.path.join(_MULISH_DIR, "Mulish-ExtraBold.ttf")))

    pdfmetrics.registerFont(TTFont("Lora", os.path.join(_LORA_DIR, "Lora-Regular.ttf")))
    pdfmetrics.registerFont(TTFont("Lora-Medium", os.path.join(_LORA_DIR, "Lora-Medium.ttf")))
    pdfmetrics.registerFont(TTFont("Lora-SemiBold", os.path.join(_LORA_DIR, "Lora-SemiBold.ttf")))
    pdfmetrics.registerFont(TTFont("Lora-Bold", os.path.join(_LORA_DIR, "Lora-Bold.ttf")))

    # Family mapping so <b>/<i> tags inside Paragraph text resolve to real bold
    # weights instead of reportlab faking a slant/weight on the regular glyphs.
    pdfmetrics.registerFontFamily(
        "Mulish", normal="Mulish", bold="Mulish-Bold", italic="Mulish", boldItalic="Mulish-Bold"
    )
    pdfmetrics.registerFontFamily(
        "Lora", normal="Lora", bold="Lora-Bold", italic="Lora", boldItalic="Lora-Bold"
    )
    _registered = True
