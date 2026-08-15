# CLAUDE.md

Guidance for Claude Code when working in this repo. See `README.md` for the
skill folder structure, tooling command reference, and deployment process —
this file covers agent-specific operating conventions instead of repeating it.

## Tooling — run in this order when editing a skill

1. `python3 skills/lint_skills.py` — structural/schema/changelog-standard
   validation plus an IT15 Restricted-data scan. Must be all-`[PASS]` (or
   warnings only, if `--strict` isn't a concern) before moving on. Any
   `CRITICAL` finding means stop and report per IT14 Policy 10 — never
   distribute a skill with one.
2. `python3 skills/skill_budget_audit.py {skill-slug}` — advisory context/
   token-budget check (not a gate, doesn't block anything). Writes a report
   to `{skill}/_exclude/skill_budget_audit.md` and records a version
   snapshot in `skills/skill_budget_stats.json`.
3. `python3 skills/package_skill.py {skill-slug}` — packages for upload;
   refuses if lint fails.

## Final QA pass (before commit + PR)

Run this whenever the user asks for a "final QA pass" (typically right
before committing and opening a PR), in this order — the scripted checks
come first because the judgment checks below consume their output:

1. `python3 skills/final_qa.py` — lints every skill, refreshes every
   skill's budget-audit report and `skills/skill_budget_stats.json`,
   packages every skill that passes lint (also silently fixes any zip
   left over from a prior version, since packaging always rebuilds), and
   flags two things no single existing script checks: a skill with
   deferred content but no `skills/deferred_usage.json` entry, and a
   skill whose frontmatter `version`/`release_date` don't match
   `README.md`'s table. Investigate anything under `BLOCKING` before
   doing anything else — that mirrors `lint_skills.py`'s own exit code
   and means an IT15 CRITICAL finding or a schema/changelog-standard
   ERROR somewhere.
2. For any skill named in the README-drift warning, or any skill edited
   this session: reread its row in `README.md` and confirm the
   description column still accurately summarizes it — the version/date
   numbers are checked automatically, the prose isn't.
3. For any skill named in the deferred-usage-gap warning: decide whether
   it belongs in `skills/deferred_usage.json` (see that file's `_readme`
   entry for the two classifications) and add a reasoned entry if so.
4. Check `org-instructions/` drift — never trust file modification times
   (a checkout/clone stamps both files together regardless of real edit
   history, so matching mtimes prove nothing). Actually regenerate and
   diff: `cd org-instructions && python3 shorten_oi.py && git diff
   organization_instructions.md`. An empty diff is the only real proof
   the compact file is in sync with the readable source; a non-empty
   diff means it changed and needs re-pasting into the Anthropic Console
   per `README.md`'s existing process — alert the user either way.
5. Immediately before committing, run an unconditional `git status` /
   `git diff` as a last check, not a formality: this repo is edited
   outside any single conversation (direct edits, other sessions), so
   nothing verified earlier in a session substitutes for checking the
   real, current state right before commit.

## Skill-editing conventions

- Frontmatter is flat — `version`, `release_date`, and any custom fields are
  top-level YAML keys, never nested under a `metadata:` block.
- Any task that changes a skill's content (not just feature work —
  token-efficiency trims and cleanups count too) bumps `version` +
  `release_date` and gets one new entry at the top of that skill's
  `_exclude/CHANGELOG.md` — once per task, not once per edit. If a task
  touches the same skill across several individual edits, batch them: bump
  once at the end and summarize everything that changed in one entry,
  rather than adding an entry after every Edit call. A genuinely separate,
  distinctly-scoped ask still gets its own bump, even if it happens later
  in the same session — the boundary is the task, not the session. See
  `signatry-brand-core` v1.1 or `signatry-pptx-brand` v2.5 for examples of
  a single entry covering a whole trim/cleanup pass, not a blow-by-blow.
- "Development note" / provenance-style prose in a `SKILL.md` body (e.g.
  "confirmed with Ben, July 2026") can usually move to that skill's
  `CHANGELOG.md`, provided the operational fact stays put and the edit
  doesn't turn the remaining sentence into a fragment — judge each instance
  individually, don't mechanically strip every date/name mention.

## Testing the meta-tooling itself (`lint_skills.py`, `skill_budget_audit.py`, `package_skill.py`)

- Never test a change to these scripts destructively against the real
  `/skills` tree. Build a throwaway fixture skill under the scratchpad
  directory first, exercising the specific behavior being changed.
- Also verify against the real repo (`--all` where supported) once the
  fixture check passes — the real 11 skills surface real edge cases
  (duplicate content, large asset libraries, mixed frontmatter styles) a
  synthetic fixture won't.
- Watch for side effects from verification runs themselves —
  `skill_budget_audit.py` writes report files on every invocation, so a
  test run can leave stray artifacts across every skill's `_exclude/`.
  Check `git status`/`find` afterward and clean up anything the test itself
  created that wasn't intentional.
- Re-run `python3 skills/lint_skills.py` after any change that touches skill
  content or the lint script itself, even when the change looks unrelated
  to what lint checks.

## Working style

- Before a nontrivial or repo-wide change (a new lint rule, a standard
  applied across many skills, a content-cleanup sweep), do a detailed
  read-only analysis first — concrete findings with exact quotes/line
  numbers/counts, not a summary — before proposing or making any edit.
- Ground claims in actual numbers computed the same way the tooling does
  (e.g. the chars/4 token heuristic already used across these scripts)
  rather than qualitative estimates, especially for "how much would this
  save/matter" questions.
- When a fix is scoped to one specific issue, stay scoped to it — don't
  fold in adjacent-but-unrequested cleanup found along the way; call it out
  separately instead and let it be a deliberate decision, not a drive-by.

## Data handling

`lint_skills.py`'s Restricted-data scan (IT15) covers SSNs, payment cards,
bank/account numbers, and credentials across every skill's text files — a
backstop, not the only safeguard. Anything Restricted found outside a skill
(donor SSNs, health/financial detail, Board-only material) should never be
processed — stop and point to IT15/IT14 Policy 10.
