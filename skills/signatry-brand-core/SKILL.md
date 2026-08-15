---
name: signatry-brand-core
description: "Canonical source of truth for The Signatry's brand colors, fonts, and logo/mark assets — independent of file format. Use this whenever a task needs the actual hex values, font files, or logo files for The Signatry, or when building/updating a format-specific brand skill (pptx, docx, pdf, xlsx, HTML/artifacts, Canva, etc.). Format-specific brand skills should depend on this one for values and assets rather than restating them; this skill has no build mechanics of its own. For icon assets, see the separate `signatry-icons` skill; for donor/stock photography, see `signatry-photo-library`; for factual claims about The Signatry (contact info, entity/leadership names, history, figures, fund terms, boilerplate), see `signatry-facts`."
version: 1.2
release_date: 2026-08-06
---

# The Signatry Brand Core

This skill is the single canonical record of The Signatry's visual brand: colors, fonts, and logo/mark files. It intentionally contains no format-specific build mechanics — those live in per-format skills (`signatry-pptx-brand`, `signatry-docx-brand`, `signatry-pdf-brand`, and any future format skill) that depend on this one. See `CHANGELOG.md` for why this skill exists and its revision history.

**Not in this skill — redirect here first if that's what you need:**
- **Icons** → `signatry-icons` (separate skill; split out since the file set is large)
- **Donor/stock photography** → `signatry-photo-library` (owns its own usage/consent rules)
- **Factual claims about The Signatry** (contact info, entity/leadership names, history, figures, fund terms, boilerplate) → `signatry-facts`
- **Content restriction rules** (fabrication, donor-content, confidentiality) → `signatry-content-guardrails`
- **Voice/tone/terminology** → `signatry-style`

If none of those match, this skill (colors, fonts, logo/mark files) is the right one — read on.

## Color palette

Confirmed with Ben (July 2026) as the palette in current use for Signatry visual work. This is the canonical set — if any other skill or document shows different hex values for these names, this table wins.

| Name | Hex | Typical use |
|---|---|---|
| Legacy | `2b7a78` | Primary — headers, key text, primary shapes |
| Glacier | `37a49f` | Secondary accent |
| Ice | `def2f1` | Light backgrounds, subtle fills |
| Midnight | `17242a` | Body text, dark backgrounds |
| Dusk | `d77900` | Accent/highlight — use sparingly (call-outs, single data series, key stat). Also the donor-audience corollary to Passage/Mist (nonprofit) and Soar/Arctic (advisor) — see **Audience-specific accent colors** below. |
| Dawn | `f2a65a` | Gold/amber accent — used specifically for small-caps "kicker" labels (eyebrow text above a headline). Distinct from Dusk — don't substitute one for the other. Also part of the donor-audience corollary pair with Dusk. |

