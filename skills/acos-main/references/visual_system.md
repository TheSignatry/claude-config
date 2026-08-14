# acos-main visual system

Single source of truth for every HTML artifact this skill renders (`morning-plan`, `week-plan`, `month-retro`). Read this before authoring any artifact — don't re-derive the palette or layout from memory or from the `/morning` reference directly. The *layout language* below is adapted from the real `/morning` skill (an Anthropic-produced artifact Trevor supplied directly); the *colors and fonts* are `signatry-brand-core`'s actual values, mirrored locally per the same pattern `signatry-pptx-brand`/`signatry-docx-brand`/`signatry-pdf-brand` already follow — pull from `../signatry-brand-core/`, add only the HTML-specific mechanics here.

## Palette

All values from `signatry-brand-core/SKILL.md`'s base table and its precomputed tint table (tint formula: `tinted = round(255 + (base-255) * (pct/100))` per channel — recompute from there if a base hex ever changes; don't hand-edit the table below).

| Role | Token | Value | Source |
|---|---|---|---|
| Ink (headings, SVG strokes) | `--ink` | `#17242a` | Midnight, 100% |
| Ink-soft (body prose) | `--ink-soft` | `#747c7f` | Midnight, 60% |
| Ink-grey (numerals, muted labels) | `--ink-grey` | `#a2a7aa` | Midnight, 40% |
| Hairline (band border, list dividers) | `--hairline` | `#d1d3d4` | Midnight, 20% |
| Wash band background | `--wash` | `#f4f8f8` | Legacy, 5% |
| Base band background | `--bg` | `#ffffff` | plain white |
| Accent (buttons, conflict annotation, kicker underline) | `--accent` | `#d77900` | Dusk, 100% |

No brand-core token exists for a hairline/divider or a wash-tint background — both are derived here from Midnight/Legacy tints rather than invented from scratch. This is a documented gap-fill, not a deviation; recompute from `signatry-brand-core`'s own tables if either base color ever changes there.

No hover-darken shade is defined for `--accent` — brand-core's tint system only produces *lighter* mixes (toward white), and there's no official darker variant to draw on. Skip a distinct hover treatment rather than inventing an unofficial shade; a static report artifact doesn't lean on hover states the way an interactive app does.

## Fonts

Mirrored locally from `signatry-brand-core/assets/fonts/`, embedded as base64 `@font-face` in every artifact (self-contained, no external font requests):

- **Headline**: Lora Regular (`Lora-Regular.ttf`) — **regular weight only, never bold**, per brand-core's standing July 2026 rule. Derive visual weight from size and color (`--ink`, ~32–36px), not from font-weight. This is a deliberate divergence from the `/morning` reference (which uses Fraunces at weight 600) — brand-core's rule wins.
- **Body / everything else**: Mulish. Regular for prose, SemiBold for bold titles/emphasis, Bold/ExtraBold for uppercase section labels and kickers.

## Category → color mapping (acos-calendar-analysis's 7 benchmark categories)

Used by `week-plan`'s time-of-day day chart and `month-retro`'s category-comparison chart (see their own sections below — neither is a segmented proportional bar; that was the original design and was replaced 2026-08-15 after live use showed it double-counting overlapping time). Brand-core defines no category-color scheme of its own — this mapping is `acos-main`'s own design decision, drawing on brand-core's named hues:

