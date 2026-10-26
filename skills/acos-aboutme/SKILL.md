---
name: acos-aboutme
description: "Shared identity and org-chart profile for the acos skill family (cos, acos-email-sort, acos-jira-analysis, acos-calendar-analysis, and future acos skills) — who's a VIP/Shepherd/executive, who's staff/reports/team, which vendors are trusted partners and what functional area they belong to, which contacts should never be auto-declined or auto-filed, how to sign off an email, which Jira project keys belong to each workspace group, working hours, staff position type, known recurring meeting series, and time-allocation targets. Use when: setting up or updating an acos profile, add a VIP, add a direct report or staff member, add someone to my team, add a partner vendor, tag a functional area, add a protected contact, change my email signoff, who's on my VIP list, add a Jira project to a workspace group, change my Jira upcoming window, edit my QA checks, change my working hours, change my staff position type, add a known meeting series, correct a meeting's category, update acos aboutme, run acos aboutme."
version: "0.9"
release_date: "2026-10-24"
---

## Context

Personalization data — who counts as a VIP, who's staff, which vendors are real partners, how to sign an email, which Jira project keys make up each workspace group — used to get hardcoded or re-asked separately inside each acos skill. This skill exists so it's asked once, stored once, and read by every acos skill that needs it. It holds no logic of its own: it's a profile, plus the enrollment conversation that fills it in.

This skill does not gather calendars, inboxes, Jira issues, or anything else — it only maintains `state/profile.json`. Reading a mailbox, calendar, or Jira project is each consuming skill's own job.

## Enrollment (first run only)

Check for `state/profile.json`. If it **does** exist, this person is already enrolled — go to Updating instead, and take a snapshot first (see "Backing up and restoring the profile") before re-running enrollment over it. If it doesn't exist:

1. Copy `references/profile.example.json` to `state/profile.json` as a starting point.
2. Ask, in one short message, only for what's missing: the person's first name, full name, and how they'd like to sign off an email (e.g. "Jane," "- Jane," "Thanks, Jane" — store just the name part; the surrounding phrasing is each template's own style); their pronouns if they'd like them recorded, which any skill writing about them uses instead of guessing; who their direct reports or core staff are (name and email each); who counts as an executive/VIP for priority handling (name and email each) — this same list is the "Shepherd" group `acos-calendar-analysis` uses for its Strategy-and-transformation default; which vendor companies are trusted partners rather than random vendors (name, domain, and functional area each); any specific individual contacts that should never be auto-declined or auto-filed even if a message from them looks like a form pitch (name, email, and why); and, if they use `acos-jira-analysis`, which Jira project keys belong to each of their workspace groups (product, support, work — a group can hold more than one key) and how many days out "upcoming" should look (default 14 if they have no opinion).
3. If they use `acos-calendar-analysis`, also ask: their downstream reports as one flat list regardless of org-chart depth (`reports`); their broader team beyond just reports (`team`); their working hours if not the 08:00–17:00 default every day; their staff position type — C-suite/executive, Manager, or General staff (`owner.staff_position_type`) — used to pick the right time-allocation target range table; and a flat directory of who belongs to which functional area (Finance, HR, Legal, Compliance, Revenue, Engineering, Systems, Operations, Security, Data), for the Functional Area tag.
4. Every question is skippable — a thin or empty profile still works, it just means consuming skills can't tell a VIP from anyone else, a partner from a cold vendor, or a direct report from a stranger, until it's filled in.
5. Save the answers into `state/profile.json`, confirm back in one line, and don't ask again — only revisit when the person says something like "add a VIP," "add a partner," or "update my signoff."

## Updating

Handle these as small, targeted edits to `state/profile.json`, not a full re-enrollment:

