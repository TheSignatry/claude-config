---
name: signatry-pptx-brand
description: "Signatry brand system for PowerPoint decks: color palette, fonts (Mulish, Lora), and logo/quill assets for The Signatry. Use this skill whenever building, branding, restyling, or reviewing a .pptx presentation for The Signatry — donor-facing decks, internal/team decks, pitch decks, training decks, or any slide content — even if the user doesn't say 'brand' or 'Signatry' by name, as long as the deck is for Signatry. Always pair with the general pptx skill (build mechanics) and, if slide copy/text is being written, the signatry-style skill (voice and terminology)."
version: 1.0
release_date: 2026-07-26
---

# Signatry PowerPoint Brand System

This skill supplies the visual brand layer for The Signatry's slide decks: colors, fonts, and logo usage. It does not duplicate deck-building mechanics or writing style — see **Dependencies** below.

## Definition of done — check before delivering any deck

A deck is not finished when the `.pptx` is written. It is finished when all five of these are true:

1. **Assets loaded from disk.** `ls assets/logos/` was run, and the logo and tab PNGs were passed to `addImage` — not approximated with drawn shapes (see **Logo and mark** below).
2. **Fonts installed** in the sandbox per the bash block under **Fonts**, before any rendering.
3. **`scripts/layout_lint.py` passes** on the built file.
4. **Slides rendered to images and visually inspected.** This is the step that catches missing logos, substituted fonts, and collisions. Do not describe a deck as complete without it.
5. **`scripts/apply_font_fallbacks.py`, then `scripts/embed_fonts.py`** run as the final steps.

Report the outcome of steps 3–5 when delivering the file. If a step was skipped, name which one and why rather than staying silent about it.

## Dependencies — read these first

- **`signatry-brand-core` skill**: canonical colors, fonts, and logo files for The Signatry. This skill mirrors the specific values/files it needs locally and adds pptx-specific mechanics on top — if a color or font ever looks stale here, `signatry-brand-core` is the source of truth, not this file.
- **`pptx` skill**: use for all build mechanics (pptxgenjs script structure, chart gotchas, QA/validation, converting to images). This skill only adds Signatry-specific brand values on top of that workflow.
- **`signatry-style` skill**: use whenever the deck has donor-facing or narrative copy (titles, body text, quotes, CTAs). Apply its terminology, faith-language, and voice rules to on-slide text. Skip it for internal/operational decks per that skill's own scope note.

## Color palette

Mirrored from `signatry-brand-core` (confirmed with Ben, July 2026) — see that skill for the full rationale, including why the older hex values in `signatry-style`'s visual-reference section are superseded. Use these unless Ben specifies otherwise:

| Name | Hex | Typical use |
|---|---|---|
| Legacy | `2b7a78` | Primary — headers, key text, primary shapes |
| Glacier | `37a49f` | Secondary accent |
| Ice | `def2f1` | Light backgrounds, subtle fills |
| Midnight | `17242a` | Body text, dark backgrounds |
| Dusk | `d77900` | Accent/highlight — use sparingly (call-outs, single data series, key stat). Also the donor-audience pair with Dawn (see below). |
| Dawn | `f2a65a` | Gold/amber accent — used specifically for small caps "kicker" labels (eyebrow text above a headline, e.g. "FLEXIBLE GIVING TOOLS"). Distinct from Dusk — don't substitute one for the other. |

Confirmed with Ben (July 2026): **Jubilee** (`8a1e41`) and **Heartfelt** (`fd4a5c`) are additional accent colors, usable sparingly in any context — including decks. (An earlier version of this table called this pair unused/retired from a prior theme and cited a stale hex for Heartfelt, `fd495c` — Ben has confirmed `fd4a5c` is correct.) Note this is a statement about the brand palette generally, not about the 2026 template files specifically: within those four files (see **Reference template files** below — not bundled, for size reasons), the slots that carried this pair in the prior theme were remapped to Glacier/Dusk during the July 2026 migration, so don't expect to find Jubilee/Heartfelt already present if inspecting them — add them deliberately if a deck needs them.

Hex values above are lowercase to match pptxgenjs's expected format (no `#`, no 8-digit alpha — see `pptx` skill gotchas). If this table and `signatry-brand-core`'s ever disagree, treat that as drift to fix, not a choice to make — sync them and flag it to Ben.

