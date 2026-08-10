---
name: acos-aboutme
description: "Shared identity and org-chart profile for the acos skill family (cos, acos-email-sort, acos-jira-analysis, and future acos skills) — who's a VIP/executive, who's staff, which vendors are trusted partners, which contacts should never be auto-declined or auto-filed, how to sign off an email, and which Jira project keys belong to each workspace group. Use when: setting up or updating an acos profile, add a VIP, add a direct report or staff member, add a partner vendor, add a protected contact, change my email signoff, who's on my VIP list, add a Jira project to a workspace group, change my Jira upcoming window, update acos aboutme, run acos aboutme."
version: "0.1"
release_date: "2026-08-02"
---

## Context

Personalization data — who counts as a VIP, who's staff, which vendors are real partners, how to sign an email, which Jira project keys make up each workspace group — used to get hardcoded or re-asked separately inside each acos skill. This skill exists so it's asked once, stored once, and read by every acos skill that needs it. It holds no logic of its own: it's a profile, plus the enrollment conversation that fills it in.

This skill does not gather calendars, inboxes, Jira issues, or anything else — it only maintains `state/profile.json`. Reading a mailbox, calendar, or Jira project is each consuming skill's own job.

## Enrollment (first run only)

Check for `state/profile.json`. If it doesn't exist:

1. Copy `references/profile.example.json` to `state/profile.json` as a starting point.
2. Ask, in one short message, only for what's missing: the person's first name, full name, and how they'd like to sign off an email (e.g. "Trevor," "- Trevor," "Thanks, Trevor" — store just the name part; the surrounding phrasing is each template's own style); who their direct reports or core staff are (name and email each); who counts as an executive/VIP for priority handling (name and email each); which vendor companies are trusted partners rather than random vendors (name and domain each); any specific individual contacts that should never be auto-declined or auto-filed even if a message from them looks like a form pitch (name, email, and why); and, if they use `acos-jira-analysis`, which Jira project keys belong to each of their workspace groups (product, support, work — a group can hold more than one key) and how many days out "upcoming" should look (default 14 if they have no opinion).
3. Every question is skippable — a thin or empty profile still works, it just means consuming skills can't tell a VIP from anyone else, or a partner from a cold vendor, until it's filled in.
4. Save the answers into `state/profile.json`, confirm back in one line, and don't ask again — only revisit when the person says something like "add a VIP," "add a partner," or "update my signoff."

## Updating

Handle these as small, targeted edits to `state/profile.json`, not a full re-enrollment:

- "Add \<name\> as a VIP" → append to `vip_senders`.
- "\<company\> is a partner, not just a vendor" → append to `partner_vendors` (name + domain).
- "Never auto-decline \<name\>/\<email\>" → append to `protected_senders` with a short reason.
- "Add \<name\> to my staff" → append to `staff`.
- "Change my signoff to \_\_\_" → update `owner.signoff`.
- "Add \<KEY\> to my \<product/support/work\> Jira workspace" → append the project key to that list under `jira_workspaces`.
- "Change my Jira upcoming window to \<N\> days" → update `jira_workspaces.upcoming_window_days`.

Confirm each edit back in one line after saving.

## Schema

See `references/profile.example.json` for the full shape. Summary:

- `owner` — `first_name`, `full_name`, `email`, `signoff` (just the name/phrase to sign with — a template supplies its own "Thanks," or "-" lead-in around it).
- `staff` — direct reports / core team, each `{name, email, role}`.
- `vip_senders` — executives or anyone whose mail should get priority handling, each `{name, email, domain, title}` (domain is for when a whole domain should count, e.g. a small partner org where everyone is effectively a VIP; leave null otherwise).
- `partner_vendors` — companies that are external but should never read as a random cold vendor, each `{name, domain}`.
- `protected_senders` — specific individuals who should never be auto-declined or auto-filed without a human look, each `{name, email, reason}`. This is for people, not companies — use `partner_vendors` for a whole company.
- `jira_workspaces` — Jira workspace groups for `acos-jira-analysis` (and future acos skills), each a plain list of one or more Jira project keys: `product`, `support`, `work`. A group is never assumed to hold exactly one project — `work` in particular is usually several. `upcoming_window_days` is the shared "next N days" window every consuming skill should read from here rather than hardcoding its own default (14 if unset).

## For skill authors (how a consuming skill reads this)

This skill's only externally-useful artifact is `state/profile.json`, read from a sibling skill directory at the fixed relative path `../acos-aboutme/state/profile.json` (adjust the relative depth to wherever skills are actually installed side by side). Treat every field as optional:

- If the file doesn't exist at all, this skill hasn't been installed or enrolled — degrade gracefully (e.g., an empty VIP list) rather than failing. Don't silently invent identity data on someone else's behalf.
- If a field exists but is an empty list, treat it exactly like "not provided" — don't distinguish "empty because unfilled" from "empty because there truly are none" unless the consuming skill has its own reason to care.
- Prefer this profile's data over any locally-duplicated copy a consuming skill might otherwise keep — a single source of truth avoids the two drifting out of sync. A consuming skill may still keep its own local fallback fields for people who install it standalone without this skill; in that case, this profile's data should win whenever it's present and non-empty.
- Never write to this file from another skill's logic — only this skill's own enrollment/update flow does that. A consuming skill that needs a correction should tell the person to say it here (e.g., "tell acos-aboutme to add so-and-so as a VIP"), not patch the JSON itself.

## Ground rules

- This file holds identity/org-chart data (names, emails, roles, short reasons) plus small shared config values that consuming skills would otherwise each hardcode on their own (e.g. `jira_workspaces`' project keys and window-day setting). Never store anything beyond that here — no financial, health, credential, or other Restricted-category data, even if someone tries to paste it in during enrollment. If that happens, leave it out and say why, per IT15.
- Names and emails collected here are colleagues' and vendor contacts' business contact information — permitted Confidential data under IT14/IT15, handled normally, no special warnings needed.
- This skill never reads or acts on a calendar, inbox, or any other data source — it only maintains the profile itself.
