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

Positions are starting points; adjust for content while honoring the universal standards.

### A. Title (full-bleed photo with brand overlay)
- Photo: x=0, y=0, w=13.33, h=7.5 (pre-cropped to 16:9)
- **Photo selection — mandatory check, not a guideline.** The overlay below is teal (Legacy), so a green-dominant or heavily-foliage photo compounds with it: the whole slide collapses into a narrow green range and reduces the contrast the white logo needs. **Run `scripts/title_photo_check.py <photo>` on the chosen photo before placing it** (Definition of done, step 1 in SKILL.md) — do not rely on judging this by eye or on remembering this note later. On FAIL: pick a different photo, or switch the overlay below to Midnight `17242a` (same or higher opacity) instead of Legacy for that slide.
- **Overlay (required):** full-bleed rectangle over the photo, fill Legacy `2b7a78` at 60% opacity — pptxgenjs: `fill: { color: C.legacy, transparency: 40 }`, `line: { type: "none" }`. This teal wash is the signature title treatment; a bare photo is off-brand. (See photo-selection note above for when to use Midnight instead.)
- Logo `logo_white_1C.png` on top of the overlay, centered: x=4.67, y=3.08, w=4.0, h=1.35
- Layer order matters: photo → overlay → logo
- **No text of any kind on this slide** — no headline, deck title, subtitle, presenter, or date, and no topic/subject line either. The logo is the entire slide content. This holds even though "The Signatry" logo alone doesn't identify the deck's topic — that's intentional, not a gap: topic and title are deferred to slide 2 by design (see **Opening/Closing sequence** below), not omitted by oversight. Wanting to make the subject clear sooner is not grounds to add text here; if a specific deck seems to need an exception, ask Ben rather than deviating and offering to revert if asked.

### B. Content slide, light (Ice or white bg)
- Background: Ice `def2f1` or white
- Kicker: x=1.2, y=0.9, w=8, h=0.35
- Headline: x=1.2, y=1.3, w=8, h=1.3 (36pt Lora Regular; drop to 32pt if >2 lines)
- Body: x=1.2, y=2.9, w=6.2 (leave right side for photo) or w=10.5 (no photo), 14–16pt
- Optional photo right: x=8.0, y=1.6, w=4.4, h=4.6
- Corner tab: legacy variant
- **Not for slide 2 or the closing slide** — those use the distinct Title/Closing archetype below, whose kicker/headline sit lower and closer to vertical-center. Reusing B's near-top position for a title or closing slide is a mismatch, not a style choice.

