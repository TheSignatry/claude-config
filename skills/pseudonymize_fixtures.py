#!/usr/bin/env python3
"""Pseudonymize a skill's test fixtures before they are committed.

Fixtures built from real Jira (or any connector) data carry real staff names
and real ticket text. Tests never ship (package_skill.py excludes tests/),
but the repo is still a copy of that data, and the IT15 minimum-necessary
principle says a regression fixture doesn't need the real thing. This
rewrites fixture files in place so they keep every property the code under
test depends on, while carrying none of the original names or wording:

  * Person names (in known name fields) map token by token to synthetic
    names from a fixed pool. The mapping preserves alphabetical order, so
    anything sorted by name sorts the same way afterward, and the same token
    always maps to the same name everywhere -- including inside free text.
  * Free text (summaries, descriptions, notes, agenda files) maps word by
    word to same-length pseudo-words. Casing, punctuation, whitespace, digits,
    issue keys (TRM-383), and word count are untouched, and the mapping is
    one-to-one, so token-overlap matching and repeated-word detection behave
    exactly as before. Words a rule matches on (--preserve-*, plus a built-in
    list of function words and calendar words) are kept verbatim, as is any
    word of two letters or fewer.
  * URLs become example.org links; emails outside example.org become
    example.org addresses.

The map file holds the salt and every original-to-synthetic pair, so it is
the re-identification key. It must live outside the repo; the tool refuses a
--map path inside any git work tree. Reuse the same map on a later run so new
fixtures stay consistent with old ones.

Usage (the acos-jira-analysis invocation, from the repo root; the preserve
lists are what its rewrite rules and agenda parser match on):
  J=skills/acos-jira-analysis; D=skills/acos-aboutme/references/defaults.json
  python3 skills/pseudonymize_fixtures.py --map ~/.claude/fixture-maps/acos-jira-analysis.json \\
      --preserve-json "$D#jira_workspaces.product_qa.rewrite_rules" \\
      --substring-cues "$D#jira_workspaces.product_qa.rewrite_rules.no_outcome_cue.cues" \\
      --preserve-word featured --preserve-word other --preserve-word queued \\
      --preserve-word holding --preserve-word pattern --preserve-word create \\
      --text-key customfield_10153 --template-source $J/scripts --template-source $J/assets \\
      $J/tests/fixtures/*/raw.json $J/tests/fixtures/*/plan.json $J/tests/fixtures/*/profile.json \\
      $J/tests/fixtures/*/agenda.txt $J/_exclude/*_data.json $J/tests/test_*.py
  Then regenerate each expected_payload.json from the rewritten inputs and
  confirm the suite passes. Goldens are outputs, so never pseudonymize them
  directly.

  --dry-run      report what would change; write nothing (the map is not saved)
  --forbid TEXT  after rewriting, fail if TEXT still appears in any file
                 (repeatable; every original name token is always checked)

File handling by extension:
  .json  structural: name fields and text fields (see NAME_KEYS etc.); every
         other string gets only the capitalized-name backstop
  .txt   the whole file is free text
  .py    source: in string literals and comments, runs of two or more words
         copied from the data are mapped exactly as the data was, while
         template wording found in --template-source or config stays put;
         names are replaced in any case; code is otherwise untouched

Exit codes:
  0 - rewritten (or --dry-run shown), and no forbidden text remains
  1 - bad arguments, or forbidden text / an original name remains
"""
import argparse
import hashlib
import json
import re
import secrets
import sys
from pathlib import Path

# Keys whose string value is a person's name, in Jira payloads and acos fixtures.
NAME_KEYS = {"displayName", "assignee", "owner", "who", "full_name", "first_name"}
# Keys whose value (a list, or a dict of lists) holds only person names.
NAME_LIST_KEYS = {"roster", "people_tokens"}
# Keys whose value is a dict keyed by person name, with name-string results.
DIRECTORY_KEYS = {"directory"}
# Keys whose string value is free text. Extend with --text-key.
TEXT_KEYS = {"summary", "shortDesc", "note", "weak"}
# Name tokens that are already synthetic placeholders.
# ("Former Template Owner" is the fixtures' own placeholder for template issues.)
NAME_PRESERVE = {"requester", "example", "owner", "unassigned", "user", "former", "template"}

