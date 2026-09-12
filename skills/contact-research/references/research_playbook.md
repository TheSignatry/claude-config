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

Queries are 1–6 words. Start with the most distinctive token: corporate domain, unusual handle, or uncommon surname plus geography. Add the referral context in the second query if the first misses. Do not repeat near-identical queries.

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

A third-party report supplied by staff (e.g., WhiteBridge) counts as one signal for facts it documents (title, event attendance, a named video). Its AI-generated "insights" sections count for nothing and must not be reproduced.

## 5. What to capture

**Identity:** public spelling of the name (flag variants such as "Vander Well" vs "VanderWell"), city/state, LinkedIn URL from search results, other public web (personal site, X handle, author page).

**Household:** a spouse only when a public source names one — a bio ("lives in Pella with his wife Wendy"), a team page, a property record listing co-owners, an event photo caption, a video title. Record the source. Then say whether that spouse is in HubSpot: `confirmed` (association), `probable` (household pair or same-form guest), `surname-only`, `no`, or `unknown`. People-search and property-record aggregators are acceptable for corroboration but must be labeled "verify".

**Company and role:** legal/common name, HQ address, website, and the person's title as a source states it. If the person is an employee of a large firm, say so and set ownership to `N/A – employee`.

**Revenue:** only with a named source. Label third-party estimates as estimates (ZoomInfo, Dun & Bradstreet, Growjo). Label predecessor or parent-company figures as such (Beaman Automotive's 2019 revenue is not Beaman Ventures' revenue). Small professional practices rarely publish revenue; write "Not public" and give the best proxy you found (employee count).

**Ownership:** type (public / private / family / professional practice / nonprofit / N/A – employee), owners or principals, and where that came from (Secretary of State filing, press, company "about" page, professional-registration data). When the source is a bio rather than a filing, say so.

**Nonprofit role associations:** boards, officer roles, and staff positions at nonprofits that a public source documents. This is where a HubSpot "referral" company can legitimately become a role if a bio proves it.

**Flags:** ZIP/city mismatches, placeholder names, spelling variants, likely duplicates among surname matches, referral-only associations stored as companies, stale LinkedIn headlines.

## 6. Writing the overview

Three to six sentences, third person, plain and factual, in Signatry house style: "The Signatry", "donors", "nonprofits", "donor advised fund", Oxford comma, no emojis, dates without ordinals. Cite the type of source inline in words ("per a June 2026 company press release", "a Nashville property record lists"). No adjectives about character, no advice on how to approach the person.

## 7. Company reuse

Before researching a company, check `state/companies/<slug>.json` (slug = email domain or lower-snake company name). If present, reuse it and add this contact to `used_by`. If not, write it after researching so colleagues in the same batch get it for free.

## 8. Write the fragment

Produce a JSON fragment matching the `research` block in `state_schema.md` and merge it:

```bash
python scripts/merge_state.py --run-dir state/ --id <id> --stage research --file /tmp/research_<id>.json
```

The validator will reject fragments where a High/Moderate result has no sources, where Low/None candidate fields lack the `Candidate only:` prefix, where the overview contains characterization language, or where any value looks like Restricted data. Fix and re-merge rather than bypassing.