| Category | Color | Hex |
|---|---|---|
| Focused production | Legacy | `#2b7a78` |
| People leadership | Dusk | `#d77900` |
| External ecosystem | Glacier | `#37a49f` |
| Operating rhythm | Jubilee | `#8a1e41` |
| Strategy and transformation | Heartfelt | `#fd4a5c` |
| Stakeholder partnership | Dawn | `#f2a65a` |
| Capacity unavailable | Midnight 40% tint | `#a2a7aa` (muted — deliberately, this time shouldn't visually compete) |
| Margin / Flex capacity (free time) | Ice | `#def2f1` (near-blank — reads as open capacity) |

## HTML/CSS band skeleton

Two full-bleed bands per artifact (more for `month-retro`'s four stacked sections — same skeleton repeated), centered content, no cards, no shadows, no rounded corners — matching `/morning`'s minimal chrome exactly, just reskinned:

```css
:root {
  --ink:#17242a; --ink-soft:#747c7f; --ink-grey:#a2a7aa;
  --hairline:#d1d3d4; --wash:#f4f8f8; --bg:#ffffff; --accent:#d77900;
}
* { margin:0; padding:0; box-sizing:border-box; }
body { background:var(--bg); font-family:'Mulish', -apple-system, 'Segoe UI', sans-serif; color:var(--ink); }
.band { width:100%; }
.band.wash { background:var(--wash); border-bottom:1px solid var(--hairline); }
.band.base { background:var(--bg); }
.inner { max-width:860px; margin:0 auto; padding:40px 32px 36px 32px; }
.eyebrow { color:var(--ink-soft); font-size:14px; letter-spacing:0.02em; margin-bottom:10px; }
.headline { font-family:'Lora', Georgia, serif; font-weight:400; font-size:34px; line-height:1.25; color:var(--ink); max-width:680px; margin-bottom:14px; }
.section-heading { font-size:13px; font-weight:800; text-transform:uppercase; letter-spacing:0.04em; color:var(--ink); margin-bottom:18px; }
.list { list-style:none; }
.item { display:flex; gap:14px; padding:16px 0; border-top:1px solid var(--hairline); }
.item:first-child { border-top:none; padding-top:0; }
.item-num { color:var(--ink-grey); font-size:13px; font-weight:600; min-width:16px; padding-top:2px; }
.item-title { font-weight:700; font-size:15px; color:var(--ink); margin-bottom:4px; }
.item-sentence { font-size:14px; line-height:1.5; color:var(--ink-soft); }
.src { color:var(--ink); text-decoration:underline; text-decoration-color:var(--ink-grey); }
.btn { display:inline-block; margin-top:8px; padding:6px 14px; background:var(--accent); color:#fff; font-size:13px; font-weight:700; text-decoration:none; }
@media (max-width:640px) { .headline { font-size:26px; } }
```

A button (`.btn`) only appears where a genuine next step exists that Claude could take in a follow-up ask (e.g. "Draft a reply") — never for "you decide this yourself" items, matching `/morning`'s own rule exactly. `acos-main` itself has no write access beyond `morning-plan`'s email-sort step, so any button here is an offer for the *next* conversation turn, not an action the artifact performs itself.

## SVG conventions (morning-plan's day timeline)

Straight horizontal baseline spanning the day's working hours (not `/morning`'s freehand curve — that curve's y-wobble is a stylistic flourish; the x-position/size of each dot *is* real data and should stay deterministic and reproducible run to run):

- One `<line>` baseline, `stroke="var(--ink-grey)"` equivalent (`#a2a7aa`), `stroke-width="2"`.
- Each meeting: a filled `<circle>`, `cx` scaled linearly from time-of-day across the baseline's width, `r` scaled from duration (roughly 4–10px), `fill="#17242a"` for a real meeting, `fill="#a2a7aa"` for free/optional/tentative.
- A double-booking: **two hollow circles** — `fill="#ffffff" stroke="#17242a" stroke-width="2"` — the only hollow shapes on the page, positioned at the two meetings' actual overlap point. Never use a hollow circle for anything else.
- A small `--accent` (`#d77900`) squiggle or short mark annotating the conflict specifically (optional, sparing — one per genuine conflict, not decorative elsewhere).
- A translucent `var(--wash)`-toned bar under the baseline for a protected Working Block (not a dot — it's not a meeting to check for conflicts against).

## Week-plan day chart (time-of-day axis, replaces the original segmented-bar design)

The original design called for a 7-row segmented horizontal bar (one bar per day, length = working hours, segments = category-colored proportional widths). Built and shipped 2026-08-13, then replaced 2026-08-15 after live use surfaced two real problems: (1) summing each event's own duration per day double-counts overlapping time the same way `acos-calendar-analysis`'s own `compute_time_allocation` already had to solve once with a priority sweep — a segmented bar has nowhere to *show* an overlap, only a place to silently mis-total it; (2) a bar whose only axis is "proportion of the working day" can't answer "when does the conflict actually happen." The replacement:

- **X-axis is time-of-day** (07:00–18:00, one `<div>`-per-event track per day row, not SVG) — position and width are computed directly from each event's real start/end minute, linearly scaled to the track's pixel width. Never derive a day's pixel layout from category totals; always from the raw per-event start/end times.
- **Correct aggregate hours still come from `acos-calendar-analysis`'s `daily_time_allocation` report field** (see that skill's `compute_daily_time_allocation`), not from summing the rendered rects — the chart's rect positions and the day's reported category-hour/free-hour totals are computed by two different code paths on purpose (raw events for the visual, the priority-swept report field for the numbers), so don't try to make the rendered rects "add up to" the printed hours by construction.
- **A Focused-production block** (a "Working Block," or any solo event with no real attendees) renders as a translucent wash (`fill-opacity`/`opacity` ~0.20, full row height) *behind* everything else — it's context, not a competing meeting.
- **Every other category** renders as a solid, category-colored rect in its own lane row. Real overlapping meetings (e.g. two double-booked calls) get separate lanes via simple greedy lane assignment (sort by start time; place in the first lane whose previous occupant already ended, else open a new lane) — this is deliberate: a genuine double-booking should be *visible* as two stacked rects, never hidden by only showing one.
- **Free time is the visual absence of a rect** against the hour gridlines — no separate free-time rendering needed.
- Wrap the whole chart in a horizontally-scrolling container (`overflow-x:auto`) since the time-axis track is a fixed pixel width wider than the 640px mobile breakpoint.
- A day with no events (e.g. a quiet Saturday) still gets its own empty row — don't drop the row, since the empty space itself is the answer to "what's on Saturday."

## Month-retro category-comparison chart

Not a reuse of week-plan's chart at a smaller scale (an earlier draft of this doc said that; it isn't accurate — month-retro compares a *percentage against a benchmark range and a prior-month point*, not raw event time, so it's a different chart). One row per benchmark category:

- A horizontal track represents a fixed percentage scale (0% to comfortably above the highest value actually being plotted that run — 32% covered every category in the July 2026 run, but recompute the scale from the actual data rather than hard-coding 32 forever).
- The category's **benchmark target range** renders as a shaded band on the track (a neutral tint, not the category color — the band means "the target," the dot means "this category").
- **Prior month** is a thin tick mark (neutral color).
- **This month** is a solid dot in the category's own color, outlined for contrast against pale category colors (Margin/Flex's Ice `#def2f1` is nearly invisible without an outline).
- The percentage delta next to each row is colored by *direction relative to the target*, not by raw sign — above-target-and-rising or below-target-and-falling are both "moving away" (a warning tone), while a change that moves a category back toward its target range is the "good" tone, regardless of whether the raw number went up or down. Compute this from `(benchmark_status, delta_sign)`, don't hard-code per category.
- `Capacity unavailable` has no benchmark range and isn't plotted on this chart — mention its raw hours (e.g. a PTO/travel block) in the surrounding prose instead, since a made-up "target" for unavailable time would be meaningless.

## Jira key links and the Roadmap column

Any Jira key rendered in an artifact (`product_deliveries`, `support_tickets`, `delivered_products`) is a hyperlink, not plain text — `https://signatry1.atlassian.net/browse/<KEY>`, using the `url` field each `acos-jira-analysis` detail row already carries. Style as `.jira-link` (underlined, `--ink`, hover shifts the underline to `--accent`) — never a raw `<a>` with default blue/purple browser styling.

The product-deliveries table's third data column is **Roadmap** (`customfield_10139`: Now / Next / Won't do), not workflow `status` — this changed 2026-08-15. Roadmap and status can genuinely disagree (an issue can read status "In Progress" while its Roadmap value is "Won't do"); don't reintroduce a Status column as a substitute or assume the two always match. A "Won't do" row with an open target date approaching is worth a one-line callout in the section's caption (a hygiene/decision flag), not a delivery-risk framing.

