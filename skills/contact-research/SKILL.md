---
name: contact-research
description: "Research and enrich HubSpot contacts for The Signatry's relationship managers, one at a time or in batches. Given a HubSpot Contact ID, a name, and at least one other data point (email, phone, or address), the skill pulls the full HubSpot record, checks associations and activity for spouse and company links, researches the person on the public web (LinkedIn URL, company, role, revenue, business ownership), and produces two outputs from a JSON state folder: an enrichment spreadsheet that separates HubSpot data from inferred web data and includes HubSpot upload-prep sheets, and one branded PDF profile per contact with a user-chosen file-naming convention. Use this skill whenever someone asks to enrich, research, profile, dossier, look up, or 'fill in the gaps' on HubSpot contacts, donors, or prospects; asks who a contact's spouse or company is; asks for a contact profile PDF; or asks to run RM contact research in bulk — even if they don't say 'contact_research' or 'HubSpot' by name."
version: 1.5
release_date: 2026-09-14
---

# contact_research

Enrich HubSpot contacts with public-web research and deliver a review-ready spreadsheet plus per-contact PDF profiles. Everything flows through a **state folder of JSON files**, so a run can be paused, resumed, re-rendered, or batched without repeating work.

## Why the state folder matters

Research is the expensive, rate-limited part; rendering is cheap. Keeping every fact in `state/contacts/<id>.json` means a spreadsheet or PDF can be regenerated at any time, a batch can stop after 20 contacts and pick up tomorrow, and a human reviewer can see exactly which field came from HubSpot and which was inferred. Never write research directly into the xlsx or PDF; write it to state and render from there.

## Governance (read before the first run)

This skill handles **Confidential** donor data (IT15). Names, contact info, and giving relationships are fine to process. **Restricted** data is never pulled, searched for, or recorded: government IDs, account numbers, card data, health/medical/hardship details, credentials, privileged or Board Confidential material. If any appears in a HubSpot note or search result, drop it, flag the record, and remind the user to report it (IT14 Policy 10). Every output is AI-assisted and needs human review before use (IT14 Policy 1); the renderers stamp this automatically. Never invent a fact, never characterize personality or "how to approach" a person, and never reproduce a third-party report's AI-generated behavioral sections. `references/governance.md` has the full list.

## Model

Policy, from a September 2026 comparison of three models on identical HubSpot state: **Fable 5.1 by default**, **Opus 5** acceptable and the escalation choice when Fable returns `None` on a standard-tier contact, **Haiku 4.5** only for `thin`/`placeholder` tiers, and **Sonnet 5 not for household or spouse work** (it promoted a same-name wedding page to a confirmed spouse). The batch runner (`scripts/api_batch_runner.py`) applies this routing itself. In an interactive run the skill cannot change the session's model, so at the start of Step 3 check your own model ID: if it is off-policy, tell the user before researching and offer to stop so they can switch (`/model` in Claude Code); if they continue, proceed — `merge_state.py` adds an off-policy flag to every research fragment so the reviewer sees it on the PDF and in the workbook. Advisory only; nothing blocks.

## Workflow

### Step 0 — Ask two things up front

1. **Naming convention for PDFs** (present as options with `ask_user_input` if available):
   1. `{HubSpotContactId}_{FirstName}_{LastName}_profile.pdf`
   2. `{LastName}_{FirstName}_{HubSpotContactId}_profile.pdf`
   3. `{ContactOwner}_{LastName}_{FirstName}_{HubSpotContactId}_profile.pdf`
2. **Batch size** if more than ~10 contacts were supplied (default 10). HubSpot connector calls and web searches are rate-limited; small batches keep a failure from costing the whole run.

Skip the questions if the user already stated both.

### Step 1 — Initialize the run

Input is a CSV/xlsx/JSON list or an inline list. Each contact needs a HubSpot Contact ID, a name, and at least one more data point (email, phone, or address). Rows missing these are rejected with a reason, not guessed.

