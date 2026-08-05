# Changelog — signatry-facts

Every substantive change to a fact, and every correction. Newest first.

Format: date · file · what changed · why it matters.

---

## 2026-08-04 — Mission/Vision/Values canonical wording confirmed

`facts.md` updated — following a `signatry-style` update (v2.0) sourced from the Full Brand Voice Guide, updated 2026-08-04 (`BVG-202608`).

The prior open flag on the Mission/Vision/Values row ("wording varies by source... confirm canonical wording") is resolved for Identity, Mission, and Vision: `BVG-202608` states them verbatim-matching `AR-2025`, and two independent authoritative sources agreeing settles it. Values now cites `BVG-202608` alongside `CG-2023`, since the current internal brand guide corroborates the same list and order. Non-canonical variants (Charity Navigator's mission addition, `CG-2023`'s vision wording) are named explicitly so they aren't mistaken for live alternatives.

**Why it matters:** this had been sitting as an unresolved discrepancy since the skill was built; content needing these statements had to route around it or ask Ben each time. It's now a settled `VERIFIED` value with two-source corroboration.

## 2026-07-31 — donor clearance is a standing policy; release tracking removed

`reference/stories.md` and `SKILL.md` updated — Ben Martin.

Ben confirmed that The Signatry obtains clearance before photographing a donor or writing a donor story, so every donor photograph and story it holds is already cleared. There is no per-piece consent limitation and no per-family verification step.

Removed from `reference/stories.md`: the nine-person signed-release table, the SharePoint release-form locations, the "Release confirmed?" column in the story inventory, the "no release gaps remain" statement, and the note about SharePoint search pagination. These recorded a verification process that is not performed. Removed from `SKILL.md`: "confirming per-family releases" from the open-items list, and the stale "Pending: `signatry-pptx-brand` guardrail" section (that guardrail was corrected at pptx v1.2).

**Why it matters:** the release table was being read as an allowlist. Because it named five families and the photo library holds seven different ones, material for the other six read as uncleared when it was not. Downstream skills were checking a list that should not exist. Two limits are unchanged and are not clearance questions: gift amounts tied to a named donor still need Ben or Legal, and fabricating a donor quote remains prohibited outright.

## 2026-07-27 — stakeholder grant framing corrected

`reference/assets.md` and `reference/fees.md` updated — Ben Martin.

The minimum stakeholder grant is not a flat donor cost. Where a sale is a near-term reality it is **the first grant from the resulting donor advised fund**, effectively deducted from the gift: not out of the donor's pocket, but a reduction in the charitable total available for further grant recommendations. Where the model is to donate and hold rather than liquidate, the donor funds it and it may be an additional cost — though still a gift to a 501(c)(3) and therefore possibly tax deductible.

**This is a correction of a correction.** The original July 2026 draft deck omitted the stakeholder grant entirely. This file then overcorrected, describing a $5M gift as carrying a $150,000 cost to the donor. Neither was accurate. Rate language ("the fee is 3%") is now barred as inviting an expense-ratio comparison that does not fit the near-term-sale case.

Worth noting as a pattern: the overcorrection was produced while fixing a fabrication, and was not flagged by anything in the skill. Being demonstrably wrong once does not make the next characterization right.

---

## 2026-07-27 — asset giving added

`reference/assets.md` created from Ben Martin's direct statement. Closes the largest remaining content gap.

Key facts now on file: most asset types accepted, with gift value the primary factor rather than type. **A $1,000,000 minimum applies to nonliquid gifts, measured on the value of the stake given to The Signatry, not the whole asset.** Cryptocurrency and publicly traded securities are exempt. The Signatry must receive its stake before the rest of the asset is sold or liquidated. On transfer, The Signatry has full legal control. Liquidation generally follows the remaining ownership, with proceeds going to the related DAF net of the stakeholder grant.

Reconciliation recorded: the `fees.md` bottom nonliquid tier reads "up to $2,000,000," which combined with the floor gives an effective range of $1M–$2M and an effective rate of 5% down to 2.5%.

---

## 2026-07-27 — RM Training Manual excluded

`SKILL.md` gains an **Excluded sources** section. The RM Training Manual (`RM Manual Version 1.2 2.2020-Revised.pdf`, RelationshipManagers site) is ruled out entirely as badly outdated — Ben Martin. It had been raised as a possible source for asset-type process detail; it is not.

The section is structured to grow. Superseded material remains searchable in SharePoint, and nothing about a stale file signals its staleness to a reader.

---

## 2026-07-27 — skill created and built out

**Origin.** A donor-facing deck was generated containing a fabricated phone number and a fabricated general email. Neither came from any source; a contact-information slot was filled with tokens shaped like contact information. This skill exists so that actionable values come from a file.

### Created
- `SKILL.md`, `facts.md`, `reference/fees.md`, `reference/figures.md`, `reference/history.md`, `reference/stories.md`, `reference/products.md`, `reference/named-things.md`, this changelog

### Corrections made during the build — each was wrong in the file before it was right

| What was recorded | What is true | How it was caught |
|---|---|---|
| Phone 888-697-2926, email hello@thesignatry.com | (913) 310-0279 and info@thesignatry.com | Ben asked where the numbers came from. They were invented. |
| "Legal entity name" as a single field, then "Servant Foundation" as the answer, then a note that the prior value was wrong | Not a single value. Servants and Stewards Foundation is the parent; Servant Foundation is the historical filing entity. Both earlier values were right at different levels; the *field* was malformed. | Ben supplied the structure. |
| Board of Directors page overstates the audited grant figure; top correction priority | The board page is **correct** at $3.9B. The homepage at $3.5B is the only stale figure. The error came from missing `IR-2026Q1` and from treating a CMS `modified_time` as evidence about page content. | Ben asked for the source on the impact report claim. |
| "No 2026 Q1 Impact Report exists" | It exists, in BrandTeam SharePoint, data as of May 2026. One non-paginated keyword search was reported as an exhaustive check. | Ben asked for the source. |
| Releases not found for Brian Roland, Bridget Joyner, Joel Hodgdon, Kate Gardner | All four on file, named exactly as searched. Cause was pagination — first page of results treated as the full set. An earlier "Video vs Media naming" explanation was also wrong. | Ben supplied the links. |

### Values promoted to `VERIFIED`
Contact block, entity structure, EIN 43-1890105 (Servant Foundation), leadership roster of ten, board of six, all seven founders, full fee schedule effective 2026-01-01, cumulative figures from `IR-2026Q1`, CY2025 detail from `AR-2025`, all nine donor releases, three fund types, Statement of Faith.

### Known-bad values recorded
Homepage $3.5B · three disclaimer variants including one in `AR-2025` that omits "financial" · securities gift-count percentage of 38.9% that should read 28.9% · "twice the industry average" claim that holds only on the Candid measure.

---

## How to use this file

Add an entry when a value changes, a correction is made, or a source is superseded. A value's status column says whether it was verified; this file says *when* and *after what*. If a fact in this skill turns out to be wrong, the correction goes here — including who caught it. The pattern of what gets caught is more useful than any single fix.
