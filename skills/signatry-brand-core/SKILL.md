---
name: signatry-brand-core
description: "Canonical source of truth for The Signatry's brand colors, fonts, and logo/mark assets — independent of file format. Use this whenever a task needs the actual hex values, font files, or logo files for The Signatry, or when building/updating a format-specific brand skill (pptx, docx, pdf, xlsx, HTML/artifacts, Canva, etc.). Format-specific brand skills should depend on this one for values and assets rather than restating them; this skill has no build mechanics of its own."
---

# The Signatry Brand Core

This skill is the single canonical record of The Signatry's visual brand: colors, fonts, and logo/mark files. It intentionally contains no format-specific build mechanics — those live in per-format skills (`signatry-pptx-brand`, `signatry-docx-brand`, `signatry-pdf-brand`, and any future format skill) that depend on this one.

**Why this skill exists:** before it, colors and fonts were independently restated inside `signatry-pptx-brand`, `signatry-docx-brand`, and `signatry-style`. They had already drifted — `signatry-pptx-brand` had wrongly recorded Jubilee/Heartfelt as a retired theme pair (with an incorrect hex for Heartfelt), while `signatry-style` still carried an older table that predated the July 2026 confirmations. Centralizing here gives one place to update when the brand changes, instead of hunting down every skill that copied the numbers.

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

Note: an earlier draft of `signatry-pptx-brand` referred to this pair as an unused `8A1E41`/`FD495C` combination from a retired theme. `FD495C` was a stale/incorrect value — Ben has confirmed `fd4a5c` is the correct hex for Heartfelt.

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

- **Mulish** — use for body copy, bullets, captions, and any non-headline text. Weights bundled: Regular, Medium, SemiBold, Bold, ExtraBold.
- **Lora** — use for headlines/titles. Weights bundled: Regular, Medium, SemiBold, Bold. The standing rule confirmed for all documents (July 2026) is **Lora Regular only — not bold — for headlines**.

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

Confirmed with Ben (July 2026): every color above may be used at a tint — 80%, 60%, 40%, 20%, or 5% — as needed, matching usage visible on thesignatry.com. (This formula wasn't reverse-engineered from the site's own CSS — I didn't have a way to pull that directly — so it's the standard tint convention below; flag to Ben if a specific piece needs to match a pixel-sampled site color exactly rather than this formula.)

**Definition:** a tint is the base color mixed with white. The percentage is how much of the base color survives — 100% is the full color, 0% is pure white. Formula per channel (R, G, or B, 0–255):

```
tinted_channel = round(255 + (base_channel - 255) * (percent / 100))
```

**Reference table** (all values lowercase hex, no `#`, generated with the formula above and spot-checked against `pypdf`/reportlab rendering):

| Color | 100% (base) | 80% | 60% | 40% | 20% | 5% |
|---|---|---|---|---|---|---|
| Legacy | `2b7a78` | `559593` | `80afae` | `aacac9` | `d5e4e4` | `f4f8f8` |
| Glacier | `37a49f` | `5fb6b2` | `87c8c5` | `afdbd9` | `d7edec` | `f5fafa` |
| Ice | `def2f1` | `e5f5f4` | `ebf7f7` | `f2faf9` | `f8fcfc` | `fdfefe` |
| Midnight | `17242a` | `455055` | `747c7f` | `a2a7aa` | `d1d3d4` | `f3f4f4` |
| Dusk | `d77900` | `df9433` | `e7af66` | `efc999` | `f7e4cc` | `fdf8f2` |
| Dawn | `f2a65a` | `f5b87b` | `f7ca9c` | `fadbbd` | `fcedde` | `fefbf7` |
| Jubilee | `8a1e41` | `a14b67` | `b9788d` | `d0a5b3` | `e8d2d9` | `f9f4f6` |
| Heartfelt | `fd4a5c` | `fd6e7d` | `fe929d` | `feb7be` | `ffdbde` | `fff6f7` |
| Passage | `595378` | `7a7593` | `9b98ae` | `bdbac9` | `dedde4` | `f7f6f8` |
| Mist | `8c88a3` | `a3a0b5` | `bab8c8` | `d1cfda` | `e8e7ed` | `f9f9fa` |
| Soar | `68a269` | `86b587` | `a4c7a5` | `c3dac3` | `e1ece1` | `f7faf8` |
| Arctic | `8cb7c9` | `a3c5d4` | `bad4df` | `d1e2e9` | `e8f1f4` | `f9fbfc` |

Notes:
- Ice is already very light, so its tints converge on near-white quickly — expected, not an error.
- Recompute rather than eyeball if a color or its base hex ever changes here; the table above is a snapshot, not itself the source of truth (the formula + base hex table above it are).
- Format skills (`signatry-pptx-brand`, `signatry-pdf-brand`, `signatry-docx-brand`) should apply tints as literal computed hex values, not as an opacity/alpha effect — a tint is a lighter *opaque* color, not a transparent one. Don't confuse the two: alpha transparency lets whatever is behind a shape show through and shifts appearance depending on background; a tint is a fixed, computed color that looks the same on any background.

## Consumers of this skill

Format-specific skills that should depend on this one for values/assets rather than restating them:

- `signatry-pptx-brand` — decks (pptxgenjs)
- `signatry-docx-brand` — Word documents (docx templates)
- `signatry-pdf-brand` — PDFs (reportlab)

Any new format skill (xlsx charts, HTML/artifact work, Canva) should follow the same pattern: pull colors/fonts/logos from here, add only the format-specific mechanics of applying them (embedding, registration, style definitions, QA rendering).

## What's still known to be out of scope here

- Voice, tone, and terminology (donors not givers, DAF capitalization, scripture format, etc.) — see `signatry-style`. That skill's Section 9 (visual/formatting references) now defers to this skill for colors and fonts; it still owns the logo-text and book-link rules that aren't duplicated here.
- Confidentiality/donor-content guardrails for specific deliverables (e.g., deck donor photo reuse) — those live in the format skill that produced the original guardrail (currently `signatry-pptx-brand`), since they're tied to specific bundled source material, not to brand values.
