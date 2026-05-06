"""Storyteller tool surface — closure-bound implementations.

The Storyteller's Pro-tier `LlmAgent` decides WHEN to call which tool
(CONSTITUTION Law 1). Python here defines the physics: read the
investigation packet, validate the structural envelope of the draft,
persist to Firestore, route the cleared draft to the Equity Editor and
the Publish Gate. No orchestration sequences live here — only the rails.

Each tool below is built as a closure in `build_storyteller_tools(...)`
so runtime deps (Firestore, the WireEmitter, the live agents) are
captured once and the LLM-facing surface stays clean. Mirrors the
Investigator and Equity Editor patterns.

Voice text lives in `/prompts/storyteller.md`. This file contains zero
voice text and zero decision logic.

CRITICAL — Place over Person (CONSTITUTION Law 4 + PROJECT_BRIEF §5):
  - Every persisted field is post-Storyteller, pre-NIL-Layer. The
    Storyteller's prompt enforces no-name discipline. The Publish Gate's
    NIL Redaction Layer is the architectural backstop that runs after
    this module persists the draft.
  - The Wire emit is routed through `wire.emit()` (the proxy); direct
    Firestore writes to `wire_events` are forbidden (CI lint blocks them
    — see `scripts/lint_no_direct_wire_writes.py`). Writes to
    `/story_drafts/`, `/killed_drafts/`, `/investigation_packets/` are
    direct-and-fine.

CRITICAL — Documentary, not Sportscaster (CONSTITUTION Law 5 +
BUILD_SPEC §5.5): structural envelope of the draft is enforced here:
headline 8-12 words, dek a single sentence, body 400-700 words, three
"why this matters" bullets, hometown panel 50-75 words, historical echo
50-100 words. Out-of-bounds raises `_DraftValidationError` so the agent
loop counts the failure as a revision and re-prompts the model.

Constitutional reference: §3 Law 5 ("Documentary, Not Sportscaster")
plus PROJECT_BRIEF §10 (restricted terminology). The Storyteller is the
literary-restraint specialist — its output is the Broadcast page.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from agents.handoffs import safe_emit_handoff

logger = logging.getLogger(__name__)


# Structural-envelope thresholds (BUILD_SPEC §5.5). Surfaced as module
# constants so the validator + tests share one source of truth.
_HEADLINE_MIN_WORDS = 8
_HEADLINE_MAX_WORDS = 12
_BODY_MIN_WORDS = 400
_BODY_MAX_WORDS = 700
_HOMETOWN_PANEL_MIN_WORDS = 50
_HOMETOWN_PANEL_MAX_WORDS = 75
_HISTORICAL_ECHO_MIN_WORDS = 50
_HISTORICAL_ECHO_MAX_WORDS = 100
_WHY_THIS_MATTERS_BULLET_COUNT = 3


# --- Tool builder -------------------------------------------------------------


def build_storyteller_tools(
    *,
    wire: Any,
    firestore: Any | None = None,
    bigquery: Any | None = None,
    runtime_state: Any | None = None,
    runtime_state_provider: Any | None = None,
) -> list[Any]:
    """Build the Storyteller's tools as closures over runtime deps.

    Returns a list ready for `LlmAgent(tools=...)`. Tool docstrings are
    the LLM-facing spec — be careful when editing. ADK's Runner
    introspects the function signature to build the JSONSchema the model
    sees.

    Args:
        wire: WireEmitter instance — for the in-process write-through
            proxy. All Wire writes route through here (NIL Layer enforced
            at proxy time).
        firestore: Firestore async-capable client. Used by every tool
            that reads or writes a document.
        bigquery: BigQuery client. Currently unused at the Storyteller
            level (the Investigator already produced a packet); reserved
            for future ad-hoc fact lookups.
        runtime_state: backref to `agents/runtime.py::RuntimeState` so
            `request_equity_review` and `request_publish_gate` can locate
            the live `equity_editor` and `publish_gate` agent instances.
            Optional — None falls through to a graceful "not initialized"
            return dict (parallel-worker race tolerance during Day-6).
        runtime_state_provider: callable returning the current
            runtime_state (or None if it isn't constructed yet). Use
            this when the agent is built BEFORE RuntimeState exists
            and a setter needs to wire the backref later — the closure
            then resolves the state lazily on each tool call. Either
            `runtime_state` (eager) or `runtime_state_provider` (lazy)
            may be passed; if both, the provider takes precedence.

    Tools (each docstring is the LLM-facing spec):
        - read_investigation_packet(packet_id) → dict
        - write_story_draft(headline, dek, body, why_this_matters,
            hometown_panel, historical_echo, place_name, era_reference,
            investigation_packet_id) → dict
        - request_equity_review(draft_id) → dict
        - request_publish_gate(draft_id) → dict
    """
    # Resolve the state-getter once. Provider takes precedence — it's
    # the lazy path used when the agent is built before RuntimeState
    # exists and a setter wires the backref later.
    if runtime_state_provider is not None:
        _state_getter = runtime_state_provider
    else:
        def _state_getter():
            return runtime_state

    return [
        _make_read_investigation_packet(firestore=firestore),
        _make_write_story_draft(firestore=firestore, wire=wire),
        _make_request_equity_review(state_getter=_state_getter, wire=wire),
        _make_request_publish_gate(state_getter=_state_getter, wire=wire),
    ]


# --- read_investigation_packet -----------------------------------------------


def _make_read_investigation_packet(*, firestore: Any | None):
    async def read_investigation_packet(packet_id: str) -> dict:
        """Read an Investigation Packet from Firestore.

        Looks up `/investigation_packets/{packet_id}`. The packet is the
        Storyteller's only source of truth — every claim in the draft
        must trace back to a field on this doc (BUILD_SPEC §5.5: "Work
        from the Investigation Packet only. Do not invent.").

        Args:
            packet_id: id of the Investigation Packet (the Investigator's
                `dispatch_investigator` tool surfaces this as
                `investigation_packet_id`).

        Returns:
            The Investigation Packet dict per BUILD_SPEC §8.4:
            `{id, story_unit_id, story_unit_title, story_unit_type,
              narrative_spine, geography, historical_context,
              trend_signals, sources, paralympic_depth_score,
              ready_for_storyteller}`.

            On missing-doc / firestore-unavailable, returns
            `{"error": "not_found", "packet_id": packet_id}` so the LLM
            can recover without raising into the Runner.
        """
        if firestore is None or not hasattr(firestore, "collection"):
            return {
                "error": "not_found",
                "packet_id": packet_id,
                "reason": "firestore_unavailable",
            }
        try:
            coll = firestore.collection("investigation_packets")
        except Exception as e:
            return {
                "error": "not_found",
                "packet_id": packet_id,
                "reason": f"investigation_packets_unavailable: {e}",
            }

        # Try direct doc-id lookup first (fastest + canonical).
        try:
            if hasattr(coll, "document"):
                doc_ref = coll.document(packet_id)
                snapshot = doc_ref.get() if hasattr(doc_ref, "get") else None
                if snapshot is not None:
                    if asyncio.iscoroutine(snapshot) or hasattr(snapshot, "__await__"):
                        snapshot = await snapshot
                    if snapshot is not None and getattr(snapshot, "exists", False):
                        data = (
                            snapshot.to_dict() if hasattr(snapshot, "to_dict") else None
                        )
                        if data:
                            data.setdefault("id", packet_id)
                            return data
        except Exception:
            logger.debug(
                "storyteller.read_investigation_packet: doc-id lookup failed; falling back to scan",
                exc_info=True,
            )

        # Fallback: scan the collection for a matching `id` field (the
        # path the unit-test stub takes).
        try:
            stream = coll.stream() if hasattr(coll, "stream") else []
            if hasattr(stream, "__aiter__"):
                async for d in stream:
                    data = _doc_to_dict(d)
                    if data.get("id") == packet_id:
                        return data
            else:
                for d in stream:
                    data = _doc_to_dict(d)
                    if data.get("id") == packet_id:
                        return data
        except Exception as e:
            return {
                "error": "not_found",
                "packet_id": packet_id,
                "reason": f"investigation_packets_scan_failed: {e}",
            }

        return {"error": "not_found", "packet_id": packet_id}

    return read_investigation_packet


# --- write_story_draft -------------------------------------------------------


def _make_write_story_draft(*, firestore: Any | None, wire: Any):
    async def write_story_draft(
        headline: str,
        dek: str,
        body: str,
        why_this_matters: list[str],
        hometown_panel: str,
        historical_echo: str,
        place_name: str,
        era_reference: str,
        investigation_packet_id: str,
        story_unit_id: str = "",
        storyteller_notes: str = "",
    ) -> dict:
        """Persist a Storyteller draft to Firestore (`/story_drafts/{auto_id}`).

        Validates the structural envelope per BUILD_SPEC §5.5 BEFORE
        writing. On any envelope failure, raises `_DraftValidationError`
        AFTER emitting a Wire `thinking` event so the operator sees the
        revision moment as Wire texture. The agent loop catches the
        exception and counts it as a revision attempt.

        Structural envelope (all enforced):
          - headline: 8-12 words.
          - dek: 1 sentence (no trailing-period sentence delimiter
            beyond the final one).
          - body: 400-700 words.
          - why_this_matters: exactly 3 strings.
          - hometown_panel: 50-75 words.
          - historical_echo: 50-100 words.

        Args:
            headline: declarative, place/program/pattern subject. NEVER
                names an athlete. 8-12 words.
            dek: one sentence emotional hook. NEVER names an athlete.
            body: the 400-700 word narrative. Athletes appear as counts
                and roles only. Forbidden Storyteller words are out
                (the prompt enforces; the Publish Gate's Language Review
                catches any leak).
            why_this_matters: exactly 3 bullets. Each describes the
                place's / program's / pattern's significance.
            hometown_panel: 50-75 word place portrait. No athlete names.
            historical_echo: 50-100 words connecting to a parallel ERA
                (never a named athlete).
            place_name: the canonical place display string for the
                Narrator's hometown-panel cue (e.g., "Mt. Pleasant,
                Iowa").
            era_reference: the canonical era reference for the
                Narrator's historical-echo cue (e.g., "1960 Rome
                sprint era").
            investigation_packet_id: id of the source packet.
            story_unit_id: optional — carried through from the packet
                for downstream search. Falls through to "" if the model
                doesn't have it.
            storyteller_notes: optional internal commentary. NOT
                user-facing — strip-checked by the Publish Gate's audit
                drawer never displays this.

        Returns:
            `{id, draft_id, persisted, investigation_packet_id}`. The
            `id` is the Firestore doc id; `draft_id` is its alias for
            ergonomic chaining into `request_equity_review(draft_id)`.

        Raises:
            _DraftValidationError: with `.field` and `.message` set when
                the envelope is violated. The agent's `write_story` loop
                catches this and re-prompts the model.
        """
        # --- Structural validation -------------------------------------
        _validate_draft(
            headline=headline,
            dek=dek,
            body=body,
            why_this_matters=why_this_matters,
            hometown_panel=hometown_panel,
            historical_echo=historical_echo,
            wire=wire,
        )

        # --- Persist ---------------------------------------------------
        draft_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()
        doc = {
            "id": draft_id,
            "investigation_packet_id": investigation_packet_id,
            "headline": headline,
            "dek": dek,
            "body": body,
            "why_this_matters": list(why_this_matters),
            "hometown_panel": hometown_panel,
            "historical_echo": historical_echo,
            "storyteller_notes": storyteller_notes,
            "place_name": place_name,
            "era_reference": era_reference,
            "story_unit_id": story_unit_id,
            "equity_review": {
                "cleared": False,
                "feedback": "",
                "revisions_count": 0,
            },
            "publish_gate_decision": "pending",
            "created_at": now,
            "updated_at": now,
        }

        persisted = False
        fs_id = draft_id
        if firestore is not None and hasattr(firestore, "collection"):
            try:
                coll = firestore.collection("story_drafts")
                res = coll.add(doc)
                if asyncio.iscoroutine(res) or hasattr(res, "__await__"):
                    res = await res
                # Some clients return (write_result, doc_ref). Prefer
                # that doc_ref.id over our generated id — but keep our
                # id in the doc body so reads are stable across paths.
                if isinstance(res, tuple) and len(res) >= 2:
                    doc_ref = res[1]
                    fs_id = getattr(doc_ref, "id", draft_id)
                elif hasattr(res, "id"):
                    fs_id = str(res.id)
                persisted = True
                logger.info(
                    "storyteller.write_story_draft: persisted draft_id=%s firestore_id=%s",
                    draft_id, fs_id,
                )
            except Exception:
                logger.exception(
                    "storyteller.write_story_draft: firestore write failed"
                )

        return {
            "id": fs_id,
            "draft_id": fs_id,
            "persisted": persisted,
            "investigation_packet_id": investigation_packet_id,
        }

    return write_story_draft


# --- request_equity_review ---------------------------------------------------


def _make_request_equity_review(*, state_getter: Any, wire: Any):
    async def request_equity_review(draft_id: str) -> dict:
        """Dispatch the Storyteller draft to the Paralympic Equity Editor.

        The Equity Editor reviews the draft, then calls exactly one of
        `clear_draft` / `return_draft` / `block_draft`. The decision is
        read off the Runner's tool-call log and surfaced here.

        Args:
            draft_id: id of the persisted draft (returned by
                `write_story_draft`).

        Returns:
            The Equity Editor's review result:
            `{action: 'ok'|'skipped'|'error',
              decision: 'cleared'|'returned'|'blocked'|'no_decision',
              draft_id, feedback?, latency_ms, ...}`.

            On `runtime_state` or `equity_editor` being None
            (parallel-worker race during Day-6 rollout), returns
            `{decision: 'unknown', draft_id, error: 'agent not yet
            operational'}` so the Storyteller can keep working without
            crashing the Runner.
        """
        state = state_getter()
        equity_editor = _resolve_runtime_attr(state, "equity_editor")
        if equity_editor is None:
            logger.warning(
                "storyteller.request_equity_review: equity_editor not initialized"
            )
            return {
                "decision": "unknown",
                "draft_id": draft_id,
                "error": "agent not yet operational",
            }
        logger.info(
            "storyteller.request_equity_review: dispatching draft_id=%s",
            draft_id,
        )
        # Agent-graph particle stream (BUILD_SPEC §9.6): the Storyteller
        # is dispatching its draft to the Equity Editor for parity review.
        await safe_emit_handoff(
            _resolve_runtime_attr(state, "firestore"),
            from_agent="storyteller",
            to_agent="equity_editor",
            tool_call_id="request_equity_review",
        )
        result = await equity_editor.review_draft(draft_id)
        # Make sure draft_id is on the return regardless of how the
        # equity editor's contract evolves.
        out = dict(result or {})
        out.setdefault("draft_id", draft_id)
        out.setdefault("decision", "no_decision")
        return out

    return request_equity_review


# --- request_publish_gate ----------------------------------------------------


def _make_request_publish_gate(*, state_getter: Any, wire: Any):
    async def request_publish_gate(draft_id: str) -> dict:
        """Dispatch a cleared draft to the Publish Gate.

        The Publish Gate runs the seven-sub-stage audit (BUILD_SPEC §5.7
        — Fact Check, Source Review, Parity Review, NIL Redaction
        Review, Safety Review, Language Review, Visual Review) and
        returns a final pass / revise / kill decision.

        Args:
            draft_id: id of the persisted draft. The Publish Gate looks
                it up under `/story_drafts/{draft_id}` to read the
                Storyteller's prose plus the equity-review block.

        Returns:
            The Publish Gate's review result:
            `{action: 'ok'|'skipped'|'error',
              decision: 'cleared'|'returned'|'killed',
              draft_id, audit_id?, ...}`.

            On `runtime_state` or `publish_gate` being None (a parallel
            Day-6 worker is shipping the Publish Gate; race tolerance),
            returns `{decision: 'unknown', draft_id, error: 'agent not
            yet operational'}`.
        """
        state = state_getter()
        publish_gate = _resolve_runtime_attr(state, "publish_gate")
        if publish_gate is None:
            logger.warning(
                "storyteller.request_publish_gate: publish_gate not initialized"
            )
            return {
                "decision": "unknown",
                "draft_id": draft_id,
                "error": "agent not yet operational",
            }
        logger.info(
            "storyteller.request_publish_gate: dispatching draft_id=%s",
            draft_id,
        )
        # Agent-graph particle stream (BUILD_SPEC §9.6): the Storyteller
        # is dispatching the equity-cleared draft to the Publish Gate's
        # seven-substage audit.
        await safe_emit_handoff(
            _resolve_runtime_attr(state, "firestore"),
            from_agent="storyteller",
            to_agent="publish_gate",
            tool_call_id="request_publish_gate",
        )
        result = await publish_gate.review(story_draft_id=draft_id)
        out = dict(result or {})
        out.setdefault("draft_id", draft_id)
        out.setdefault("decision", "no_decision")
        return out

    return request_publish_gate


# --- Validation -------------------------------------------------------------


class _DraftValidationError(Exception):
    """Raised by `write_story_draft` when the structural envelope fails.

    The Storyteller's `write_story` loop catches this and counts it as a
    revision attempt — re-prompting the model with the field + message.
    Up to 3 revisions per the agent's `max_revisions` setting.
    """

    def __init__(self, field: str, message: str) -> None:
        super().__init__(f"draft validation failed: {field}: {message}")
        self.field = field
        self.message = message


def _validate_draft(
    *,
    headline: str,
    dek: str,
    body: str,
    why_this_matters: list[str],
    hometown_panel: str,
    historical_echo: str,
    wire: Any,
) -> None:
    """Validate the BUILD_SPEC §5.5 structural envelope.

    On failure: emit a Wire `thinking` event ("draft [field] [message],
    asking model to revise") and raise `_DraftValidationError(field,
    message)`. The first violation found is the one reported — fields
    are checked top-to-bottom (headline → dek → body → bullets →
    hometown panel → historical echo) so the model sees one focused
    revision request, not a wall of errors.
    """
    # headline ---------------------------------------------------------
    headline_words = _word_count(headline)
    if headline_words < _HEADLINE_MIN_WORDS or headline_words > _HEADLINE_MAX_WORDS:
        msg = (
            f"headline word count {headline_words} out of bounds "
            f"({_HEADLINE_MIN_WORDS}-{_HEADLINE_MAX_WORDS} required)"
        )
        _emit_validation_thinking(wire, "headline", msg)
        raise _DraftValidationError("headline", msg)

    # dek --------------------------------------------------------------
    if not _is_single_sentence(dek):
        msg = "dek must be a single sentence (no internal '.' beyond the final one)"
        _emit_validation_thinking(wire, "dek", msg)
        raise _DraftValidationError("dek", msg)

    # body -------------------------------------------------------------
    body_words = _word_count(body)
    if body_words < _BODY_MIN_WORDS or body_words > _BODY_MAX_WORDS:
        msg = (
            f"body word count {body_words} out of bounds "
            f"({_BODY_MIN_WORDS}-{_BODY_MAX_WORDS} required)"
        )
        _emit_validation_thinking(wire, "body", msg)
        raise _DraftValidationError("body", msg)

    # why_this_matters --------------------------------------------------
    if (
        not isinstance(why_this_matters, list)
        or len(why_this_matters) != _WHY_THIS_MATTERS_BULLET_COUNT
        or not all(isinstance(b, str) and b.strip() for b in why_this_matters)
    ):
        msg = (
            f"why_this_matters must be exactly {_WHY_THIS_MATTERS_BULLET_COUNT} "
            f"non-empty strings (got {len(why_this_matters) if isinstance(why_this_matters, list) else type(why_this_matters).__name__})"
        )
        _emit_validation_thinking(wire, "why_this_matters", msg)
        raise _DraftValidationError("why_this_matters", msg)

    # hometown_panel ---------------------------------------------------
    panel_words = _word_count(hometown_panel)
    if (
        panel_words < _HOMETOWN_PANEL_MIN_WORDS
        or panel_words > _HOMETOWN_PANEL_MAX_WORDS
    ):
        msg = (
            f"hometown_panel word count {panel_words} out of bounds "
            f"({_HOMETOWN_PANEL_MIN_WORDS}-{_HOMETOWN_PANEL_MAX_WORDS} required)"
        )
        _emit_validation_thinking(wire, "hometown_panel", msg)
        raise _DraftValidationError("hometown_panel", msg)

    # historical_echo --------------------------------------------------
    echo_words = _word_count(historical_echo)
    if (
        echo_words < _HISTORICAL_ECHO_MIN_WORDS
        or echo_words > _HISTORICAL_ECHO_MAX_WORDS
    ):
        msg = (
            f"historical_echo word count {echo_words} out of bounds "
            f"({_HISTORICAL_ECHO_MIN_WORDS}-{_HISTORICAL_ECHO_MAX_WORDS} required)"
        )
        _emit_validation_thinking(wire, "historical_echo", msg)
        raise _DraftValidationError("historical_echo", msg)


def _word_count(text: str) -> int:
    """Whitespace-split word count. Empty / whitespace-only → 0."""
    if not isinstance(text, str):
        return 0
    return len(text.split())


def _is_single_sentence(text: str) -> bool:
    """True iff `text` is a single sentence.

    Definition: whitespace-trimmed text with at most one trailing
    sentence terminator (`.`, `!`, `?`) and no internal terminators
    other than the trailing one. We intentionally accept commas,
    semicolons, and dashes (the dek can be a long single sentence).
    Also accepts a sentence with no terminator at all (some
    headlines/deks omit the period entirely).
    """
    if not isinstance(text, str):
        return False
    stripped = text.strip()
    if not stripped:
        return False
    # Drop a single trailing terminator if present.
    if stripped[-1] in ".!?":
        stripped = stripped[:-1]
    # No internal sentence-terminators allowed in the remainder.
    return not any(ch in stripped for ch in ".!?")


def _emit_validation_thinking(wire: Any, field: str, message: str) -> None:
    """Best-effort Wire emit on validation failure.

    Schedules the emit on the running event loop and returns
    immediately; we do NOT await here because validation runs
    synchronously inside the tool call. If no loop is running (rare —
    only in pure unit-test contexts where the test bypassed asyncio),
    we silently skip the emit so the validator stays fully synchronous
    and the test can still observe the raised exception.
    """
    if wire is None:
        return
    event = {
        "agent": "storyteller",
        "message": (
            f"*draft {field} {message}, asking model to revise*"
        ),
        "message_type": "thinking",
        "mode": "live",
    }
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        return
    try:
        # Schedule but don't block — the tool path has already decided
        # to raise. The emit is texture, not gating.
        coro = wire.emit(event)
        if asyncio.iscoroutine(coro):
            asyncio.ensure_future(coro, loop=loop)
    except Exception:
        logger.debug(
            "storyteller._emit_validation_thinking: wire emit scheduling failed",
            exc_info=True,
        )


# --- Helpers ----------------------------------------------------------------


def _resolve_runtime_attr(runtime_state: Any, attr: str) -> Any | None:
    """Best-effort attribute lookup on the runtime_state backref.

    Returns None for both "no runtime_state" and "runtime_state has no
    such attribute" — both are the same outward symptom: the live agent
    is not yet operational.
    """
    if runtime_state is None:
        return None
    return getattr(runtime_state, attr, None)


def _doc_to_dict(doc: Any) -> dict:
    """Coerce a Firestore doc snapshot (or dict) to a plain dict."""
    if isinstance(doc, dict):
        return doc
    if hasattr(doc, "to_dict"):
        try:
            d = doc.to_dict() or {}
            if "id" not in d and hasattr(doc, "id"):
                d = dict(d)
                d["id"] = doc.id
            return d
        except Exception:
            return {}
    return {}