### Audience-specific accents (nonprofit and advisor content)

Donor is the default audience, so Dusk/Dawn above already cover it. Confirmed with Ben (July 2026), also mirrored from `signatry-brand-core`, Nonprofit and Advisor each have their own dedicated pair:

| Name | Hex | Audience | Typical use |
|---|---|---|---|
| Passage | `595378` | Nonprofit content | Accent — use minimally |
| Mist | `8c88a3` | Nonprofit content | Accent — use minimally |
| Soar | `68a269` | Advisor content | Accent — use minimally |
| Arctic | `8cb7c9` | Advisor content | Accent — use minimally |

Use these only for decks whose audience is specifically nonprofits or advisors — not as general substitutes for the primary palette above.

### Tints

Every color may be used at a tint (80%, 60%, 40%, 20%, or 5%) per `signatry-brand-core`, which has the formula and full reference table. For pptxgenjs, apply a tint as a literal computed hex color (same lowercase-no-`#` format as the base palette) — not as pptxgenjs's transparency option, which is an alpha effect and will shift appearance depending on what's behind the shape. Pull the exact tint hex from the core table rather than approximating.

## Fonts

Bundled in `assets/fonts/` (mirrored from `signatry-brand-core`, the canonical source for these files):

- **Mulish** — `Regular`, `Medium`, `SemiBold`, `Bold`, `ExtraBold`. Use for all body copy, bullets, captions, and any non-headline text.
- **Lora** — `Regular`, `Medium`, `SemiBold`, `Bold`. Use **Lora Regular only — not bold** for headlines/titles. This is the standing rule for all Signatry decks (confirmed July 2026), not an optional or formal-only pairing.

**Before visual QA (rendering to PDF/images via `soffice`), install the fonts locally so previews reflect real rendering instead of a substituted font:**

```bash
mkdir -p /usr/local/share/fonts/signatry
cp <this-skill's-directory>/assets/fonts/Mulish/*.ttf /usr/local/share/fonts/signatry/
cp <this-skill's-directory>/assets/fonts/Lora/*.ttf /usr/local/share/fonts/signatry/
fc-cache -f
```

(`<this-skill's-directory>` is wherever this SKILL.md was loaded from — check its own path.)

**Caveat on the final `.pptx` file itself:** pptxgenjs sets `fontFace` by name; it does not embed the font file into the package. The deck will render correctly in this sandbox (fonts installed above) and on any machine that already has Mulish/Lora installed, but will silently substitute a fallback font on a machine that doesn't. If the deck needs to look correct on an arbitrary recipient's machine, either (a) tell the recipient to install Mulish/Lora first, (b) deliver a PDF export alongside the `.pptx`, or (c) ask Ben if PowerPoint's native "embed fonts in file" step should be added — this skill does not currently automate font embedding.

## Keeping this skill in sync

The color table and font/logo files in this skill are mirrors of `signatry-brand-core`, not forks. If the canonical values or files change: update `signatry-brand-core` first, then re-copy the affected files here and update this table to match.

## Logo and mark

Bundled in `assets/logos/` (mirrored from `signatry-brand-core`, the canonical source for these files):

| File | Description | Use when |
|---|---|---|
| `logo_color_2C-1.png` (600dpi) / `logo_color_2C.svg` | Full "The Signatry" wordmark + quill, two-color | Light backgrounds (white, Ice) |
| `logo_white_1C.png` | Full wordmark + quill, solid white, one color | Dark or colored backgrounds (Legacy, Midnight, photos) |
| `quill_2color.svg` | Quill mark alone, two-color | Light backgrounds, as a standalone accent/mark |
| `quill_white.svg` | Quill mark alone, white | Dark or colored backgrounds, as a standalone accent/mark |
| `quill_tab_legacy.png` | Corner quill tab, teal | Interior slides on white/Ice backgrounds |
| `quill_tab_midnight.png` | Corner quill tab, dark | Interior slides on photo or colored backgrounds needing contrast |
Usage notes:

