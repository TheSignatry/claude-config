---
name: signatry-photo-library
description: "The Signatry's curated image library — 44 photographs covering donor families, stock lifestyle, and landscape/nature imagery — with a searchable catalog and a search script. Use this whenever a Signatry deliverable needs a photograph: decks, one-pagers, reports, letterhead pieces, flyers, fund summaries, web/artifact mockups, or anything else calling for imagery. Trigger even when the user does not say 'photo', 'image', or 'library' by name: if a slide needs a hero image, a report needs a section opener, or a document would benefit from a portrait or backdrop, search here first rather than using placeholder boxes, outside stock, or generated images. Pair with signatry-brand-core for colors/fonts/logos and with the relevant format skill for build mechanics."
version: 2.1
release_date: 2026-07-31
---

# The Signatry Photo Library

44 curated images available for Signatry deliverables, catalogued with keywords, orientation, dimensions, and dominant colors.

This is the image counterpart to `signatry-brand-core`: that skill owns colors, fonts, and logos; this one owns photography. Neither contains build mechanics — those live in the format skills.

**Use these images instead of reaching for outside stock, generated images, or grey placeholder rectangles.**

## What is in the library

| Source | Count | Content |
|---|---|---|
| iStock | 21 | Licensed nature and landscape — fields, water, forests, aerial views, botanical close-ups |
| Donor | 17 | Signatry donor families: Almirola (4), Roland (3), McGowan (2), Clark (2), Roberts (2), Snyder (2), Trogden (2) |
| Unsplash | 6 | Landscape and nature — mountains, roads, seasonal close-ups; photographer credited in the catalog |

Files are organised on disk to make the donor/stock distinction structural, because different rules apply to each:

```
assets/photos/
├── donor/<Family>/     17 photos — attribution rule applies
└── stock/              27 photos — licensing terms apply
```

37 are landscape, 7 portrait; most are 3:2. All are JPEG, none exceeding 2048px on the longest edge.

**The library divides cleanly into people and nature, with nothing between.** All 17 donor images show identifiable people; all 27 stock images are nature and landscape, only one containing any human element (a pair of cupped hands, no face). There is no generic people photography here — no anonymous business, office, or lifestyle imagery. When a piece needs a human subject, it must come from the donor set, and the attribution rule below governs it.

## Finding an image

Use the search script rather than browsing folders or reading the whole catalog into context:

```bash
python3 scripts/find_photos.py --keywords family outdoor
python3 scripts/find_photos.py --family Roland          # one donor family
python3 scripts/find_photos.py --source stock           # exclude donor imagery
python3 scripts/find_photos.py -k mountains --format paths
python3 scripts/find_photos.py --list                   # counts by source and family
```

Useful flags: `--match any` (loosen an over-narrow search), `--exclude`, `--orientation`, `--aspect 3:2`, `--min-width`, `--limit`, and `--format paths` (bare absolute paths for a build script) or `--format csv`.

The catalog is `assets/photo_catalog.csv`. Columns: Photo ID, File Name, Source, Family, Photographer, Relative Path, Description, Keywords, Orientation, Aspect Ratio, Width, Height, Capture Date, Dominant Colors.

**Verify before placing.** When an image carries real weight — a cover, a full-bleed hero, anything a donor or board member will look at directly — open the file and confirm it shows what the piece needs. A description mentioning "family outdoors" does not tell you whether the composition leaves room for a headline.

## Donor imagery: attribution integrity

**Clearance is not a check to perform.** Every photograph here is already cleared for use — The Signatry obtains clearance before photographing a donor (confirmed by Ben Martin, 2026-07-31; see `signatry-content-guardrails` §3 and `signatry-facts` `reference/stories.md`). Donor photos may be used in donor-facing, internal, advisor, and nonprofit material without confirming a release, and no release records are kept.

**What still applies is an accuracy rule, not a permissions one: never pair a donor's photograph with another donor's story, quote, or name.** If a layout puts a photo and an attributed story on the same page, spread, or slide, they must be the same family. Getting this wrong misrepresents real people to an audience that may know them.

