# Changelog

All notable changes to this skill are documented here, newest first.

## 3.4 — 2026-07-31, EMF dropped; PNG-512 is now the Office format

Per request, `emf/glacier/` and `emf/white/` (138 files) were removed from disk, along with the `emf_glacier`/`emf_white` columns in `icon_catalog.csv` and the `emf` format option in `find_icons.py`. Rationale: at the sizes these icons are actually placed (roughly 0.5–1.2 in), a 512px PNG already exceeds print-quality PPI, so the vector precision of EMF bought little in practice — while EMF carries real, documented cross-platform risk (Word/PowerPoint for Mac has known blurred/garbled EMF rendering in some builds; Google Slides/Docs requires a conversion step to import EMF at all). PNG, by contrast, renders identically everywhere. `signatry-docx-brand`'s "Placing an icon" section was updated to embed PNG (via a `blipFill` referencing a PNG relationship) instead of the EMF drawing XML. `svg` is unaffected. Net effect on this skill: 279 files → 141, and no format skill lost real capability — Office builds move from EMF to PNG, which was already the documented fallback for anything that chokes on vector.

## 3.3 — 2026-07-31 (superseded), file count reduced via archive

An earlier pass kept EMF and instead dropped `png_128/glacier/` and packed `png_512/glacier/` into a zip extracted on demand. That approach is superseded by v3.4: dropping EMF outright made the archive trick unnecessary, and a zip-in-zip isn't accepted by all skill upload pipelines. `png_512` now ships as 69 plain files again.

## 3.2 — 2026-07-31, non-Glacier baked variants removed

Per request, the second baked color was dropped from disk: `emf/white/` (69 files), `png_512/white/` (69 files), and `png_128/white/` (69 files), along with the matching columns in `icon_catalog.csv` and the `--color` option in `find_icons.py`. `svg` is unaffected — it still recolors to any value, including a light color for dark backgrounds, via the root `color` override documented above.

## 3.0 — 2026-07-31, converted out of EPS

The library was EPS-only, which is why no format skill could place an icon: Microsoft turned off EPS insertion in Office by default with the April 2017 security update and removed the registry workaround in May 2018 for Microsoft 365 and Office 2019. There is no supported way to insert EPS into current Office. Converted to SVG, EMF, and PNG (512 and 128).

Verified on intake: 69 files in every one of the seven sets that existed at conversion time, filename stems identical across all sets and matching the previous EPS set exactly; all SVG paths `fill:currentColor` under a root `color`; 901 fill records in each EMF set, matching the 901 `currentColor` instances in the SVGs; all PNGs RGBA with transparency; sampled opaque pixels matched the expected color per set; no trace of the stale `3aafa9` in any file; all 69 rendered and visually inspected.

**EPS masters are no longer bundled.** They were 29.2 MB, of which the actual vector artwork was 0.61 MB — 2.1%. The rest was Illustrator round-trip data and embedded XMP preview thumbnails. Keep the EPS originals archived in SharePoint as the designer source; SVG is the working master here.

**Color correction, now closed.** The EPS masters drew in the correct Glacier `37a49f` but carried a stale `3aafa9` in their XMP swatch metadata, so an earlier note claiming the correction was fully verified was only half right — the artwork was checked, the metadata was not. The converted files carry no swatch metadata, so the discrepancy is gone rather than fixed.

**Catalog rebuilt** as `icon_catalog.csv` from the prior `icon_catalog.xlsx`. The spreadsheet held 70 rows for 69 icons: an instructional example row duplicated the real `Cross` entry. The duplicate was dropped and per-variant paths added. The original `.xlsx` is not bundled.

**Earlier history.** A 78-icon set was trimmed to 69 on July 31, 2026 to fit a 30 MB size target — removing Ministry, Globe, Financial-Advisors, Open-Fund, Complex-Assets, No-IRS, Selling-Assets, Single-Report, and Digital as conceptual near-duplicates of icons that remain. That constraint no longer applies: this skill is now well under that target with the remaining variant sets. **If the 78-icon originals still exist, the nine can be restored.** One caveat if they are: `Complex-Assets` uses a term `signatry-style` marks deprecated in favor of "nonliquid" — rename on the way in.

Before the trim, the set had been consolidated from four libraries (one one-color plus three audience-specific two-color sets using Dawn, Mist, and Arctic) down to a single library, per Ben.
