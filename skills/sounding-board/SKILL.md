---
name: sounding-board
description: Use this skill whenever the user wants to sounding board, stress-test, pressure-test, "run this by" a panel, or "get reactions to" an idea, message, decision, proposal, email, policy, or announcement before it goes out — including questions phrased as "how would a donor react to this?", "what would our advisors say?", "how would employees take this?", "would a VIP family be okay with this?", "how would the board react to this?", "what would leadership/the C-suite/the shepherds say?", or "how would a nonprofit/grant recipient react to this?". Also trigger on requests to role-play multiple perspectives or simulate audience reactions to Signatry content. Do not wait for the user to name this skill explicitly — if they are asking to test something against how people will receive it, this skill applies.
version: "0.5"
release_date: "2026-07-26"
---

# Sounding Board

Role-plays a small panel of fictional, composite personas reacting to an idea, message, decision, or proposal—so the user can see where it lands, where it snags, and what to fix before it reaches real people. This is a rehearsal tool, not a takedown: keep every reaction constructive.

There are seven audiences, each with its own persona file in `references/`:

| Audience | File | Covers |
|---|---|---|
| Employee | `references/employee.md` | Internal staff reactions to policies, tools, process change, announcements |
| Donor | `references/donor.md` | Donor advised fund holders reacting to appeals, emails, reports, web copy |
| Advisors | `references/advisors.md` | CPAs, wealth managers, estate attorneys who refer or partner with donors |
| VIP family | `references/vip-family.md` | High-net-worth families with complex giving and white-glove expectations |
| Board | `references/board.md` | Board of directors reacting to proposals at the level of governance and fiduciary duty, not day-to-day operations |
| Shepherds (C-suite) | `references/shepherds.md` | Executive leadership reacting at the level of execution—resourcing, sequencing, and delivering a decision |
| Nonprofit | `references/nonprofit.md` | Grant recipient organizations reacting as the receiving end of a grant, across a range of DAF sophistication |

Each file contains six to nine personas who do **not** all agree with each other — some are enthusiastic, some are skeptical of AI, jargon, or anything that reads as inauthentic. Preserve that disagreement; don't flatten it into consensus.

## How to run this skill

**1. Confirm the idea and the audience(s).**
Restate in one line what's being tested (the email, announcement, policy, decision, etc.). Then determine the audience:

- **If the request already names the audience** ("how would donors react to this," "run this by our advisors"), proceed with that audience and briefly say which one was picked and why.
- **If the request is ambiguous** ("sounding board this announcement," "stress-test this idea"), ask the user which audience or audiences apply before proceeding—do not guess silently. A user can select more than one audience (e.g., an internal policy that will eventually go external to VIP families).

**2. Load only the relevant reference file(s).**
Read `references/<audience>.md` for each selected audience. Do not load files for audiences that weren't selected—each file is scoped to its own persona set and there's no need to load all seven for a single-audience request.

**3. Give each persona a short in-character reaction.**
For every persona in the loaded file(s), cover in a few sentences:
- Their gut reaction (in character, in their voice)
- Their main concern, question, or objection
- A one-line suggestion for how to address it, if relevant

Keep each persona's reaction distinct and grounded in what the reference file says about them—their perspective, communication style, and typical objections. Don't let personas within the same audience converge on the same take; if they would genuinely agree, say so briefly rather than padding out repetitive reactions.

**4. Close with a brief synthesis.**
End with:
- Where personas agree (a real signal worth acting on)
- Where they conflict (a tradeoff the user needs to decide, not paper over)
- The single highest-leverage change to make before this goes out

**5. Keep it constructive.**
This is a rehearsal, not a review board. Frame every concern as something fixable, and don't pile on more objections than the artifact actually warrants—a strong draft should get a short, mostly positive pass.

## Style

Any sample dialogue, persona quotes, or suggested rewrites should follow The Signatry's house style — read the `signatry-style` skill first if it hasn't already been loaded this session. In particular: always "The Signatry," donors (not givers), nonprofits (not charities), donor advised fund with no hyphen, biblically responsible investments/BRI (not ESG or faith-based investing), no emojis, Oxford comma, and NIV for any scripture reference.

## Notes

- Personas are fictional composites, not real people or organizations. Never map a reaction onto a specific named employee, donor, advisor, family, or nonprofit partner.
- If the idea being tested involves a decision affecting donors, grants, finances, personnel, or external communications, remind the user that a human still needs to review and approve before it goes out—this skill is a rehearsal, not the approval step.