- Never alter, recolor, stretch, or rotate the logo or quill artwork (per `signatry-style` skill: don't alter logo text or design).
- "The Signatry" with no tagline is the preferred lockup — that's what's bundled here; don't fabricate a tagline version.
- No official clearspace/minimum-size values are on file for slides — use generous whitespace around the mark (comparable to the mark's own height) and keep it legible at typical presentation viewing distance; confirm exact clearspace with Ben if a client/board-facing deck needs pixel-precise placement.
- python-pptx's `add_picture` cannot read SVG (see `pptx` skill) — use the bundled PNG/rasterized logo for python-pptx workflows, or the SVGs only where the tool chain supports vector (e.g., Canva, HTML/web contexts).
- **Never substitute a drawn shape for a bundled asset.** The corner tab is `quill_tab_legacy.png` or `quill_tab_midnight.png` placed with `addImage` — not a `RECTANGLE` filled with Legacy teal at the same coordinates. The same applies to the wordmark: there is no text-and-shape approximation of the logo. If an asset cannot be found on disk, stop and say so rather than drawing a stand-in.

### Loading the assets into a build

Copy the assets into the working directory before writing the generator script, so the paths in the script are stable and verifiably present:

```bash
mkdir -p ./assets
cp <this-skill's-directory>/assets/logos/*.png ./assets/
ls -la ./assets/    # confirm the files are there before referencing them
```

Then reference them in pptxgenjs:

```javascript
slide.addImage({ path: "./assets/quill_tab_legacy.png", x: 11.7, y: 6.36, w: 0.86, h: 1.15 });
```

`addImage` takes `path` for a local file or `data` for a base64 string; it does not fetch remote URLs.

## How to build a deck: from scratch, in the template style

**Required reading before building any deck: `references/design-system.md`** in this skill. It codifies the visual language of the 2026 Signatry templates — slide archetypes with explicit geometry, the type scale (kicker/headline/body), corner-tab placement, color-scheme variants — plus universal text-placement and spacing standards.

**Build new decks from scratch with pptxgenjs following that design system. Do NOT duplicate-and-edit slides from the bundled template files.** The templates carry stale PowerPoint autofit scale factors (`<a:normAutofit fontScale=.../>`) computed for their original Arial text; with the current fonts or any new copy, those cause text overflow and element collisions. Building fresh with explicit font sizes avoids that entire failure class.

## Reference template files (not bundled — size constraint)

The four original 2026 template files (`Signatry_PPT_2026_Legacy/Midnight/Dawn/Master.pptx`) are **not included in this skill package** — at ~34–60MB each (~185MB total, mostly embedded photography) they pushed the package over Claude.ai's upload/download limits. Everything in `references/design-system.md` (the archetypes, geometry, type scale) was captured directly from those files, so the skill still fully reflects their visual language without needing them present.

Two ways to get their photography back for reuse, if needed:
1. **Ask Ben to re-upload them in a conversation** — Claude can extract photos from `ppt/media/` on the spot and use them in the current build.
2. **Re-attach them to the skill later** if the size constraint is resolved (e.g. a Team/Enterprise plan or a higher upload limit) — drop the four files into `assets/templates/` and repackage.

Until then, decks built from this skill need photography supplied by the user per request (see the donor-content guardrail below — donor-specific photos/quotes are on hold pending Ben's team's decision either way).

## Confidentiality guardrail

Do not source content for these decks from anything marked confidential, board-only, or privileged, or from board agendas/financials/succession planning — per organization policy, that content should not be processed here at all. If a deck's source material includes it, stop and flag it rather than continuing.

## Donor content guardrail (photos and quotes)

**Never fabricate a donor quote, testimonial, or named "donor" persona to fill a slide.** A quote attributed to a real name is a specific factual claim about what that person said — inventing one, or inventing a generic unnamed "donor" quote to sound authentic, is misrepresentation, not a stylistic shortcut. If no approved quote is available for a deck, use a scripture reference or a thematic pull-quote instead (see archetype F/I), never a synthetic testimonial.

**Reuse of existing named donor photos/quotes (from the bundled templates or elsewhere) is on hold pending an internal decision from Ben's team** on donor consent scope — whether a donor's story/photo/quote approved for one piece may be reused in others. Until that's resolved:
- Treat every donor-attributed photo and quote in the bundled templates as tied to its original slide/context only — don't repurpose Krista Roland's, Brian Roland's, or Michael Sollazzo's photos or quotes onto new, unrelated slides.
- Generic, unnamed lifestyle/nature photography (no story or name attached) is fine to reuse freely.
- If a deck needs a donor story and none is supplied, ask Ben rather than substituting a bundled one.
