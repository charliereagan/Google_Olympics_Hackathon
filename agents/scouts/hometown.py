"""Hometown Scout — LlmAgent shell. Voice in /prompts/hometown_scout.md."""

from __future__ import annotations

from typing import Any

from agents.scouts.cinderella import _build_scout


def build_hometown_scout(
    *,
    prompt: str,
    model: str = "gemini-3-flash-preview",
    tools: list[Any] | None = None,
) -> Any:
    return _build_scout("hometown", prompt=prompt, model=model, tools=tools)
