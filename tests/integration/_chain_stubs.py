"""Shared stubs for the full-chain integration test.

Factored out of `tests/integration/test_full_chain_e2e.py` because the
in-memory Firestore + ADK Runner stubs are large enough to deserve their
own module — and because the existing
`tests/integration/test_hnd_fires_end_to_end.py` will likely re-use the
Firestore stub once it grows beyond the HND-only shape.

NIL discipline (CONSTITUTION Law 4 + PROJECT_BRIEF §5):
  - The 600-row registry fixture uses synthetic + non-Team-USA names
    only. No real Team USA athlete name appears anywhere.
  - Place / program ids are synthetic strings:
    `place_test_iowa`, `program_test_wrestling`.

This module is import-safe — no side effects at import time.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Iterable
from typing import Any, Callable

logger = logging.getLogger(__name__)


# --- Synthetic athlete-registry fixture --------------------------------------


def make_synthetic_registry_rows(n: int = 600) -> list[dict]:
    """Build an n-row registry fixture for `NilRedactionLayer`.

    Mirrors the seeds used in `agents/publish_gate/test_nil_redaction_layer_stub.py`
    and `tests/integration/test_hnd_fires_end_to_end.py` so the NIL Layer's
    fail-closed assertion (≥500 rows, HOE-DEC-019) is satisfied without
    leaking any Team USA NIL into the test corpus.
    """
    seeds: list[dict] = [
        {
            "full_name": "Pelé",
            "first_name": "Pelé",
            "last_name": "",
            "known_variants": ["Edson Arantes"],
        },
        {
            "full_name": "Diego Maradona",
            "first_name": "Diego",
            "last_name": "Maradona",
            "known_variants": [],
        },
        {
            "full_name": "Roger Federer",
            "first_name": "Roger",
            "last_name": "Federer",
            "known_variants": [],
        },
    ]
    while len(seeds) < n:
        i = len(seeds)
        seeds.append(
            {
                "full_name": f"Synthetic Person {i}",
                "first_name": f"Synthetic{i}",
                "last_name": f"Person{i}",
                "known_variants": [],
            }
        )
    return seeds[:n]


# --- In-memory Firestore stubs ----------------------------------------------


class FsDoc:
    """Doc snapshot with `to_dict()`, `id`, `exists`."""

    def __init__(self, data: dict, *, doc_id: str | None = None) -> None:
        self._data = dict(data)
        self.id = doc_id or data.get("id") or "fake-id"
        self.exists = True

    def to_dict(self) -> dict:
        return dict(self._data)


class _MissingSnapshot:
    exists = False

    def to_dict(self) -> dict:  # pragma: no cover — defensive
        return {}


class FsDocRef:
    """Document reference shim. Supports `.get()`, `.update()`, `.set()`,
    `.delete()` against a parent collection."""

    def __init__(self, doc_id: str, parent: "FsCollection") -> None:
        self.id = doc_id
        self._parent = parent

    def get(self) -> Any:
        data = self._parent._by_id.get(self.id)
        if data is None:
            return _MissingSnapshot()
        return FsDoc(data, doc_id=self.id)

    def update(self, payload: dict) -> None:
        existing = self._parent._by_id.get(self.id)
        if existing is None:
            self._parent._by_id[self.id] = dict(payload)
            self._parent._by_id[self.id]["id"] = self.id
        else:
            existing.update(payload)
        self._parent.updates.append({"id": self.id, **payload})

    def set(self, payload: dict, merge: bool = False) -> None:  # noqa: ARG002
        if merge and self.id in self._parent._by_id:
            self._parent._by_id[self.id].update(payload)
        else:
            self._parent._by_id[self.id] = dict(payload)
            self._parent._by_id[self.id].setdefault("id", self.id)
        self._parent.sets.append({"id": self.id, **payload})

    def delete(self) -> None:
        self._parent._by_id.pop(self.id, None)


class FsCollection:
    """Minimal in-memory Firestore collection.

    Supports `.add(doc)`, `.document(id).get()/.update()/.set()/.delete()`,
    `.where(...).stream()`, `.limit(n)`, `.order_by(...)`. The behaviour
    mirrors the surface that the seven agents actually exercise; we don't
    try to be a real Firestore.
    """

    def __init__(self, name: str, *, seed: Iterable[dict] | None = None) -> None:
        self.name = name
        self._by_id: dict[str, dict] = {}
        # Mutation tracking so tests can assert on writes.
        self.added: list[dict] = []
        self.updates: list[dict] = []
        self.sets: list[dict] = []
        if seed:
            for d in seed:
                self._add_internal(dict(d))

    # -- Internal mutation helper -----------------------------------------

    def _add_internal(self, doc: dict) -> str:
        doc_id = doc.get("id") or f"{self.name}-{uuid.uuid4().hex[:8]}"
        doc.setdefault("id", doc_id)
        self._by_id[doc_id] = doc
        self.added.append(dict(doc))
        return doc_id

    # -- Async-shaped public API ------------------------------------------

    def add(self, doc: dict) -> Any:
        """Async-shaped add — returns an awaitable producing
        `(write_result, doc_ref)` to match google-cloud-firestore's
        AsyncClient surface, AND also acts as a sync .add() that returns
        the same tuple directly. Both paths are used in production.
        """
        doc_id = self._add_internal(doc)
        doc_ref = FsDocRef(doc_id, self)
        result = (None, doc_ref)

        class _Awaitable:
            def __await__(self_inner):
                async def _coro():
                    return result
                return _coro().__await__()

            # Also supports tuple unpacking on the sync path:
            def __iter__(self_inner):
                return iter(result)

        return _Awaitable()

    def document(self, doc_id: str) -> FsDocRef:
        return FsDocRef(doc_id, self)

    def where(self, *args, **kwargs) -> "FsCollection":  # noqa: ARG002
        # Non-filtering pass-through: the tests we run don't depend on
        # selective filtering at this layer.
        return self

    def order_by(self, *args, **kwargs) -> "FsCollection":  # noqa: ARG002
        return self

    def limit(self, n: int) -> "FsCollection":  # noqa: ARG002
        return self

    def stream(self):
        """Sync-iterable stream — every doc currently in the collection."""
        return [FsDoc(d, doc_id=did) for did, d in self._by_id.items()]


class FsClient:
    """In-memory async-shaped Firestore client.

    `collection(name)` returns the same `FsCollection` instance on
    repeated calls so writes/reads land on the same store.
    """

    def __init__(self) -> None:
        self.collections: dict[str, FsCollection] = {}

    def collection(self, name: str) -> FsCollection:
        return self.collections.setdefault(name, FsCollection(name))

    # Convenience for tests:
    def docs(self, name: str) -> list[dict]:
        return list(self.collections.get(name, FsCollection(name))._by_id.values())


# --- Stub TTS client ---------------------------------------------------------


class StubTtsClient:
    """Returns deterministic PCM bytes per call. ~1KB per sentence."""

    model_id = "gemini-3.1-flash-tts-preview"

    def __init__(self, *, chunk_size_bytes: int = 1024) -> None:
        self._chunk_size = chunk_size_bytes
        self.calls: list[dict] = []

    async def synthesize(
        self,
        text: str,
        *,
        voice_name: str,
        speaking_rate: float | None = None,
        timeout_s: float = 30.0,
    ) -> tuple[bytes, str]:
        self.calls.append(
            {
                "text": text,
                "voice_name": voice_name,
                "speaking_rate": speaking_rate,
                "timeout_s": timeout_s,
            }
        )
        # Even-byte buffer so wrap_pcm_as_wav doesn't choke on alignment.
        return (
            b"\x00\x00" * (self._chunk_size // 2),
            "audio/l16; rate=24000; channels=1",
        )


class _StubBlob:
    def __init__(self) -> None:
        self.data: bytes | None = None
        self.content_type: str | None = None

    def upload_from_string(self, data: bytes, content_type: str = "") -> None:
        self.data = data
        self.content_type = content_type


class _StubBucket:
    def __init__(self) -> None:
        self.blobs: dict[str, _StubBlob] = {}

    def blob(self, name: str) -> _StubBlob:
        b = _StubBlob()
        self.blobs[name] = b
        return b


class StubStorage:
    """In-memory Cloud Storage stand-in for the Narrator."""

    def __init__(self) -> None:
        self.buckets: dict[str, _StubBucket] = {}

    def bucket(self, name: str) -> _StubBucket:
        return self.buckets.setdefault(name, _StubBucket())


# --- ADK Runner stub ---------------------------------------------------------


class StubRunnerResult(dict):
    """Just a dict — but typed for clarity at call sites."""


def make_runner_response(
    tool_calls: list[dict],
    *,
    input_tokens: int = 1000,
    output_tokens: int = 500,
) -> StubRunnerResult:
    """Build the dict shape every agent's `_run_adk_once` returns."""
    return StubRunnerResult(
        tool_calls=tool_calls,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


async def invoke_bound_tool(
    agent: Any,
    tool_name: str,
    /,
    **tool_args,
) -> Any:
    """Invoke a closure-bound tool by name on the given agent.

    The agents store their bound tools as `agent._bound_tools` (a list of
    callables, each with a meaningful `__name__`). This helper exists so
    a stubbed ADK Runner can ACTUALLY drive the agent's tools — exercising
    the real wiring (Storyteller -> EquityEditor.review_draft, etc.) —
    rather than simulating tool responses inline.
    """
    for tool in agent._bound_tools:  # noqa: SLF001 — the test owns the contract
        if getattr(tool, "__name__", "") == tool_name:
            result = tool(**tool_args)
            if asyncio.iscoroutine(result) or hasattr(result, "__await__"):
                result = await result
            return result
    raise AssertionError(
        f"tool {tool_name!r} not found on agent {agent.__class__.__name__}; "
        f"available: "
        f"{[getattr(t, '__name__', '?') for t in agent._bound_tools]}"
    )


def make_adk_runner_stub(
    agent: Any,
    plan: Callable[..., list[tuple[str, Any]] | "PlanCycle"],
):
    """Build a stub for `agent._run_adk_once` that drives `plan`.

    `plan` is a callable returning a list of `(tool_name, args)` tuples,
    where `args` is either a `dict` (eager — passed straight through) or
    a zero-arg callable returning a dict (LAZY — invoked just before the
    tool runs, after prior tools in the same cycle have executed). Use
    the lazy form when an arg depends on a side-effect of an earlier
    tool — e.g., the `request_equity_review(draft_id=...)` call needs
    the id `write_story_draft` just produced.

    The plan callable receives `user_message`, `investigation_id`, and
    `cycle` (1-based) so a single test can drive multi-cycle behavior
    (e.g., revision loop). Plain zero-arg callables are also accepted.
    """
    cycle_index = {"n": 0}

    async def _stub_run_adk_once(
        *,
        user_message: str,
        investigation_id: str,
    ) -> StubRunnerResult:
        cycle_index["n"] += 1
        try:
            spec = plan(
                user_message=user_message,
                investigation_id=investigation_id,
                cycle=cycle_index["n"],
            )
        except TypeError:
            spec = plan()  # type: ignore[call-arg]

        tool_calls: list[dict] = []
        if isinstance(spec, PlanCycle):
            iterator = spec.with_overrides()
        else:
            iterator = ((name, args, None) for name, args in spec)
        for name, args, override in iterator:
            # Resolve lazy args.
            resolved_args = args() if callable(args) else dict(args)
            if override is not None:
                response = override
            else:
                response = await invoke_bound_tool(agent, name, **resolved_args)
            tool_calls.append(
                {"name": name, "args": dict(resolved_args), "response": response}
            )

        return make_runner_response(tool_calls)

    return _stub_run_adk_once


class PlanCycle:
    """One Runner cycle's plan: tool calls plus optional overrides.

    `tools` is `[(name, args), ...]`; `overrides[name]` lets a test
    inject a pre-computed response without invoking the real tool. Used
    sparingly — most chain tests want the real tool to fire.
    """

    def __init__(
        self,
        tools: list[tuple[str, dict]],
        *,
        overrides: dict[str, Any] | None = None,
    ) -> None:
        self.tools = tools
        self.overrides = overrides or {}

    def with_overrides(self):
        for name, args in self.tools:
            yield (name, args, self.overrides.get(name))


# --- Synthetic InvestigationPacket fixture -----------------------------------


def synthetic_investigation_packet(
    packet_id: str = "pkt-test-001",
    *,
    story_unit_id: str = "place_test_iowa",
) -> dict:
    """A packet rich enough to drive a Storyteller draft through clean.

    All names synthetic; place ids are `place_test_*`.
    """
    return {
        "id": packet_id,
        "story_unit_id": story_unit_id,
        "story_unit_title": "A small Iowa county pipeline (test fixture)",
        "story_unit_type": "place",
        "narrative_spine": (
            "A small Iowa county has produced Team USA representation in "
            "three consecutive Games. The pattern took shape from a single "
            "high-school program three decades ago."
        ),
        "geography": {
            "state": "IA",
            "region": "Southeast Iowa",
            "population": 8500,
            "notes": "rural county seat; one large high school",
        },
        "historical_context": {
            "era_parallel": "1960s post-war regional pipelines",
            "pattern_notes": (
                "regional programs feeding the national team; pre-2008 "
                "expansion era"
            ),
        },
        "trend_signals": {
            "olympic_count_history": [
                {"year": 1976, "count": 1},
                {"year": 2008, "count": 2},
                {"year": 2024, "count": 3},
            ],
            "paralympic_count_history": [
                {"year": 2012, "count": 1},
                {"year": 2024, "count": 2},
            ],
        },
        "sources": [
            {
                "url": "https://example.com/iowa-county-pipeline",
                "outlet": "Local Quad-City Times",
                "relevance_note": "summary of county program history",
            },
            {
                "url": "https://example.com/iowa-paralympic-coverage",
                "outlet": "Iowa Public Radio",
                "relevance_note": "paralympic athlete pipeline coverage",
            },
        ],
        "paralympic_depth_score": 0.7,
        "ready_for_storyteller": True,
        "created_at": "2026-05-02T12:00:00+00:00",
        "updated_at": "2026-05-02T12:00:00+00:00",
    }


def synthetic_story_draft_args(
    *,
    investigation_packet_id: str = "pkt-test-001",
    story_unit_id: str = "place_test_iowa",
) -> dict:
    """Args for `write_story_draft` that satisfy the structural envelope."""
    return {
        "headline": (
            "A small Iowa county keeps producing Team USA representation"
        ),  # 8 words → boundary-passes
        "dek": (
            "The pattern took shape from a single high-school program "
            "three decades ago"
        ),
        "body": (
            "The county sits on the eastern edge of Iowa, a place "
            "of rolling fields and a single large high school. "
            "The first Team USA athlete from this region competed "
            "in 1976; the newest competed in 2024. "
        ) * 13,  # ~468 words; well within 400-700
        "why_this_matters": [
            "Regional pipelines, not metros, drive Team USA representation.",
            "Paralympic and Olympic depth grew in parallel here.",
            "A single program decision in the 1990s opened the pipeline.",
        ],
        "hometown_panel": (
            "The county seat sits at 8,500 residents on the eastern "
            "edge of Southeast Iowa. The single regional high school "
            "feeds a community pipeline that has produced Team USA "
            "representation in three consecutive Games. The pattern "
            "is not anomalous; it is regional policy made decades "
            "ago and quietly continued. The county is a portrait "
            "of how regional decisions become national stories."
        ),  # ~62 words
        "historical_echo": (
            "This echoes the 1960s post-war pattern of regional "
            "pipelines becoming national stories. The program here "
            "was built three decades ago, before the 2008 expansion "
            "wave changed the landscape of regional development. "
            "The earliest pipeline trace is to a single coach and "
            "a single decision about funding. The pattern continued, "
            "quietly, for thirty years, producing one wave of "
            "representation after another."
        ),  # ~70 words
        "place_name": "the county seat, Iowa",
        "era_reference": "1960s post-war regional pipelines",
        "investigation_packet_id": investigation_packet_id,
        "story_unit_id": story_unit_id,
        "storyteller_notes": "(test fixture draft)",
    }