BASE_PRESERVE = {
    # function words (product_qa.STOPWORDS and the common rest)
    "a", "an", "the", "and", "or", "of", "for", "to", "in", "on", "with", "by", "at",
    "from", "is", "are", "be", "this", "that", "as", "into", "via", "vs", "our", "we",
    "it", "its", "not", "no", "but", "if", "so", "all", "any", "was", "were", "has",
    "have", "had", "will", "can", "per", "up", "out", "new",
    # calendar words, which date parsers and relative-date rules match on
    "jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec",
    "january", "february", "march", "april", "june", "july", "august", "september",
    "october", "november", "december",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "today", "tomorrow", "yesterday", "week", "month", "quarter", "year", "next", "last",
}

# Synthetic name pool. Ordered selection from it preserves the originals' order.
NAME_POOL = """
Abbott Acosta Adair Alden Alvarez Ambrose Ansel Arden Ashby Avery Baines Barlow
Beckett Bellamy Benton Blaine Bodie Bramwell Brennan Briar Caldwell Calloway
Camden Carver Cassidy Channing Colby Corwin Crispin Dalton Darby Delaney Dempsey
Desmond Dorian Draper Easton Ellery Elwood Emery Everett Fairley Farrow Fenwick
Finlay Fletcher Forbes Galloway Garrison Gideon Gilmore Granger Greer Hadley
Halloran Harlow Hartley Haskell Hawthorne Hendrix Holloway Huxley Imogen Ingram
Iverson Jarrell Jessop Jocelyn Kendrick Kersey Kimball Kinsley Lachlan Langford
Larkin Lennox Linwood Lockhart Lowell Lysander Macklin Marlowe Merritt Milburn
Montague Morrow Nadine Nashton Nolan Norwood Oakley Odette Orson Osgood Padgett
Pemberton Percival Prescott Quill Quimby Radcliffe Ramsey Redmond Remington
Rhiannon Rockwell Rowan Rutledge Sawyer Selwyn Sheffield Sinclair Stanhope
Sterling Sutton Talbot Tamsin Thatcher Thornton Tobias Treadwell Truman Upton
Vance Vaughn Wakefield Waverly Wendell Whitaker Wilder Winslow Wrenley Yardley
Yorke Zeller Zephyr
""".split()

TOKEN_RE = re.compile(
    r"https?://\S+"                      # URL
    r"|[\w.+-]+@[\w-]+\.[\w.]+"          # email
    r"|\b[A-Z][A-Z0-9]{1,9}-\d+\b"       # issue key
    r"|[A-Za-z]+"                        # word
)
CONS, VOW = "bcdfghjklmnprstvz", "aeiou"


class PseudoError(Exception):
    pass


# --- map --------------------------------------------------------------------

class Mapper:
    def __init__(self, data, preserve, cues):
        self.salt = bytes.fromhex(data.get("salt") or secrets.token_hex(16))
        self.names = dict(data.get("names") or {})   # original token (lower) -> synthetic token
        self.words = dict(data.get("words") or {})   # original word (lower) -> pseudo-word (lower)
        self.texts = dict(data.get("texts") or {})   # original text value -> rewritten value
        self.preserve = preserve
        self.cues = [c.lower() for c in cues]
        self.taken = set(self.words.values()) | {v.lower() for v in self.names.values()}
        self.source_tokens = set()
        self.template = []          # config strings and template sources: wording that isn't data

    def to_json(self):
        return {"version": 1, "salt": self.salt.hex(), "names": self.names,
                "words": self.words, "texts": self.texts}

    # names -------------------------------------------------------------------

    def assign_names(self, tokens, anchors=()):
        """Map new name tokens to pool names, preserving alphabetical order
        among all mapped tokens, and relative to anchors (placeholder tokens
        such as "Example" that stay as they are), wherever the pool leaves room."""
        avoid = self.source_tokens | self.taken
        pool = [p for p in sorted(NAME_POOL, key=str.lower) if p.lower() not in avoid]
        pool = [p for p in pool if not any(q != p and q.lower().startswith(p.lower()) for q in pool)]
        fixed = {**{a: a for a in anchors}, **{k: v.lower() for k, v in self.names.items()}}
        new = sorted(t for t in tokens if t not in self.names)
        i = 0
        while i < len(new):
            # A run of new tokens with no fixed point between them shares one gap.
            lo_key = max((k for k in fixed if k < new[i]), default=None)
            hi_key = min((k for k in fixed if k > new[i]), default=None)
            run = [t for t in new[i:] if hi_key is None or t < hi_key]
            lo, hi = fixed.get(lo_key, ""), fixed.get(hi_key, "\uffff")
            free = [p for p in pool if p not in self.names.values() and lo < p.lower() < hi]
            if len(free) < len(run):
                raise PseudoError(f"Only {len(free)} order-preserving pool names for {len(run)} name tokens; extend NAME_POOL.")
            for j, tok in enumerate(run):
                self.names[tok] = free[int((j + 0.5) * len(free) / len(run))]
            i += len(run)
        self.taken |= {v.lower() for v in self.names.values()}

    # words -------------------------------------------------------------------

    def keep_word(self, low):
        if len(low) <= 2 or low in self.preserve:
            return True
        for c in self.cues:
            stem = c.strip()
            if stem and (stem in low if not c.endswith(" ") else low.endswith(stem)):
                return True
        return False

    def bad_pseudo(self, p):
        if p in self.preserve or p in self.taken or p in self.source_tokens:
            return True
        for c in self.cues:
            stem = c.strip()
            if stem and (stem in p if not c.endswith(" ") else p.endswith(stem)):
                return True
        return False

    def word(self, low):
        if low not in self.words:
            for attempt in range(1000):
                d = hashlib.shake_256(self.salt + f"{low}|{attempt}".encode()).digest(len(low) + 1)
                off = d[0] & 1
                p = "".join((VOW if (i + off) % 2 else CONS)[d[i + 1] % (5 if (i + off) % 2 else 17)] for i in range(len(low)))
                if not self.bad_pseudo(p):
                    break
            else:
                raise PseudoError(f"No usable pseudo-word for a {len(low)}-letter word.")
            self.words[low] = p
            self.taken.add(p)
        return self.words[low]


