# claude-config

Configuration for using Claude at The Signatry — organization-wide instructions and reusable skills.

## Contents

### Organization instructions (`org-instructions/`)

- **`organization_instructions_readable.md`** — the source of truth. Written in an
  expanded, easy-to-edit format with one ALL-CAPS section heading and one paragraph
  per idea.
- **`organization_instructions.md`** — the compact version actually loaded as Claude's
  organization-level system instructions. Generated from the readable file.
- **`shorten_oi.py`** — converts the readable file into the compact one. Each ALL-CAPS
  heading is folded into a `Heading: ` prefix, and the paragraphs within a section are
  joined onto a single line, removing the blank lines between them.

To regenerate `organization_instructions.md` after editing the readable version:

```bash
cd org-instructions
python3 shorten_oi.py
```

Edit `organization_instructions_readable.md`, not `organization_instructions.md`
directly — the compact file is generated output and will be overwritten.

### Skills

Every skill under `skills/{skill-slug}/` follows the same folder layout:

- **`SKILL.md`** — required. Flat YAML frontmatter (`name`, `description`,
  `version`, `release_date` — always top-level keys, never nested under a
  `metadata:` block) plus the body Claude reads when the skill fires.
- **`reference/` or `references/`**, **`scripts/`**, **`assets/`** — optional.
  Detail, code, and data files deferred out of `SKILL.md`, loaded only when
  the skill's own instructions point Claude to them.
