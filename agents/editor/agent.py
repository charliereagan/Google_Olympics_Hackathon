"""EditorAgent: orchestrator + autonomous loop owner.

The Editor is the *root* agent in ADK's hierarchy (BUILD_SPEC §3.6) but
sub-scouts/Investigator/etc. are NOT registered as ADK auto-handoff sub-
agents. Handoffs are mediated by Editor's tool-call decisions and Python
invokes the next agent's Runner. This protects Voice Signatures (CONSTITUTION
Law 2) — see plan §A.5 / HOE-DEC §HOE-REVIEW item 5.

Voice signature is enforced by `/prompts/editor.md`; this Python file
contains zero voice text.
"""

from __future__ import annotations

import logging
from typing import Any

from agents.editor.loop import autonomous_loop
from agents.wire.pacing import WirePacer

logger = logging.getLogger(__name__)


class EditorAgent:
    def __init__(
        self,
        *,
        prompt: str,
        wire: Any,
        scout_desk: Any,
        firestore: Any,
        model_id: str = "gemini-3.1-pro-preview",
        pacer: WirePacer | None = None,
    ) -> None:
        self._prompt = prompt
        self._wire = wire
        self._scout_desk = scout_desk
        self._firestore = firestore
        self._model_id = model_id
        self._pacer = pacer or WirePacer(compression_factor=1.0)
        self._llm = self._build_llm()

    @property
    def llm(self) -> Any:
        return self._llm

    @property
    def name(self) -> str:
        return getattr(self._llm, "name", "editor")

    @property
    def model(self) -> str:
        return self._model_id

    def _build_llm(self) -> Any:
        try:
            from google.adk.agents import LlmAgent  # type: ignore[import-untyped]

            # Tools are wired at construction; for Day-2 we don't pre-bind the
            # injected dependencies (`wire=`, `scout_desk=`, `firestore=`) —
            # the Day-3 work formalizes the dependency-injection wrapper layer.
            return LlmAgent(
                name="editor",
                model=self._model_id,
                instruction=self._prompt,
                tools=[],
            )
        except ImportError:
            logger.warning("google.adk not installed; EditorAgent built as placeholder shell")
            return _PlaceholderEditor(
                name="editor",
                model=self._model_id,
                instruction=self._prompt,
            )

    async def think_once(self, ctx: Any | None = None) -> dict:
        """One autonomous think-cycle.

        Day-2: shell. Day-3 builds the Runner invocation: feed (queue +
        recent feed) snapshot, parse tool calls, invoke selected tool.
        """
        logger.debug("editor.think_once (model=%s)", self._model_id)
        return {"action": "noop", "reason": "day-2 shell"}

    async def autonomous_loop(self, *, stop_event=None) -> None:
        """Always-on loop wrapper. See `autonomous_loop` in `loop.py`."""
        await autonomous_loop(self.think_once, stop_event=stop_event, pacer=self._pacer)


class _PlaceholderEditor:
    def __init__(self, *, name: str, model: str, instruction: str) -> None:
        self.name = name
        self.model = model
        self.instruction = instruction
        self.tools: list = []