- When a piece supplies a named story or pull-quote, search by `--family` — not by visual fit.
- If the needed family has no photo here, that is a gap in this library, not a permissions problem. Ask whether one exists elsewhere rather than substituting a visually similar family.
- Unattributed use is unrestricted: a Roland photo can open a section on generosity with no name attached.
- When a photo and a name appear near each other, state in your summary which family the photo depicts, so the pairing is checkable at review.

This rule does not apply to `--source stock` imagery, which depicts no Signatry donor.

**Note the consequence, because it constrains layouts:** stock cannot stand in for a person. If a piece carries one family's story and needs a human image, the only compliant options are that family's own photos or no photo at all — a nature image, an illustration, or a type-led layout. Do not reach for a different family's photo to fill the space. If the piece truly needs a face this library cannot supply, say so rather than improvising.

**Known gap.** Four families with published long-form stories in `signatry-facts` — Hodgdon, Kouplen, Joyner, and Gardner — have no photographs in this library. Roland is the only family with both. A deliverable built around one of those four stories currently has no compliant human image available here; ask whether photography exists outside this library before designing around a portrait.

One donor image is self-identifying: `SnyderFeature (37 of 41).jpg` includes a visible "Welcome the Snyders" sign. It can never appear alongside another family's story, even unattributed.

## Stock imagery: licensing

- **iStock** images are licensed content. Standard iStock licenses cover marketing and promotional use. The set is nature and landscape only, so the usual model-release and endorsement concerns do not arise — but do not present a stock landscape as a specific Signatry property, project site, or grant location unless that is actually where it was taken.
- **Unsplash** images carry the Unsplash License, which permits commercial use without required attribution. Photographer names are recorded in the catalog's Photographer column; crediting is optional but appreciated, and worth including where layout allows.
- If a piece is going to paid placement, out-of-home, or anything beyond standard marketing collateral, confirm license scope before use.

## Using images in layouts

Pull colors, fonts, and logo files from `signatry-brand-core`; the notes below cover only what is specific to placing photographs.

**Logo over imagery.** Use `logo_white_1C.png` (or `quill_white.svg`) on photographs — never the two-color logo, which loses legibility against a varied background. Brand-core's clearspace rule still applies.

**Text over imagery.** Do not set type directly on an unmodified photograph. Either overlay Midnight (`17242a`) at 40–60% opacity across the photo or the portion behind the text and set type in white, or place the text in an adjacent solid or Ice (`def2f1`) panel. This is one of the few places where genuine alpha transparency is correct rather than a computed tint — the photo needs to show through.

**Cropping.** Crop freely to fit a layout, but do not crop a person's face out of frame to make a composition work, and do not flip images horizontally — background text will reverse.

**Choosing by color.** The Dominant Colors column helps match an image to a section's palette: gray/navy/beige dominants sit comfortably beside Legacy and Ice, while brown/cream/tan dominants pair better with Dusk and Dawn.

**Resolution.** 2048px maximum. Full-bleed on a 16:9 slide is fine. At 300dpi that is roughly 6.8 inches, so avoid full-page print bleed at letter size or larger.

## Dependencies

- `signatry-content-guardrails` — owns the content restriction rules, including the standing donor clearance policy and the attribution rule restated above. If this file and that skill ever disagree on what is permitted, that skill wins.
- `signatry-facts` — the story inventory these photos are paired against, and the source of the clearance policy
- `signatry-brand-core` — colors, fonts, logo files, clearspace and tint rules
- `signatry-style` — voice and terminology for accompanying copy
- Format skills for build mechanics: `signatry-pptx-brand`, `signatry-docx-brand`, `signatry-pdf-brand`

## Maintenance

To add images: place them under `assets/photos/donor/<Family>/` or `assets/photos/stock/`, resize to 2048px maximum on the longest edge and encode as JPEG at quality 85 with a `.jpg` extension — a file whose extension disagrees with its actual encoding will embed incorrectly in pptx/docx/pdf builds even though image viewers open it fine — then append a catalog row with every column filled. The search script relies on Description and Keywords, so thin entries will not surface in results. Keep Photo IDs unique.

To retire an image, remove both the file and its catalog row, and tell Ben which deliverables used it.