- "Add \<name\> as a VIP" → append to `vip_senders`.
- "\<company\> is a partner, not just a vendor" → append to `partner_vendors` (name + domain).
- "Never auto-decline \<name\>/\<email\>" → append to `protected_senders` with a short reason.
- "Add \<name\> to my staff" → append to `staff`.
- "Change my signoff to \_\_\_" → update `owner.signoff`.
- "My pronouns are \_\_\_" → update `owner.pronouns`.
- "Add \<KEY\> to my \<product/support/work\> Jira workspace" → append the project key to that list under `jira_workspaces`.
- "Change my Jira upcoming window to \<N\> days" → update `jira_workspaces.upcoming_window_days`.
- "Turn off the \<name\> QA check" (e.g. the T-shirt size check) → set that entry's `enabled` to false in `jira_workspaces.product_qa.checks`.
- "Add a misspelling \<X\> → \<Y\>" → add it to `jira_workspaces.product_qa.rewrite_rules.misspellings.map`.
- "Change my QA horizon to \<N\> days" → set `jira_workspaces.product_qa.horizon_days`.
- "Change my stale threshold to \<N\> days" → set `jira_workspaces.support_qa.stale_days`.
- "Change the customer-update window to \<N\> days" → set `jira_workspaces.support_qa.customer_update_days`.
- "Turn off the past-due check" (or any support check) → set that entry's `enabled` to false in `jira_workspaces.support_qa.checks`.
- "Only count Polaris work item links as delivery links" → set `jira_workspaces.support_qa.delivery_link_types` to `["Polaris work item link"]`; an empty list means any link to a non-support ticket counts.
- "Add \<request type\> to the enhancement list" → append to `jira_workspaces.support_qa.enhancement_request_types`.
- "Mark status \<X\> on board \<Y\> as waiting on vendor \<Z\>" → append \<X\> to `jira_workspaces.work_qa.vendors.<Y>.statuses`, creating `{name: <Z>, statuses: []}` if that board has no entry.
- "Change my work stale threshold to \<N\> days" → set `jira_workspaces.work_qa.stale_days`.
- "Change backlog rot to \<N\> days old / \<M\> days untouched" → set `work_qa.backlog_age_days` and `work_qa.backlog_untouched_days`.
- "Exclude status \<X\> from work QA" → append to `work_qa.exclude_statuses`.
- "Turn off the directory check" → set `work_qa.directory_check.enabled` to false.
- "Change my next-moves count to \<N\>" / "show \<N\> next moves" → set `jira_workspaces.focus.next_moves_count`.
- "Weight people waiting on me higher" → raise `focus.score.requester_waiting_base` (confirm the new value with the owner); any other weight in `focus.score` is tuned the same way.
- "Change parked cleanup to \<N\> days" → set `focus.parked_untouched_days`.
- "Change the support update window to \<N\> days" → set `focus.owner_update_days`.
- "Show comments-waiting-on-me for work items too" → add `"work"` to `focus.comment_check_workspaces`.
- "Reset my focus weights" → remove `focus.score` from the profile so the shipped defaults apply again.
- "Save my Jira account ID" (offered after a successful Focus run) → set `owner.jira_account_id`, only with the owner's confirmation of the value.
- "My timezone is \<IANA name\>" → set `owner.timezone` (e.g. `America/Chicago`).
- "Add a QA check for field \<Z\>" → append an `empty`-type check whose `field` is a `product_fields` key (add the field ID there first if it is new). It needs an icon: offer to reuse an existing check's `svg` until one is drawn.
- "Add \<name\> to my reports/team" → append to `reports` and/or `team`.
- "\<company\> is a partner in \<area\>" → set/append `functional_area` on that `partner_vendors` entry.
- "Add \<name\> to \<area\>" (Finance/HR/Legal/Compliance/Revenue/Engineering/Systems/Operations/Security/Data) → append to that list under `functional_areas`.
- "Change my working hours \<on Friday\> to \_\_\_" → update `calendar_analysis.working_hours.default` or the relevant key under `.overrides`.
- "I'm a manager, not an executive" (or similar) → update `owner.staff_position_type` to one of `c_suite_executive`, `manager`, `general_staff`.
- "Set my \<category\> target to \_\_\_" → update `calendar_analysis.time_allocation_target_overrides` for that category — this is a personal override on top of the position-type default, never required.

Confirm each edit back in one line after saving.

**Editing `product_qa` or `support_qa` in a profile that lacks it.** The working block ships in `references/defaults.json`, so a profile without `jira_workspaces.product_qa` still gets the report. The first time an update touches `product_qa`, seed that full block from `references/profile.example.json` into the profile, then make the edit. The same applies to `support_qa`, `work_qa`, and `focus`, whose `checks` and `verdicts` are lists (and `work_qa.vendors.<board>.statuses`). `checks` is a list, and a profile's list replaces the shared one wholesale, so writing a single check would silently drop the other seven.

