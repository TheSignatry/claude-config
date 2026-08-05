---
name: signatry-facts
description: "Canonical record of The Signatry's organizational facts — contact details, legal entity and leadership names, founding history, scale figures, fund terms, and approved boilerplate/disclaimer text. Use this skill whenever content for The Signatry will contain a specific factual value a reader could act on: a phone number, email address, URL, mailing address, person's name or title, date, dollar figure, statistic, or fund term. Applies to every format and every audience — decks, letters, PDFs, emails, web and social copy, and internal documents. Pair with `signatry-style` for voice and terminology, and `signatry-brand-core` for colors, fonts, and logo files."
version: 1.1
release_date: 2026-07-31
---

# The Signatry Facts

The single canonical record of what is *true* about The Signatry, alongside `signatry-brand-core`, which records what is *correct-looking*. Values live in `facts.md`. This file holds the rules for using them.

**Why this skill exists:** in July 2026 a donor-facing deck was generated containing a fabricated phone number and a fabricated general email address. Neither came from any source. A "contact information" slot was filled with tokens shaped like contact information. The failure was invisible on inspection — a wrong phone number looks exactly like a right one — and would have surfaced only when a prospect dialed a stranger. This skill exists so that actionable values come from a file rather than from recall.

## The rules

**1. Only `VERIFIED` values may appear in output.** Copy them from `facts.md` exactly as written. Do not reformat, abbreviate, or normalize — a phone number retyped from memory after reading it is not a value from the file.

**2. Never supply a value that is not in `facts.md`.** Not from recall, not from inference, not from a plausible pattern, not from what a similar organization uses. If the field is not there, you do not have it.

**3. Missing values render as loud placeholders.** When a needed value is `UNVERIFIED` or `CANDIDATE`, emit:

```
[FIELD NAME — UNVERIFIED]
```

In a visual format, set it in Heartfelt `fd4a5c` at the surrounding text size. It must be impossible to miss in a page render or a slide thumbnail. A blank field reads as an oversight; a loud placeholder reads as an instruction.

**4. Name every placeholder in the delivery message.** List which fields were left unfilled and what source would resolve each. Silence about a missing value is the failure this skill exists to prevent.

**5. Never interpolate between facts.** If the file has a main phone but no donor care line, the donor care line stays unverified. Adjacent known values do not license inventing the one in between.

**6. Illustrative figures must be labeled on the artifact.** A hypothetical dollar amount in an example is fine, and must carry "Illustrative example" on the same slide or page — not only in the conversation where it was generated.

## Status vocabulary

Every row in `facts.md` carries exactly one status:

| Status | Meaning | May appear in output? |
|---|---|---|
| `VERIFIED` | Sourced from an authoritative source, with that source and a date recorded | Yes |
| `CANDIDATE` | A value exists but is unconfirmed — from an undated document, a prior conversation, or an inference | **No** — renders as a placeholder |
| `UNVERIFIED` | No value on file | **No** — renders as a placeholder |

`CANDIDATE` exists so that plausible values can be retained for someone to confirm without becoming usable by default. Treat `CANDIDATE` and `UNVERIFIED` identically at output time.

## Adding a fact

A value may be promoted to `VERIFIED` only with all four of: the value, the source, the date verified, and the owner. Source quality hierarchy, strongest first:

1. The Signatry's own published web properties, for public-facing details (contact information, leadership, public figures)
2. A current internal system of record — the CRM, the finance system, an HR roster
3. A dated internal document from the owning team, within its review interval
4. Direct statement from the accountable person at The Signatry

Not adequate on their own: undated documents, prior marketing collateral, third-party aggregators and directories, prior conversations, and anything reconstructed from recall. These may be entered as `CANDIDATE`.

Transcribe values character by character from the source. Do not paraphrase a value. Re-reading a source and retyping from memory reintroduces the failure with extra steps.

## Excluded sources — do not draw from these

Superseded material still sits in SharePoint and is fully searchable. Age alone is not the test; these are excluded because someone accountable has said so.

| Source | Status | Ruled by |
|---|---|---|
| `RM Manual Version 1.2 2.2020-Revised.pdf` and the RM Training Manual generally (RelationshipManagers site → Training) | **Do not use.** Badly outdated. | Ben Martin, 2026-07-27 |

Two related rules, narrower than the above:

- `CG-2023` (Culture Guide, June 2023) is authoritative for founding history and **never** for current figures, leadership, or practice.
- Third-party aggregators — Cause IQ, Hinchilla, Charity Navigator, GuideStar, MinistryWatch — corroborate only. They never promote a value to `VERIFIED`.

**When a SharePoint document looks old and is not on this list, ask before using it.** Do not infer that it is fine because it has not been excluded, and do not infer that it is stale because it is old.

## Staleness

Every row in the dated section carries a review interval. A value past its interval is treated as `CANDIDATE` regardless of what the status column says — the date column overrides. A stale figure in a canonical file is worse than no file, because it launders a wrong number through an authoritative-looking source.

## Scope limit — data classification

Public and Internal organizational facts only. Do not record donor names, giving history, grant recipient records, employee personal contact details, or anything Restricted under IT15. This file loads into every content task, so anything in it is exposed far more widely than minimum-necessary allows. Organizational facts, not people's records.

## File map

| File | Contents | Load when |
|---|---|---|
| `facts.md` | Contact block, entity structure, leadership and board, mission/vision/values, boilerplate, headline figures, known-bad values, CLO list | **Default** — any task naming a factual value |
| `reference/fees.md` | Fee schedule, minimums, investment option fees, contribution fees, nonliquid gift stakeholder grant tiers | Fees, minimums, investments, or any modelled gift scenario |
| `reference/figures.md` | Full scale figures, CY2025 detail, cause categories, annual trends, activation rates | Reports, impact copy, anything quantitative beyond the six headline numbers |
| `reference/history.md` | Founding narrative, founders, timeline, quotes | Anniversary, about-us, or origin-story content |
| `reference/stories.md` | Donor story inventory, published quotes, standing clearance policy, asset locations | Any content using a donor story or quote |
| `reference/products.md` | Donor advised, designated, and charity funds; QCD eligibility; life insurance; Statement of Faith | Explaining what a fund type is or who it is for |
| `reference/assets.md` | Asset acceptance, the $1M nonliquid floor, timing constraint, post-transfer mechanics | Any asset giving, business interest, or real estate content |
| `reference/named-things.md` | Programs, ventures, partners, advisory structure, and how each is styled | Any content naming a Signatry program, partner, or initiative |
| `CHANGELOG.md` | Dated record of every fact change and correction | Before trusting a value you did not verify yourself |

Every file names an owner and a review interval at the top. A value past its review interval is `CANDIDATE` regardless of its status column.

**`facts.md` carries a "Known-bad values" table.** Check it before reproducing any figure or disclaimer found elsewhere in Signatry material — several published values are wrong, including two disclaimer variants and one website figure.

## Open questions are not tracked here

This skill records what is verified, not what is outstanding. Open items — reconciling the annual report against the impact reports, the staff roster below executive level — belong in a ticket, not in reference data, where they would go stale unnoticed.

## Relationship to other skills

- `signatry-brand-core` — colors, fonts, logo files. Visual truth; this skill is factual truth.
- `signatry-style` — voice, terminology, capitalization, mechanics. Governs how a value is written into a sentence; this skill governs whether the value is real.
- `signatry-pptx-brand`, `signatry-docx-brand`, `signatry-pdf-brand` — format mechanics. Each should declare this skill as a dependency so it loads on any build.
