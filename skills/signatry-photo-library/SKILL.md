---
name: signatry-photo-library
description: "The Signatry's image library: 44 catalogued photographs — donor families (people) and stock nature/landscape. Use whenever a Signatry deliverable needs a photograph: decks, one-pagers, reports, letterhead, flyers, fund summaries, web mockups. Trigger even if the user does not say photo, image, or library — if a slide needs a hero image or a document needs a section opener, search here before using placeholder boxes, outside stock, or generated images. Pair with signatry-brand-core for colors/fonts/logos."
version: 2.1
release_date: 2026-08-06
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
assets/photos/       full resolution — embed these in deliverables
├── donor/<Family>/  17 — attribution rule applies
└── stock/           27 — licensing terms apply
assets/previews/     480px copies, same structure — for visual checking only
```

37 are landscape, 7 portrait; most are 3:2. All are JPEG, none exceeding 2048px on the longest edge.

**The library divides cleanly into people and nature, with nothing between.** All 17 donor images show identifiable people; all 27 stock images are nature and landscape, only one containing any human element (a pair of cupped hands, no face). There is no generic people photography here — no anonymous business, office, or lifestyle imagery. When a piece needs a human subject, it must come from the donor set, and the attribution rule below governs it.

## Finding an image

Use the search script rather than browsing folders or reading the whole catalog into context:

```bash
python3 scripts/find_photos.py --keywords family outdoor
python3 scripts/find_photos.py --family Roland          # one donor family
python3 scripts/find_photos.py --source stock           # all non-donor imagery
python3 scripts/find_photos.py -k mountains --format full -n 3   # detail on a shortlist
python3 scripts/find_photos.py -k mountains --format previews    # small images to look at
python3 scripts/find_photos.py -k mountains --format paths       # full-res, for the build
python3 scripts/find_photos.py --list                            # counts by source and family
```

Output defaults to one compact line per result — enough to shortlist. `--format full` gives descriptions and both paths; use it on a narrowed set, not a broad search. Other flags: `--match any` (loosen an over-narrow search), `--exclude`, `--orientation`, `--aspect 3:2`, `--min-width`, `--limit`, `--format csv`.

The catalog is `assets/photo_catalog.csv`. Columns: Photo ID, File Name, Source, Family, Photographer, Relative Path, Description, Keywords, Orientation, Aspect Ratio, Width, Height, Capture Date, Dominant Colors.

**Verify before placing.** When an image carries real weight — a cover, a full-bleed hero, anything a donor or board member will look at directly — look at it before committing. A description mentioning "family outdoors" does not tell you whether the composition leaves room for a headline.

Use `--format previews` for this. Previews are 480px copies in `assets/previews/`, mirroring the `photos/` structure, and are enough to judge composition, crop, and headline space. Open the full-resolution original only if you need to check fine detail the preview cannot settle. Never place a preview in a deliverable — builds always use `--format paths`.

## Donor imagery: attribution integrity

Consent for use is in place across contexts (confirmed with Ben, July 2026), so donor photos may be used in donor-facing, internal, advisor, and nonprofit material.

**One hard rule: never pair a donor's photograph with another donor's story, quote, or name.** If a layout puts a photo and an attributed story on the same page, spread, or slide, they must be the same family. Getting this wrong misrepresents real people to an audience that may know them.

- When a piece supplies a named story or pull-quote, search by `--family` — not by visual fit.
- If the needed family is not in the library, ask rather than substituting a visually similar family.
- Unattributed use is unrestricted: a Roland photo can open a section on generosity with no name attached.
- When a photo and a name appear near each other, state in your summary which family the photo depicts, so the pairing is checkable at review.

This rule does not apply to `--source stock` imagery, which depicts no Signatry donor.

**Note the consequence, because it constrains layouts:** stock cannot stand in for a person. If a piece carries one family's story and needs a human image, the only compliant options are that family's own photos or no photo at all — a nature image, an illustration, or a type-led layout. Do not reach for a different family's photo to fill the space. If the piece truly needs a face the library cannot supply, say so rather than improvising.

One donor image is self-identifying: `SnyderFeature (37 of 41).jpg` includes a visible "Welcome the Snyders" sign. It can never appear alongside another family's story, even unattributed.

## Before placing an image

Read `references/placement-rules.md` before assembling any layout that uses these images. It covers stock licensing terms and the layout rules for photographs — logo choice over imagery, text-over-photo tinting, cropping, color matching, and resolution limits. Searching and shortlisting do not need it; placing an image does.

The attribution rule above is the exception: it governs every use and is stated here rather than in the reference file, because it constrains which image may appear anywhere at all.

## Dependencies

- `signatry-brand-core` — colors, fonts, logo files, clearspace and tint rules
- `signatry-style` — voice and terminology for accompanying copy
- Format skills for build mechanics: `signatry-pptx-brand`, `signatry-docx-brand`, `signatry-pdf-brand`

## Maintenance

To add images: place them under `assets/photos/donor/<Family>/` or `assets/photos/stock/`, resize to 2048px maximum on the longest edge and encode as JPEG at quality 85 with a `.jpg` extension, then generate a matching 480px preview at the same relative path under `assets/previews/` — a file whose extension disagrees with its actual encoding will embed incorrectly in pptx/docx/pdf builds even though image viewers open it fine — then append a catalog row with every column filled. The search script relies on Description and Keywords, so thin entries will not surface in results. Keep Photo IDs unique.

To retire an image, remove both the file and its catalog row, and tell Ben which deliverables used it.