### One exception: `calendar_analysis.known_meeting_series` is writable by `acos-calendar-analysis` directly

Every other field in this file is read-only to every other acos skill — a correction always flows through this skill's own update flow, per the ground rules below. `calendar_analysis.known_meeting_series` is the sole, deliberate exception: `acos-calendar-analysis`'s own correction flow (its "sticky corrections" requirement) writes new match patterns or category/tag changes into that array directly, without a round trip through this skill. This is documented here so the exception is visible in one place rather than silently assumed. If a person asks to remove or hand-edit a known series, that's fine to do from here too — it's the same array either way.

## Backing up and restoring the profile

`state/profile.json` is the only copy of this person's identity data. It is deliberately kept out of git and out of the packaged skill zip, so neither a commit nor a reinstall can bring it back — an acos profile has already been lost once to a folder restructure. `scripts/state_backup.py` is the safety net. It is stdlib-only and writes to `~/.claude/acos-state-backups/`, outside every skill folder, so a snapshot survives a re-sync, a reinstall, a branch switch, or a deleted checkout.

Run it from this skill's own directory:

```bash
python3 scripts/state_backup.py               # snapshot every acos state file
python3 scripts/state_backup.py --roots       # show what would be covered first
python3 scripts/state_backup.py --list        # snapshots, newest first
python3 scripts/state_backup.py --verify LABEL
python3 scripts/state_backup.py --restore LABEL
python3 scripts/state_backup.py --restore LABEL --skill acos-aboutme
```

`LABEL` is the UTC timestamp `--list` prints, e.g. `20260924T174557Z`.

**Take a snapshot before anything that could overwrite an existing profile**: a re-enrollment over a profile that already exists, an acos skill upgrade, or a bulk edit such as replacing a whole list. First-time enrollment has nothing to lose, so it needs no snapshot. Taking one is cheap and needs no permission — just say afterwards that it happened and give the label.

**A person usually has two live copies of this state** — the installed skill folder that actually runs, and a development checkout if they maintain these skills. They drift apart. The tool finds both on its own and keeps them separate inside one snapshot, restoring each file to the copy it came from. `--roots` shows what it found; add another with `--root PATH`.

**Restoring is guarded.** It refuses to overwrite a live file whose contents differ from the snapshot unless `--force` is passed, so a restore cannot silently discard a profile rebuilt since. If a recorded location no longer exists, it says so and restores the rest. Use `--list-roots LABEL` and `--from-root` to pull one specific copy when redirecting a restore somewhere new with `--root`.

If a restore would overwrite a differing live profile, show the person what differs and let them choose — do not pass `--force` on their behalf.

## Two files: shared defaults, then personal profile

Configuration is split by who it belongs to, and consuming skills read both:

- **`references/defaults.json`** ships with this skill and holds every value that is the same for everyone in the organization: the Jira Cloud site and its Product Discovery field IDs, the Functional Area tagging vocabulary, the time-allocation benchmark tables, and the default working hours. Nobody edits this locally — it arrives with the package and is updated by shipping a new version.
- **`state/profile.json`** holds only what is personal: who the owner is, their staff, reports, team, VIPs, partner vendors, protected contacts, their own Jira project keys, their meeting series, and any deliberate override of a shared default.

A consumer loads the defaults, then overlays the profile. Any key the profile sets wins; anything it omits falls back to the shared value. Dicts merge key by key, so overriding one working-hours day does not discard the rest.

**Why the split exists.** Before it, a shared value like the Functional Area regex vocabulary lived in the profile schema, so every profile created before that value was introduced silently ran without it. `(cal.get(...) or {})` cannot distinguish "absent" from "legitimately empty", so tagging returned nothing and reported no error. Shipping the shared half separately makes a stale profile structurally impossible: a profile written years earlier still picks up today's defaults, because it never had to carry them.

**Overriding a default** means setting the same key in `state/profile.json`. Do that only to differ from the organization deliberately; it opts that key out of future updates to the shared file.