def apply_case(src, repl):
    if src.isupper() and len(src) > 1:
        return repl.upper()
    if len(repl) == len(src):
        return "".join(r.upper() if s.isupper() else r.lower() for s, r in zip(src, repl))
    return repl[:1].upper() + repl[1:].lower() if src[:1].isupper() else repl.lower()


# --- transforms ---------------------------------------------------------------

def name_tokens(value):
    head = value.split("(")[0]
    return {t.lower() for t in re.findall(r"[A-Za-z]+", head) if len(t) > 2 and t.lower() not in NAME_PRESERVE}


def map_name(m, value, strict=False):
    """Replaces known name tokens in a string: every token in a name field.
    With strict=True (the backstop for every other string, and for source
    files), only capitalized tokens and email local parts, and never a token
    in an n't contraction, so "don’t" in generated wording survives."""
    def sub(x):
        tok, low = x.group(0), x.group(0).lower()
        if low not in m.names:
            return tok
        if strict:
            in_email = re.match(r"[\w.+-]*@", value[x.start():])
            if re.match(r"['\u2019]t\b", value[x.end():x.end() + 3]) or not (tok[:1].isupper() or in_email):
                return tok
        return apply_case(tok, m.names[low])
    return re.sub(r"[A-Za-z]+", sub, value)


def map_text(m, value):
    if value in m.texts:
        return m.texts[value]

    def sub(x):
        tok = x.group(0)
        if tok.startswith(("http://", "https://")):
            return "https://example.org/" + hashlib.sha256(m.salt + tok.encode()).hexdigest()[:10]
        if "@" in tok:
            return tok if tok.lower().endswith("example.org") else "user@example.org"
        if "-" in tok and tok[-1].isdigit():
            return tok
        low = tok.lower()
        if low in m.names:
            return apply_case(tok, m.names[low])
        if m.keep_word(low):
            return tok
        return apply_case(tok, m.word(low))

    out = TOKEN_RE.sub(sub, value)
    m.texts[value] = out
    return out


def walk(obj, text_keys, visit, key=None, parent=None):
    """visit(kind, value) -> new value, for kind in {'name', 'text'}. Inside a
    NAME_LIST_KEYS or DIRECTORY_KEYS value, every string is a name."""
    names = key in NAME_LIST_KEYS or key == "__names__"
    if isinstance(obj, dict):
        if key in DIRECTORY_KEYS:
            return {visit("name", k): walk(v, text_keys, visit, "__names__", obj) for k, v in obj.items()}
        return {k: walk(v, text_keys, visit, "__names__" if names else k, obj) for k, v in obj.items()}
    if isinstance(obj, list):
        return [walk(v, text_keys, visit, "__names__" if names else key, parent) for v in obj]
    if not isinstance(obj, str):
        return obj
    if names or key in NAME_KEYS or (key == "name" and isinstance(parent, dict) and "email" in parent):
        return visit("name", obj)
    if key in text_keys:
        return visit("text", obj)
    return visit("other", obj)


