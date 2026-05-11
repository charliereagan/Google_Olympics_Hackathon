"""Sub-stage 6: Language Review.

Pure-Python regex check. NO LLM call. CONSTITUTION Law 5 lives here —
the Storyteller's forbidden-words list (PROJECT_BRIEF §10) and the
predictive-phrasing list (PROJECT_BRIEF §11) are enforced
deterministically. No model in the loop = no chance the LLM "remembers"
to check or "decides" to soften.

Three categories of patterns:

  1. FORBIDDEN_WORDS — flagged unconditionally.
  2. CONTEXT_AWARE_FORBIDDEN — flagged only when within ~30 chars of a
     disability-context word (e.g., "fighter" + "paralympic" → flag;
     "fighter" alone → ignore).
  3. PREDICTIVE_PATTERNS — flagged AS A FAIL (VPS-DEC-053). Predictive
     frames are FORBIDDEN per PROJECT_BRIEF §11, not "soften to." The
     Day-6 Tucson failure proved that softening "will" → "could" while
     leaving the rest of the sentence intact still leaks predictive
     prose past the gate. We now return the draft to the Storyteller
     for revision and surface the offending constructions verbatim.

ENCOURAGED_TEMPORAL_PATTERNS describe a place's representation
("first Olympian", "next Paralympian", etc.) per PROJECT_BRIEF §10 +
CONSTITUTION Law 5. They MUST NOT be flagged on the surface words
"Olympian" / "Paralympian" — the regex matches both forbidden and
encouraged constructions; we re-scan and remove any flagged_terms
overlapping an encouraged pattern before returning. Predictive patterns
do not include "first/next/newest/oldest"-style temporal phrasing, so
the encouraged-overlap filter cannot accidentally suppress them.

Voice text lives in `/prompts/publish_gate.md`. This module's prose
contains zero forbidden words outside the explicit FORBIDDEN_WORDS list.
"""

from __future__ import annotations

import logging
import re
from typing import Any  # noqa: F401 — kept for type-annotation parity with siblings

from agents.publish_gate.types import LanguageReviewResult

logger = logging.getLogger(__name__)


# --- Pattern lists -----------------------------------------------------------
#
# Each entry is the canonical lowercase form. The matcher is case-insensitive
# and word-boundary anchored.
#
# Per PROJECT_BRIEF §10 + CONSTITUTION Law 5. These constructions appear in
# this module ONLY in the FORBIDDEN_WORDS literal — never in prose.

FORBIDDEN_WORDS: list[str] = [
    # Inspiration-porn tropes (PROJECT_BRIEF §10 / CONSTITUTION Law 5).
    "inspirational",
    "inspiring",
    "hero",
    "overcame",
    "warrior",
    "wheelchair-bound",
    "suffers from",
    # Athlete-identity-as-ended (PROJECT_BRIEF §10).
    "former olympian",
    "past olympian",
    "ex-olympian",
    "retired olympian",
    "former paralympian",
    "past paralympian",
    "ex-paralympian",
    "retired paralympian",
]

# Words that are forbidden ONLY in disability context. Tuple shape:
#   (forbidden_term, context_marker_root)
# e.g., ("fighter", "disability") flags only when 'fighter' appears within
# the context window of any disability-related word.
CONTEXT_AWARE_FORBIDDEN: list[tuple[str, str]] = [
    ("fighter", "disability"),
    ("despite", "disability"),
]

# Disability-context window words (anchors for CONTEXT_AWARE_FORBIDDEN).
_DISABILITY_CONTEXT_TOKENS: list[re.Pattern[str]] = [
    re.compile(r"\bparalymp\w*\b", re.IGNORECASE),
    re.compile(r"\badaptive\b", re.IGNORECASE),
    re.compile(r"\bwheelchair\b", re.IGNORECASE),
    re.compile(r"\bdisability\b", re.IGNORECASE),
    re.compile(r"\bdisabled\b", re.IGNORECASE),
    re.compile(r"\bamputee\b", re.IGNORECASE),
    re.compile(r"\bvisually impaired\b", re.IGNORECASE),
    re.compile(r"\bblind\b", re.IGNORECASE),
    re.compile(r"\bdeaf\b", re.IGNORECASE),
]
_CONTEXT_WINDOW_CHARS = 30