## Print/PDF support

Every artifact needs this `@media print` block (found missing 2026-08-15 after Trevor printed week-plan and month-retro from Chrome: chart colors disappeared and the time-axis/comparison charts ran off the page edge) — include it in every future artifact from the start, not just the two this was retrofitted onto:

```css
@media print {
  * {
    -webkit-print-color-adjust: exact !important;
    print-color-adjust: exact !important;
    color-adjust: exact !important;
  }
  @page { size: landscape; margin: 0.5in; }
  body { background: var(--bg) !important; }
  .table-wrap { overflow: visible !important; }
}
```

- **Colors disappearing**: Chrome strips backgrounds/fills on print by default unless told otherwise — the `print-color-adjust: exact !important` rule (applied via a universal selector, since chart rects set `background` via inline `style=`) is the fix, not a per-element patch.
- **Width exceeding the page**: the time-axis and category-comparison charts are laid out with real pixel widths (~780–820px, computed once at generation time so rect positions line up with hour/percentage gridlines) — those pixel values are baked into inline styles and can't be rescaled by ordinary CSS without breaking alignment. Requesting landscape via `@page { size: landscape }` (giving ~900–980px of printable width on Letter/A4) is the fix, not shrinking the chart. Chrome's Save-as-PDF flow generally honors this hint automatically; if a physical print dialog doesn't, tell Trevor to select Landscape manually rather than trying to force it further in CSS.
- `box-shadow` is unreliable in Chrome print even with color-adjust set (a long-standing engine quirk) — anywhere a box-shadow is load-bearing for visually separating adjacent elements (e.g. `.tc-evt`'s halo against a neighboring lane), pair it with a real `border` in the same color, which does print reliably. Don't rely on box-shadow alone for anything that needs to survive print.

## One standard content width per report

Found 2026-08-15: `.inner`'s `max-width` was set generously (900px) while individual text elements (`.headline`, `.subhead`, `.item-sentence`, a month-retro `.intentional p`/`.thin-note`) each carried their own, much narrower `max-width` (a `ch`-based reading-measure cap, e.g. 62–70ch, or a flat 700px). On any page/viewport wider than the chart or table's own natural content width, this produced a visibly ragged report — prose sections stopping well short of the right edge while the chart/table stretched wider, so no two sections shared the same right edge. It's not a print-only bug: it shows on a wide desktop browser window too, print just made it obvious because forcing landscape (see above) handed every section more room to disagree in.

The fix is two parts, both required:

1. **Set `.inner`'s `max-width` to the exact natural width of the report's widest fixed-geometry element** (the time-axis or category-comparison chart, per their own grid — label column + gap + the chart's own explicit track width + gap + trailing label column — plus `.inner`'s own left+right padding), not a round, generous number picked without doing that arithmetic. Recompute this per report the same way — week-plan's chart and month-retro's chart have different native widths (their grid columns and track widths differ), so the two files' `.inner` max-widths are correctly different (844px and 880px as shipped 2026-08-15), not a bug to "fix" into matching each other.
2. **Remove the individual, narrower `max-width` overrides on prose elements** (`.headline`, `.subhead`, `.item-sentence`, and month-retro's `.intentional p`/`.thin-note`) entirely, rather than picking a new shared value for them — with `.inner` now precisely sized, every plain block child already fills exactly that width by default; a leftover per-element cap narrower than it just reintroduces the same raggedness on a smaller scale. Yes, this means a short subhead paragraph wraps at a wider-than-classically-ideal measure (roughly 780–816px, north of 100 characters at 14px) — accepted deliberately: these are 2–4 sentence blocks, not long-form prose, and the explicit ask (consistent width across every section of one report) outweighs classic reading-measure guidance here.

Don't reach for a `min-width` floor on the chart container as a fix for this — a floor doesn't stop a wider parent from stretching the container past its own content's natural size (which is what caused the problem in the first place: the flex/grid child's `1fr` track absorbed the surplus, opening a gap between the fixed-width chart track and its trailing label column). Tightening the parent (`.inner`) to the exact right number is what actually closes that gap, and is simpler than changing every chart's internal grid to fixed-px tracks to defend against a parent that might overshoot.

## Numbered attention list

Bold title + one or two prose sentences, source folded in inline via `<span class="src">…</span>` (e.g. "in Jira, SUP-930", "on your calendar") — never a badge, pill, or color-coded severity chip. Ordering conveys priority (most urgent first); a `.btn` appears only when there's a concrete next step to offer. Also the pattern for week-plan's **Calendar infringements** section (added 2026-08-15, sourced directly from `acos-calendar-analysis`'s `schedule_health` — deep-work infringements, after-hours meetings, PTO interruptions), not a new list style of its own.
