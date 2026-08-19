# Signatry Deck Design System

Build NEW decks from scratch (pptxgenjs) in the visual language of the 2026 template, with universal text-placement standards applied. Do not duplicate-and-edit template slides even if the user supplies them mid-conversation — they carry stale PowerPoint autofit scaling computed for a previous font, which causes text overflow when copy changes. Treat the template as a **style reference and photo library**, not a build base. See SKILL.md's "Reference template files" section for its bundled location.

All coordinates below are inches on a 13.33" × 7.5" canvas (`pres.layout = "LAYOUT_WIDE"`). Colors reference the palette in SKILL.md.

## Universal text standards (apply to every slide, non-negotiable)

1. **Explicit font sizes only.** Never rely on autofit. If pptxgenjs is generating the deck this is automatic (it doesn't emit autofit); if post-editing XML, strip any `<a:normAutofit .../>` scale factors.
2. **Fit check before finalizing.** For every dense text block (anything estimated over ~60% of its box), run `scripts/fit_check.py` in this skill — it measures wrapped height with the bundled TTFs and passes at ≤ 90% of usable box height. On failure: reduce font 1–2pt, enlarge the box, or split the slide. Never "fix" a failure with autofit.
3. **No element collisions.** No text box may intersect a photo, card, or other text box on either axis — a text box's full rectangle (x to x+w) must end ≥ 0.3" before the next element begins, even if the current copy happens to be short. Sizing a headline box "wide because the text won't reach that far" is how text ends up behind images when copy changes. After building, run `scripts/layout_lint.py` on the .pptx to catch intersections and tab-zone violations.
4. **Pre-crop photos; never stretch, never blind-center.** Before adding any photo, crop it to the exact target aspect ratio with `scripts/crop_photo.py`. Do not rely on pptxgenjs `sizing: cover` and never place an image at a w/h that differs from its native aspect ratio without cropping first. Also convert CMYK JPEGs to RGB (the script does this automatically) — several template photos are CMYK and render incorrectly otherwise.
   - **If the photo contains a person or a clear focal subject, view the source image first** and estimate the subject's position as a fraction of width/height. Pass that as `center_x`/`center_y` to the script. A plain center-crop assumes the subject sits in the middle of the frame; when it doesn't, cropping equally from both edges can cut straight through it (e.g. a person standing right-of-center in a 3:2 photo, cropped to a narrow portrait column). Only use the script's default center (0.5, 0.5) for photos with no off-center subject — landscapes, textures, evenly distributed group shots.
   - **After cropping, re-view the output file**, not just the source — confirm the subject is fully inside the frame before placing it in the deck.
5. **Never distort an image — placed w/h must match native aspect ratio.** Once a photo is pre-cropped (previous step) or a logo/icon is loaded from `assets/`, its w/h in the pptxgenjs call must match that file's actual pixel aspect ratio. Do not eyeball this or trust that a box "looks about right" — run `scripts/image_ratio_check.py` on the built file (it reads each placed image's native pixel dimensions and compares them to the placed w/h, for every image on every slide, not just ones that look off). This catches distorted logos and icons as well as photos, since all three fail the same way: a w/h pair chosen without checking the source file's actual ratio.
6. **Margins:** ≥ 0.6" from slide edges for text (the corner tab and full-bleed photos are the only elements that touch edges).
7. **Gaps:** ≥ 0.3" between distinct elements (text block ↔ photo, card ↔ card). Nothing may enter the corner-tab zone: the rectangle from (11.5, 6.1) to (13.33, 7.5) is reserved whenever a tab is present.
8. **Left-align body text.** Center only standalone headlines (closing/CTA slides).
9. **Line spacing:** body text `lineSpacing` ≈ 1.15–1.2× font size; add `paraSpaceAfter: 8` between list items instead of blank lines.
10. **Kickers never wrap.** If a kicker exceeds its line, shorten the label — do not shrink below 14pt and do not allow two-line kickers.
11. **Apply font fallbacks, then embed fonts, before delivery.** First run `scripts/apply_font_fallbacks.py <deck.pptx>` — it writes the fallback typeface's PANOSE classification onto every Lora/Mulish reference (Lora → Georgia, Mulish → Arial), so on machines missing these fonts (where embedding isn't honored) PowerPoint's substitution engine falls back to the intended typeface rather than an arbitrary one. OOXML has no true font-stack mechanism, so this is a strong steer rather than a hard guarantee. Then embed fonts (next sentence). **Embed fonts before delivery.** Run `scripts/embed_fonts.py <deck.pptx>` as the final step — it embeds Lora and Mulish into the file using the same OOXML mechanism as PowerPoint's own "Embed fonts in this file" option, so decks render on-brand on machines without the fonts installed. Verification caveat: PowerPoint honors this mechanism, but LibreOffice (the sandbox renderer) ignores PPTX embedded fonts — so (a) sandbox QA renders require the fonts installed locally regardless (see SKILL.md), and (b) embedding cannot be end-to-end verified in the sandbox; if a delivered deck still shows wrong fonts in PowerPoint, the fallback is asking recipients to install Mulish/Lora (both free on Google Fonts) or delivering PDF alongside.