```bash
python scripts/init_run.py --input <file-or-json> --run-dir state/ --naming <1|2|3> [--batch-size 10]
```

Creates `state/manifest.json`, `state/contacts/<id>.json` (stage `init`), and `state/rejected.csv`. Contact IDs are stored as strings; Excel-exported IDs like `2.44057E+11` are flagged as unusable and must be re-supplied.

### Step 2 — Pull the HubSpot record

Two paths; prefer the API when a token is available because it returns association *labels* (Spouse, Employee, Referred By) that the connector cannot see.

- **API path** (`HUBSPOT_TOKEN` set): `python scripts/hubspot_pull.py --run-dir state/ --batch <n>` pulls properties, associations with labels, companies, and engagements, then runs the redaction screen and writes stage `hubspot` + `associations` + `activity`.
- **Connector path** (Claude.ai with the HubSpot connector): follow `references/hubspot_extraction.md` — batch-read the contacts with the listed property set, search same-surname contacts, read associated companies (`give_recipient_id`, `type`), and pull NOTE/EMAIL/CALL/MEETING/TASK engagements with an `associatedWith` filter. Write each result with:
  ```bash
  python scripts/merge_state.py --run-dir state/ --id <id> --stage hubspot --json '<fragment>'
  ```

Then derive the deterministic facts (no model judgment needed):

```bash
python scripts/derive.py --run-dir state/
```

