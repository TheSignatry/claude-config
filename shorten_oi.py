"""Collapse organization_instructions_readable.md into the compact
organization_instructions.md format.

Each section in the readable file is a standalone ALL-CAPS heading
paragraph followed by one or more body paragraphs, separated by blank
lines. This script folds each heading into a "Heading: " prefix on its
section and joins that section's paragraphs into a single paragraph,
removing the now-unnecessary blank lines between them.
"""

import pathlib

SRC = pathlib.Path(__file__).parent / "organization_instructions_readable.md"
DST = pathlib.Path(__file__).parent / "organization_instructions.md"


def is_heading(paragraph):
    text = paragraph.strip()
    return bool(text) and text.isupper()


def shorten(text):
    paragraphs = text.split("\n\n")
    sections = [paragraphs[0]]

    for paragraph in paragraphs[1:]:
        if is_heading(paragraph):
            sections.append(paragraph.strip().capitalize() + ": ")
        else:
            sections[-1] += paragraph

    return "\n\n".join(sections)


def main():
    DST.write_text(shorten(SRC.read_text(encoding="utf-8")), encoding="utf-8")


if __name__ == "__main__":
    main()
