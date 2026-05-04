"""Unit tests for WireVocabulary.

Constitutional checks (these are the load-bearing tests):
  - All required agent keys present.
  - Each agent has ≥50 fragments across all message types (BUILD_SPEC §6.4).
  - No forbidden Storyteller-list words anywhere (PROJECT_BRIEF §10).
  - No Team USA athlete names anywhere (CONSTITUTION Law 4 — same names
    used in `data/load_athlete_registry/merge.py::FALLBACK_FIXTURES`).
  - No NGB names anywhere (PROJECT_BRIEF §10).

Functional checks:
  - sample() returns a string for a known (agent, message_type).
  - fill() substitutes provided slots.
  - fill() leaves unknown slots in place rather than raising.
"""

from __future__ import annotations

import re

import pytest

from agents.wire.vocabulary import WireVocabulary


REQUIRED_AGENTS = [
    "editor",
    "cinderella_scout",
    "comeback_scout",
    "hometown_scout",
    "echo_scout",
    "investigator",
    "equity_editor",
    "storyteller",
    "narrator",
    "publish_gate",
]

# PROJECT_BRIEF §10 — Storyteller forbidden list. Whole-word matches only;
# 'despite' and 'fighter' are forbidden in disability context but appear in
# everyday phrases — we're stricter and forbid them outright in fragments
# since the vocabulary is small and we control every line.
FORBIDDEN_WORDS = [
    "inspirational",
    "inspiring",
    "hero",
    "overcame",
    "despite",
    "warrior",
    "fighter",
    "wheelchair-bound",
    "suffers from",
    "former olympian",
    "former paralympian",
    "past olympian",
    "past paralympian",
    "ex-olympian",
    "ex-paralympian",
    "retired olympian",
    "retired paralympian",
]

# Names that MUST NOT appear anywhere in the vocabulary. These are the same
# Team USA fixtures the NIL Layer is designed to redact (mirrors
# `data/load_athlete_registry/merge.py::FALLBACK_FIXTURES`). Including them
# here as negative assertions guarantees they never leak into Wire texture.
ATHLETE_NAMES = [
    "Wilma Rudolph",
    "Jesse Owens",
    "Jim Thorpe",
    "Kerri Strug",
    "Michael Phelps",
    "Simone Biles",
    "Katie Ledecky",
    "Tatyana McFadden",
    "Trischa Zorn",
    "Oksana Masters",
]

# PROJECT_BRIEF §10 — sport names not NGB names.
NGB_NAMES = [
    "USA Swimming",
    "USA Gymnastics",
    "USATF",
    "USA Wrestling",
    "USOPC",
    "USA Track and Field",
    "USA Track & Field",
]


@pytest.fixture(scope="module")
def vocab() -> WireVocabulary:
    return WireVocabulary.load()


@pytest.fixture(scope="module")
def all_fragments(vocab: WireVocabulary) -> list[tuple[str, str, str]]:
    return list(vocab.all_fragments())


# ----- Structural ------------------------------------------------------------


def test_load_returns_all_agents(vocab: WireVocabulary) -> None:
    """Every required agent key is present after load."""
    loaded = set(vocab.agents())
    missing = [a for a in REQUIRED_AGENTS if a not in loaded]
    assert not missing, f"Missing agent buckets: {missing}"


def test_each_agent_has_50_fragments(vocab: WireVocabulary) -> None:
    """Every agent has ≥50 total fragments (BUILD_SPEC §6.4)."""
    short: list[str] = []
    for agent in REQUIRED_AGENTS:
        n = vocab.total_fragments(agent)
        if n < 50:
            short.append(f"{agent}={n}")
    assert not short, f"Agents under 50 fragments: {short}"


def test_editor_has_decision_bucket(vocab: WireVocabulary) -> None:
    """Editor's decision bucket exists with ≥10 fragments (terse instructions)."""
    decisions = vocab.data.get("editor", {}).get("decision", [])
    assert len(decisions) >= 10, f"Editor decision bucket too small: {len(decisions)}"


def test_equity_editor_has_intervention_bucket(vocab: WireVocabulary) -> None:
    """Equity Editor's intervention bucket exists (BUILD_SPEC §6.5 — interventions arrive instant)."""
    interventions = vocab.data.get("equity_editor", {}).get("intervention", [])
    assert len(interventions) >= 10, (
        f"Equity Editor intervention bucket too small: {len(interventions)}"
    )


# ----- Content compliance ----------------------------------------------------


def _scan(fragments: list[tuple[str, str, str]], needle: str) -> list[tuple[str, str, str]]:
    """Return triples whose fragment contains needle (case-insensitive, whole-word)."""
    pattern = re.compile(r"\b" + re.escape(needle) + r"\b", re.IGNORECASE)
    return [t for t in fragments if pattern.search(t[2])]