This computes the email handle, identifiability tier (`placeholder` / `thin` / `standard`), referral-vs-role for every company association, household-pair candidates (same surname, same form, created within 120 s), the DAF rollup (fund count, sum of associated Fund `current_balance`, and `direct_fund_balance_tier_min` passed through as-is), and data-quality flags. **A nonprofit company association is kept only when the contact holds a role there**; a referral (`referral_company_give_id` equals the company's `give_recipient_id`, or a Referred-By label) goes to the referral field instead. See `references/hubspot_extraction.md` for why this rule exists.

### Step 3 — Research each contact

Work through `python scripts/batch.py --run-dir state/ next` which lists the next unresearched contacts in the current batch. For each, read `references/research_playbook.md` and:

- Skip web research entirely for `placeholder` tier (e.g., first name "Husband").
- Spend at most two searches on `thin` tier; up to six searches plus four page fetches on `standard`. Run the searches in the fixed order given in `references/research_playbook.md` §2 (the search recipe) and stop only on a High match or when the recipe is exhausted — never write `None` for a contact before the recipe's household step has run.
- If HubSpot or research names a spouse or household member (`associations.spouse_in_hubspot`, `household_pair_candidate`, or a public source) and the contact herself is Low/None, research **that person's** employer, role, and ownership as household context into `research.household.spouse_company` — never into the contact's own `company` block. `merge_state.py` refuses a fragment that skips this.
- Use **Playwright** for page navigation when the environment allows it: `python scripts/playwright_fetch.py --url <url> [--search "<query>"]`. The script fails fast with a clear reason (no browser binaries, blocked network) — when it does, fall back to the `web_search` / `web_fetch` tools and record `"navigation": "web_tools_fallback"` in state so the reviewer knows. Do not attempt to log in to LinkedIn or any site; use only what is publicly indexed.
- Score two things separately, each with the same scale: `match_confidence` for the **contact's own** public identification and `household_confidence` for the **spouse/household** identification (`None` when no household member is known). **High** needs two independent signals; **Moderate** is one strong match on an uncommon name; **Low** is circumstantial; **None** leaves the corresponding fields null. Prefix every Low/None candidate detail with `Candidate only:`. Sources used for household context are real sources — list them. A public page naming a spouse supports household **High** only when it matches a HubSpot fact (address, city, employer/email domain, phone, age band) — record which in `household.spouse_corroboration`; a same-name couple that matches nothing is Moderate at most.
- Research the company once per email domain / company name and reuse it for colleagues (`--company-prior`).
- Write the result:
  ```bash
  python scripts/merge_state.py --run-dir state/ --id <id> --stage research --file research_<id>.json
  ```
  The fragment must match the `research` block in `references/state_schema.md`, including `model` set to your exact model ID (it prints in the PDF footer); `merge_state.py` validates it and rejects fabricated-looking values (non-null research fields with no source).

Mark the batch and move on: `python scripts/batch.py --run-dir state/ advance`.

For unattended bulk runs, `scripts/api_batch_runner.py` submits the same research prompt (in `references/research_prompt.md`) through the Claude Message Batches API and merges results into state. It needs `ANTHROPIC_API_KEY`; see the script header for model routing by tier.

### Step 4 — Render outputs (any time, repeatable)

```bash
python scripts/build_workbook.py --run-dir state/ --out outputs/<RunName>_Enriched.xlsx
python scripts/build_profiles.py --run-dir state/ --out outputs/profiles/ [--naming 1|2|3] [--ids <id,id>]
```

Requires `openpyxl` (workbook) and `reportlab` (PDF profiles) — install with `pip install openpyxl reportlab` if either import fails.

**Workbook sheets:** `Contact Enrichment` (HubSpot columns in blue — including the `DAF:` fund count/tier/balance columns — spouse in purple, research in green, ownership in gold, each research column prefixed `Research:`), `Summary`, `Upload Prep – Contacts` (HubSpot import headers; a reviewer types Y in **Accept?** and the row is ready for the import template), `Upload Prep – Notes` (one pre-composed, sourced note per contact for a Notes import), `Methodology`, and `Sources`.

**PDF profile:** three pages per contact, Signatry-branded via the `signatry-pdf-brand` skill (Lora/Mulish, Legacy header, embedded fonts; falls back to Helvetica with a warning if that skill is absent). Header shows a confidence-tier badge (left) and a Contact Owner badge (right); the footer shows the skill version, model, render date, and page number. Sections: Sources checked, Overview, About, Contact, DAF, Social/Web, Household & Spouse, Career & Company, Ownership, HubSpot Activity & Referral, Notes & Flags, Sources.

Present both with `present_files`. Rendering never calls the model, so re-running after a reviewer edits a state file is free.

### Step 5 — Hand off for review

Point the user to the `Accept?` column and the per-contact `review` block in state. Nothing is written back to HubSpot by this skill; the upload-prep sheets are what a human submits after review.

## Where to look next

| Need | File |
|---|---|
| Exact HubSpot properties, connector call patterns, association labels, redaction screen | `references/hubspot_extraction.md` |
| How to search, match standard, spouse/ownership/revenue rules, Playwright vs fallback | `references/research_playbook.md` |
| JSON layout of `manifest.json` and `contacts/<id>.json` | `references/state_schema.md` |
| System prompt used by the API batch runner (also a good checklist when researching by hand) | `references/research_prompt.md` |
| HubSpot import header mapping for the upload-prep sheets | `assets/upload_template_columns.json` |
| Confidentiality, fabrication, characterization, and disclosure rules | `references/governance.md` |

## Worked example (from the pilot)

Input: `239596421482, Paul Brown, pabrown54@gmail.com`. HubSpot showed no address, no company, no activity, record created by the "2026-08 Iowa NASCAR Race (YL) VIP" form, referral channel "Family Office". Derivation: handle `pabrown`, tier `standard`, two same-surname contacts (different emails, one in IL). Research: query `"Paul Brown" family office Iowa` → Paul Alvin Brown, investment adviser, Principal Financial Advisors, Des Moines. Three consistent signals but nothing ties the Gmail address to him → `match_confidence: Low`, every company field prefixed `Candidate only:`, ownership `N/A – employee`, flag the two surname matches as possible duplicates. Two searches, stop. PDF badge reads "CANDIDATE ONLY · UNCONFIRMED." That is the correct outcome, not a failure.