### B-title. Title slide & Closing ("Thank You") — shared layout
Both the deck's opening title (slide 2) and its final "Thank You" slide use this same geometry — they're distinguished by copy only, not layout. Confirmed against `TheSignatry2026.potx`, which uses it identically at both ends of the deck (and again at each internal section break in that reference file — see **Opening/Closing sequence** below for how that applies to normal decks).
- Background: Ice `def2f1` (default) — see closing accent-band variant below for an alternate treatment
- Kicker: x=1.81, y=2.78, w=7.64, h=0.44 — Mulish Bold, uppercase, accent color (kicker color follows the section's color scheme; see **Color scheme variants**)
- Headline: x=1.81, y=3.22, w=9.72, h=1.53 — Lora Regular, large size (deck title on slide 2; literally "Thank You" on the closing slide)
- Corner tab: x=11.71, y=6.35, w=0.86, h=1.15 — section-matched variant, same position used everywhere else a tab appears
- On a Midnight-background instance, kicker and headline both go white and the tab inverts to a white square with a dark feather (matches archetype D's tab guidance)

**Closing slide — accent-band variant.** An alternate closing treatment seen in the reference file: white background instead of Ice, with a bottom band (rect x=0, y=5.62, w=13.33, h=1.88, fill = the section's accent color) sitting behind the corner tab. Kicker/headline keep the same x/y as the base layout above. Optional decorative upgrade for a closing slide — not required.

## Opening/Closing sequence (every deck)

Every deck opens and closes with the Title/Closing archetype, not archetype B:
1. **Slide 1 — archetype A.** Full-bleed photo, overlay, logo only. No text of any kind (see archetype A note — this is intentional, not incomplete).
2. **Slide 2 — archetype B-title.** Deck title, subtitle, presenter/date as needed. This is the first slide with a corner tab, and the first place the topic is stated.
3. **Slide 3 through the second-to-last slide — content**, using whichever archetype fits each section (B and onward).
4. **Final slide — archetype B-title, closing.** A "Thank You" (or comparable sign-off) slide, same layout as slide 2. Every deck ends on this, the same way every deck opens on slide 1 and 2 — it's not optional filler to add only when asked.

**Only exception:** the user states an explicit space constraint the sequence can't fit inside — e.g. "make a three-slide presentation," "keep it to 5 slides total." When that happens, say which slides you're collapsing (e.g. "combining logo and title onto slide 1 to fit your 3-slide limit," or "dropping the closing slide since the limit doesn't leave room for one") rather than silently dropping part of the sequence or silently keeping all of it anyway. Absent a stated constraint, build the full sequence regardless of overall deck length.

### C. Split slide (photo half)
- Photo: x=0, y=0, w=5.2, h=7.5 (or mirrored on the right)
- Text column starts x=5.9, w=6.5: kicker y=1.4, headline y=1.85, body y=3.4
- Corner tab: choose variant by what's behind it (photo → midnight tab or omit)

### D. Dark slide (Midnight bg)
- Background: Midnight `17242a`
- Kicker: Dawn, same geometry as B
- Headline + body: white; body may use Ice for secondary lines
- Corner tab: midnight variant reads as tone-on-tone; on pure Midnight use the white quill (`quill_white.svg` rasterized) or omit

### E. Numbered process ("How it works")
- Kicker + headline top-left (as B)
- Numbered list right column: x=6.3, y=2.5, w=5.0, 14pt, `paraSpaceAfter: 10`
- Optional photo left under headline: x=1.2, y=2.5, w=4.4, h=4.4
- Max 5 steps per slide; 6+ steps → split across two slides

### F. Quote / donor story
- Photo left (as C) or top-right card
- Quote: Mulish italic 15pt, x=5.9, y=1.8, w=6.3
- Attribution directly below quote, 12pt bold, gap 0.25"
- Reflective question as headline (Lora 30–32pt) below attribution when the slide doubles as a CTA

### G. Stat slide
- Kicker + headline (as B)
- Up to three stat cards: rounded rects (`rectRadius: 0.08`), fill Ice, w=3.6, h=2.2, y=2.6, x=1.2 / 5.05 / 8.9
- Stat number: Mulish ExtraBold 40pt — one card may use Dawn or Dusk for the standout figure, others Legacy/Glacier
- Label under number: Mulish 14pt Midnight
- Cite sources at 9–10pt bottom-left, ≥0.3" below cards, never in the tab zone

### H. Closing / CTA
- Background: Legacy `2b7a78` or Midnight
- Centered reflective question: Lora Regular 30–34pt white, x=1.7, y=2.8, w=9.9 (keeps clear of tab zone)
- Logo lower-left as on title slide
- Per signatry-style: invitation or question, never a command

### I. Accent-corner portrait quote (from Legacy slide 3)
- Dawn-gold accent block peeking from top-left corner: rect x=0, y=0, w=2.0, h=3.0, fill Dawn `f2a65a`
- Tall portrait photo overlapping it: x=0.55, y=0.49, w=4.8, h=6.5 (pre-crop to ~0.74 aspect)
- Quote right: x=5.9, y=1.73, w=6.0, h=2.2, Mulish italic 15pt; attribution below
- Reflective headline: x=5.9, y=4.24, w=6.0, h=1.25, Lora Regular 30–32pt
- Corner tab: legacy variant

### J. Section divider with white card (from Legacy slide 7)
- Full-bleed photo background (pre-cropped 16:9)
- White card right of center: x=7.09, y=2.53, w=6.24, h=3.17, fill white
- Headline inside card: x=7.38, y=2.6, w=5.55, Lora Regular 28–30pt Midnight
- Support line below headline: x=7.38, w=5.55, Mulish 13–14pt
- Ice edge strip on the card's right edge: rect x=12.93, y=2.53, w=0.40, h=3.17, fill Ice
- Corner tab: variant with contrast against the photo

### K. Photo collage split (from Dawn slide 2)
- Tall photo left: x=0, y=0.65, w=3.92, h=5.85
- Two stacked square photos: x=4.13, w=2.83, h=2.84, at y=0.65 and y=3.66
- Color panel right: x=7.17, y=0.65, w=6.16, h=5.85 — fill Legacy (white text) or Ice (Midnight text)
- Inside panel: kicker x=7.67, y=1.5; headline x=7.67, y=1.9, w=5.0, Lora Regular 28–32pt; body x=7.67, y=3.66, w=5.0
- All three photos pre-cropped to their exact aspect (0.67 / 1.0 / 1.0); 0.21" gutters between photos
- Corner tab sits on the panel — use a variant that contrasts with the panel fill

### L. Scripture / impact split (from Midnight slide 3)
- Square photo top-left: x=0, y=0, w=4.85, h=4.85 (pre-crop 1:1)
- Color block under it completing the column: x=0, y=4.85, w=4.85, h=2.65, fill Legacy or Dawn
- Scripture inside the block: x=0.28, y=5.4, w=4.28, h=1.55 — verse in Mulish italic 13pt, reference on its own line in Mulish Bold 12pt ("1 Chronicles 29:12, 14" style, NIV per signatry-style)
- Right column on the slide background (Midnight or white): kicker x=5.38, y=2.11; headline x=5.38, y=2.4, w=6.0; body x=5.38, y=3.4, w=6.0
- Corner tab: white-on-dark variant for Midnight background

## Color scheme variants (Legacy / Midnight / Dawn sections)

For a longer deck covering distinct topics, switch section treatments the way the Master template does:
- **Legacy sections** (default): light slides (B) with Ice backgrounds, teal accents
- **Midnight sections**: dark slides (D) predominate; photos with dark overlays
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
