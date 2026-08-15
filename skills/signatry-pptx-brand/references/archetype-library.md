# Slide Archetype Library (interior content slides)

Load this file once you know what a given content slide needs to show —
narrative + photo, a list of steps, a quote, a stat block, and so on — and
pick only the archetype(s) that fit. `design-system.md` already covers what
every deck needs regardless of content (archetype A, archetype B-title, the
Opening/Closing sequence, universal text standards, type scale, recurring
elements); this file is the variety of interior layouts a deck's middle
section draws from. Positions are starting points; adjust for content while
honoring `design-system.md`'s universal standards.

### B. Content slide, light (Ice or white bg)
- Background: Ice `def2f1` or white
- Kicker: x=1.2, y=0.9, w=8, h=0.35
- Headline: x=1.2, y=1.3, w=8, h=1.3 (36pt Lora Regular; drop to 32pt if >2 lines)
- Body: x=1.2, y=2.9, w=6.2 (leave right side for photo) or w=10.5 (no photo), 14–16pt
- Optional photo right: x=8.0, y=1.6, w=4.4, h=4.6
- Corner tab: legacy variant
- **Not for slide 2 or the closing slide** — those use archetype B-title in `design-system.md`, whose kicker/headline sit lower and closer to vertical-center. Reusing B's near-top position for a title or closing slide is a mismatch, not a style choice.

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
