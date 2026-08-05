---
name: signatry-content-guardrails
description: "Content restriction rules for The Signatry — what is and isn't allowed to be produced, independent of format. Covers: never inventing a fact about The Signatry, never fabricating a donor quote/testimonial/persona, donor photo attribution integrity, gift-amount confidentiality, and the confidentiality/board-only source restriction. Use this whenever building or reviewing any Signatry deliverable — decks, documents, PDFs, emails, web/social copy — regardless of format. Depends on `signatry-facts` for the actual factual values and the standing donor clearance policy; this skill states the rules, `signatry-facts` holds the data those rules are checked against."
version: 2.1
release_date: 2026-07-31
---

# The Signatry Content Guardrails

This skill is the single record of what content is and isn't allowed to be produced for The Signatry — separate from brand values (`signatry-brand-core`), factual data (`signatry-facts`), and asset libraries (`signatry-icons`, `signatry-photo-library`). Those skills answer "what's true" or "what assets exist"; this one answers "what's permitted."

**Why this skill exists:** these rules previously lived duplicated (and drifting) inside `signatry-pptx-brand` alone, meaning `signatry-docx-brand` and `signatry-pdf-brand` had no equivalent guardrail even though the same risks (a fabricated quote, a mishandled donor photo, a leaked board figure) apply regardless of which format skill is producing the deliverable.

## 1. Never invent a fact about The Signatry

Any specific, actionable value about The Signatry — a phone number, email, URL, person's name/title, date, dollar figure, statistic, fund term, or boilerplate/disclaimer — must come from `signatry-facts`, not from recall, inference, or a plausible-looking pattern. See that skill for the full mechanism: `VERIFIED` / `CANDIDATE` / `UNVERIFIED` status, the placeholder format for missing values, and sourcing rules. This guardrail states the principle; `signatry-facts` is where it's enforced.

## 2. Never fabricate a donor quote, testimonial, or named "donor" persona

A quote attributed to a real name is a specific factual claim about what that person said — inventing one, or inventing a generic unnamed "donor" quote to sound authentic, is misrepresentation, not a stylistic shortcut. If no approved quote is available for a piece, use a scripture reference or a thematic pull-quote instead, never a synthetic testimonial. This prohibition is unconditional and doesn't depend on release/consent status below — a release governs *reuse of real material*, not license to invent.

## 3. Donor photo and quote reuse

**Clearance is not a check to perform.** Per `signatry-facts` (`reference/stories.md`, confirmed by Ben Martin, 2026-07-31): The Signatry obtains clearance before photographing a donor or writing a donor story, so every donor photograph and story it holds is already cleared for use. There is no per-piece consent limitation and no per-family verification step. Do not gate a deliverable on confirming a release, do not maintain a release list, and do not report a donor's material as unavailable because no clearance record was found — no such record is kept.

If a deliverable still describes clearance as pending, conditional, or limited to a named subset of families, that text is stale.

Two limits remain, neither of which is a clearance question:

- **Gift amounts.** Clearance covers photographs and narrative material, not dollar figures or transaction detail tied to a named donor. Confirm with Ben or Legal before using any such figure externally.
- **Attribution integrity.** Never pair a donor's photograph with another donor's story, quote, or name. This is an accuracy rule, not a permissions rule — it protects against misrepresenting real people to an audience that may know them. See `signatry-photo-library` for how this constrains layouts.

Generic, unnamed lifestyle/nature photography carries no attribution obligation and is free to use.

## 4. Confidentiality / board-only source restriction

**This is a restriction on sources, not on audiences.** Producing a deliverable *for* the board is normal work — a marketing update deck, an impact report, a program summary presented at a board meeting. Build those like any other deliverable.

What is restricted is *drawing from* material that is marked confidential, board-only, or privileged, or from board agendas, minutes, resolutions, financials, executive evaluations, or succession planning. Per organization policy that content should not be processed at all. If source material handed over for a deliverable includes it, stop and flag it rather than continuing.

One narrower limit sits on top of this and is set by organization policy rather than by The Signatry's brand team: generating the board-confidential artifacts themselves — agendas, minutes, resolutions, board updates, executive evaluations, succession planning documents — is out of scope regardless of source. A deck *presented to* the board is fine; a set of board minutes is not.

## Relationship to other skills

- `signatry-facts` — the data these rules check against (factual values, the standing donor clearance policy, story inventory). This skill states the rule; that skill holds the answer.
- `signatry-photo-library` — the actual photo files, the searchable catalog, and the layout consequences of the attribution rule. This skill states the attribution rule; that skill is where the files live and where the practical constraints on pairing are worked out.
- `signatry-brand-core` — visual truth (colors/fonts/logos), unrelated to this skill's scope.
- `signatry-pptx-brand`, `signatry-docx-brand`, `signatry-pdf-brand` — each should declare this skill as a dependency and load it on any build, rather than restating these rules locally.
