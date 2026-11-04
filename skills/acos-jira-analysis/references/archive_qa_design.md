# Archive QA report: design decisions

Recorded so the next person doesn't relitigate them. `scripts/archive_qa.py` reads the top-level bullets below into the report's "Design notes" panel, so keep each decision as one `- **Title.** body` bullet (nested bullets fold into their parent).

- **Why this report exists.** Archiving an idea in Jira Product Discovery hides it but leaves its Roadmap value and workflow status as they were. An idea archived from Now or In Progress still reads as live work to anything that queries those fields, including the standard report's Product detail list before 0.7. This report finds those ideas so someone can set a concluding state by hand.
- **Concluding is config, not judgment.** A Roadmap value concludes when it's in archive_qa.concluding_roadmap (Done, Won't do, and Merged ship by default). A status concludes when its category is in archive_qa.concluding_status_categories (done). Parking Lot is deliberately not concluding: it means "maybe later", which is the opposite of archived.
- **Every archived idea is listed.** Concluded ideas sit in a collapsed section, so the ledger's "of N" counts the whole archive and an owner can see their clean ideas too.
- **Fixed sections.** Neither concluded, Needs a Roadmap value, Needs the status closed, then Concluded. An idea's section comes from the two checks alone; turning a check off moves its ideas toward Concluded rather than hiding them.
- **One query, filtered twice.** The JQL asks for every idea whose archived field is set. Python checks the same field again, so a raw file built some other way can't slip an unarchived idea in.
- **Shared visual system.** Same bands, ledger, owner filter, glyph QA cell, embedded fonts, and print rules as the other QA reports; colors come from product_qa.palette. No chart: an archive has no timeline worth plotting.
- **Glyph meanings.**
  - Flag: Roadmap not concluded.
  - Open clock: status still open.
