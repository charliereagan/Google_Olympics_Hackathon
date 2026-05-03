"""Name normalization + variant generation for the athlete registry.

Pure-stdlib. Deterministic. Operates on names — not the input source — so the
same inputs always produce the same outputs.

Outputs per record:
    full_name        — canonical form, NFKD-folded + diacritic-stripped
    first_name       — everything except the last whitespace-separated token
    last_name        — the final whitespace-separated token
    known_variants   — diacritic original + nickname expansions + initials +
                       hyphen splits + (when supplied) maiden/married pair

The variant set is deliberately broad: false-positives at this layer become
disambiguation work for the NIL Redaction Layer, but a missing variant means a
name reaches a user-facing surface unredacted, which is the failure mode the
Layer exists to prevent (BUILD_SPEC §5.7, HOE-DEC-019).
"""

from __future__ import annotations

import re
import unicodedata
from typing import Iterable

# Common US-English nickname expansions. Bidirectional — if either form
# appears, the other is generated. Keep this list conservative; a big list of
# nicknames in production is fine but each new entry risks false-positive
# noise for the disambiguation pass downstream. (BUILD_SPEC §5.7 step 3.)
NICKNAME_PAIRS: list[tuple[str, list[str]]] = [
    ("michael", ["mike"]),
    ("robert", ["bob", "rob", "bobby"]),
    ("james", ["jim", "jimmy"]),
    ("william", ["bill", "billy", "will", "willy"]),
    ("thomas", ["tom", "tommy"]),
    ("david", ["dave", "davey"]),
    ("christopher", ["chris"]),
    ("stephen", ["steve", "stevie"]),
    ("steven", ["steve", "stevie"]),
    ("joseph", ["joe", "joey"]),
    ("samuel", ["sam", "sammy"]),
    ("elizabeth", ["liz", "beth", "lizzy", "betty"]),
    ("patricia", ["pat", "patty", "tricia"]),
    ("patrick", ["pat", "paddy"]),
    ("katherine", ["kate", "katie", "kathy"]),
    ("kathryn", ["kate", "katie", "kathy"]),
    ("jennifer", ["jen", "jenny"]),
    ("daniel", ["dan", "danny"]),
    ("john", ["jack", "johnny"]),
    ("jackson", ["jack"]),
    ("richard", ["rich", "rick", "dick", "ricky"]),
    ("kenneth", ["ken", "kenny"]),
    ("anthony", ["tony"]),
    ("charles", ["charlie", "chuck"]),
    ("edward", ["ed", "eddie", "ted", "teddy"]),
    ("nicholas", ["nick", "nicky"]),
    ("alexander", ["alex"]),
    ("alexandra", ["alex"]),
    ("benjamin", ["ben", "benny"]),
    ("matthew", ["matt", "matty"]),
    ("andrew", ["andy", "drew"]),
    ("rebecca", ["becky", "becca"]),
    ("margaret", ["maggie", "meg", "peggy"]),
    ("deborah", ["deb", "debbie"]),
    ("susan", ["sue", "susie"]),
    ("frederick", ["fred", "freddy"]),
    ("gregory", ["greg"]),
    ("ronald", ["ron", "ronnie"]),
    ("donald", ["don", "donny"]),
    ("timothy", ["tim", "timmy"]),
    ("joshua", ["josh"]),
    ("nathaniel", ["nate", "nathan"]),
    ("zachary", ["zach", "zack"]),
]

# Build the bidirectional lookup once.
_NICKNAME_LOOKUP: dict[str, set[str]] = {}
for canonical, nicks in NICKNAME_PAIRS:
    bucket = {canonical, *nicks}
    for token in bucket:
        _NICKNAME_LOOKUP.setdefault(token, set()).update(bucket - {token})


_NON_LETTER = re.compile(r"[^\w\s\-'\.]+", re.UNICODE)
_WHITESPACE_RUN = re.compile(r"\s+")


