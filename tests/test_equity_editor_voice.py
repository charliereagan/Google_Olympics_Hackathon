"""Voice-lock tests for the Paralympic Equity Editor.

Per Day-8 Pass-1 review Q4 (`Docs/Engineering/refinement/day8-pass1-wire/review.md`)
and CONSTITUTION Rule 5 ("voice signatures are sacred"): the Equity Editor
states facts about coverage parity — it does not apologize, hedge, or soften.

These tests are fixture-driven so they fail loudly if anyone slips an
apology into either the system prompt or a Wire fixture sample.

Two assertions:

  1. The system prompt at `prompts/equity_editor.md` does not instruct
     the agent to apologize, AND explicitly forbids apology prefixes.
  2. Any Equity Editor sample utterance found in the repo's web fixtures
     does not begin with a forbidden apology / hedge prefix.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PROMPT_PATH = REPO_ROOT / "prompts" / "equity_editor.md"
WIRE_FIXTURE_PATH = REPO_ROOT / "web" / "app" / "fixture" / "wire" / "page.tsx"

# Case-insensitive forbidden prefixes. Each must match the start of the
# utterance after trimming whitespace. We compare prefix-by-prefix so the
# failure message can name the offender.
FORBIDDEN_PREFIXES: tuple[str, ...] = (
    "sorry",
    "i apologize",
    "i'm sorry",
    "my apologies",
    "apologies",
    "unfortunately",
    "i regret",
    "i hate to",
)


def _starts_with_forbidden(text: str) -> str | None:
    """Return the matching forbidden prefix, or None if clean."""
    stripped = text.lstrip().lower()
    for prefix in FORBIDDEN_PREFIXES:
        # Match as a prefix followed by a non-letter (or end of string) so
        # "sorry" matches "Sorry, ..." but a hypothetical word starting with
        # "sorry" wouldn't trigger. Practically this just guards against
        # false positives in longer composites.
        if stripped.startswith(prefix):
            tail = stripped[len(prefix):]
            if not tail or not tail[0].isalpha():
                return prefix
    return None


# -- Test 1: prompt does not instruct apology, explicitly forbids it ----------


def test_prompt_does_not_instruct_apology() -> None:
    """The system prompt must not tell the agent to apologize and must
    explicitly forbid the apology / hedge openers we ban."""
    assert PROMPT_PATH.exists(), f"Equity Editor prompt missing at {PROMPT_PATH}"
    text = PROMPT_PATH.read_text(encoding="utf-8")
    lower = text.lower()

    # Negative: the prompt cannot contain instructions that command apology.
    # We look for imperatives like "apologize when ..." or "say sorry ...".
    bad_imperatives = (
        "you should apologize",
        "you must apologize",
        "always apologize",
        "begin with sorry",
        "begin with apolog",
        "say sorry",
    )
    for bad in bad_imperatives:
        assert bad not in lower, (
            f"Equity Editor prompt contains apology-imperative '{bad}'. "
            "The Equity Editor does not apologize."
        )

    # Positive: the prompt explicitly forbids the apology stance.
    assert "do not apologize" in lower, (
        "Equity Editor prompt must explicitly state 'You do not apologize.' "
        "(see prompts/equity_editor.md voice signature section)."
    )

    # Positive: the prompt explicitly bans apology-prefix openers.
    # Look for the no-apology rule block (added per review.md Q4).
    assert "no-apology rule" in lower, (
        "Equity Editor prompt must include the 'No-apology rule' block "
        "naming forbidden opener prefixes (review.md Q4)."
    )
    # Sanity-check that at least the canonical forbidden openers appear in
    # that block as banned strings.
    for required in ("sorry", "i apologize", "unfortunately"):
        assert required in lower, (
            f"Equity Editor prompt's no-apology rule must explicitly name "
            f"'{required}' as a forbidden opener."
        )


# -- Test 2: fixture utterances do not start with forbidden prefixes ---------


def _extract_equity_editor_messages_from_wire_fixture() -> list[str]:
    """Parse `web/app/fixture/wire/page.tsx` and return every `message` field
    on an entry whose `agent` is `equity_editor`.

    The fixture is a TypeScript object literal, not JSON, so we use a regex
    that walks `agent: 'equity_editor'` blocks and pulls the adjacent
    `message: '...'` (single OR double-quoted, possibly multi-line within
    template/string-concatenated form).
    """
    if not WIRE_FIXTURE_PATH.exists():
        return []
    src = WIRE_FIXTURE_PATH.read_text(encoding="utf-8")

    # Find each object block that contains agent: 'equity_editor'. We split on
    # `{` boundaries roughly by looking for the agent line and then the
    # nearest preceding/following message line. Simpler: scan the file line
    # by line, accumulating the most recent `message:` value, and emit it
    # when we hit `agent: 'equity_editor'`. Fixture entries are single
    # objects per array element, so this is reliable for our shape.
    messages: list[str] = []
    last_message: str | None = None
    # message: 'literal' OR message: "literal" — capture inside the quotes.
    # We also handle the soft-wrapped form where the value spans multiple
    # lines via string concatenation by stripping `'+\n  '` joiners.
    msg_re = re.compile(r"message:\s*(['\"])(.*?)\1\s*,", re.DOTALL)
    agent_re = re.compile(r"agent:\s*['\"]equity_editor['\"]")

    # Scan the file for message: ... blocks and remember which ones are
    # followed by agent: 'equity_editor' (or preceded — fixture can put
    # agent first or message first). Easiest: build a list of (kind, value,
    # span_start) markers and pair message <-> agent within the same braces.
    # For our concrete fixture, agent comes BEFORE message, so we track the
    # last seen agent and flush message when we see one.
    last_agent: str | None = None
    for m in re.finditer(
        r"(agent:\s*['\"](?P<agent>[a-z_]+)['\"])|"
        r"(message:\s*(?P<q>['\"])(?P<msg>.*?)(?P=q)\s*,)",
        src,
        re.DOTALL,
    ):
        if m.group("agent"):
            last_agent = m.group("agent")
        elif m.group("msg") is not None:
            msg = m.group("msg")
            if last_agent == "equity_editor":
                # Normalize whitespace from soft-wrapped TSX (the fixture
                # writes long messages on one quoted line, but be tolerant).
                cleaned = re.sub(r"\s+", " ", msg).strip()
                messages.append(cleaned)
            last_agent = None
    # Quiet the linter that flags unused locals from the simpler pass above.
    _ = (last_message, msg_re, agent_re)
    return messages


def test_wire_fixture_equity_editor_messages_have_no_apology_prefix() -> None:
    """Every Equity Editor sample utterance in the Wire fixture must NOT
    start with an apology / hedge prefix (case-insensitive)."""
    messages = _extract_equity_editor_messages_from_wire_fixture()

    # If we couldn't find any equity_editor fixture entry, that's a soft
    # signal — skip rather than fail, because the fixture lives in /web
    # and a refactor could move it. The prompt-side guard (test 1) is the
    # primary lock; this is the belt-and-suspenders.
    if not messages:
        pytest.skip(
            "No equity_editor messages found in web wire fixture; "
            "skipping fixture-side voice check."
        )

    offenders: list[tuple[str, str]] = []
    for msg in messages:
        prefix = _starts_with_forbidden(msg)
        if prefix is not None:
            offenders.append((prefix, msg))

    assert not offenders, (
        "Equity Editor fixture utterances must not start with apology / hedge "
        "prefixes. Offenders: "
        + "; ".join(f"[{p!r}] -> {m!r}" for p, m in offenders)
    )


# -- Sanity: the helper itself works as documented ---------------------------


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Sorry, the feed drifted.", "sorry"),
        ("I apologize for the drift.", "i apologize"),
        ("I'm sorry — drift detected.", "i'm sorry"),
        ("Unfortunately, drift detected.", "unfortunately"),
        ("Apologies, drift detected.", "apologies"),
        ("Feed drift detected. Promoting next.", None),
        ("Cleared. Paralympic depth equal.", None),
        # Hedge swallowed mid-sentence is fine — only the leading position
        # is banned.
        ("Drift detected. Sorry was the wrong word.", None),
    ],
)
def test_starts_with_forbidden_helper(text: str, expected: str | None) -> None:
    assert _starts_with_forbidden(text) == expected
