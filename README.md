# claude-config

Configuration for using Claude at The Signatry — organization-wide instructions and reusable skills.

## Contents

### Organization instructions

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
python3 shorten_oi.py
```

Edit `organization_instructions_readable.md`, not `organization_instructions.md`
directly — the compact file is generated output and will be overwritten.

### Skills

- **`skills/signatry-style/`** — applies The Signatry's brand voice and style guide
  (audience and voice, required terminology, faith-related capitalization and
  scripture usage, number/date/mechanics rules, structural and narrative patterns,
  and visual/brand references) whenever content is written, edited, reviewed, or
  proofread for The Signatry.

## License

Released under CC0 1.0 Universal — see [LICENSE](LICENSE).