Hex values are given without a leading `#` to match the format most build tools (pptxgenjs, etc.) expect; add the `#` where a given tool requires it (e.g., HTML/CSS, reportlab's `colors.HexColor`).

**Jubilee and Heartfelt** are confirmed additional accent colors, usable sparingly in any context (not audience-restricted like the set below):

| Name | Hex | Typical use |
|---|---|---|
| Jubilee | `8a1e41` | Additional accent — use sparingly, any context |
| Heartfelt | `fd4a5c` | Additional accent — use sparingly, any context |

Note: Heartfelt's hex is `fd4a5c` — a prior stale value (`fd495c`) is documented as corrected in `CHANGELOG.md`; don't reintroduce it.

## Audience-specific accent colors

Confirmed with Ben (July 2026): three parallel accent pairs, one per audience. Donor is the default/primary audience (see `signatry-style` Section 1), so its pair (Dusk/Dawn) is already listed in the main palette above; Nonprofit and Advisor each get their own dedicated pair, used only when content is specifically for that audience.

| Audience | Colors | Hex |
|---|---|---|
| Donor (default/primary) | Dusk, Dawn | `d77900`, `f2a65a` |
| Nonprofit | Passage, Mist | `595378`, `8c88a3` |
| Advisor | Soar, Arctic | `68a269`, `8cb7c9` |

| Name | Hex | Audience | Typical use |
|---|---|---|---|
| Passage | `595378` | Nonprofit content | Accent — use minimally |
| Mist | `8c88a3` | Nonprofit content | Accent — use minimally |
| Soar | `68a269` | Advisor content | Accent — use minimally |
| Arctic | `8cb7c9` | Advisor content | Accent — use minimally |

Use the Nonprofit/Advisor pairs only when the content's audience is specifically nonprofits or advisors — not as general-purpose substitutes for the primary palette. Dusk/Dawn, by contrast, are already general-purpose (donor being the default audience) and don't need audience-gating.

## Fonts

Canonical typefaces: **Mulish** (body/UI) and **Lora** (headlines).

- **Mulish** — use for body copy, bullets, captions, and any non-headline text. Weights bundled: Regular, Medium, SemiBold, Bold, ExtraBold, Italic.
- **Lora** — use for headlines/titles. Weights bundled: Regular, Medium, SemiBold, Bold, Italic. The standing rule confirmed for all documents (July 2026) is **Lora Regular only — not bold — for headlines**.

Both fonts' Italic weight (added 2026-08-06) is reconstructed from Google's own Fontsource distribution (Latin, Latin Extended, Cyrillic, Cyrillic Extended, and Vietnamese subsets merged into one file; Lora also includes Math and Symbols) rather than downloaded as a single pre-merged file, since a direct fonts.google.com fetch wasn't reachable from this environment. Glyph coverage is verified equal to the other bundled weights for Latin text, including accented characters; a small number of symbol/misc glyphs present in the Regular weight's original multi-script build (see CHANGELOG.md) are not present in Italic. No bold-italic face is bundled for either font.

Master font files live in `assets/fonts/Mulish/` and `assets/fonts/Lora/` in this skill. These are the source copies — format skills that need their own local copy for build scripts (e.g., `signatry-pptx-brand`'s embedding scripts, `signatry-pdf-brand`'s font registration) should mirror these files, not fork them. **If a font file needs updating (new weight, corrected file, license change), update it here first, then re-copy into any dependent skill.**

## Logo and mark

Master files live in `assets/logos/` in this skill:

| File | Description | Use when |
|---|---|---|
| `logo_color_2C-1.png` (600dpi) / `logo_color_2C.svg` | Full "The Signatry" wordmark + quill, two-color | Light backgrounds (white, Ice) |
| `logo_white_1C.png` | Full wordmark + quill, solid white, one color | Dark or colored backgrounds (Legacy, Midnight, photos) |
| `quill_2color.svg` | Quill mark alone, two-color | Light backgrounds, as a standalone accent/mark |
| `quill_white.svg` | Quill mark alone, white | Dark or colored backgrounds, as a standalone accent/mark |
| `quill_tab_legacy.png` / `quill_tab_midnight.png` | Quill mark as a corner-tab graphic, on Legacy/Midnight fields respectively | Slide/page corner-tab treatments matching those background colors |

Usage rules (apply regardless of format):

- Never alter, recolor, stretch, or rotate the logo or quill artwork.
- "The Signatry" with no tagline is the preferred lockup — don't fabricate a tagline version.
- Clearspace: minimum clearspace on all sides of the logo is equal to the height of the letter "n" in the "Signatry" wordmark, measured from that same logo. Use this unit whenever the logo appears near other elements (text, images, edges of the page/slide) — the "n"-height gap is the floor, not a target; more is always fine.

## Tints

Confirmed with Ben (July 2026): every color above may be used at a tint — 80%, 60%, 40%, 20%, or 5% — as needed, matching usage visible on thesignatry.com. (This formula wasn't reverse-engineered from the site's own CSS; it's the standard tint convention below — flag to Ben if a piece needs to match a pixel-sampled site color exactly rather than this formula.)

**Definition:** a tint is the base color mixed with white. The percentage is how much of the base color survives — 100% is the full color, 0% is pure white. Formula per channel (R, G, or B, 0–255):

```
tinted_channel = round(255 + (base_channel - 255) * (percent / 100))
```

**Full precomputed table** (all 12 colors × 6 percentages) is in `reference/tints.md` — load that file only when a specific tint value is actually needed; don't load it for a basic hex/font/logo lookup.

Application rule: format skills (`signatry-pptx-brand`, `signatry-pdf-brand`, `signatry-docx-brand`) should apply tints as literal computed hex values, not as an opacity/alpha effect — a tint is a lighter *opaque* color, not a transparent one. Alpha transparency lets whatever is behind a shape show through and shifts appearance depending on background; a tint is a fixed, computed color that looks the same on any background.

## Consumers of this skill

Format-specific skills that should depend on this one for values/assets rather than restating them:

- `signatry-pptx-brand` — decks (pptxgenjs)
- `signatry-docx-brand` — Word documents (docx templates)
- `signatry-pdf-brand` — PDFs (reportlab)

Any new format skill (xlsx charts, HTML/artifact work, Canva) should follow the same pattern: pull colors/fonts/logos from here, add only the format-specific mechanics of applying them (embedding, registration, style definitions, QA rendering).

Icon assets live in the separate `signatry-icons` skill, which itself depends on this skill for color values. Format skills needing icons should depend on `signatry-icons`, not look for icon files here.

Donor family and stock photos live in the separate `signatry-photo-library` skill. It does not depend on this skill for anything (photo usage rules are independent of brand color/font/logo values) — it's referenced here only so anyone starting from `signatry-brand-core` knows it exists.

Organizational facts (contact info, entity/leadership names, history, figures, fund terms, boilerplate) live in the separate `signatry-facts` skill. Like the photo library, it doesn't depend on this skill — it's referenced here only for discoverability. Format skills that both apply brand values and state factual content should declare both `signatry-brand-core` and `signatry-facts` as dependencies.

## What's still known to be out of scope here

- Voice, tone, and terminology (donors not givers, DAF capitalization, scripture format, etc.) — see `signatry-style`. That skill's Section 9 (visual/formatting references) now defers to this skill for colors and fonts; it still owns the logo-text and book-link rules that aren't duplicated here.
- Confidentiality and donor-content guardrails — see `signatry-content-guardrails`, which owns all content restriction rules independent of format.
