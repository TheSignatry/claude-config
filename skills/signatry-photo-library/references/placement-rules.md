# Placement rules — licensing and layout

Read this before placing any library image into a deliverable. Searching and shortlisting do not require it; assembling a layout does.

## Stock imagery: licensing

- **iStock** images are licensed content. Standard iStock licenses cover marketing and promotional use. The set is nature and landscape only, so the usual model-release and endorsement concerns do not arise — but do not present a stock landscape as a specific Signatry property, project site, or grant location unless that is actually where it was taken.
- **Unsplash** images carry the Unsplash License, which permits commercial use without required attribution. Photographer names are in the catalog's Photographer column; crediting is optional but appreciated, and worth including where layout allows.
- If a piece is going to paid placement, out-of-home, or anything beyond standard marketing collateral, confirm license scope before use.

Donor imagery carries no licensing restriction, but is governed by the attribution rule in SKILL.md, which applies whether or not this file has been read.

## Using images in layouts

Pull colors, fonts, and logo files from `signatry-brand-core`; the notes below cover only what is specific to placing photographs.

**Logo over imagery.** Use `logo_white_1C.png` (or `quill_white.svg`) on photographs — never the two-color logo, which loses legibility against a varied background. Brand-core's clearspace rule still applies.

**Text over imagery.** Do not set type directly on an unmodified photograph. Either overlay Midnight (`17242a`) at 40–60% opacity across the photo or the portion behind the text and set type in white, or place the text in an adjacent solid or Ice (`def2f1`) panel. This is one of the few places where genuine alpha transparency is correct rather than a computed tint — the photo needs to show through.

**Cropping.** Crop freely to fit a layout, but do not crop a person's face out of frame to make a composition work, and do not flip images horizontally — background text will reverse.

**Choosing by color.** The Dominant Colors column helps match an image to a section's palette: gray/navy/beige dominants sit comfortably beside Legacy and Ice, while brown/cream/tan dominants pair better with Dusk and Dawn.

**Resolution.** 2048px maximum. Full-bleed on a 16:9 slide is fine. At 300dpi that is roughly 6.8 inches, so avoid full-page print bleed at letter size or larger.

**Which file to embed.** Always embed the full-resolution file from `assets/photos/` — the paths returned by `--format paths`. The `assets/previews/` set exists only for visual checking during selection and must never be placed in a deliverable.