## Type scale

| Role | Font | Size | Weight | Color | Case |
|---|---|---|---|---|---|
| Kicker (eyebrow above headline) | Mulish | 18pt (14 min) | Bold | Dawn `f2a65a` | ALL CAPS, `charSpacing: 2` |
| Headline | Lora | 32–40pt | Regular (never bold) | Midnight on light bg; White on dark | Sentence case |
| Subhead | Mulish | 18–20pt | SemiBold | Legacy or Midnight | Sentence case |
| Body / bullets | Mulish | 14–16pt | Regular | Midnight on light; White/Ice on dark | — |
| Quote | Mulish | 14–16pt italic | Regular | Midnight | — |
| Attribution | Mulish | 12pt | Bold | Midnight | — |
| Scripture reference | Mulish | 12–14pt | Bold | Dawn or Legacy | — |

## Recurring elements

**Corner quill tab** — the signature mark on interior slides. Image `assets/logos/quill_tab_legacy.png` (teal, for white/Ice slides) or `quill_tab_midnight.png` (dark, for photo/colored slides needing contrast). Place at x=11.7, y=6.36, w=0.86, h=1.15 (flush to bottom-right corner region). Use on every interior slide; omit on the full-bleed title slide.

**Full-bleed title slide** — edge-to-edge photo, `logo_white_1C.png` centered or lower-left (w≈2.2, keep aspect 1201:406). No headline text required; the logo is the slide.

**Photo treatment** — photos are large and structural (half-slide columns, full-bleed, or big card blocks), never small clip-art. Search the `signatry-photo-library` skill first (44 catalogued images; use its `scripts/find_photos.py`) rather than using placeholder boxes or outside stock. Reuse of any donor-family image is governed by the `signatry-content-guardrails` skill — check it before placing a named-family photo. If the user supplies a template file mid-conversation, photography can also be pulled from `ppt/media/` (large images are content photography; small PNGs are logos/tabs). Ask the user only when neither source has a fit.

## Slide archetypes

Positions are starting points; adjust for content while honoring the universal standards. Archetypes A and B-title are covered here because every deck uses them (see Opening/Closing sequence below). **For interior content slides, load `reference/archetype-library.md`** and pick only the archetype(s) that fit what a given slide needs to show (narrative + photo, a list of steps, a quote, a stat block, and eleven more) — it's a variety library, not a checklist to read start to finish.

### A. Title (full-bleed photo with brand overlay)
- Photo: x=0, y=0, w=13.33, h=7.5 (pre-cropped to 16:9)
- **Photo selection — mandatory check, not a guideline.** The overlay below is teal (Legacy), so a green-dominant or heavily-foliage photo compounds with it: the whole slide collapses into a narrow green range and reduces the contrast the white logo needs. **Run `scripts/title_photo_check.py <photo>` on the chosen photo before placing it** (Definition of done, step 1 in SKILL.md) — do not rely on judging this by eye or on remembering this note later. On FAIL: pick a different photo, or switch the overlay below to Midnight `17242a` (same or higher opacity) instead of Legacy for that slide.
- **Overlay (required):** full-bleed rectangle over the photo, fill Legacy `2b7a78` at 60% opacity — pptxgenjs: `fill: { color: C.legacy, transparency: 40 }`, `line: { type: "none" }`. This teal wash is the signature title treatment; a bare photo is off-brand. (See photo-selection note above for when to use Midnight instead.)
- Logo `logo_white_1C.png` on top of the overlay, centered: x=4.67, y=3.08, w=4.0, h=1.35
- Layer order matters: photo → overlay → logo
- **No text of any kind on this slide** — no headline, deck title, subtitle, presenter, or date, and no topic/subject line either. The logo is the entire slide content. This holds even though "The Signatry" logo alone doesn't identify the deck's topic — that's intentional, not a gap: topic and title are deferred to slide 2 by design (see **Opening/Closing sequence** below), not omitted by oversight. Wanting to make the subject clear sooner is not grounds to add text here; if a specific deck seems to need an exception, ask Ben rather than deviating and offering to revert if asked.

(Archetype B, "Content slide, light," and all other interior-content archetypes are in `reference/archetype-library.md`.)

