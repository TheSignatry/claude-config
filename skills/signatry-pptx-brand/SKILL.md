---
name: signatry-pptx-brand
description: "Signatry brand system for PowerPoint decks: color palette, fonts (Mulish, Lora), and logo/quill assets for The Signatry. Use this skill for ANY request to create, build, generate, edit, restyle, or review a .pptx presentation or slide deck in this organization — including plain, generic phrasing with no mention of 'brand,' 'Signatry,' colors, or a template, such as 'create a presentation,' 'make me a deck,' 'build a PowerPoint about X,' or 'add a slide.' This skill is deployed org-wide for The Signatry; every deck built in this environment (Claude.ai, Claude Code, or the Claude for PowerPoint add-in) is a Signatry deck by default unless the user explicitly says otherwise (e.g., a competitor mockup or an intentionally unbranded draft). Do not wait for brand-specific language before applying this skill. Always pair with the general pptx skill (build mechanics) and, if slide copy/text is being written, the signatry-style skill (voice and terminology)."
version: 2.4
release_date: 2026-08-07
---

# Signatry PowerPoint Brand System

This skill supplies the visual brand layer for The Signatry's slide decks: colors, fonts, and logo usage. It does not duplicate deck-building mechanics or writing style — see **Dependencies** below.

## Definition of done — check before delivering any deck

A deck is not finished when the `.pptx` is written. It is finished when all eight of these are true:

1. **Title-slide photo checked before building slide 1.** If slide 1 uses archetype A, run `scripts/title_photo_check.py <candidate-photo>` on the chosen photo before placing it — not after the deck is built. On FAIL, either pick a different photo or switch that slide's overlay to Midnight (see design-system.md archetype A). This step exists because the check is easy to skip when a photo is chosen mid-conversation rather than at build time — do it at selection time regardless.
2. **Every photo containing a person or clear subject was viewed before cropping, not blind-center-cropped.** Use `scripts/crop_photo.py` with `center_x`/`center_y` set to the subject's actual position (see design-system.md standard #4), then re-view the cropped output to confirm the subject isn't cut off at an edge. Reserve the script's default center for photos with no off-center subject.
3. **Assets loaded from disk.** `ls assets/logos/` was run, and the logo and tab PNGs were passed to `addImage` — not approximated with drawn shapes (see **Logo and mark** below).
4. **Fonts installed** in the sandbox per the bash block under **Fonts**, before any rendering.
5. **`scripts/layout_lint.py` passes** on the built file.
6. **`scripts/image_ratio_check.py` passes** on the built file — catches any placed image (logo, icon, or photo) whose w/h doesn't match its native pixel aspect ratio, i.e. anything distorted. Run this regardless of how confident the placement looked when it was built.
7. **Slides rendered to images and visually inspected.** This is the step that catches missing logos, substituted fonts, clipped subjects, and collisions. Do not describe a deck as complete without it.
8. **`scripts/apply_font_fallbacks.py`, then `scripts/embed_fonts.py`** run as the final steps.

Report the outcome of steps 1, 2, 5, 6, and 8 when delivering the file. If a step was skipped, name which one and why rather than staying silent about it.

The scripts referenced above ship in `scripts/` in this skill. `references/design-system.md` documents what each one does and how to invoke it.

## Dependencies — read these first

- **`signatry-brand-core` skill**: canonical colors, fonts, and logo files for The Signatry. This skill mirrors the specific values/files it needs locally and adds pptx-specific mechanics on top — if a color or font ever looks stale here, `signatry-brand-core` is the source of truth, not this file.
- **`pptx` skill**: use for all build mechanics (pptxgenjs script structure, chart gotchas, QA/validation, converting to images). This skill only adds Signatry-specific brand values on top of that workflow.
- **`signatry-style` skill**: use whenever the deck has donor-facing or narrative copy (titles, body text, quotes, CTAs). Apply its terminology, faith-language, and voice rules to on-slide text. Skip it for internal/operational decks per that skill's own scope note.
- **`signatry-facts` skill**: use whenever a slide will state a factual value about The Signatry — contact info, entity/leadership names, history, figures, fund terms, or boilerplate/disclaimers. Load it on any build; don't supply these values from recall.
- **`signatry-content-guardrails` skill**: content restriction rules (fabrication prohibition, donor photo/quote reuse, gift-amount confidentiality, board-only source restriction) — independent of format, load on any build. See that skill rather than looking for these rules here.
- **`signatry-photo-library` skill**: the 44-image catalog and `scripts/find_photos.py`. Search it for any deck photography before asking the user or using a placeholder. Reuse of donor-family images is gated by `signatry-content-guardrails`.
- **`signatry-icons` skill**: the 69-icon brand set. Use it if a slide needs an icon — do not draw substitutes or pull outside icon sets.

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

