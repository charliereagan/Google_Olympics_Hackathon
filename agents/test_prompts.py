"""Tests for the prompt loader's ADK placeholder sanitization (HOE-DEC-032)."""

from __future__ import annotations

from pathlib import Path

import pytest

from agents.prompts import _sanitize_for_adk, load_prompts


def test_sanitize_replaces_snake_case_slot() -> None:
    assert _sanitize_for_adk("Going with {place}.") == "Going with [place]."


def test_sanitize_replaces_kebab_case_slot() -> None:
    assert _sanitize_for_adk("the {sport-era} pattern") == "the [sport-era] pattern"


def test_sanitize_handles_multiple_slots() -> None:
    out = _sanitize_for_adk("{n} {sport} pipeline since {year}")
    assert out == "[n] [sport] pipeline since [year]"


def test_sanitize_is_idempotent() -> None:
    once = _sanitize_for_adk("first {place} from {region}")
    twice = _sanitize_for_adk(once)
    assert once == twice == "first [place] from [region]"


def test_sanitize_skips_uppercase_and_mixed_case() -> None:
    # Mixed-case in braces is something else (e.g., JSON, TOML, etc.) — leave alone.
    assert _sanitize_for_adk("{Place}") == "{Place}"
    assert _sanitize_for_adk("{ABC}") == "{ABC}"


def test_sanitize_skips_already_bracketed() -> None:
    assert _sanitize_for_adk("[place]") == "[place]"


def test_sanitize_passes_through_text_without_slots() -> None:
    assert _sanitize_for_adk("plain text with no placeholders") == "plain text with no placeholders"


def test_load_prompts_sanitizes_all_files(tmp_path: Path) -> None:
    """Round-trip: write a .md with {slot}; load_prompts returns [slot]."""
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "editor.md").write_text("Going with {place}. Investigator, {n} seconds.\n", encoding="utf-8")
    (prompts_dir / "echo_scout.md").write_text("the {year} {city} {sport-era} pattern\n", encoding="utf-8")
    out = load_prompts(tmp_path)
    assert "{" not in out["editor"]
    assert "[place]" in out["editor"]
    assert "[n]" in out["editor"]
    assert "[year]" in out["echo_scout"]
    assert "[sport-era]" in out["echo_scout"]


def test_load_prompts_raises_on_missing_dir(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_prompts(tmp_path)


def test_load_prompts_raises_on_empty_dir(tmp_path: Path) -> None:
    (tmp_path / "prompts").mkdir()
    with pytest.raises(ValueError):
        load_prompts(tmp_path)
