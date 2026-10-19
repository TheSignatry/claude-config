# Research playbook

The goal is a defensible identification, not a complete one. A reviewer will act on what you write, so an honest "not identified" is worth more than a confident guess.

## 1. Read the state file first

Everything HubSpot knows is already in `contacts/<id>.json`. Before searching, form one to three hypotheses from:

- **Email handle** (`derived.email_handle`). This was the single best matching token in the pilot: `tridocrecker` → a triathlete dentist named Recker; `tomvanderwell` → a personal domain and X handle; `pabrown54` → Paul A. Brown. A corporate domain (`@patriotmobile.com`, `@beamanventures.com`) is itself a strong signal.
- **Record-source event** (`derived.record_source_event`) for geography.
- **Referral channel** for context ("Family Office" → wealth management; "Nonprofit Partner" → event guest).
- **Household pair / surname matches** to know who else to expect.
- **Notes and emails**, when they exist, for the company or spouse named in passing.

## 2. Budget by tier

| Tier | Searches | Fetches | Notes |
|---|---|---|---|
| `placeholder` | 0 | 0 | First name is Husband/Wife/Guest/blank. Write the not-researchable form. |
| `thin` | ≤ 2 | 0 | No email, no address/phone. Common names almost never resolve; try one distinctive query then stop. |
| `standard` | ≤ 6 | ≤ 4 | Stop as soon as High is reached. |

Queries are 1–6 words. Run them in this fixed order — the **search recipe** — so that two runs on the same contact make the same moves. Skip a step only when its input is missing (no address, no spouse); never reorder.

| # | Query | Skip when |
|---|---|---|
| 1 | `"First Last" city state` (or the event geography from `record_source_event`) | never |
| 2 | corporate email domain, or the email handle if it is not a plain name (`tridocrecker`, `pabrown54`) | free-mail address with a plain-name handle |
| 3 | `"First Last" "street address"` or `"street address" city` | no address on file |
| 4 | **household step**: `"Spouse First Last" company` / `"Spouse First Last" email-domain` — the spouse from `associations.spouse_in_hubspot`, `household_pair_candidate`, or a public source. Then, if the contact is still Low/None, research that person's employer, role, and ownership (see §5, Household) | no spouse or household member known |
| 5 | company site or press: `"Company" about`, `"Company" acquisition OR founder OR owner` | no company named by steps 1–4 |
| 6 | one disambiguation query for the strongest remaining ambiguity (title conflict, two candidates) | nothing left to disambiguate |

Stop rules: stop as soon as **both** scores reach High, or when the budget is spent, or when the recipe is exhausted. `None` for the contact is allowed only after steps 1–4 have run (or been legitimately skipped) — "the name is too common" is a rationale for `None`, not a reason to skip the household step. Every URL you relied on, including those about the spouse or the household company, goes in `sources`; a source is not disqualified because it is about the spouse rather than the contact.

## 3. Navigation: Playwright first, tools as fallback

Use `python scripts/playwright_fetch.py --url <url>` to open a page and `--search "<query>"` to run a DuckDuckGo HTML search and return result titles/URLs/snippets as JSON. The script:

- exits non-zero with `reason: no_browser` if Playwright's Chromium is not installed (`python -m playwright install chromium` fixes it where the network allows);
- exits non-zero with `reason: network_blocked` when the sandbox cannot reach the site;
- never submits credentials, never clicks "Sign in", honors `robots.txt` disallow for the path, and truncates page text to ~6,000 characters.

When it fails for environmental reasons, use the `web_search` and `web_fetch` tools instead and set `research.navigation = "web_tools_fallback"`. Both paths produce the same evidence; only the transport differs. LinkedIn profile pages cannot be read without login on either path; capture the public URL from search results and take role/company details from other public sources (company site, press releases, directories, bios).

## 4. Match standard

- **High** — two or more independent signals agree. Corporate email domain + a company press release naming the person; email handle + a personal domain; handle + a bio detail + the geographic cluster from the event form.
- **Moderate** — one strong public match for an uncommon name with nothing contradicting it, but HubSpot holds no confirming data (no email, no city).
- **Low** — a plausible candidate whose link to this record is circumstantial (common name + geography + context). Everything about the candidate is prefixed `Candidate only:`.
- **None** — not identifiable. Research fields stay null. Say in `notes` what was tried.

