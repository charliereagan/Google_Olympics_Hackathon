"""Echo Scout — LlmAgent shell. Voice in /prompts/echo_scout.md."""

from __future__ import annotations

from typing import Any

from agents.scouts.cinderella import _build_scout


def build_echo_scout(
    *,
    prompt: str,
    model: str = "gemini-3-flash-preview",
    tools: list[Any] | None = None,
) -> Any:
    return _build_scout("echo", prompt=prompt, model=model, tools=tools)