def json_layout(text):
    first = text.split("\n", 2)
    if len(first) < 2:
        return None
    second = first[1]
    return len(second) - len(second.lstrip(" ")) or None


# --- driver ---------------------------------------------------------------------

def resolve_json_ref(ref):
    path, _, dotted = ref.partition("#")
    node = json.loads(Path(path).read_text())
    for part in filter(None, dotted.split(".")):
        node = node[part]
    return node


def strings_in(node):
    """Every string in a JSON subtree, dict keys included (a misspelling map's
    keys are the words the rule matches)."""
    if isinstance(node, dict):
        for k, v in node.items():
            yield k
            yield from strings_in(v)
    elif isinstance(node, list):
        for v in node:
            yield from strings_in(v)
    elif isinstance(node, str):
        yield node


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("files", nargs="+")
    ap.add_argument("--map", required=True, help="map file (outside the repo); created if missing")
    ap.add_argument("--preserve-json", action="append", default=[], help="FILE#dotted.path: keep every word in that subtree")
    ap.add_argument("--preserve-word", action="append", default=[])
    ap.add_argument("--substring-cues", action="append", default=[], help="FILE#dotted.path: a list of substring cues")
    ap.add_argument("--text-key", action="append", default=[], help="extra JSON key holding free text")
    ap.add_argument("--template-source", action="append", default=[],
                    help="file or directory of code whose wording is not data (the skill's scripts/)")
    ap.add_argument("--forbid", action="append", default=[])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    map_path = Path(a.map).expanduser().resolve()
    repo = next((d for d in map_path.parents if (d / ".git").exists()), None)
    if repo:
        print(f"[ERROR] --map must be outside any git work tree (found {repo}); it is the re-identification key.", file=sys.stderr)
        return 1

    preserve = set(BASE_PRESERVE) | {w.lower() for w in a.preserve_word}
    for ref in a.preserve_json:
        for s in strings_in(resolve_json_ref(ref)):
            preserve |= {t.lower() for t in re.findall(r"[A-Za-z]+", s)}
    cues = [c for ref in a.substring_cues for c in resolve_json_ref(ref)]
    text_keys = TEXT_KEYS | set(a.text_key)

    m = Mapper(json.loads(map_path.read_text()) if map_path.exists() else {}, preserve, cues)
    for src in map(Path, a.template_source):
        m.template += [f.read_text(errors="ignore") for f in ([src] if src.is_file() else sorted(src.rglob("*"))) if f.is_file()]
    files = [Path(f) for f in a.files]
    loaded = {}
    for f in files:
        if not f.exists():
            print(f"[ERROR] {f}: not found", file=sys.stderr)
            return 1
        raw = f.read_text()
        loaded[f] = raw
        m.source_tokens |= {t.lower() for t in re.findall(r"[A-Za-z]+", raw)}
        # Project keys (TRM in TRM-383) stay as-is wherever they appear, even bare.
        m.preserve |= {k.lower() for k in re.findall(r"\b([A-Z][A-Z0-9]{1,9})-\d+\b", raw)}

    # Pass 1: collect every name token, so the order-preserving assignment sees them all.
    found, anchors = set(), set()

    def collect(kind, value):
        if kind == "name":
            found.update(name_tokens(value))
            anchors.update(t.lower() for t in re.findall(r"[A-Za-z]+", value.split("(")[0]) if t.lower() in NAME_PRESERVE)
        elif kind == "other":
            m.template.append(value)
        return value

    for f, raw in loaded.items():
        if f.suffix == ".json":
            walk(json.loads(raw), text_keys, collect)
    m.assign_names(found, anchors)

    # Pass 2: rewrite.
    def visit(kind, value):
        if kind == "text":
            return map_text(m, value)
        return map_name(m, value, strict=(kind == "other"))

    changed = {}
    for f, raw in loaded.items():
        if f.suffix == ".json":
            obj = walk(json.loads(raw), text_keys, visit)
            indent = json_layout(raw)
            new = json.dumps(obj, ensure_ascii=False, indent=indent) + ("\n" if raw.endswith("\n") else "")
        elif f.suffix == ".txt":
            new = map_text(m, raw)
        else:
            new = rewrite_source(m, raw)
        if new != raw:
            changed[f] = new

    for f, new in changed.items():
        print(f"{'[DRY-RUN] would rewrite' if a.dry_run else '[OK] rewrote'} {f}")
        if not a.dry_run:
            f.write_text(new)
    print(f"{len(m.names)} name tokens, {len(m.words)} words mapped; {len(changed)}/{len(files)} files changed.")

    if not a.dry_run:
        map_path.parent.mkdir(parents=True, exist_ok=True)
        map_path.write_text(json.dumps(m.to_json(), ensure_ascii=False, indent=1) + "\n")
        print(f"Map saved to {map_path} (keep it out of the repo).")

    # Leftover check: no original name token and no forbidden text may remain.
    final = {f: (loaded[f] if a.dry_run else changed.get(f, loaded[f])) for f in files}
    bad = 0
    for f, text in final.items():
        for tok in sorted(m.names):
            if re.search(rf"\b{re.escape(tok)}\b(?!['\u2019]t\b)", text, re.IGNORECASE):
                bad += 1
                print(f"[LEFTOVER] {f}: original name token {tok!r}", file=sys.stderr)
        for phrase in a.forbid:
            if phrase.lower() in text.lower():
                bad += 1
                print(f"[LEFTOVER] {f}: forbidden text {phrase!r}", file=sys.stderr)
    if a.dry_run:
        return 0
    return 1 if bad else 0


