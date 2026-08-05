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

## Revision history

**July 31, 2026 — v3.4, EMF dropped; PNG-512 is now the Office format.** Per request, `emf/glacier/` and `emf/white/` (138 files) were removed from disk, along with the `emf_glacier`/`emf_white` columns in `icon_catalog.csv` and the `emf` format option in `find_icons.py`. Rationale: at the sizes these icons are actually placed (roughly 0.5–1.2 in), a 512px PNG already exceeds print-quality PPI, so the vector precision of EMF bought little in practice — while EMF carries real, documented cross-platform risk (Word/PowerPoint for Mac has known blurred/garbled EMF rendering in some builds; Google Slides/Docs requires a conversion step to import EMF at all). PNG, by contrast, renders identically everywhere. `signatry-docx-brand`'s "Placing an icon" section was updated to embed PNG (via a `blipFill` referencing a PNG relationship) instead of the EMF drawing XML. `svg` is unaffected. Net effect on this skill: 279 files → 141, and no format skill lost real capability — Office builds move from EMF to PNG, which was already the documented fallback for anything that chokes on vector.

**July 31, 2026 — v3.3 (superseded), file count reduced via archive.** An earlier pass kept EMF and instead dropped `png_128/glacier/` and packed `png_512/glacier/` into a zip extracted on demand. That approach is superseded by v3.4: dropping EMF outright made the archive trick unnecessary, and a zip-in-zip isn't accepted by all skill upload pipelines. `png_512` now ships as 69 plain files again.

**July 31, 2026 — v3.2, non-Glacier baked variants removed.** Per request, the second baked color was dropped from disk: `emf/white/` (69 files), `png_512/white/` (69 files), and `png_128/white/` (69 files), along with the matching columns in `icon_catalog.csv` and the `--color` option in `find_icons.py`. `svg` is unaffected — it still recolors to any value, including a light color for dark backgrounds, via the root `color` override documented above.

**July 31, 2026 — v3.0, converted out of EPS.** The library was EPS-only, which is why no format skill could place an icon: Microsoft turned off EPS insertion in Office by default with the April 2017 security update and removed the registry workaround in May 2018 for Microsoft 365 and Office 2019. There is no supported way to insert EPS into current Office. Converted to SVG, EMF, and PNG (512 and 128).

Verified on intake: 69 files in every one of the seven sets that existed at conversion time, filename stems identical across all sets and matching the previous EPS set exactly; all SVG paths `fill:currentColor` under a root `color`; 901 fill records in each EMF set, matching the 901 `currentColor` instances in the SVGs; all PNGs RGBA with transparency; sampled opaque pixels matched the expected color per set; no trace of the stale `3aafa9` in any file; all 69 rendered and visually inspected.

**EPS masters are no longer bundled.** They were 29.2 MB, of which the actual vector artwork was 0.61 MB — 2.1%. The rest was Illustrator round-trip data and embedded XMP preview thumbnails. Keep the EPS originals archived in SharePoint as the designer source; SVG is the working master here.

**Color correction, now closed.** The EPS masters drew in the correct Glacier `37a49f` but carried a stale `3aafa9` in their XMP swatch metadata, so an earlier note claiming the correction was fully verified was only half right — the artwork was checked, the metadata was not. The converted files carry no swatch metadata, so the discrepancy is gone rather than fixed.

**Catalog rebuilt** as `icon_catalog.csv` from the prior `icon_catalog.xlsx`. The spreadsheet held 70 rows for 69 icons: an instructional example row duplicated the real `Cross` entry. The duplicate was dropped and per-variant paths added. The original `.xlsx` is not bundled.

**Earlier history.** A 78-icon set was trimmed to 69 on July 31, 2026 to fit a 30 MB size target — removing Ministry, Globe, Financial-Advisors, Open-Fund, Complex-Assets, No-IRS, Selling-Assets, Single-Report, and Digital as conceptual near-duplicates of icons that remain. That constraint no longer applies: this skill is now well under that target with the remaining variant sets. **If the 78-icon originals still exist, the nine can be restored.** One caveat if they are: `Complex-Assets` uses a term `signatry-style` marks deprecated in favor of "nonliquid" — rename on the way in.

Before the trim, the set had been consolidated from four libraries (one one-color plus three audience-specific two-color sets using Dawn, Mist, and Arctic) down to a single library, per Ben.

## Still open

1. **Restore the nine trimmed icons**, if the 78-icon source survives.
2. **No tinted or alternate-color PNG variants.** Only Glacier is on disk. SVG recolors to any tint; Word and PowerPoint would need a new export. Raise it if a deliverable actually needs one.
3. **No vector format for Office.** EMF was dropped in v3.4; Word/PowerPoint builds now use PNG, which is fine at this set's normal placement sizes but not infinitely scalable. Raise it if a deliverable needs a Signatry icon significantly larger than ~3 in in Word or PowerPoint.