# Predictive constructions (PROJECT_BRIEF §11; VPS-DEC-053).
#
# Each entry is a (lead-phrase regex, human-readable label) pair. The
# scanner detects the lead phrase and captures up to ~120 chars of
# trailing context (or the next sentence terminator, whichever comes
# first) so the violation can be reported verbatim to the Storyteller.
#
# Per VPS-DEC-053 these are HARD FAILS — the Day-6 Tucson failure proved
# that softening the modal ("will" → "could") while leaving the rest of
# the predictive sentence intact still produces policy-memo prose. The
# right move is: detect → return draft to Storyteller for revision.
PREDICTIVE_LEAD_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bcould lead to\b", re.IGNORECASE), "predictive: 'could lead to'"),
    (re.compile(r"\bmay lead to\b", re.IGNORECASE), "predictive: 'may lead to'"),
    (re.compile(r"\bwill lead to\b", re.IGNORECASE), "predictive: 'will lead to'"),
    (re.compile(r"\bwill result in\b", re.IGNORECASE), "predictive: 'will result in'"),
    (re.compile(r"\bmay indicate\b", re.IGNORECASE), "predictive: 'may indicate'"),
    (re.compile(r"\bcould indicate\b", re.IGNORECASE), "predictive: 'could indicate'"),
    (re.compile(r"\bis positioned to\b", re.IGNORECASE), "predictive: 'is positioned to'"),
    (re.compile(r"\bare positioned to\b", re.IGNORECASE), "predictive: 'are positioned to'"),
    (re.compile(r"\bis poised to\b", re.IGNORECASE), "predictive: 'is poised to'"),
    (re.compile(r"\bare poised to\b", re.IGNORECASE), "predictive: 'are poised to'"),
    (re.compile(r"\bpoints toward\b", re.IGNORECASE), "predictive: 'points toward'"),
    (re.compile(r"\bsuggests a future\b", re.IGNORECASE), "predictive: 'suggests a future'"),
    (re.compile(r"\bis on track to\b", re.IGNORECASE), "predictive: 'is on track to'"),
    (re.compile(r"\bare on track to\b", re.IGNORECASE), "predictive: 'are on track to'"),
    (re.compile(r"\bguarantees?\b", re.IGNORECASE), "predictive: 'guarantee(s)'"),
    (re.compile(r"\bpredicts?\b", re.IGNORECASE), "predictive: 'predict(s)'"),
    (re.compile(r"\bensures?\b", re.IGNORECASE), "predictive: 'ensure(s)'"),
    (re.compile(r"\bthis means\b", re.IGNORECASE), "predictive: 'this means'"),
    (re.compile(r"\bthis proves\b", re.IGNORECASE), "predictive: 'this proves'"),
]

# Maximum trailing-context chars to capture after a predictive lead phrase
# (truncated at the next sentence terminator).
_PREDICTIVE_TAIL_CHARS = 120

# Encouraged temporal constructions per PROJECT_BRIEF §10 + CONSTITUTION
# Law 5. These describe a PLACE'S representation arc and are required for
# place stories. The forbidden-list scan would otherwise flag the words
# "olympian" / "paralympian" inside; we re-scan and remove overlapping
# matches before returning.
ENCOURAGED_TEMPORAL_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bfirst (?:olympian|paralympian)\b", re.IGNORECASE),
    re.compile(r"\bnext (?:olympian|paralympian)\b", re.IGNORECASE),
    re.compile(r"\bnewest (?:olympian|paralympian)\b", re.IGNORECASE),
    re.compile(r"\bearliest (?:documented|olympian|paralympian)\b", re.IGNORECASE),
    re.compile(r"\bmost recent (?:olympian|paralympian)\b", re.IGNORECASE),
    re.compile(r"\boldest (?:olympian|paralympian)\b", re.IGNORECASE),
]


