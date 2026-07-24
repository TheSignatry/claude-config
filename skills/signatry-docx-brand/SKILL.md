---
name: signatry-docx-brand
description: "Signatry brand templates for Word documents: which of the two bundled .dotx templates to base a new .docx on (general brand-styles template vs. letterhead template), and the exact mechanical steps to build from a .dotx starting point instead of from scratch. Use this whenever creating a Word document for The Signatry — always pair with the general docx skill (build/edit mechanics) and, if there is donor-facing or narrative copy, the signatry-style skill (voice and terminology). Trigger even if the user doesn't say 'template' or 'brand' by name, as long as the deliverable is a Signatry Word document."
---

# Signatry Word Document Brand Templates

This skill supplies the starting-point templates for Signatry `.docx` deliverables and the mechanics of building from them. It does not duplicate general docx build/edit mechanics or writing voice — see **Dependencies**.

## Dependencies — read these first

- **`signatry-brand-core` skill**: canonical colors, fonts, and logo files for The Signatry — including tints (80%/60%/40%/20%/5%) of every color, if a document needs a lighter variant. The two `.dotx` templates already carry the correct fonts/colors baked into their own `styles.xml` and embedded font files, so this skill doesn't need to separately bundle raw font files the way `signatry-pptx-brand` and `signatry-pdf-brand` do — but if a document ever needs a brand hex value directly (e.g., a manual accent run, or a tint), pull it from `signatry-brand-core`, not from memory or the older `signatry-style` table.
- **`docx` skill**: build/edit mechanics (docx-js gotchas, unzip-edit-rezip workflow for existing files, tracked changes, comments, verification via soffice/pdftoppm). The "editing existing documents" workflow in that skill is exactly the mechanism this skill uses to build *from* a template.
- **`signatry-style` skill**: voice, terminology, and faith-language rules for any donor-facing or narrative copy going into the document.

## Which template to use

| Situation | Template |
|---|---|
| The document is addressed to someone, has a salutation/sign-off, and reads as correspondence (thank-you letter, gift acknowledgment, cover letter, etc.) | **Letterhead** (`The_Signatry_Letterhead_2026.dotx`) |
| Everything else — reports, memos, guides, policies, internal docs, board materials, proposals | **Brand Styles** (`2026_Brand_Styles.dotx`) |

If ambiguous (e.g., a "letter to donors" that's really a multi-page report), ask the user rather than guessing — the two templates have different header/footer behavior and picking wrong means redoing the page setup.

## Why start from the `.dotx`, not from docx-js scratch

Both templates already carry the correct fonts, heading colors, margins, and (for the letterhead) the logo header/footer and embedded font files. Recreating that from scratch in docx-js risks drifting from the real brand spec. Instead, treat the `.dotx` as an existing document to edit, per the `docx` skill's unzip → edit `word/document.xml` → rezip workflow — just with placeholder body content instead of a prior version's content.

## Mechanical steps (both templates)

1. Copy the relevant file from `assets/templates/` in this skill to your working directory.
2. Unzip it: `unzip -q template.dotx -d unpacked/`
3. **Change the document content type from template to document**, in `unpacked/[Content_Types].xml`:
   - Find: `<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.template.main+xml"/>`
   - Replace `template.main+xml` with `document.main+xml`. This is the only difference between a `.dotx` and a `.docx` package at the XML level — without this change, the rezipped file will still behave as a template.
4. Edit `unpacked/word/document.xml` to replace the placeholder body content with the real content (see per-template notes below). Leave `styles.xml`, `theme/theme1.xml`, headers, footers, and `fonts/` untouched.
5. Rezip as `.docx`: `(cd unpacked && zip -Xrq ../output.docx .)`
6. Verify per the `docx` skill: convert to PDF with `scripts/office/soffice.py`, render pages with `pdftoppm`, and view the images before sharing.

## Brand Styles template — what's in it

Confirmed by direct inspection of `word/styles.xml` (July 2026):

| Style | Font | Size | Color |
|---|---|---|---|
| Normal (body) | Mulish | — | default |
| Title | Lora | 36pt | Legacy `2b7a78` |
| Heading 1 | Lora | 30pt | Legacy `2b7a78` |
| Heading 2 | Lora | 24pt | Legacy `2b7a78` |
| Heading 3 | Lora | 18pt | Legacy `2b7a78` |
| Subtitle | default | 18pt | gray (theme text1, 60% tint) |
| Quote | default | — | gray (theme text1, 75% tint) |

Page setup: US Letter (12240×15840 DXA), 1" margins all sides. Use Word's built-in style names (`Heading1`, `Title`, etc.) in `document.xml` — the styles are already defined, so headings just need the right `pStyle` reference, not manual font/color runs.

This palette (Legacy `2b7a78`) matches the canonical set in `signatry-brand-core`. That skill's Glacier/Ice/Midnight/Dusk/Dawn accents are not defined as named Word styles here — if a doc needs an accent color, apply it as a direct run property using the hex values from `signatry-brand-core` rather than inventing new ones or pulling from the older `signatry-style` table.

## Letterhead template — what's in it

- Logo + return address ("7171 W 95th St., Suite 501, Overland Park, KS 66212" + phone) sit in the **first-page header** (`header3.xml`, an embedded EMF logo image) — this is a first-page-different layout, so don't expect the same header on page 2+ of a multi-page letter.
- A thin teal rule sits near the bottom of the first page as a footer element.
- 15 embedded font files (`word/fonts/*.odttf`) ship with the template — leave the `fontTable.xml` and `fonts/` folder untouched so the fonts stay embedded.
- Body placeholder in `document.xml` (`April 2, 2018` / `To Whom It May Concern:` / `This is the body of the letter.` / `Sincerely,` / `The Sender`) shows the expected shape: date line, salutation, body paragraph(s), closing, signer name. Replace text content only; don't restructure the paragraph styles.
- Same US Letter / 1" margins as the brand-styles template.

## Verified

Both templates were tested end-to-end (content-type swap → rezip → LibreOffice PDF render) on July 20, 2026, and rendered correctly, including the letterhead's logo, address block, and footer rule.

## Output format: always `.docx`, never `.dotx`

Confirmed with Ben (July 2026): deliverables must always be `.docx`. Never hand back a `.dotx` file or leave a document in template mode.

The content-type swap in step 3 above (`template.main+xml` → `document.main+xml`) is what Word itself does internally when a person opens a `.dotx` and chooses File > Save As > Word Document — it's the same outcome via script, not a shortcut around it. So that step is mandatory, not optional, for every document built from these templates.

Confirmed with Ben (July 2026): the letterhead footer is rule-only by design — no footer text is needed.