def fold_diacritics(text: str) -> str:
    """NFKD + drop combining marks. ``Ürümqi`` -> ``Urumqi``."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))


def canonical_form(name: str) -> str:
    """Canonical comparison form: folded, lower, single-spaced, punct-light.

    This is what dedup keys are derived from. NOT what gets stored as
    ``full_name`` (we want the folded but properly-cased version there).
    """
    if not name:
        return ""
    folded = fold_diacritics(name).lower()
    folded = _NON_LETTER.sub(" ", folded)
    folded = _WHITESPACE_RUN.sub(" ", folded).strip()
    return folded


def display_form(name: str) -> str:
    """Folded but case-preserved. Used for ``full_name`` field."""
    if not name:
        return ""
    folded = fold_diacritics(name)
    folded = _WHITESPACE_RUN.sub(" ", folded).strip()
    return folded


def split_first_last(name: str) -> tuple[str | None, str | None]:
    """Return (first, last). Last token wins for ``last_name``; everything
    else (including middle tokens) joins as ``first_name``.

    Returns (None, None) on empty input. If only one token, treats it as a
    last_name with no first_name.
    """
    cleaned = display_form(name)
    if not cleaned:
        return (None, None)
    parts = cleaned.split(" ")
    if len(parts) == 1:
        return (None, parts[0])
    return (" ".join(parts[:-1]), parts[-1])


def _expand_nicknames(token: str) -> set[str]:
    """Return the alternate forms for a given-name token."""
    return set(_NICKNAME_LOOKUP.get(token.lower(), ()))


def generate_variants(
    full_name: str,
    *,
    original_with_diacritics: str | None = None,
    extra: Iterable[str] = (),
) -> list[str]:
    """Generate the ``known_variants`` list.

    Always includes:
      - The folded full name (``Michael Phelps``)
      - The original (with diacritics) form, if different from folded
      - All extras (e.g. married/maiden alternate, Wikidata native label)
      - Initial form ``M. Phelps`` and dotless ``M Phelps``
      - First name only and last name only (helps Aho-Corasick match
        constructions like "Phelps swept the event" — but disambiguation in
        the Layer suppresses common-name false positives downstream)
      - Hyphenated <-> space-split for hyphenated last names
      - Each nickname expansion of the first-name token, paired with the
        last name (``Michael Phelps`` -> ``Mike Phelps``)

    Sorted, lowercased-deduplicated, but stored in display case.
    """
    seen: dict[str, str] = {}  # lower-key -> display-form

    def add(value: str) -> None:
        if not value:
            return
        v = _WHITESPACE_RUN.sub(" ", value).strip()
        if not v:
            return
        seen.setdefault(v.lower(), v)

    folded = display_form(full_name)
    add(folded)

    if original_with_diacritics:
        add(original_with_diacritics)

    for x in extra:
        add(x)

    first, last = split_first_last(folded)
    if last:
        add(last)
        if first:
            add(first)
            # Initial forms.
            initial = first[0]
            add(f"{initial}. {last}")
            add(f"{initial} {last}")
            # Nickname expansions: replace the FIRST given-name token only.
            first_tokens = first.split(" ")
            head = first_tokens[0]
            tail = " ".join(first_tokens[1:])
            for alt in _expand_nicknames(head):
                # Capitalize first letter of nick to match display style.
                alt_display = alt.capitalize()
                if tail:
                    add(f"{alt_display} {tail} {last}")
                else:
                    add(f"{alt_display} {last}")

        # Hyphenated last-name handling.
        if "-" in last:
            split_last = last.replace("-", " ")
            joined_last = last.replace("-", "")
            if first:
                add(f"{first} {split_last}")
                add(f"{first} {joined_last}")
            else:
                add(split_last)
                add(joined_last)

    return sorted(seen.values(), key=lambda v: v.lower())


def normalize_record(
    *,
    full_name_raw: str,
    extra_variants: Iterable[str] = (),
) -> dict:
    """Normalize a single name into the registry's name shape.

    Returns a dict with: ``full_name``, ``first_name``, ``last_name``,
    ``known_variants``, plus an internal ``_canonical`` key used for dedup.
    """
    folded_display = display_form(full_name_raw)
    first, last = split_first_last(folded_display)
    variants = generate_variants(
        folded_display,
        original_with_diacritics=full_name_raw,
        extra=extra_variants,
    )
    canonical = canonical_form(folded_display)
    return {
        "full_name": folded_display,
        "first_name": first,
        "last_name": last,
        "known_variants": variants,
        "_canonical": canonical,
    }


def era_for_year(year: int | None) -> str | None:
    """Map a year to a coarse era bucket for the NIL near-id check.

    Returns "1990s", "2000s", "1980s", "pre-1900", "1930s", etc.
    None if year is None.
    """
    if year is None:
        return None
    if year < 1900:
        return "pre-1900"
    decade = (year // 10) * 10
    return f"{decade}s"
