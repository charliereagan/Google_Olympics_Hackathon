"""Comeback Scout — LlmAgent shell. Voice in /prompts/comeback_scout.md."""

from __future__ import annotations

from typing import Any

from agents.scouts.cinderella import _build_scout


def build_comeback_scout(
    *,
    prompt: str,
    model: str = "gemini-3-flash-preview",
    tools: list[Any] | None = None,
) -> Any:
    return _build_scout("comeback", prompt=prompt, model=model, tools=tools)