- **`_exclude/`** — required. Holds `CHANGELOG.md` (this skill's revision
  history — newest first, one `##` heading per release; see
  `signatry-brand-core` for the reference example) and any generated
  reports (e.g. `skill_budget_audit.py`'s output, below). Excluded from
  `package_skill.py`'s zip and never read into context automatically —
  nothing here is meant to reach Claude.

Version and release date come from each skill's own `SKILL.md` frontmatter — update
this table whenever those change. `python3 skills/lint_skills.py` enforces that the
frontmatter fields exist, but does not check that this table matches them.

| Skill | Description | Version | Release date |
|---|---|---|---|
| [`signatry-style`](skills/signatry-style/) | The Signatry's official writing and brand voice guide: audience and voice, required terminology, faith-related capitalization and scripture usage, number/date/mechanics rules, structural and narrative patterns, and visual/brand references. Use whenever writing, editing, reviewing, or proofreading any content for The Signatry. | 2.2 | 2026-08-06 |
| [`signatry-brand-core`](skills/signatry-brand-core/) | Canonical source of truth for The Signatry's brand colors, fonts, and logo/mark assets, independent of file format. Format-specific brand skills (pptx, docx, pdf) depend on this one for values and assets rather than restating them. | 1.1 | 2026-07-31 |
| [`signatry-content-guardrails`](skills/signatry-content-guardrails/) | Content restriction rules for The Signatry — fabrication prohibition, donor photo/quote reuse, gift-amount confidentiality, and board-only source restriction — independent of format. Use on every Signatry deliverable, any format. | 2.1 | 2026-07-31 |
| [`signatry-facts`](skills/signatry-facts/) | Canonical record of The Signatry's organizational facts: contact details, legal entity and leadership names, founding history, scale figures, fund terms, and approved boilerplate/disclaimer text. Use whenever content will state a specific factual value. | 1.3 | 2026-08-06 |
| [`signatry-resource-library`](skills/signatry-resource-library/) | The Signatry's authoritative Fact Sheets and Guides on DAF mechanics, complex asset giving, family generosity, and nonprofit vetting/fundraising — 45 SharePoint documents and public webpages. Use whenever recommending an existing donor resource or drafting content that should be grounded in these documents. | 1.0.1 | 2026-08-06 |
| [`signatry-icons`](skills/signatry-icons/) | The Signatry's brand icon library — 69 single-color icons (SVG and PNG, Glacier) with a searchable catalog and search script. Use whenever a deliverable needs an icon, in any format. | 3.4 | 2026-07-31 |
| [`signatry-photo-library`](skills/signatry-photo-library/) | The Signatry's curated image library — 44 photographs (donor families, stock lifestyle, landscape/nature) with a searchable catalog and search script. Use whenever a deliverable needs a photograph, in any format. | 2.1 | 2026-08-06 |
| [`signatry-pptx-brand`](skills/signatry-pptx-brand/) | Signatry brand system for PowerPoint decks: color palette, fonts (Mulish, Lora), and logo/quill assets. Pair with a general pptx build skill and, for donor-facing copy, `signatry-style`. | 2.4 | 2026-08-07 |
| [`signatry-docx-brand`](skills/signatry-docx-brand/) | Signatry brand templates for Word documents: which of the two bundled `.dotx` templates to start from (general brand-styles vs. letterhead) and the mechanics of building from one. Pair with a general docx build skill and, for donor-facing copy, `signatry-style`. | 1.6 | 2026-08-07 |
| [`signatry-pdf-brand`](skills/signatry-pdf-brand/) | Signatry brand system for PDFs built with reportlab: font registration/embedding, color palette, and logo usage. Pair with a general pdf skill and, for donor-facing copy, `signatry-style`. | 1.3 | 2026-08-06 |
| [`sounding-board`](skills/sounding-board/) | Role-plays a panel of fictional, composite personas reacting to an idea, message, decision, or proposal before it goes out. Covers seven audiences (employee, donor, advisors, VIP family, board, shepherds/C-suite, nonprofit partner), each with its own persona file in `references/`. | 0.5 | 2026-07-26 |

### Skill tooling

- **`schemas/skill-schema.json`** — the JSON Schema every skill's SKILL.md
  frontmatter is evaluated against (required: `name`, `description`,
  `version`, `release_date`, plus field formats). This is the rubric
  `lint_skills.py` enforces; edit it to change what counts as a valid skill.
- **`skills/lint_skills.py`** — validates every skill package under `skills/`:
  SKILL.md frontmatter against `schemas/skill-schema.json` (required: `name`,
  `description`, `version`, `release_date`), description trigger-language
  quality, relative markdown link integrity, and an IT15 Restricted-data scan
  (SSNs, payment card numbers, bank/account numbers, credentials/keys) across
  every text file in the skill. Any Restricted-data finding hard-fails the
  build; matched values are always masked in the output. Also enforces the
  folder-structure standard above: frontmatter must not nest `version`/
  `release_date` (or anything else) under a `metadata:` block, `_exclude/CHANGELOG.md`
  must exist and be non-empty, and no changelog/revision-history section may
  remain inline in `SKILL.md`.
- **`skills/skill_budget_audit.py`** — advisory only (never blocks a build,
  unlike lint): estimates how much of a skill's content loads into Claude's
  context and flags ways to reduce it — a `SKILL.md` body that's an outlier
  relative to its siblings, large inline code blocks/tables that belong in
  `scripts/`/`reference(s)/` instead, deferred files never mentioned anywhere
  in `SKILL.md`, and reference/scripts/assets mentions with no "load only
  when..." gating language. Writes a Markdown report (or JSON with `--json`)
  to `<skill>/_exclude/skill_budget_audit.md` by default, in addition to
  printing to stdout; override the filename with `--output`.
- **`skills/lint_allowlist.json`** — marks specific `assets/`/`scripts/`
  path mentions as expected even though they don't exist in that skill
  (e.g. a path that belongs to a different skill/tool), keyed by skill
  directory name. Each entry is `{"path": ..., "reason": ...}` — a
  non-empty `reason` explaining *why* the path is expected is required;
  `lint_skills.py` warns on entries missing one (or written as a bare
  string) and separately warns if an entry no longer appears anywhere in
  that skill's text, so the file can't be a rubber stamp or silently go
  stale.
- **`skills/package_skill.py`** — packages a single skill into an
  upload-ready `{skill-slug}-{version}.zip` (SKILL.md at the zip root, no
  wrapping folder), refusing to package if the skill fails
  `lint_skills.py` with an ERROR or CRITICAL finding.

Run these from the repo root:

```bash
# Lint every skill; add --strict to treat warnings as failures too
python3 skills/lint_skills.py

# Lint a skills/ directory in a different location, as text or JSON
python3 skills/lint_skills.py --path path/to/skills --json

# Package one skill after it passes lint (writes into that skill's own dir)
python3 skills/package_skill.py signatry-style

# Preview what would be packaged without writing the zip
python3 skills/package_skill.py signatry-style --dry-run

# Advisory: how much of a skill's context/token budget it uses, and how to trim it
python3 skills/skill_budget_audit.py signatry-style

# Same, across every skill, as JSON
python3 skills/skill_budget_audit.py --all --json
```

If `lint_skills.py` reports a `CRITICAL` finding, do not distribute the
skill — remove the offending data and report it to the Technology Team per
IT14 Policy 10.

## How to Use

This repo is the source-controlled copy of everything Claude is configured
with at The Signatry. The files here aren't consumed directly by Claude —
each piece has to be deployed to where Claude actually reads it.

### Organization instructions

`org-instructions/organization_instructions.md` (the compact, generated file)
is what's pasted into the organization-level system instructions field in the
Anthropic Console admin settings. That Console field is the only place it
takes effect — editing the file in this repo alone changes nothing for
end users until it's re-pasted there.

### Skills

- **Local development/testing** — symlink or copy an individual skill folder
  (e.g. `skills/signatry-style/`) into your local `~/.claude/skills/` (or a
  project's `.claude/skills/`) to try it out with Claude Code before
  publishing it org-wide.
- **Org-wide deployment** — package the skill with `package_skill.py` (see
  below) and upload the resulting zip on the Claude.ai/Console admin Skills
  page. That upload is what makes the skill available to all Signatry users
  in Claude.ai; committing the skill to this repo does not by itself deploy
  it.

## How to Update

### Organization instructions

1. Edit `org-instructions/organization_instructions_readable.md` (never edit
   `organization_instructions.md` by hand — it's generated).
2. Regenerate the compact file:
   ```bash
   cd org-instructions
   python3 shorten_oi.py
   ```
3. Copy the regenerated `organization_instructions.md` contents into the
   organization-level system instructions field in the Anthropic Console
   admin settings, and commit the updated files here so the repo stays the
   source of truth.

### Skills

1. Edit the skill's files under `skills/{skill-slug}/`, bumping `version` and
   `release_date` in its SKILL.md frontmatter (flat top-level keys, never
   nested under `metadata:`), and add a new entry at the top of its
   `_exclude/CHANGELOG.md` (newest first, one `##` heading per release).
2. Lint it: `python3 skills/lint_skills.py` (fix any `ERROR` or `CRITICAL`
   finding — CRITICAL findings are IT15 Restricted-data hits and must never
   be distributed; see IT15 and report them per IT14 Policy 10).
3. Optionally check its context/token footprint:
   `python3 skills/skill_budget_audit.py {skill-slug}` — advisory only,
   doesn't block packaging.
4. Package it: `python3 skills/package_skill.py {skill-slug}`, which refuses
   to build a zip if the skill still fails lint.
5. Upload the new `{skill-slug}-{version}.zip` on the Claude.ai/Console admin
   Skills page, replacing the previous version.
6. Commit the skill changes (the zip itself is gitignored) so this repo
   reflects what was deployed.

## License

Released under CC0 1.0 Universal — see [LICENSE](LICENSE).
