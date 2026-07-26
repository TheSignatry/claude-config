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

- **`skills/signatry-style/`** — The Signatry's official writing and brand voice guide:
  audience and voice, required terminology, faith-related capitalization and scripture
  usage, number/date/mechanics rules, structural and narrative patterns, and
  visual/brand references. Use whenever writing, editing, reviewing, or proofreading
  any content for The Signatry.
- **`skills/signatry-brand-core/`** — canonical source of truth for The Signatry's
  brand colors, fonts, and logo/mark assets, independent of file format. Format-specific
  brand skills (pptx, docx, pdf) depend on this one for values and assets rather than
  restating them.
- **`skills/signatry-pptx-brand/`** — Signatry brand system for PowerPoint decks: color
  palette, fonts (Mulish, Lora), and logo/quill assets. Pair with a general pptx build
  skill and, for donor-facing copy, `signatry-style`.
- **`skills/signatry-docx-brand/`** — Signatry brand templates for Word documents:
  which of the two bundled `.dotx` templates to start from (general brand-styles vs.
  letterhead) and the mechanics of building from one. Pair with a general docx build
  skill and, for donor-facing copy, `signatry-style`.
- **`skills/signatry-pdf-brand/`** — Signatry brand system for PDFs built with
  reportlab: font registration/embedding, color palette, and logo usage. Pair with a
  general pdf skill and, for donor-facing copy, `signatry-style`.

## License

Released under CC0 1.0 Universal — see [LICENSE](LICENSE).
