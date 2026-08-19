---
name: signatry-icons
description: "The Signatry's brand icon library — 69 single-color icons in SVG and PNG, in Glacier, with a searchable catalog and a search script. Use this whenever a Signatry deliverable needs an icon: decks, documents, PDFs, one-pagers, web and artifact work, or Canva. Trigger even when the user does not say 'icon' by name — if a slide needs a visual marker beside a stat, a document needs a section glyph, or a layout would otherwise get a drawn shape or an outside icon set, search here first. Depends on `signatry-brand-core` for color values; this skill owns the icon files themselves, not the palette."
version: 3.4
release_date: 2026-07-31
---

# The Signatry Icon Library

69 single-color icons, each available in two formats, catalogued by what they depict.

This is the icon counterpart to `signatry-brand-core`: that skill owns colors, fonts, and logos; this one owns icons. Neither contains build mechanics — those live in the format skills.

**Use these instead of drawing shapes, pulling from an outside icon set, or leaving a placeholder.**

## Which file to use

| Building | Format | Why |
|---|---|---|
| Word, PowerPoint | `png_512` | Universal, renders identically on every version and platform of Office — Windows, Mac, and web. |
| PDF (reportlab) | `png_512`, or `svg` via `svglib` | reportlab reads raw SVG only with help |
| HTML, artifacts, Canva | `svg` | Native, and recolorable |
| Anything that chokes on vector | `png_512` | Universal fallback — downscale it for small marks rather than looking for a smaller baked size |

**Color:** `png_512` is baked in `glacier` (`37a49f`) only, for use on light backgrounds — light backgrounds, Ice, light tints. If a deliverable needs a light-colored mark on a dark or colored background (Legacy, Midnight, photographs), use `svg` and override its color (see below) — there is no baked light-color PNG variant on disk.

```
assets/icons/
├── svg/                 69 — Glacier default, recolorable to anything
└── png_512/glacier/     69      512×512, RGBA, transparent
```

## Finding an icon

Use the search script rather than browsing folders or reading the catalog into context:

```bash
python3 scripts/find_icons.py -k generosity
python3 scripts/find_icons.py -k family giving --match any
python3 scripts/find_icons.py --name Advisor --format png_512
python3 scripts/find_icons.py -k stewardship --output paths --format svg
python3 scripts/find_icons.py --list
```

Useful flags: `--match any` (loosen an over-narrow search), `--exclude`, `--limit`, `--output paths` (bare absolute paths for a build script).

The catalog is `assets/icon_catalog.csv` — one row per icon, with a plain-language description of what it depicts and the path to every variant. Search on meaning, not filename: the icon for corporate giving is named `Business-Interest`, and `Kingdom` depicts a crown.

**Pick by what the icon shows, not by what its name suggests.** Descriptions were written from the artwork. `Generosity` is a box of groceries, not a heart; if a layout needs a heart, that is `Generosity (Lifestyle)`.

## Only one SVG set exists, and that is deliberate

Every SVG carries `style="color:#37a49f"` on the root and `fill:currentColor` on every path. Overriding one property recolors the whole icon:

```html
<!-- a light tint on a Midnight panel -->
<svg style="color:#d5e4e4" viewBox="0 0 110 110">…</svg>

<!-- or inherit from a parent -->
<div style="color:#d5e4e4"><svg viewBox="0 0 110 110">…</svg></div>
```

Verified by rendering: the same file produces Glacier, Midnight, or any tint from `signatry-brand-core` with identical geometry. So there is no separate color-specific SVG folder — recoloring means editing one attribute.

Note the mechanism only works for **inline** SVG or SVG referenced by `<use>`. An SVG loaded through `<img src>` is an isolated document and will not inherit `color`; inline it, or edit the root attribute in the file.

PNG bakes the color in, which is why Glacier exists as its own fixed set of files for that format.

## Tints

Any tint from `signatry-brand-core` works in SVG via the same override — pull the computed hex from that skill's reference table and set it as `color`. Do not use opacity to fake a tint; a tint is an opaque lighter color, and opacity will let the background show through.

For PNG, only Glacier exists on disk. If a deliverable genuinely needs a different baked color in Word or PowerPoint, ask rather than approximating with transparency.

## Scaling limit for `png_512`

At 512×512px, an icon holds print quality (≥220 PPI) up to roughly 2.3 in and screen quality well beyond that. Past about 2.5–3 in, regenerate at higher resolution from the SVG rather than stretching the existing PNG — this set is sized for small marks (stat glyphs, section icons), not hero-sized graphics.

## Format skills

Each format skill owns its own placement mechanics; this skill owns only the files.

- `signatry-pptx-brand` — declares this skill as a dependency. Use `png_512` with `addImage`. pptxgenjs encodes SVG but PowerPoint renders it only on current versions.
- `signatry-docx-brand` — declares this skill as a dependency and documents the PNG embed (content-type registration, relationship, drawing XML, EMU sizing). Verified end to end.
- `signatry-pdf-brand` — declares this skill as a dependency and documents both the `png_512` and `svglib` paths. Both verified against reportlab 4.4.10.

See `_exclude/CHANGELOG.md` for this skill's revision history.

## Still open

1. **Restore the nine trimmed icons**, if the 78-icon source survives.
2. **No tinted or alternate-color PNG variants.** Only Glacier is on disk. SVG recolors to any tint; Word and PowerPoint would need a new export. Raise it if a deliverable actually needs one.
3. **No vector format for Office.** EMF was dropped in v3.4; Word/PowerPoint builds now use PNG, which is fine at this set's normal placement sizes but not infinitely scalable. Raise it if a deliverable needs a Signatry icon significantly larger than ~3 in in Word or PowerPoint.