**Caveat on the final `.pptx` file itself:** pptxgenjs sets `fontFace` by name; it does not embed the font file into the package. Left at that, the deck renders correctly in this sandbox (fonts installed above) and on any machine that already has Mulish/Lora installed, but silently substitutes a fallback font on a machine that doesn't.

**This skill automates the fix — it is step 8 of Definition of done, not optional.** Run `scripts/apply_font_fallbacks.py <deck.pptx>` and then `scripts/embed_fonts.py <deck.pptx>` as the final build steps; `embed_fonts.py` uses the same OOXML mechanism as PowerPoint's own "embed fonts in this file" option. See `references/design-system.md` step 11 for what each script does and its verification caveat (LibreOffice ignores PPTX embedded fonts, so embedding cannot be end-to-end verified in the sandbox).

Residual risk after running both: if a delivered deck still shows wrong fonts in PowerPoint, fall back to telling the recipient to install Mulish/Lora (both free on Google Fonts) or delivering a PDF export alongside the `.pptx`.

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
- **Clearspace:** per `signatry-brand-core`, minimum clearspace on all sides of the logo equals the height of the letter "n" in the "Signatry" wordmark, measured from that same logo. This is the floor, not a target — more is always fine. Measure the n-height off the actual asset at the size you are placing it; do not assume a fixed inch value, since it scales with the logo. The corner tab is a bleed element and is exempt — it is designed to sit flush to the slide edge, and its reserved zone (11.5, 6.1)–(13.33, 7.5) is defined in `references/design-system.md` instead.
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

**Required reading before building any deck: `references/design-system.md`** in this skill. It codifies the visual language of the 2026 Signatry templates — the universal (every-deck) archetypes A and B-title, the type scale (kicker/headline/body), corner-tab placement, color-scheme variants — plus universal text-placement and spacing standards. **For interior content slides, also load `references/archetype-library.md`** and pick only the archetype(s) a given slide's content actually needs (narrative + photo, numbered steps, a quote, a stat block, and more) rather than reading the full library start to finish.

**Build new decks from scratch with pptxgenjs following that design system. Do NOT duplicate-and-edit slides from the bundled template files.** The templates carry stale PowerPoint autofit scale factors (`<a:normAutofit fontScale=.../>`) computed for their original Arial text; with the current fonts or any new copy, those cause text overflow and element collisions. Building fresh with explicit font sizes avoids that entire failure class.

Every deck's first and last slides are fixed, not content slides: slide 1 is archetype A (full-bleed photo + overlay + logo, no text of any kind — watch for green-dominant photos compounding with the teal overlay), slide 2 is the Title/Closing archetype (archetype B-title) carrying the deck title and related info, content runs from slide 3 through the second-to-last slide, and the deck's final slide is archetype B-title again — a "Thank You" close, not just an option to add on request. This holds regardless of overall deck length unless the user states an explicit slide-count constraint that can't fit it (see "Opening/Closing sequence" in `references/design-system.md` for how to handle that case).

## Reference template files

`TheSignatry2026.pptx` is bundled at `assets/templates/` (Aug 2026, ~6.5MB), replacing the earlier `.potx` version of the same deck and, before that, `Signatry_PPT_2026_Master_optimized.pptx`. It's a 27-slide deck built entirely with placeholder (lorem ipsum) copy — unlike the original Master file, which mixed real donor-story content into the reference slides — organized as four repeating demo sections (Legacy, Midnight, Dawn-orange, and a fourth), each opening with a Title slide and closing with a "Thank You" slide around a run of content-layout examples. Treat it as a **style reference and photo library**, not a build base — the "Opening/Closing sequence" and title/closing archetype in design-system.md were captured from it, and its own slides carry the same stale-autofit caveat as any template (see design-system.md's opening note). Its `ppt/media/` photography is available for reuse via the same extraction approach as any template file.

Photography for decks comes from the `signatry-photo-library` skill — search it with `scripts/find_photos.py` before asking the user. If this template's photography is needed instead, extract from its `ppt/media/`. Ask the user only when neither source has a fit.

## Content guardrails

Fabrication rules (never invent a fact or a donor quote), donor photo/quote reuse rules, gift-amount confidentiality, and the confidentiality/board-only source restriction have moved to a dedicated `signatry-content-guardrails` skill, shared across all format skills (pptx, docx, pdf) rather than duplicated in each. Load that skill on any build — see **Dependencies** above.

See `_exclude/CHANGELOG.md` for this skill's revision history.