# Surfaces in a StoryDraft we scan (per BUILD_SPEC §8.5).
_SURFACES = (
    "headline",
    "dek",
    "body",
    "why_this_matters",
    "hometown_panel",
    "historical_echo",
)


def _build_forbidden_pattern(words: list[str]) -> re.Pattern[str]:
    """Compile one alternation regex covering every word in `words`.

    Word-boundary anchored so 'hero' doesn't match 'heroic' (we want
    exact lexeme matches). The hyphen in "wheelchair-bound" requires us
    to use a custom non-word boundary (`(?<![A-Za-z])` ... `(?![A-Za-z])`)
    instead of `\\b`, because Python's `\\b` treats hyphens as word
    boundaries already and would over-match.
    """
    # Sort longest first so multi-word phrases win over their constituent
    # words.
    sorted_words = sorted(words, key=len, reverse=True)
    escaped = [re.escape(w) for w in sorted_words]
    pattern = (
        r"(?<![A-Za-z])(?:" + "|".join(escaped) + r")(?![A-Za-z])"
    )
    return re.compile(pattern, re.IGNORECASE)


_FORBIDDEN_RE = _build_forbidden_pattern(FORBIDDEN_WORDS)


def _find_disability_context_spans(text: str) -> list[tuple[int, int]]:
    """Return (start, end) spans where any disability-context word matches."""
    spans: list[tuple[int, int]] = []
    for pat in _DISABILITY_CONTEXT_TOKENS:
        for m in pat.finditer(text):
            spans.append(m.span())
    return spans


def _within_context(
    match_span: tuple[int, int],
    context_spans: list[tuple[int, int]],
    *,
    window: int = _CONTEXT_WINDOW_CHARS,
) -> bool:
    """True if any context span is within `window` chars of match_span."""
    m_start, m_end = match_span
    for c_start, c_end in context_spans:
        # Distance is min gap between intervals.
        if c_end < m_start - window:
            continue
        if c_start > m_end + window:
            continue
        return True
    return False


def _encouraged_overlap_spans(text: str) -> list[tuple[int, int]]:
    """Return spans where an encouraged temporal pattern matches.

    Used to filter out forbidden-list hits that overlap an encouraged
    pattern (e.g., the word 'Olympian' inside 'first Olympian').
    """
    spans: list[tuple[int, int]] = []
    for pat in ENCOURAGED_TEMPORAL_PATTERNS:
        for m in pat.finditer(text):
            spans.append(m.span())
    return spans


