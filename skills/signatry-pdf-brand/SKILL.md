---
name: signatry-pdf-brand
description: "Signatry brand system for PDFs built with reportlab: font registration/embedding, color palette, and logo usage for The Signatry. Use whenever building, branding, or reviewing a PDF for The Signatry — reports, flyers, one-pagers, fund summaries, or any PDF deliverable — even if the user doesn't say 'brand' or 'Signatry' by name, as long as the deliverable is a Signatry PDF. Always pair with the general pdf skill (build/extraction mechanics) and, if there is donor-facing or narrative copy, the signatry-style skill (voice and terminology)."
version: 1.2
release_date: 2026-07-26
---

# Signatry PDF Brand System

This skill supplies the visual brand layer for The Signatry's reportlab-built PDFs: font registration/embedding and color usage. It does not duplicate PDF build mechanics or writing style — see **Dependencies**. Canonical brand values themselves (the source of truth for hex codes, font weights, and logo files) live in `signatry-brand-core`; this skill mirrors what it needs locally and adds reportlab-specific mechanics on top.

## Dependencies — read these first

- **`signatry-brand-core` skill**: canonical colors, fonts, and logo files. If a value here ever looks wrong or out of date, that skill wins — check it, don't guess.
- **`pdf` skill**: general PDF build/extraction mechanics (reportlab basics, pypdf, pdfplumber, merging/splitting). This skill only adds Signatry-specific brand values on top of that workflow.
- **`signatry-style` skill**: use whenever the PDF has donor-facing or narrative copy (headlines, body copy, CTAs, disclosures). Apply its terminology, faith-language, and voice rules to the text content.
- **`signatry-facts` skill**: use whenever a PDF will state a factual value about The Signatry — contact info, entity/leadership names, history, figures, fund terms, or boilerplate/disclaimers. Load it on any build; don't supply these values from recall.
- **`signatry-content-guardrails` skill**: content restriction rules (fabrication prohibition, donor photo/quote reuse, gift-amount confidentiality, board-only source restriction) — independent of format, load on any build.
- **`signatry-icons` skill**: the 69-icon brand set. Use the `png_512` variants, or `svg` through `svglib` — see **Placing an icon** below. Search with that skill's `scripts/find_icons.py`; don't draw substitutes or pull outside icon sets.
- **`signatry-photo-library` skill**: the 44-image catalog and `scripts/find_photos.py`. Search it before using a placeholder or outside stock.

## Why this skill exists

reportlab defaults to Helvetica/Times and will silently substitute those in for any font name it doesn't recognize — it does not raise an error. Without explicit registration, a Signatry PDF built with reportlab renders in the wrong typeface with no warning. This skill exists so that doesn't happen again.

## Colors

Mirrored from `signatry-brand-core` (check there if these ever look stale):

| Name | Hex | Typical use |
|---|---|---|
| Legacy | `#2b7a78` | Primary — headers, key text, primary shapes |
| Glacier | `#37a49f` | Secondary accent |
| Ice | `#def2f1` | Light backgrounds, subtle fills |
| Midnight | `#17242a` | Body text, dark backgrounds |
| Dusk | `#d77900` | Accent/highlight — use sparingly. Also the donor-audience pair with Dawn (see below). |
| Dawn | `#f2a65a` | Kicker/eyebrow label accent — distinct from Dusk, don't substitute |

In reportlab, build these with `colors.HexColor("#2b7a78")` (reportlab needs the leading `#`, unlike pptxgenjs).

### Additional accent colors (any context, sparingly)

| Name | Hex |
|---|---|
| Jubilee | `#8a1e41` |
| Heartfelt | `#fd4a5c` |

### Audience-specific accents (nonprofit and advisor content)

Donor is the default audience, so Dusk/Dawn above already cover it. Nonprofit and Advisor each have their own dedicated pair:

| Name | Hex | Audience | Typical use |
|---|---|---|---|
| Passage | `#595378` | Nonprofit content | Accent — use minimally |
| Mist | `#8c88a3` | Nonprofit content | Accent — use minimally |
| Soar | `#68a269` | Advisor content | Accent — use minimally |
| Arctic | `#8cb7c9` | Advisor content | Accent — use minimally |

Use the Nonprofit/Advisor pairs only when the PDF's audience is specifically nonprofits or advisors — not as general substitutes for the primary palette. All twelve colors are available as `SIGNATRY_COLORS` keys in the bundled helper (`"passage"`, `"mist"`, `"soar"`, `"arctic"`, `"jubilee"`, `"heartfelt"`, lowercase).

### Tints

Every color may be used at a tint (80%, 60%, 40%, 20%, or 5% of the base color, mixed with white) per `signatry-brand-core`, which has the full reference table. For code, use the bundled `tint()` helper rather than hand-picking a hex from the table:

```python
from signatry_pdf_brand import tint

light_legacy = tint("2b7a78", 20)   # returns a reportlab Color, verified against the core reference table
```

`tint()` takes a hex string (with or without `#`) and a percent (0–100, where 100 is the unmodified base color) and returns a reportlab `Color` object — an opaque lighter color, not a transparency effect. Don't use reportlab's alpha/`Color(..., alpha=...)` to fake a tint; the result depends on whatever's drawn underneath, whereas a tint is a fixed, computed color.

## Fonts