Score **two things separately** on this scale. `match_confidence` is about the **contact's own** public identification. `household_confidence` is about the **spouse/household**: High when the spouse's identity and employer are corroborated by two independent signals (for example a HubSpot association or the donor's own statement plus a public listing at the same address or a corporate email domain matching a public bio); Moderate for one strong public match; Low for circumstantial; `None` when no spouse or household member is known at all. The two scores are independent — a donor with no public footprint married to a well-documented executive is `match_confidence: None`, `household_confidence: High`, and that is a complete, useful result, not a failure. The PDF badge shows both.

**Corroboration rule for public spouse sources.** A wedding website, engagement announcement, or bio that names a spouse counts toward High only when it matches at least one fact HubSpot already holds — the street address or city, the employer or its email domain, a phone number, or an age band consistent with the record. Record which one in `household.spouse_corroboration`. "Andrew Cook and Melanie" on a wedding page in another state, for a couple whose HubSpot household predates the wedding, is a different couple until proven otherwise: Moderate at most, and say so. `merge_state.py` enforces this unless the spouse came from an association label.

A third-party report supplied by staff (e.g., WhiteBridge) counts as one signal for facts it documents (title, event attendance, a named video). Its AI-generated "insights" sections count for nothing and must not be reproduced.

## 5. What to capture

**Identity:** public spelling of the name (flag variants such as "Vander Well" vs "VanderWell"), city/state, LinkedIn URL from search results, other public web (personal site, X handle, author page).

**Household:** a spouse only when a public source names one — a bio ("lives in Pella with his wife Wendy"), a team page, a property record listing co-owners, an event photo caption, a video title. Record the source. Then say whether that spouse is in HubSpot: `confirmed` (association), `probable` (household pair or same-form guest), `surname-only`, `no`, or `unknown`. People-search and property-record aggregators are acceptable for corroboration but must be labeled "verify".

**Spouse's company (required when a spouse is known and the contact is Low/None).** Research the spouse the same way you would the contact — employer, role/title, HQ, website, revenue with source, ownership type and principals — and write it to `household.spouse_company`, a block with the same keys as `company`. It never goes in the contact's own `company` block: the reviewer must be able to tell the donor's employer from the donor's spouse's employer at a glance. If the spouse has no public footprint either, set `spouse_company.name` to `Not found – <what was tried>` so the validator can see the step ran. Reuse `companies/<slug>.json` for the spouse's company exactly as for the contact's.

**Company and role:** legal/common name, HQ address, website, and the person's title as a source states it. If the person is an employee of a large firm, say so and set ownership to `N/A – employee`.

**Revenue:** only with a named source. Label third-party estimates as estimates (ZoomInfo, Dun & Bradstreet, Growjo). Label predecessor or parent-company figures as such (Beaman Automotive's 2019 revenue is not Beaman Ventures' revenue). Small professional practices rarely publish revenue; write "Not public" and give the best proxy you found (employee count).

**Ownership:** type (public / private / family / professional practice / nonprofit / N/A – employee), owners or principals, and where that came from (Secretary of State filing, press, company "about" page, professional-registration data). When the source is a bio rather than a filing, say so.

**Nonprofit role associations:** boards, officer roles, and staff positions at nonprofits that a public source documents. This is where a HubSpot "referral" company can legitimately become a role if a bio proves it.

**Public identifiers:** an EIN from a Form 990, a CRD from an SEC or FINRA record, a state professional license number, or a Secretary of State entity number is public data published by the regulator to identify the registrant. Record it where it helps a reviewer confirm the match (usually in `revenue_source`, `ownership_source`, or a source title) and leave it in source URLs. Do not record private identifiers (account, card, or government ID numbers of a person).

**Deceased:** if an obituary, memorial page, or local news reports the contact has died, set `deceased_per_public_source: true` and put the date in `notes`. Never the cause. HubSpot often still shows such a record as an active client; the flag is what tells the relationship manager to fix it before outreach.

**Role on the fund:** `derived.role_on_fund` comes from the Fund association labels. `advisor` means the contact is a financial or grant advisor on a client's fund, not a donor — research the firm normally, say so plainly in the overview, and do not describe the contact as a donor.

**Flags:** ZIP/city mismatches, placeholder names, spelling variants, likely duplicates among surname matches, referral-only associations stored as companies, stale LinkedIn headlines.

## 6. Writing the overview

Three to six sentences, third person, plain and factual, in Signatry house style: "The Signatry", "donors", "nonprofits", "donor advised fund", Oxford comma, no emojis, dates without ordinals. Cite the type of source inline in words ("per a June 2026 company press release", "a Nashville property record lists"). No adjectives about character, no advice on how to approach the person.

## 7. Company reuse

Before researching a company, check `state/companies/<slug>.json` (slug = email domain or lower-snake company name). If present, reuse it and add this contact to `used_by`. If not, write it after researching so colleagues in the same batch get it for free.

**Shared domains.** Broker-dealer and wirehouse domains (`nm.com`, `lpl.com`, `ml.com`, `ubs.com`, `edwardjones.com`, and the rest of `SHARED_DOMAINS` in `cr_common.py`) are used by thousands of unrelated practices. A company record keyed to one of them describes one practice, not the next contact's employer. For a contact on a shared domain, use the practice's own website domain as the slug (`bieldwealth.com`, not `nm.com`); if the practice has no domain of its own, leave `company_slug` null and put the facts in the contact's `company` block only. `orchestrate.py pack` never offers a shared-domain record as `company_prior`; it does offer `company_prior_by_employer`, a record whose name matches the HubSpot employer, so colleagues on different email domains still share one record.

**Personal and family domains.** `derive.py` marks free-mail, privacy-relay, and ISP domains (`PERSONAL_DOMAINS`) and surname vanity domains (`thewilsoncrew.com`, `sollazzo.org`; `derived.is_vanity_domain`) as non-corporate. Never write a company record for one.

## 8. Write the fragment

Produce a JSON fragment matching the `research` block in `state_schema.md` and merge it:

```bash
python scripts/merge_state.py --run-dir state/ --id <id> --stage research --file /tmp/research_<id>.json
```

Set `model` to the exact model ID of the model doing the research (for example `claude-fable-5-1`), never a placeholder such as `interactive` — it is printed in every PDF footer and in the workbook so a reviewer can see which model produced the profile.

The validator will reject fragments where `model` is missing or a placeholder, where a High/Moderate result has no sources, where Low/None candidate fields lack the `Candidate only:` prefix, where the overview contains characterization language, or where any value looks like Restricted data. Fix and re-merge rather than bypassing.
