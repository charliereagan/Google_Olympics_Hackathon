"""Hometown Scout — LlmAgent constructor. Voice in /prompts/hometown_scout.md."""

from __future__ import annotations

from typing import Any

from agents.scouts.cinderella import _build_scout


def build_hometown_scout(
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
    return _build_scout(
        "hometown",
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
