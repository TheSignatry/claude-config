# Changelog

All notable changes to this skill are documented here, newest first.

## 2.5 — 2026-08-14

Token-efficiency pass, no content changes. The Jubilee/Heartfelt color-palette entry carried an inline retelling of the hex-correction history (an earlier draft's stale `fd495c` value, corrected to `fd4a5c`) that's already recorded in full in `signatry-brand-core`'s own changelog — the same duplicated-history pattern that skill's changelog exists to prevent. Trimmed to the current facts (the colors, and the note that the 2026 template files don't carry this pair) with a pointer to `signatry-brand-core`'s changelog for the correction history, instead of retelling it here.

## 2.4 — 2026-08-07

Trigger wording only, no content changes. Description previously required "building, branding, restyling, or reviewing a .pptx presentation" language to fire; generic phrasing with no format/brand keyword (e.g. "add a slide," "make me a deck") could miss it, including inside the Claude for PowerPoint add-in where a request may reference the open file rather than naming a format. Replaced with explicit org-wide-default wording naming the add-in directly, matching wording already in use on the separately-versioned copy at `/mnt/skills/user/signatry-pptx-brand` (v1.5) — that copy predates the pass-1/pass-2 audit fixes below, so its content was not merged, only its trigger phrasing.

## 2.3 — 2026-08-06

Token-efficiency pass, no design changes. Split `references/design-system.md`: archetypes C through L (the 11 interior-content layouts) moved to new `references/archetype-library.md`, loaded only once a slide's content need is known. `design-system.md` keeps the universal-standards material and the two every-deck archetypes (A, B-title). Was ~4,700 tokens required reading for every build regardless of which archetypes a deck actually used; now ~3,850, with the archetype variety loaded separately and selectively.

## 2.2 — 2026-08-06

`scripts/embed_fonts.py` extended to embed Lora/Mulish Italic and the two distinct type-scale typefaces (`Mulish-SemiBold`, `Mulish-ExtraBold`) that were previously left unembedded; stale "60-icon" and template-filename references corrected. See `signatry-brand-core`'s changelog for the italic font sourcing.
