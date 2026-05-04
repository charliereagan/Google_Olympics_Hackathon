"""Cinderella Scout — LlmAgent constructor.

Voice + behavior are defined entirely in `/prompts/cinderella_scout.md`
(CONSTITUTION Rule 1 + Law 2). This file constructs the ADK `LlmAgent` with
the runtime-bound tool surface (`wire_emit`, `query_candidates`,
`grounded_search`, `write_lead_report`).

Falls back to a `_PlaceholderAgent` if `google.adk` is not importable on
the host — keeps unit tests runnable on dev machines without ADK installed.
The placeholder shell carries the same surface (`name`, `model`,
`instruction`, `tools`) so `ScoutDesk._run_one_scout` can introspect it.
"""

from __future__ import annotations

import logging
from typing import Any

from agents.scouts.tools import build_scout_tools

logger = logging.getLogger(__name__)


def build_cinderella_scout(
    *,
    prompt: str,
    model: str = "gemini-3-flash-preview",
    wire: Any | None = None,
    bigquery: Any | None = None,
    firestore: Any | None = None,
    hnd: Any | None = None,
    cost_counter: Any | None = None,
    tools: list[Any] | None = None,
    wire_vocabulary: Any | None = None,
) -> Any:
    """Construct the Cinderella sub-scout LlmAgent with bound tools.

    `tools` is an optional override (used by unit tests that want a custom
    tool list). When omitted, the five standard scout tools are bound from
    the runtime deps.
    """
    return _build_scout(
        "cinderella",
        prompt=prompt,
        model=model,
        wire=wire,
        bigquery=bigquery,
        firestore=firestore,
        hnd=hnd,
        cost_counter=cost_counter,
        tools=tools,
        wire_vocabulary=wire_vocabulary,
    )


def _build_scout(
    name: str,
    *,
    prompt: str,
    model: str,
    wire: Any | None,
    bigquery: Any | None,
    firestore: Any | None,
    hnd: Any | None,
    cost_counter: Any | None,
    tools: list[Any] | None,
    wire_vocabulary: Any | None = None,
) -> Any:
    bound_tools = list(tools) if tools is not None else build_scout_tools(
        scout=name,  # type: ignore[arg-type]
        wire=wire,
        bigquery=bigquery,
        firestore=firestore,
        hnd=hnd,
        cost_counter=cost_counter,
        grounded_model=model,
        wire_vocabulary=wire_vocabulary,
    )
    try:
        from google.adk.agents import LlmAgent  # type: ignore[import-untyped]

        return LlmAgent(
            name=name,
            model=model,
            instruction=prompt,
            tools=bound_tools,
        )
    except ImportError:
        logger.warning(
            "google.adk not installed; %s constructed as placeholder shell", name
        )
        return _PlaceholderAgent(
            name=name,
            model=model,
            instruction=prompt,
            tools=bound_tools,
        )


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
