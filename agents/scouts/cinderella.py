"""Cinderella Scout — LlmAgent shell.

Voice + behavior are defined entirely in `/prompts/cinderella_scout.md`
(CONSTITUTION Rule 1). This file constructs the ADK LlmAgent if ADK is
available; otherwise returns a placeholder shell with the same shape.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def build_cinderella_scout(
    *,
    prompt: str,
    model: str = "gemini-3-flash-preview",
    tools: list[Any] | None = None,
) -> Any:
    """Return an `LlmAgent(name='cinderella', ...)` if ADK is on the host.

    Falls back to a `_PlaceholderAgent` if `google.adk` is not importable —
    keeps the Day-2 unit-test path runnable on dev machines without ADK.
    """
    return _build_scout("cinderella", prompt=prompt, model=model, tools=tools)


def _build_scout(name: str, *, prompt: str, model: str, tools: list[Any] | None) -> Any:
    try:
        from google.adk.agents import LlmAgent  # type: ignore[import-untyped]

        return LlmAgent(
            name=name,
            model=model,
            instruction=prompt,
            tools=list(tools or []),
        )
    except ImportError:
        logger.warning(
            "google.adk not installed; %s constructed as placeholder shell", name
        )
        return _PlaceholderAgent(name=name, model=model, instruction=prompt, tools=list(tools or []))


class _PlaceholderAgent:
    """Stand-in for `LlmAgent` when ADK isn't on the host.

    Has the right surface (`name`, `model`, `instruction`, `tools`) so other
    code that introspects an agent doesn't crash.
    """

    def __init__(self, *, name: str, model: str, instruction: str, tools: list[Any]) -> None:
        self.name = name
        self.model = model
        self.instruction = instruction
        self.tools = tools

    async def think(self, *_args, **_kwargs):  # pragma: no cover
        raise NotImplementedError(
            f"placeholder agent {self.name!r}: install google-adk to invoke "
            "the LlmAgent runtime"
        )