## Schema

See `references/profile.example.json` for the personal shape and `references/defaults.json` for the shared one. Summary:

- `owner` — `first_name`, `full_name`, `email`, `signoff` (just the name/phrase to sign with — a template supplies its own "Thanks," or "-" lead-in around it), `pronouns` — optional, e.g. `she/her`, `he/him`, `they/them`; any skill writing prose about the owner uses these, and falls back to they/them when unset rather than guessing from a name. `staff_position_type` — one of `c_suite_executive`, `manager`, `general_staff`; picks which row of `calendar_analysis.time_allocation_targets` applies. `jira_account_id` — optional Jira account ID; when set, `acos-jira-analysis`'s Focus dashboard queries this account instead of `currentUser()`. `timezone` — optional IANA timezone name such as `America/Chicago`; `acos-jira-analysis`'s Support QA report counts days to noon in this timezone, falling back to `jira_workspaces.support_qa.timezone` (the Work Boards QA report uses the same fallback). `linkedin_url` — the owner's personal LinkedIn profile URL, optional; `acos-email-sort` reads this for its `{personal_linkedin_url}` decline-template placeholder so a decline draft never hardcodes it.
- `staff` — legacy field, direct reports / core team, each `{name, email, role, is_executive_assistant}`. Other acos skills (e.g. `acos-email-sort`) already read this as "my core team" for their own purposes — left untouched. **Not read by `acos-calendar-analysis`** — it uses `reports` and `team` below instead, which are more precise about a genuinely different distinction, not just a rename. `is_executive_assistant: true` on exactly one entry is how `acos-email-sort` resolves its `ea_name`/`ea_email` fields — set explicitly rather than inferred by matching `role` text, since role phrasing varies too much (title case, abbreviations, "to the CEO" suffixes) to match reliably.
- `reports` — **strict management-chain fact**: everyone who reports to the owner, directly or through someone who reports to them, flattened regardless of org-chart depth — an org-chart fact, not a judgment call. Each `{name, email}`. Feeds exactly three things: (1) the People-leadership category's 2-person-1:1 rule (exactly one other attendee, and they're on this list); (2) the People-leadership category's management-keyword rule, jointly with `team`; (3) the Audience tag's "direct team" value (*all* non-organizer attendees on this list).
- `team` — **looser "who counts as my team" fact** — a superset of `reports` that can include people who don't formally report to the owner (a dotted-line collaborator, a peer's report embedded with the group). Each `{name, email}`. Feeds three things: (1) the People-leadership keyword rule, jointly with `reports`; (2) the Operating-rhythm category default (every attendee is the owner plus people on Team/Reports, no Shepherd present); (3) the Audience tag's "broader internal" value (*all* non-organizer attendees on Team, but not narrowly all on Reports).
- `vip_senders` — executives or anyone whose mail should get priority handling, each `{name, email, domain, title}` (domain is for when a whole domain should count, e.g. a small partner org where everyone is effectively a VIP; leave null otherwise). This is also the **Shepherd** group: `acos-calendar-analysis` reuses it as-is for its Strategy-and-transformation audience default — there is no separate Shepherd list.
- `partner_vendors` — companies that are external but should never read as a random cold vendor, each `{name, domain, functional_area}`. `functional_area` is one of the ten values below, or `null` if it doesn't cleanly fit one — used for the Stakeholder-vs-External distinction and the Functional Area tag.
- `functional_areas` — flat per-area directories, each a list of `{name, email}`: `Finance`, `HR`, `Legal`, `Compliance`, `Revenue`, `Engineering`, `Systems`, `Operations`, `Security`, `Data`. `Systems` is literal product/tool ownership (HubSpot, CRM, Give Interactive, Jira, TalentLMS, Rippling, etc.), distinct from `Engineering`'s dev/infra work. A person can appear in more than one area. Matched by email only, never by name.
- `protected_senders` — specific individuals who should never be auto-declined or auto-filed without a human look, each `{name, email, reason}`. This is for people, not companies — use `partner_vendors` for a whole company.
- `jira_workspaces` — Jira workspace groups for `acos-jira-analysis` (and future acos skills), each a plain list of one or more Jira project keys: `product`, `support`, `work`. A group is never assumed to hold exactly one project — `work` in particular is usually several. `upcoming_window_days` is the shared "next N days" window every consuming skill should read from here rather than hardcoding its own default (14 if unset). `cloud_id` is the Jira Cloud site hostname `acos-jira-analysis` queries — required, no built-in default; that skill's `plan` step fails with a clear error rather than guessing a site if this is unset. `product_fields` holds the site's Jira Product Discovery custom-field IDs (`project_target`, `project_start`, `product_area`, `roadmap`, `short_description`, `teams`, `commitment_level`, `tshirt_size`, `idea_archived`) plus `roadmap_exclude`; they are fixed per Jira site and ship in the defaults.
- `jira_workspaces.product_qa` — config for `acos-jira-analysis`'s Product QA report. Ships complete in both `defaults.json` and `profile.example.json`; a profile value wins key by key. Keys:
  - `horizon_days` (how far ahead "due soon" looks) and `chart_lookback_days` (how far back the runway chart starts, snapped to the 1st of the month).
  - `qa_roadmap_exclude` — Roadmap values left out of the QA query. Deliberately longer than `product_fields.roadmap_exclude` (adds `Won't do`).
  - `exclude_from_qa` — an idea is excluded if any one applies: `archived`, Roadmap value in `roadmap_values`, or status category in `status_categories`.
  - `started_statuses`, `delivery_link_types`, `date_format` (only `dd MMM yyyy` is supported).
  - `checks` — run in listed order. Each has `id`, `enabled`, `name`, `rule`, `type` (`empty`, `exact_date`, `date_before_today`, `no_delivery_links`), the `field`/`fields` it reads (keys of `product_fields`), `color_role` (a `palette` key), and `svg` (the glyph's inner SVG on a 16×16 viewBox). An unknown type, unknown field key, or malformed `svg` stops the report with an error naming the check.
  - `rewrite_rules` — the short-description rewrite rules (`min_words`, `repeated_word`, `misspellings`, `relative_date`, `list_fragment`, `aux_plus_base_verb`, `no_outcome_cue`), each with `enabled` and a `message`, plus `featured_suffix`.
  - `palette` — `[light, dark]` hex pairs for the page's color roles. The Support QA report shares these tokens.
- `jira_workspaces.support_fields` — the site's Jira Service Management custom-field IDs (`request_type`, `pending_reason`, `urgency`, `software_affected`, `system_data_source`, `time_to_resolution`, `time_to_first_response`, `timely_updates`, `date_of_first_response`), fixed per site and shipped in the defaults.
- `jira_workspaces.support_qa` — config for `acos-jira-analysis`'s Support QA report, shipped complete in both files like `product_qa`. Keys:
  - Thresholds: `stale_days`, `customer_quiet_days`, `customer_update_days`, `enhancement_grace_days`, `month_untouched_days`.
  - `status_names` — which status names mean `waiting_on_us`, `waiting_on_customer`, and `pending`; `customer_update_statuses` scopes the no-team-comment check.
  - `enhancement_request_types`, `delivery_link_scope` (only `any_non_support`), `delivery_link_types` (empty = any link type), `team_roster_sources`, `team_roster_include_assignees`, `aging_buckets`, `timezone` (org default for day counts).
  - `checks` — run in listed order; each has `id`, `enabled`, `name`, `rule`, `type` (`stale_on_us`, `customer_quiet`, `no_team_comment`, `pending_no_link`, `pending_empty_field`, `linked_unscheduled`, `enhancement_not_routed`, `due_before_today`, `linked_all_done`), an optional `field` (a `support_fields` key), `color_role` (`ink`, `risk`, or `good`), and `svg`.
  - `verdicts` — report sections in priority order; a ticket lands in the first whose `when` matches. A `when` entry is a check id, `id@status_group`, or `*` (fallback, must be last). `stuck_verdicts` names the ones counted as stuck.
  - `diagnostics` thresholds and `palette_extra` (aging-chart dot colors).
- `jira_workspaces.work_fields` — custom-field IDs the Work Boards QA report reads (`give_ticket_id`, `priority_ranking`, `ge_type`, `flagged`, `start_date`), shipped in the defaults.
- `jira_workspaces.work_qa` — config for `acos-jira-analysis`'s Work Boards QA report, shipped complete in both files. Keys:
  - Thresholds: `stale_days`, `backlog_age_days`, `backlog_untouched_days`; `exclude_statuses`, `blocked_statuses`, `idea_projects`.
  - `vendors` — keyed by work project key: `{name, statuses, ticket_ref_field, release_label_pattern}`. A status in `statuses` puts an item in that vendor's lane; the last two are optional and enable the vendor-ref and release checks.
  - `board_names`, `team_roster_sources` (which profile lists form the Technology roster), `directory_check` (`enabled`, `source: slack`, `cache_days`), `aging_buckets`.
  - `checks`, `verdicts` (a `when` entry is a check id, `id@lane` with lane `ours`, `vendor`, or `backlog`, or the trailing `*`), and `palette_extra` (`board_<KEY>` color pairs, `board_default`, `stale_line`).
- `jira_workspaces.focus` — config for `acos-jira-analysis`'s Personal Focus dashboard (the owner's own items), shipped complete in both files. Keys:
  - Counts and windows: `next_moves_count`, `timeline_months`, `timeline_start`, `week_days`, `soon_days`, `no_movement_days`, `owner_update_days`, `parked_untouched_days`, `product_mine_window_days`, `work_recent_days`, `comment_check_workspaces`.
  - `lanes` — whose-move rules per workspace (product `parked_roadmap` and `mine_if`; support `mine_statuses` and `waiting_statuses`; work `waiting_from: work_qa.vendors` and `mine_if`).
  - `contradictions` (ids `roadmap_wont_do_open`, `roadmap_now_parking_status`, `pending_reason_not_pending`, each with display text), `score` (every next-moves weight), `checks`, and `palette_extra` (lane, workspace, and today-line colors).