def _spans_overlap(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return not (a[1] <= b[0] or b[1] <= a[0])


def _capture_predictive_violation(text: str, start: int) -> str:
    """Capture a predictive-frame violation verbatim from `text`.

    Starting at `start` (the lead phrase's position), walk forward up to
    `_PREDICTIVE_TAIL_CHARS` chars or until the next sentence terminator
    (`.`, `!`, `?`, newline) — whichever comes first. The returned slice
    is the offending construction the Storyteller must revise.
    """
    end_cap = min(len(text), start + _PREDICTIVE_TAIL_CHARS)
    # Walk to the first sentence terminator inside the capped window.
    end = end_cap
    for i in range(start, end_cap):
        ch = text[i]
        if ch in ".!?\n":
            end = i
            break
    snippet = text[start:end].strip()
    return snippet


def _scan_surface(
    text: str,
) -> tuple[list[str], list[tuple[str, str]]]:
    """Scan one text surface.

    Returns ``(flagged_terms, predictive_hits)`` where:
      - `flagged_terms` is a list of the actual matched forbidden substrings
        (lowered) suitable for audit display. Encouraged-temporal overlaps
        are filtered out. Context-aware forbidden words are filtered if
        they don't sit near a disability-context anchor.
      - `predictive_hits` is a list of (verbatim_construction, reason)
        tuples — one per detected predictive frame. Each construction is
        captured verbatim from the source text (case preserved) up to the
        next sentence terminator so the Storyteller can find and rewrite
        the exact phrase.
    """
    if not text:
        return [], []

    flagged: list[str] = []

    # 1. Encouraged spans we must NOT flag against.
    encouraged_spans = _encouraged_overlap_spans(text)

    # 2. Forbidden-list scan.
    for m in _FORBIDDEN_RE.finditer(text):
        span = m.span()
        if any(_spans_overlap(span, e) for e in encouraged_spans):
            # The forbidden word sits inside an encouraged construction
            # (e.g., 'Olympian' inside 'first Olympian'). Skip.
            continue
        flagged.append(m.group(0).lower())

    # 3. Context-aware scan.
    if CONTEXT_AWARE_FORBIDDEN:
        context_spans = _find_disability_context_spans(text)
        for term, _label in CONTEXT_AWARE_FORBIDDEN:
            term_pat = re.compile(
                r"(?<![A-Za-z])" + re.escape(term) + r"(?![A-Za-z])",
                re.IGNORECASE,
            )
            for m in term_pat.finditer(text):
                if not _within_context(m.span(), context_spans):
                    continue
                flagged.append(m.group(0).lower())

    # 4. Predictive-frame scan (VPS-DEC-053). Capture verbatim with tail.
    #    De-dupe by (lowered_construction, reason) so the same lead phrase
    #    appearing twice in the same surface only reports once.
    predictive_hits: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for pat, label in PREDICTIVE_LEAD_PATTERNS:
        for m in pat.finditer(text):
            span = m.span()
            # Defensive: filter out any predictive hit overlapping an
            # encouraged-temporal span. Predictive patterns above don't
            # use 'first/next/newest/oldest' phrasing, but this guards
            # future additions to either list.
            if any(_spans_overlap(span, e) for e in encouraged_spans):
                continue
            snippet = _capture_predictive_violation(text, span[0])
            key = (snippet.lower(), label)
            if key in seen:
                continue
            seen.add(key)
            predictive_hits.append((snippet, label))

    return flagged, predictive_hits


class LanguageReviewSubstage:
    """Sub-stage 6 — Language Review.

    Synchronous, deterministic, no LLM, no I/O. Cheap to run.
    """

    def __init__(self) -> None:  # noqa: D401 — empty by design
        pass

    def review(self, *, story_draft: dict) -> LanguageReviewResult:
        """Scan all draft surfaces for forbidden / predictive constructions.

        Args:
            story_draft: the StoryDraft dict per BUILD_SPEC §8.5.

        Returns:
            `LanguageReviewResult`. `passed` is True iff there are zero
            restricted-term flags AND zero predictive-frame violations.
            On a predictive-frame hit, `predictive_violations` lists the
            offending constructions verbatim and `predictive_reasons`
            carries the per-violation 1-line reason for the Storyteller's
            revision feedback (VPS-DEC-053). `predictive_phrases_softened`
            is preserved as a deprecated count for audit-doc parity.
        """
        draft = story_draft or {}

        all_flagged: list[str] = []
        all_predictive_hits: list[tuple[str, str]] = []

        for surface in _SURFACES:
            text = draft.get(surface) or ""
            if not isinstance(text, str):
                continue
            flagged, predictive_hits = _scan_surface(text)
            all_flagged.extend(flagged)
            all_predictive_hits.extend(predictive_hits)

        # Dedupe + sort for stable audit output. We keep the first
        # occurrence's casing implicitly via lowercase.
        deduped = sorted(set(all_flagged))

        # Cross-surface de-dupe of predictive hits by (lowered_snippet, reason).
        seen_keys: set[tuple[str, str]] = set()
        violations: list[str] = []
        reasons: list[str] = []
        for snippet, reason in all_predictive_hits:
            key = (snippet.lower(), reason)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            violations.append(snippet)
            reasons.append(reason)

        passed = (len(deduped) == 0) and (len(violations) == 0)

        return LanguageReviewResult(
            restricted_terms_flagged=len(deduped),
            flagged_terms=deduped,
            # Legacy field: count of predictive hits across all surfaces.
            # Kept for backward compatibility with existing audit consumers.
            predictive_phrases_softened=len(violations),
            predictive_violations=violations,
            predictive_reasons=reasons,
            passed=passed,
        )