def _map_words(m, seg):
    """Word-level map of a fragment, exactly as the data containing it was mapped."""
    def sub(x):
        low = x.group(0).lower()
        rep = m.names.get(low) or m.words.get(low)
        return apply_case(x.group(0), rep) if rep else x.group(0)
    return re.sub(r"[A-Za-z]+", sub, seg)


def _data_segments(m, value, corpus):
    """Maximal runs of two or more words in value that appear verbatim in the
    original data, left to right. A run that also appears verbatim in the
    template corpus (config strings, --template-source code) is wording the
    code generates ("is waiting on", a vendor name), not data, and stays put."""
    template = "\n".join(m.template)
    words = list(re.finditer(r"[A-Za-z0-9]+(?:[.'][A-Za-z0-9]+)*", value))
    out, i = [], 0
    while i < len(words):
        for j in range(len(words) - 1, i, -1):
            seg = value[words[i].start():words[j].end()]
            mapped = any(w.lower() in m.words for w in re.findall(r"[A-Za-z]+", seg))
            if mapped and seg in corpus and seg not in template:
                out.append(seg)
                i = j + 1
                break
        else:
            i += 1
    return out


def rewrite_source(m, raw):
    """Source files: in string literals and comments, every run of two or more
    words copied verbatim from original data is mapped word by word, exactly as
    the data was; template wording around it is left alone. Then name tokens in
    any case (an identifier named after a person is renamed consistently).
    Code is otherwise untouched."""
    import ast
    import io
    import tokenize
    corpus = "\n".join(o for o, n in m.texts.items() if o != n)
    lines = raw.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    edits = []
    for tok in tokenize.generate_tokens(io.StringIO(raw).readline):
        if tok.type not in (tokenize.STRING, tokenize.COMMENT):
            continue
        text = tok.string
        try:
            value = ast.literal_eval(text) if tok.type == tokenize.STRING else text
        except (ValueError, SyntaxError):
            continue
        if not isinstance(value, str):
            continue
        new = text
        for seg in sorted(set(_data_segments(m, value, corpus)), key=len, reverse=True):
            new = new.replace(seg, _map_words(m, seg))
        if new != text:
            start = offsets[tok.start[0] - 1] + tok.start[1]
            edits.append((start, start + len(text), new))
    out = raw
    for start, end, new in sorted(edits, reverse=True):
        out = out[:start] + new + out[end:]
    # Names: any case here, so an identifier named after a person is renamed
    # consistently -- but never in an n't contraction ("don’t").
    for tok in m.names:
        out = re.sub(rf"\b{re.escape(tok)}\b(?!['\u2019]t\b)", lambda x: apply_case(x.group(0), m.names[tok]), out, flags=re.IGNORECASE)
    return out


if __name__ == "__main__":
    try:
        sys.exit(main())
    except PseudoError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)
