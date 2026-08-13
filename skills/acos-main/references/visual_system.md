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

Used by `week-plan`'s segmented day bars and `month-retro`'s category-comparison mini-bars. Brand-core defines no category-color scheme of its own — this mapping is `acos-main`'s own design decision, drawing on brand-core's named hues:

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

## Numbered attention list

Bold title + one or two prose sentences, source folded in inline via `<span class="src">…</span>` (e.g. "in Jira, SUP-930", "on your calendar") — never a badge, pill, or color-coded severity chip. Ordering conveys priority (most urgent first); a `.btn` appears only when there's a concrete next step to offer.