def test_no_forbidden_words(all_fragments: list[tuple[str, str, str]]) -> None:
    """No forbidden Storyteller-list words appear in any fragment.

    PROJECT_BRIEF §10. Case-insensitive, whole-word match. The vocabulary
    is small enough that we forbid these outright rather than parsing
    context.
    """
    hits: list[str] = []
    for word in FORBIDDEN_WORDS:
        for agent, mt, frag in _scan(all_fragments, word):
            hits.append(f"{word!r} in {agent}.{mt}: {frag!r}")
    assert not hits, "Forbidden words found:\n  " + "\n  ".join(hits)


def test_no_athlete_names(all_fragments: list[tuple[str, str, str]]) -> None:
    """No Team USA athlete names anywhere (CONSTITUTION Law 4).

    Mirrors `data/load_athlete_registry/merge.py::FALLBACK_FIXTURES`.
    """
    hits: list[str] = []
    for name in ATHLETE_NAMES:
        # Athlete names are multi-word; a substring scan is sufficient.
        # Case-insensitive to catch any odd spellings.
        pattern = re.compile(re.escape(name), re.IGNORECASE)
        for agent, mt, frag in all_fragments:
            if pattern.search(frag):
                hits.append(f"{name!r} in {agent}.{mt}: {frag!r}")
    assert not hits, "Athlete names found in vocabulary:\n  " + "\n  ".join(hits)


def test_no_ngb_names(all_fragments: list[tuple[str, str, str]]) -> None:
    """No NGB names anywhere — use sport names instead (PROJECT_BRIEF §10)."""
    hits: list[str] = []
    for ngb in NGB_NAMES:
        pattern = re.compile(re.escape(ngb), re.IGNORECASE)
        for agent, mt, frag in all_fragments:
            if pattern.search(frag):
                hits.append(f"{ngb!r} in {agent}.{mt}: {frag!r}")
    assert not hits, "NGB names found in vocabulary:\n  " + "\n  ".join(hits)


# ----- Functional ------------------------------------------------------------


def test_sample_returns_fragment(vocab: WireVocabulary) -> None:
    """sample('editor', 'decision') returns a non-empty string."""
    out = vocab.sample("editor", "decision")
    assert isinstance(out, str)
    assert out, "sample returned an empty string"


def test_sample_returns_none_for_unknown_agent(vocab: WireVocabulary) -> None:
    assert vocab.sample("nonexistent_agent", "thinking") is None


def test_sample_returns_none_for_unknown_message_type(vocab: WireVocabulary) -> None:
    assert vocab.sample("editor", "no_such_type") is None


def test_fill_substitutes_placeholders(vocab: WireVocabulary) -> None:
    out = vocab.fill("Going with {place}.", place="Mount Pleasant")
    assert out == "Going with Mount Pleasant."


def test_fill_substitutes_multiple_placeholders(vocab: WireVocabulary) -> None:
    out = vocab.fill("{n} olympians from {place} since {year}", n=8, place="Mount Pleasant", year=1976)
    assert out == "8 olympians from Mount Pleasant since 1976"


def test_fill_leaves_unknown_placeholders(vocab: WireVocabulary) -> None:
    """Missing slots stay as literal `{name}` rather than raising."""
    out = vocab.fill("{a} {b}", a="x")
    assert out == "x {b}"


def test_fill_returns_input_when_no_placeholders(vocab: WireVocabulary) -> None:
    out = vocab.fill("Killing it.")
    assert out == "Killing it."


def test_fill_handles_repeated_placeholders(vocab: WireVocabulary) -> None:
    out = vocab.fill("{place} → {place}", place="Mount Pleasant")
    assert out == "Mount Pleasant → Mount Pleasant"


# ----- Loader edge cases -----------------------------------------------------


def test_load_strips_underscore_buckets(tmp_path) -> None:
    """Top-level keys starting with `_` (e.g. `_comments`) are stripped on load."""
    import json as _json

    p = tmp_path / "vocab.json"
    p.write_text(
        _json.dumps(
            {
                "_comments": {"note": "ignore me"},
                "editor": {"thinking": ["a"], "milestone": ["b"]},
            }
        )
    )
    v = WireVocabulary.load(p)
    assert "_comments" not in v.data
    assert "editor" in v.data


def test_load_missing_file_returns_empty(tmp_path) -> None:
    """Missing file → empty vocabulary, NOT a crash. Texture is non-gating."""
    v = WireVocabulary.load(tmp_path / "nonexistent.json")
    assert v.data == {}
    assert v.sample("editor", "thinking") is None