### B-title. Title slide & Closing ("Thank You") — shared layout
Both the deck's opening title (slide 2) and its final "Thank You" slide use this same geometry — they're distinguished by copy only, not layout. Confirmed against `TheSignatry2026.pptx`, which uses it identically at both ends of the deck (and again at each internal section break in that reference file — see **Opening/Closing sequence** below for how that applies to normal decks).
- Background: Ice `def2f1` (default) — see closing accent-band variant below for an alternate treatment
- Kicker: x=1.81, y=2.78, w=7.64, h=0.44 — Mulish Bold, uppercase, accent color (kicker color follows the section's color scheme; see **Color scheme variants**)
- Headline: x=1.81, y=3.22, w=9.72, h=1.53 — Lora Regular, large size (deck title on slide 2; literally "Thank You" on the closing slide)
- Corner tab: x=11.71, y=6.35, w=0.86, h=1.15 — section-matched variant, same position used everywhere else a tab appears
- On a Midnight-background instance, kicker and headline both go white and the tab inverts to a white square with a dark feather (matches archetype D's tab guidance)

**Closing slide — accent-band variant.** An alternate closing treatment seen in the reference file: white background instead of Ice, with a bottom band (rect x=0, y=5.62, w=13.33, h=1.88, fill = the section's accent color) sitting behind the corner tab. Kicker/headline keep the same x/y as the base layout above. Optional decorative upgrade for a closing slide — not required.

(Archetype H, "Closing / CTA," is a distinct alternate closing treatment on a solid Legacy/Midnight background rather than this Ice-card style — see `reference/archetype-library.md` if a deck calls for that version instead.)

## Opening/Closing sequence (every deck)

Every deck opens and closes with the Title/Closing archetype, not archetype B:
1. **Slide 1 — archetype A.** Full-bleed photo, overlay, logo only. No text of any kind (see archetype A note — this is intentional, not incomplete).
2. **Slide 2 — archetype B-title.** Deck title, subtitle, presenter/date as needed. This is the first slide with a corner tab, and the first place the topic is stated.
3. **Slide 3 through the second-to-last slide — content**, using whichever archetype fits each section (B and onward).
4. **Final slide — archetype B-title, closing.** A "Thank You" (or comparable sign-off) slide, same layout as slide 2. Every deck ends on this, the same way every deck opens on slide 1 and 2 — it's not optional filler to add only when asked.

**Only exception:** the user states an explicit space constraint the sequence can't fit inside — e.g. "make a three-slide presentation," "keep it to 5 slides total." When that happens, say which slides you're collapsing (e.g. "combining logo and title onto slide 1 to fit your 3-slide limit," or "dropping the closing slide since the limit doesn't leave room for one") rather than silently dropping part of the sequence or silently keeping all of it anyway. Absent a stated constraint, build the full sequence regardless of overall deck length.

(Archetypes C through L — split slide, dark slide, numbered process, quote/donor story, stat slide, closing/CTA, and four more specialized layouts — are in `reference/archetype-library.md`. Load it once you know what an interior slide needs to show, and pick only the fitting archetype(s).)

## Color scheme variants (Legacy / Midnight / Dawn sections)

For a longer deck covering distinct topics, switch section treatments the way the Master template does:
- **Legacy sections** (default): light slides (archetype B, in `reference/archetype-library.md`) with Ice backgrounds, teal accents
- **Midnight sections**: dark slides (archetype D) predominate; photos with dark overlays
- **Dawn sections**: light slides with heavier use of Dawn-gold accent blocks/photo-corner accents
Switch per section, not per slide. A single-topic deck stays in one scheme (Legacy unless asked).

## QA checklist for generated decks

Run all five. Steps 1–4 are mechanical; step 5 catches what the others miss.

1. `validate.py` passes — this one lives in the general `pptx` skill (`scripts/office/validate.py`), not in this skill
2. `scripts/layout_lint.py` passes — catches element intersections and tab-zone violations
3. `scripts/image_ratio_check.py` passes — catches any placed logo, icon, or photo whose w/h doesn't match its native pixel aspect ratio (i.e. distorted)
4. `markitdown` output matches intended copy, with signatry-style terminology applied
5. **Render to images and look at every slide.** Fonts must be installed first (see SKILL.md), or the render shows substituted fonts and the check is meaningless. Inspect for: missing logo or corner tab, text touching box edges, text in the tab zone, gaps under 0.3", wrapped kickers, stretched or distorted photos, **and people or focal subjects clipped at a crop edge** (a visible defect distinct from stretching — check every cropped photo, not just ones that look off at a glance). This is a second, visual pass on top of the mechanical checks above — it does not substitute for running steps 2–3, or for `scripts/title_photo_check.py` and re-viewing crop output at build time (Definition of done, steps 1 and 2); by this point the deck is already built.

Do not report a deck as complete without step 5. If the user has not seen the rendered slides, no one has.
