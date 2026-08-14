# Changelog — signatry-brand-core

## Why this skill exists

Before this skill, colors and fonts were independently restated inside `signatry-pptx-brand`, `signatry-docx-brand`, and `signatry-style`. They had already drifted — `signatry-pptx-brand` had wrongly recorded Jubilee/Heartfelt as a retired theme pair (with an incorrect hex for Heartfelt), while `signatry-style` still carried an older table that predated the July 2026 confirmations. Centralizing here gives one place to update when the brand changes, instead of hunting down every skill that copied the numbers.

## 2026-07-26 — v1.0, initial creation

Colors, fonts, and logo assets centralized here from the format skills and `signatry-style`.

**Jubilee/Heartfelt correction:** an earlier draft of `signatry-pptx-brand` referred to this pair as an unused `8A1E41`/`FD495C` combination from a retired theme. `FD495C` was a stale/incorrect value — Ben confirmed `fd4a5c` is the correct hex for Heartfelt. Corrected on centralization.

## Icons split out (July 2026)

Icon assets (previously a section in this file) moved to a dedicated `signatry-icons` skill, since the icon file set is large and separate from core color/font/logo work. This file kept only a short pointer.

## Photos and Facts sections added (July 2026)

Added pointer sections for `signatry-photo-library` (donor/stock photography) and `signatry-facts` (organizational facts) — both new sibling skills, referenced here for discoverability but not restated.

## 2026-08-06 — v1.2, Italic weight added for Mulish and Lora

Cross-skill audit found that no italic TTF existed anywhere in this skill or its dependents (`signatry-pptx-brand`, `signatry-pdf-brand`), despite both format skills' design specs calling for italic Mulish (Quote role). `<i>`/italic markup was silently rendering as upright regular weight with no warning — the exact failure mode this skill exists to prevent, just unaddressed for italics specifically.

Added `Mulish-Italic.ttf` and `Lora-Italic.ttf` to `assets/fonts/`. Both are Google's own Mulish/Lora italic (SIL OFL), reconstructed by merging Fontsource's per-script subset files (Latin, Latin Extended, Cyrillic, Cyrillic Extended, Vietnamese; Lora also Math and Symbols) since a direct fonts.google.com download wasn't reachable from the build environment. Verified: correct italic rendering, correct weight/style flags, and accented-Latin glyph coverage matching the other bundled weights (spot-checked against café/Zürich-style text). Mulish's converted file initially carried an incorrect internal name-table label ("ExtraLight Italic" on a 400-weight file — an upstream Fontsource/Google Fonts quirk, not introduced here); corrected before bundling. No bold-italic face exists for either font — only regular-weight italic.

Copied into `signatry-pptx-brand` and `signatry-pdf-brand`'s local `assets/fonts/` mirrors per this file's own "update here first, then re-copy" rule. `signatry-pptx-brand/scripts/embed_fonts.py` and `signatry-pdf-brand/scripts/signatry_pdf_brand.py` updated to register/embed the new files — see those skills' own changelogs/history for detail.

## 2026-07-31 — v1.1

- Fixed a stale cross-reference: "What's still known to be out of scope" previously said donor-content/confidentiality guardrails lived in `signatry-pptx-brand`. They'd been factored out into a dedicated `signatry-content-guardrails` skill (so `signatry-docx-brand` and `signatry-pdf-brand` deliverables get the same rules) — this file's out-of-scope note was updated to match.
- Version/release_date bumped to reflect actual content state (previously stuck at 1.0/2026-07-26 despite the Icons/Photos/Facts additions above).
- Token-efficiency pass: moved this historical narrative out of `SKILL.md` into this file, and moved the full tint reference table to `reference/tints.md` (loaded only when a tint value is actually needed, not on every basic hex/font/logo lookup).