Canonical typefaces: **Mulish** (body) and **Lora** (headlines, Regular weight only — not bold, per the standing brand rule). Bundled locally in `assets/fonts/Mulish/` and `assets/fonts/Lora/`, mirrored from `signatry-brand-core`.

### Registering fonts (required — do this before building any Signatry PDF)

A tested helper is bundled at `scripts/signatry_pdf_brand.py`. Use it rather than re-deriving registration by hand:

```python
import sys
sys.path.insert(0, "<this-skill-dir>/scripts")
from signatry_pdf_brand import register_signatry_fonts, SIGNATRY_COLORS

register_signatry_fonts()
```

This registers:
- `Mulish`, `Mulish-Medium`, `Mulish-SemiBold`, `Mulish-Bold`, `Mulish-ExtraBold`
- `Lora`, `Lora-Medium`, `Lora-SemiBold`, `Lora-Bold`
- Font-family mappings for `Mulish` and `Lora` so that `<b>...</b>` markup inside a reportlab `Paragraph` resolves to the real bold weight file, instead of reportlab faking a bold by skewing the regular glyphs.

Apply fonts via `ParagraphStyle.fontName`, e.g.:

```python
from reportlab.lib.styles import ParagraphStyle
head = ParagraphStyle("Head", fontName="Lora", textColor=SIGNATRY_COLORS["legacy"], fontSize=20)
body = ParagraphStyle("Body", fontName="Mulish", textColor=SIGNATRY_COLORS["midnight"], fontSize=10)
```

For canvas-drawn text (not `Paragraph` objects), call `canvas.setFont("Mulish", 10)` after registration, same font names as above.

### Embedding is automatic — no separate step needed

Unlike the pptx brand skill (where pptxgenjs sets `fontFace` by name only, and the font must separately be embedded or installed on the recipient's machine to render correctly), registering a font with `pdfmetrics.registerFont(TTFont(...))` causes reportlab to embed a subsetted copy of that font directly into the output PDF at build time. Verified July 2026: building a test PDF with `register_signatry_fonts()` and checking it with `pdffonts` shows Lora and Mulish (regular and bold) embedded and subset (`emb yes, sub yes`). The PDF will render correctly on any machine, with no font-installation caveat to pass on to the recipient.

This guarantee is specific to reportlab's `TTFont`/`registerFont` path. If a Signatry PDF is ever produced a different way — e.g., HTML-to-PDF via WeasyPrint (as used for the fund summary PDF work) — embedding works differently (system-installed fonts or `@font-face` with a reachable font file) and isn't covered by this skill; flag that explicitly if it comes up rather than assuming the same guarantee applies.

### Subscripts/superscripts

Per the general `pdf` skill: never use Unicode subscript/superscript characters with these fonts — use reportlab's `<sub>`/`<super>` markup in `Paragraph` text instead, or manually adjust font size/position for canvas-drawn text.

## Placing an icon

Two working paths, both verified July 31, 2026 against reportlab 4.4.10.

**PNG (default).** Simplest and most predictable. Icons are 512x512 RGBA with transparency, square, so keep width and height equal:

```python
from reportlab.platypus import Image
Image("<icons-skill>/assets/icons/png_512/glacier/SIG_Icon20_Stewardship_RGB.png",
      width=48, height=48)          # points; 48pt is a comfortable inline mark
```

Use `png_128` only for marks under about 24pt. For `canvas.drawImage`, pass `mask="auto"` so transparency is honored rather than filled black.

**SVG via `svglib` (vector).** Use when the icon is large enough that raster edges would show. `svglib` is a separate install, not part of reportlab:

```python
from svglib.svglib import svg2rlg
d = svg2rlg("<icons-skill>/assets/icons/svg/SIG_Icon20_Stewardship_RGB.svg")
scale = 48.0 / d.width                # svg2rlg does not size to a target
d.width *= scale; d.height *= scale; d.scale(scale, scale)
```

The returned object is a `Drawing` flowable and goes straight into a story. Scaling is not automatic — set it explicitly or the icon renders at its natural 110pt.

**Color.** Use `png_512/glacier/` or `svg/` on light backgrounds; `png_512/white/` on Legacy, Midnight, or photographs. The SVG set carries Glacier by default and recolors via its root `color` property — see `signatry-icons`. Only Glacier and white exist as PNG; if a PDF needs a tinted icon, take the SVG path and set the tint hex from `signatry-brand-core`, rather than lowering opacity.

## Logo and mark

Two commonly needed variants are mirrored locally in `assets/logos/` (full set lives in `signatry-brand-core`):

| File | Use when |
|---|---|
| `logo_color_2C-1.png` | Light backgrounds (white, Ice) |
| `logo_white_1C.png` | Dark or colored backgrounds (Legacy, Midnight, photos) |

Place with reportlab's `Image` flowable or `canvas.drawImage`. Never alter, recolor, stretch, or rotate the artwork. If a vector/SVG logo is needed, pull the SVG directly from `signatry-brand-core/assets/logos/` — reportlab's raster `Image` flowable needs the PNG, but `svglib` can render the SVGs if vector output is required.

## Keeping this skill in sync

The font and logo files here are mirrors, not forks, of `signatry-brand-core`. If the canonical files or hex values change:

1. Update `signatry-brand-core` first.
2. Re-copy the affected files into this skill's `assets/`.
3. Update the hex table above and `scripts/signatry_pdf_brand.py`'s `SIGNATRY_COLORS` dict to match.