- `calendar_analysis` — config specific to `acos-calendar-analysis`, grouped the same way `jira_workspaces` groups `acos-jira-analysis`'s config:
  - **Audience tag algorithm** (not itself a config field — this is how `reports`/`team`/`vip_senders`/`partner_vendors` above combine into the Audience tag; documented here since it's the one place all four lists meet). Evaluated in this exact priority order, first match wins, over the event's non-organizer attendees: (1) **board** — any attendee is on `vip_senders` with a title containing "Board"; (2) **Shepherd/executive** — any attendee is on `vip_senders` otherwise (presence alone counts, same as the Strategy-and-transformation default); (3) **existing partner** — any external attendee AND every external domain present is a `partner_vendors` domain; (4) **prospective external** — any external attendee, not all partner domains; (5) **direct team** — *all* non-organizer attendees are on `reports`; (6) **broader internal** — *all* non-organizer attendees are on `team`; (7) **peer** — internal, none of the above. Board/Shepherd deliberately use an "any attendee" check (one exec in a big room still changes the read); direct-team/broader-internal deliberately use an "all attendees" check (they describe the room's overall makeup — a 20-person cross-department meeting with one report in it should not read as "direct team").
  - `working_hours` — `{default: {start, end}, overrides: {<weekday lowercase>: {start, end}}}`. `default` applies unless that weekday has its own entry under `overrides`. Saturday/Sunday should normally get a zero-width (`00:00`-`00:00`) override — leaving them on the weekday default silently counts idle weekend hours as "available capacity" in the time-allocation denominator. Override to a real window only if weekend work hours should genuinely be measured.
  - `ignored_addresses` — flat list of email addresses to treat as if they were never on an invite at all: category classification, the Audience tag, the Functional Area tag, and prep-flag attendee/external counts all filter these out at the earliest point. Two kinds of noise this absorbs: personal/family addresses cc'd alongside a staff or board member's corporate one (a spouse on a devotional call, a board member's personal email on a board meeting), and internal room-resource mailboxes that show up as an attendee but aren't a person (a conference room's own calendar identity) — the latter can inflate a meeting's headcount enough to push a real 2-person 1:1 past the People-leadership rule into 5c.
  - `known_meeting_series` — the primary mechanism for classifying recurring meetings consistently, each `{name, match_patterns, category, tags, notes}`. `match_patterns` is a list of lowercase substrings checked case-insensitively against the event subject (list more than one to support simple aliases, e.g. `"MarTech"` alongside the full series name). `category` is one of the seven primary categories. `tags` optionally pre-sets any Step-4-style tag. This is the one sub-key `acos-calendar-analysis` writes back to directly — see the exception noted under Updating.
  - `functional_area_keyword_patterns` — one regex string per Functional Area category (`Security`, `Data`, `Finance`, `HR`, `Legal`, `Compliance`, `Revenue`, `Engineering`, `Systems`, `Operations`), the subject-keyword fallback `acos-calendar-analysis` checks after the attendee-directory and partner-domain signals. Ships pre-filled with values tuned to whichever organization built this profile — review and re-tune for a different one, especially `Revenue`/`Systems`/`Operations`, which tend to carry organization-specific vocabulary (donor/DAF language, named internal tools).
  - `functional_area_disambiguation` — four auxiliary regex strings (`ai_data_governance_pattern`, `legal_non_governance_pattern`, `revenue_non_pipeline_pattern`, `bare_pipeline_pattern`) that `acos-calendar-analysis`'s Legal/Revenue special-case logic needs beyond the plain keyword pattern above — the branch structure itself is fixed code, only these strings are configurable. Same re-tune-per-organization caveat as `functional_area_keyword_patterns`.
  - `time_allocation_targets` — target percentage range `[min, max]` per primary category (the six non-excluded ones — Capacity unavailable is never in this table), keyed by staff position type (`c_suite_executive`, `manager`, `general_staff`).
  - `time_allocation_target_overrides` — optional personal override on top of the position-type default, keyed by category name to a `[min, max]` pair. Empty unless explicitly requested.

## For skill authors (how a consuming skill reads this)

This skill exposes two files, read from a sibling skill directory: `../acos-aboutme/state/profile.json` and `../acos-aboutme/references/defaults.json` (adjust the relative depth to wherever skills are actually installed side by side).

**Read both, defaults first.** Every consuming script carries an identical vendored `load_acos_profile()` helper — these skills install independently and import nothing from each other, so the block is duplicated rather than shared, and `lint_skills.py` checks the copies stay byte-identical. It returns `{}` when the profile is absent, so the not-enrolled path below is unchanged; defaults alone must never look like an enrolled profile. A missing or unparseable defaults file degrades to the profile alone rather than raising, so an older install of this skill still works.

Do not reach for a shared value directly out of `defaults.json` — read the merged view, so a person's deliberate override is honoured.

Treat every field as optional:

- If the file doesn't exist at all, this skill hasn't been installed or enrolled — degrade gracefully (e.g., an empty VIP list) rather than failing. Don't silently invent identity data on someone else's behalf.
- If a field exists but is an empty list, treat it exactly like "not provided" — don't distinguish "empty because unfilled" from "empty because there truly are none" unless the consuming skill has its own reason to care.
- Prefer this profile's data over any locally-duplicated copy a consuming skill might otherwise keep — a single source of truth avoids the two drifting out of sync. A consuming skill may still keep its own local fallback fields for people who install it standalone without this skill; in that case, this profile's data should win whenever it's present and non-empty.
- Never write to this file from another skill's logic — only this skill's own enrollment/update flow does that. A consuming skill that needs a correction should tell the person to say it here (e.g., "tell acos-aboutme to add so-and-so as a VIP"), not patch the JSON itself. The sole exception is `calendar_analysis.known_meeting_series`, which `acos-calendar-analysis` is deliberately permitted to write directly as part of its sticky-correction requirement — see "One exception" under Updating.

## Ground rules

- This file holds identity/org-chart data (names, emails, roles, short reasons) plus small shared config values that consuming skills would otherwise each hardcode on their own (e.g. `jira_workspaces`' project keys and window-day setting). Never store anything beyond that here — no financial, health, credential, or other Restricted-category data, even if someone tries to paste it in during enrollment. If that happens, leave it out and say why, per IT15.
- Names and emails collected here are colleagues' and vendor contacts' business contact information — permitted Confidential data under IT14/IT15, handled normally, no special warnings needed.
- This skill never reads or acts on a calendar, inbox, or any other data source — it only maintains the profile itself.
