# Product QA report: design decisions

Recorded so the next person doesn't relitigate them. `scripts/product_qa.py` reads the top-level bullets below into the report's "Design notes" panel, so keep each decision as one `- **Title.** body` bullet (nested bullets fold into their parent).

- **Visual system.** Follows acos-main's visual_system.md: full-bleed wash and base bands, hairline dividers, no cards or shadows, Lora Regular headline, Mulish everywhere else, and fonts embedded as base64 from signatry-brand-core.
- **One QA cell per row.** It shows only failing checks, as 16px stroke glyphs (1.6px stroke, round caps). A clean row reads "Clear". Overdue is the only colored glyph, in Jubilee; the hygiene flags stay ink.
- **Why custom glyphs.** The Signatry brand icon library was tested and doesn't read below 24px. Each glyph's SVG lives in config (`product_qa.checks[].svg`), so a new check brings its own icon.
- **Runway dot colors.** Chosen in order: delivered, overdue, in flight, not started. Stack order, bottom to top, follows the same sequence.
  - Dawn for overdue.
  - Legacy for in flight. Glacier was too close to the grey; dark mode uses Glacier because Legacy is too dark there.
  - Midnight 40% for not started. The owner prefers the lighter tone.
  - Midnight for delivered, Ice in dark mode.
- **Runway background and lines.** A 10% Dawn wash marks the overdue zone. The today line is Dusk in light mode and Ice in dark mode, so it doesn't clash with the Dawn dots.
- **Month-range targets.** Grouped into one bar per distinct range, which makes the vagueness visible instead of hiding it.
- **Filtering.** The QA ledger and the owner table are the filtering controls for the detail tables. Selecting an active filter again clears it.
- **Dates.** dd MMM yyyy everywhere. Ranges compress shared parts (01–31 Oct 2026, 01 Oct–31 Dec 2026) and use the full form when years differ. Short dd MMM appears only in chart labels and headings. Formatting happens in Python so the HTML, markdown, and JSON outputs match.
- **Exclusion.** An idea leaves QA if any one of these is true: it is archived, its Roadmap value is in exclude_from_qa.roadmap_values, or its status category is in exclude_from_qa.status_categories. Roadmap Done ideas still appear on the runway as delivered; archived ideas appear nowhere.
- **Glacier value.** The palette uses Glacier #3aafa9 at the owner's direction. As of this build, signatry-brand-core (SKILL.md and reference/tints.md), acos-main's visual_system.md, and signatry-icons' changelog all record #37a49f as Glacier and call #3aafa9 stale. The value is config in product_qa.palette, so it changes in one place once that is settled.
- **Print.** Landscape @page and print-color-adjust: exact. Rows never split across pages, table headers repeat, and the filter bar is hidden.
