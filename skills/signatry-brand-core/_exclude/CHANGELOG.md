# Changelog — signatry-brand-core

## Why this skill exists

Before this skill, colors and fonts were independently restated inside `signatry-pptx-brand`, `signatry-docx-brand`, and `signatry-style`. They had already drifted — `signatry-pptx-brand` had wrongly recorded Jubilee/Heartfelt as a retired theme pair (with an incorrect hex for Heartfelt), while `signatry-style` still carried an older table that predated the July 2026 confirmations. Centralizing here gives one place to update when the brand changes, instead of hunting down every skill that copied the numbers.

## 2026-07-31 — v1.1

- Fixed a stale cross-reference: "What's still known to be out of scope" previously said donor-content/confidentiality guardrails lived in `signatry-pptx-brand`. They'd been factored out into a dedicated `signatry-content-guardrails` skill (so `signatry-docx-brand` and `signatry-pdf-brand` deliverables get the same rules) — this file's out-of-scope note was updated to match.
- Version/release_date bumped to reflect actual content state (previously stuck at 1.0/2026-07-26 despite the Icons/Photos/Facts additions above).
- Token-efficiency pass: moved this historical narrative out of `SKILL.md` into this file, and moved the full tint reference table to `reference/tints.md` (loaded only when a tint value is actually needed, not on every basic hex/font/logo lookup).

## 2026-07-26 — v1.0, initial creation

Colors, fonts, and logo assets centralized here from the format skills and `signatry-style`.

**Jubilee/Heartfelt correction:** an earlier draft of `signatry-pptx-brand` referred to this pair as an unused `8A1E41`/`FD495C` combination from a retired theme. `FD495C` was a stale/incorrect value — Ben confirmed `fd4a5c` is the correct hex for Heartfelt. Corrected on centralization.

## Icons split out (July 2026)

Icon assets (previously a section in this file) moved to a dedicated `signatry-icons` skill, since the icon file set is large and separate from core color/font/logo work. This file kept only a short pointer.

## Photos and Facts sections added (July 2026)

Added pointer sections for `signatry-photo-library` (donor/stock photography) and `signatry-facts` (organizational facts) — both new sibling skills, referenced here for discoverability but not restated.
