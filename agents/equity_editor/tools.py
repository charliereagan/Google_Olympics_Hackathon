"""Equity Editor tool surface — closure-bound implementations.

The Equity Editor's Pro-tier `LlmAgent` decides WHEN to call which tool
(CONSTITUTION Law 1). Python here defines the physics: read the published
feed, read drafts, write interventions to Firestore, mutate draft
`equity_review` blocks, persist the audit trail. No orchestration sequences.

Each tool below is built as a closure in `build_equity_editor_tools(...)` so
runtime deps (Firestore, the WireEmitter) are captured once and the
LLM-facing surface stays clean. Mirrors the Investigator pattern at
`agents/investigator/tools.py::build_investigator_tools`.

Voice text lives in `/prompts/equity_editor.md`. This file contains zero
voice text and zero decision logic.

CRITICAL — Place over Person (CONSTITUTION Law 4 + PROJECT_BRIEF §5):
  - The Equity Editor reads aggregate counts off published wire events and
    drafts; it never queries the athlete_registry directly. Its texts on
    the Wire and in `equity_review.feedback` MUST NOT name any individual
    Team USA athlete.
  - The Wire emit is routed through `wire.emit()` (the proxy); direct
    Firestore writes to the wire_events collection are forbidden (CI lint
    blocks `firestore.add(...)` calls into wire_events; use the proxy).

Constitutional reference: §3 Law 3 ("Parity Is a System Property"). The
Equity Editor is the impact lever — its interventions are the demo's
anchor-causation moment.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from agents.handoffs import safe_emit_handoff

logger = logging.getLogger(__name__)


# Threshold: BUILD_SPEC §5.4 — "if the last 4+ published places are
# Olympic-heavy, issue a feed-drift intervention." We surface the count in
# the return dict so the LLM can decide; the gate isn't hardcoded.
_FEED_DRIFT_PLACES_WINDOW = 4


# --- Tool builder -------------------------------------------------------------


def build_equity_editor_tools(
    *,
    wire: Any,
    firestore: Any | None = None,
    bigquery: Any | None = None,
) -> list[Any]:
    """Build the Equity Editor's tools as closures over runtime deps.

    Returns a list ready for `LlmAgent(tools=...)`. Tool docstrings are the
    LLM-facing spec — be careful when editing. ADK's Runner introspects the
    function signature to build the JSONSchema the model sees.

    Args:
        wire: WireEmitter instance — for the in-process write-through proxy.
            All Wire writes route through here.
        firestore: Firestore async-capable client. Used by every tool that
            reads or writes a document.
        bigquery: BigQuery client. Currently unused — feed parity is
            computed off Firestore-published wire events, not BigQuery
            directly. Reserved for Day-7+ aggregation queries.
    """
    return [
        _make_read_published_feed(firestore=firestore),
        _make_read_draft(firestore=firestore),
        _make_intervene_feed_drift(firestore=firestore, wire=wire),
        _make_return_draft(firestore=firestore, wire=wire),
        _make_clear_draft(firestore=firestore, wire=wire),
        _make_block_draft(firestore=firestore, wire=wire),
    ]


# --- read_published_feed -----------------------------------------------------


def _make_read_published_feed(*, firestore: Any | None):
    async def read_published_feed(limit: int = 20) -> dict:
        """Aggregate parity stats across the most recently published places.

        Reads `/wire_events` filtered to `mode='published'` (the Publish
        Gate writes a `milestone` Wire event when a story is cleared and
        published). Aggregates the events by `story_unit_id`, surfacing
        Olympic vs Paralympic counts from each event's
        `representation_history` payload (BUILD_SPEC §8.1).

        Args:
            limit: max wire events to scan (capped at 50).

        Returns:
            `{recent_places, feed_olympic_heavy, feed_paralympic_heavy,
              olympic_count, paralympic_count, places_window,
              window_threshold}`:
              - `recent_places`: list of
                `{story_unit_id, story_unit_title, olympic_count,
                  paralympic_count, era}` for each unique place in the
                window.
              - `feed_olympic_heavy`: True iff every place in the window's
                last `[window_threshold]` (default 4) skews Olympic
                (paralympic_count == 0 or olympic_count >
                paralympic_count + 1).
              - `feed_paralympic_heavy`: symmetric inverse.
              - `olympic_count` / `paralympic_count`: aggregate counts
                across all `recent_places`.
              - `places_window`: how many published places were observed.
              - `window_threshold`: BUILD_SPEC §5.4 default 4.

        Aggregate counts only — no athlete names. The LLM uses these
        numbers to decide whether to call `intervene_feed_drift`. The
        threshold is in the return dict so the model can see it; the
        decision lives in the prompt, not Python.
        """
        capped_limit = max(1, min(50, int(limit)))
        out_recent: list[dict] = []
        olympic_total = 0
        paralympic_total = 0

        if firestore is None or not hasattr(firestore, "collection"):
            return {
                "recent_places": [],
                "feed_olympic_heavy": False,
                "feed_paralympic_heavy": False,
                "olympic_count": 0,
                "paralympic_count": 0,
                "places_window": 0,
                "window_threshold": _FEED_DRIFT_PLACES_WINDOW,
            }

        try:
            coll = firestore.collection("wire_events")
            # Prefer the modern FieldFilter API where available; fall back
            # to the kw-arg shape used by older clients / unit-test stubs.
            try:
                from google.cloud.firestore_v1 import FieldFilter  # type: ignore[import-untyped]
                q = coll.where(filter=FieldFilter("mode", "==", "published"))
            except Exception:
                q = (
                    coll.where("mode", "==", "published")
                    if hasattr(coll, "where")
                    else coll
                )
            if hasattr(q, "order_by"):
                try:
                    q = q.order_by("timestamp", direction="DESCENDING")
                except TypeError:
                    q = q.order_by("timestamp")
            if hasattr(q, "limit"):
                q = q.limit(capped_limit)

            stream = q.stream() if hasattr(q, "stream") else []
            docs: list[dict] = []
            if hasattr(stream, "__aiter__"):
                async for d in stream:
                    docs.append(_doc_to_dict(d))
            else:
                for d in stream:
                    docs.append(_doc_to_dict(d))

            # Aggregate by story_unit_id, preserving recency order.
            seen: dict[str, dict] = {}
            order: list[str] = []
            for doc in docs:
                sid = doc.get("story_unit_id")
                if not sid:
                    continue
                if sid not in seen:
                    rep = doc.get("representation_history") or []
                    olympic_count, paralympic_count = _split_representation(rep)
                    # Some Publish Gate events ship `olympic_count` /
                    # `paralympic_count` directly on the wire event for
                    # convenience; honor them if present.
                    olympic_count = int(doc.get("olympic_count") or olympic_count)
                    paralympic_count = int(
                        doc.get("paralympic_count") or paralympic_count
                    )
                    seen[sid] = {
                        "story_unit_id": sid,
                        "story_unit_title": doc.get("story_unit_title") or "",
                        "olympic_count": olympic_count,
                        "paralympic_count": paralympic_count,
                        "era": doc.get("era") or doc.get("era_label") or "",
                    }
                    order.append(sid)
            for sid in order:
                rec = seen[sid]
                out_recent.append(rec)
                olympic_total += int(rec["olympic_count"])
                paralympic_total += int(rec["paralympic_count"])

        except Exception:
            logger.exception(
                "equity_editor.read_published_feed: Firestore query failed"
            )
            return {
                "recent_places": [],
                "feed_olympic_heavy": False,
                "feed_paralympic_heavy": False,
                "olympic_count": 0,
                "paralympic_count": 0,
                "places_window": 0,
                "window_threshold": _FEED_DRIFT_PLACES_WINDOW,
            }

        olympic_heavy, paralympic_heavy = _classify_drift(
            out_recent, threshold=_FEED_DRIFT_PLACES_WINDOW
        )
        return {
            "recent_places": out_recent,
            "feed_olympic_heavy": olympic_heavy,
            "feed_paralympic_heavy": paralympic_heavy,
            "olympic_count": olympic_total,
            "paralympic_count": paralympic_total,
            "places_window": len(out_recent),
            "window_threshold": _FEED_DRIFT_PLACES_WINDOW,
        }

    return read_published_feed


def _split_representation(rep: Any) -> tuple[int, int]:
    """Sum a `representation_history` array into (olympic, paralympic) totals.

    Accepts the BUILD_SPEC §8.1 shape:
      `[{year, count, type: 'olympic'|'paralympic'}, ...]`.

    Tolerant of older / alternate shapes:
      - `{olympic_count: int, paralympic_count: int}` — pull directly.
      - `[{games_type: 'summer_paralympic', count: int}, ...]` — match
        substring 'paralympic' for the Paralympic bucket.
    """
    olympic = 0
    paralympic = 0
    if isinstance(rep, dict):
        olympic = int(rep.get("olympic_count") or 0)
        paralympic = int(rep.get("paralympic_count") or 0)
        return (olympic, paralympic)
    if not isinstance(rep, list):
        return (0, 0)
    for entry in rep:
        if not isinstance(entry, dict):
            continue
        try:
            count = int(entry.get("count") or 0)
        except (TypeError, ValueError):
            count = 0
        kind = (entry.get("type") or entry.get("games_type") or "").lower()
        if "paralympic" in kind:
            paralympic += count
        elif "olympic" in kind:
            olympic += count
    return (olympic, paralympic)


def _classify_drift(places: list[dict], *, threshold: int) -> tuple[bool, bool]:
    """Return `(olympic_heavy, paralympic_heavy)` for the most recent window.

    The window is the last `threshold` places (most-recent-first ordering).
    A place "skews Olympic" when paralympic_count == 0 OR olympic_count
    exceeds paralympic_count by 2+. Symmetric inverse for Paralympic.
    Both False when fewer than `threshold` places are available — we don't
    declare drift on insufficient data.
    """
    window = places[:threshold]
    if len(window) < threshold:
        return (False, False)
    olympic_skew = 0
    paralympic_skew = 0
    for rec in window:
        oc = int(rec.get("olympic_count") or 0)
        pc = int(rec.get("paralympic_count") or 0)
        if pc == 0 and oc > 0:
            olympic_skew += 1
        elif oc - pc >= 2:
            olympic_skew += 1
        elif oc == 0 and pc > 0:
            paralympic_skew += 1
        elif pc - oc >= 2:
            paralympic_skew += 1
    return (olympic_skew == threshold, paralympic_skew == threshold)


# --- read_draft ---------------------------------------------------------------


def _make_read_draft(*, firestore: Any | None):
    async def read_draft(draft_id: str) -> dict:
        """Read a Storyteller draft from Firestore (`/story_drafts/{id}`).

        Args:
            draft_id: id of the draft (the Storyteller's persistence
                returns this when it writes the draft).

        Returns:
            The Story Draft dict per BUILD_SPEC §8.5:
            `{id, investigation_packet_id, headline, dek, body,
              why_this_matters, hometown_panel, historical_echo,
              storyteller_notes, equity_review, publish_gate_decision,
              created_at, updated_at}`.

            On missing-doc / firestore-unavailable, returns
            `{found: False, draft_id, reason}` so the LLM can recover
            without throwing.
        """
        if firestore is None or not hasattr(firestore, "collection"):
            return {
                "found": False,
                "draft_id": draft_id,
                "reason": "firestore_unavailable",
            }
        try:
            coll = firestore.collection("story_drafts")
        except Exception as e:
            return {
                "found": False,
                "draft_id": draft_id,
                "reason": f"story_drafts_unavailable: {e}",
            }

        # Try direct doc-id lookup first (fastest).
        try:
            if hasattr(coll, "document"):
                doc_ref = coll.document(draft_id)
                snapshot = doc_ref.get() if hasattr(doc_ref, "get") else None
                if snapshot is not None:
                    if asyncio.iscoroutine(snapshot) or hasattr(snapshot, "__await__"):
                        snapshot = await snapshot
                    if snapshot is not None and getattr(snapshot, "exists", False):
                        data = snapshot.to_dict() if hasattr(snapshot, "to_dict") else None
                        if data:
                            data.setdefault("id", draft_id)
                            data.setdefault("found", True)
                            return data
        except Exception:
            logger.debug(
                "equity_editor.read_draft: doc-id lookup failed; falling back to scan",
                exc_info=True,
            )

        # Fallback: scan the collection looking for a matching `id` field.
        try:
            stream = coll.stream() if hasattr(coll, "stream") else []
            if hasattr(stream, "__aiter__"):
                async for d in stream:
                    data = _doc_to_dict(d)
                    if data.get("id") == draft_id:
                        data.setdefault("found", True)
                        return data
            else:
                for d in stream:
                    data = _doc_to_dict(d)
                    if data.get("id") == draft_id:
                        data.setdefault("found", True)
                        return data
        except Exception as e:
            return {
                "found": False,
                "draft_id": draft_id,
                "reason": f"story_drafts_scan_failed: {e}",
            }

        return {"found": False, "draft_id": draft_id, "reason": "draft_not_found"}

    return read_draft


# --- intervene_feed_drift -----------------------------------------------------


def _make_intervene_feed_drift(*, firestore: Any | None, wire: Any):
    async def intervene_feed_drift(
        reason: str,
        suggested_priority_lift_story_unit_id: str,
    ) -> dict:
        """Issue a feed-drift intervention to the Editor.

        Writes an entry to Firestore `/equity_interventions/{auto_id}` and
        emits an arrival-style Wire `intervention` event so the user sees
        the room's parity-correction moment in real time. The Editor reads
        `/equity_interventions/` and decides whether to apply via its
        `accept_equity_recommendation` tool.

        Args:
            reason: short human-readable reason — "Last 4 places
                Olympic-heavy" / "Paralympic representation under-counted
                in the published window". NEVER name an individual Team
                USA athlete.
            suggested_priority_lift_story_unit_id: id of the candidate
                place / program / pattern to promote to the top of queue.
                Aggregate scoring is the Editor's call; this is the
                Equity Editor's recommendation.

        Returns:
            `{intervention_id, kind, reason,
              suggested_priority_lift_story_unit_id, created_at}` on
            success. On firestore-unavailable, the intervention is still
            emitted to the Wire (visibility) and a `persisted=False` flag
            is set in the return dict.
        """
        intervention_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()
        doc = {
            "intervention_id": intervention_id,
            "kind": "feed_drift",
            "reason": reason,
            "suggested_priority_lift_story_unit_id": (
                suggested_priority_lift_story_unit_id
            ),
            "created_at": now,
            "editor_response": None,
            "editor_response_at": None,
        }

        persisted = False
        if firestore is not None and hasattr(firestore, "collection"):
            try:
                coll = firestore.collection("equity_interventions")
                res = coll.add(doc)
                if asyncio.iscoroutine(res) or hasattr(res, "__await__"):
                    res = await res
                persisted = True
                logger.info(
                    "equity_editor.intervene_feed_drift: persisted id=%s",
                    intervention_id,
                )
            except Exception:
                logger.exception(
                    "equity_editor.intervene_feed_drift: firestore write failed"
                )

        # Wire intervention — arrival-style per streaming_profile.
        await _safe_emit_intervention(
            wire,
            f"Feed drift detected. Promoting paralympic-anchored lead to top queue.",
            story_unit_id=suggested_priority_lift_story_unit_id,
        )

        # Agent-graph particle stream (BUILD_SPEC §9.6): the Equity Editor
        # is signalling drift to the Editor, which decides whether to
        # accept via accept_equity_recommendation.
        await safe_emit_handoff(
            firestore,
            from_agent="equity_editor",
            to_agent="editor",
            tool_call_id="intervene_feed_drift",
            story_unit_id=suggested_priority_lift_story_unit_id,
        )

        return {
            "intervention_id": intervention_id,
            "kind": "feed_drift",
            "reason": reason,
            "suggested_priority_lift_story_unit_id": (
                suggested_priority_lift_story_unit_id
            ),
            "created_at": now,
            "persisted": persisted,
        }

    return intervene_feed_drift


# --- return_draft -------------------------------------------------------------


def _make_return_draft(*, firestore: Any | None, wire: Any):
    async def return_draft(draft_id: str, reason: str) -> dict:
        """Return a draft to the Storyteller for revision.

        Sets `equity_review.cleared = False`,
        `equity_review.feedback = reason`,
        `equity_review.revisions_count += 1`. Marks
        `publish_gate_decision = 'returned'`. Emits a Wire `intervention`
        ("draft returned. paralympic context for this place is shallow.").

        Args:
            draft_id: id of the draft.
            reason: short feedback for the Storyteller — describes what to
                revise. NEVER name an individual Team USA athlete; NEVER
                use forbidden Storyteller words ("inspirational", "hero",
                "overcame", etc.) in the feedback itself.

        Returns:
            `{decision: 'returned', draft_id, revisions_count, feedback,
              persisted}`.
        """
        result = await _mutate_draft_equity_review(
            firestore=firestore,
            draft_id=draft_id,
            cleared=False,
            feedback=reason,
            increment_revisions=True,
            publish_gate_decision="returned",
        )

        await _safe_emit_intervention(
            wire,
            "Draft returned. Paralympic context for this place is shallow.",
            story_unit_id=result.get("story_unit_id"),
        )

        # Agent-graph particle stream (BUILD_SPEC §9.6): the Equity Editor
        # is handing the draft back to the Storyteller for revision.
        await safe_emit_handoff(
            firestore,
            from_agent="equity_editor",
            to_agent="storyteller",
            tool_call_id="return_draft",
            story_unit_id=result.get("story_unit_id"),
        )

        return {
            "decision": "returned",
            "draft_id": draft_id,
            "revisions_count": result.get("revisions_count"),
            "feedback": reason,
            "persisted": result.get("persisted", False),
        }

    return return_draft


# --- clear_draft --------------------------------------------------------------


def _make_clear_draft(*, firestore: Any | None, wire: Any):
    async def clear_draft(draft_id: str) -> dict:
        """Clear a draft for the Publish Gate.

        Sets `equity_review.cleared = True` and clears `feedback`. Leaves
        `revisions_count` unchanged. Emits a Wire `milestone` ("Cleared.
        Paralympic depth equal to Olympic for this place.").

        Args:
            draft_id: id of the draft.

        Returns:
            `{decision: 'cleared', draft_id, revisions_count, persisted}`.
        """
        result = await _mutate_draft_equity_review(
            firestore=firestore,
            draft_id=draft_id,
            cleared=True,
            feedback="",
            increment_revisions=False,
            publish_gate_decision=None,  # Publish Gate sets this; we just clear.
        )

        await _safe_emit_milestone(
            wire,
            "Cleared. Paralympic depth equal to Olympic for this place.",
            story_unit_id=result.get("story_unit_id"),
        )

        return {
            "decision": "cleared",
            "draft_id": draft_id,
            "revisions_count": result.get("revisions_count"),
            "persisted": result.get("persisted", False),
        }

    return clear_draft


# --- block_draft --------------------------------------------------------------


def _make_block_draft(*, firestore: Any | None, wire: Any):
    async def block_draft(draft_id: str, reason: str) -> dict:
        """Veto: block the draft from publication.

        Reserved for safety-level violations — drafts that frame
        Paralympic representation as inspiration porn or use forbidden
        framing the Equity Editor cannot accept on revision. Sets
        `equity_review.cleared = False`,
        `publish_gate_decision = 'killed'`. Writes an audit entry to
        `/killed_drafts/{draft_id}` so the kill is preserved (the draft
        itself is not deleted; the Publish Gate sees `killed` and stops).
        Emits a Wire `intervention` ("Blocked. Frames disability as
        inspiration. Rewrite.").

        Args:
            draft_id: id of the draft.
            reason: short audit reason. NEVER quote forbidden inspiration
                tropes back as approved language; describe the failure
                pattern (e.g., "frames disability as inspiration",
                "ableist phrasing", "uses 'wheelchair-bound'").

        Returns:
            `{decision: 'blocked', draft_id, persisted}`.
        """
        result = await _mutate_draft_equity_review(
            firestore=firestore,
            draft_id=draft_id,
            cleared=False,
            feedback=reason,
            increment_revisions=False,
            publish_gate_decision="killed",
        )

        # Audit-trail write — the kill is permanent; record it.
        if firestore is not None and hasattr(firestore, "collection"):
            try:
                killed_coll = firestore.collection("killed_drafts")
                killed_coll.add(
                    {
                        "draft_id": draft_id,
                        "reason": reason,
                        "killed_at": datetime.now(timezone.utc).isoformat(),
                        "blocked_by": "equity_editor",
                    }
                )
            except Exception:
                logger.exception(
                    "equity_editor.block_draft: killed_drafts write failed"
                )

        await _safe_emit_intervention(
            wire,
            "Blocked. Frames disability as inspiration. Rewrite.",
            story_unit_id=result.get("story_unit_id"),
        )

        return {
            "decision": "blocked",
            "draft_id": draft_id,
            "persisted": result.get("persisted", False),
        }

    return block_draft


# --- Shared mutation helper ---------------------------------------------------


async def _mutate_draft_equity_review(
    *,
    firestore: Any | None,
    draft_id: str,
    cleared: bool,
    feedback: str,
    increment_revisions: bool,
    publish_gate_decision: str | None,
) -> dict:
    """Read-modify-write the draft's equity_review block + publish_gate_decision.

    Returns `{persisted, revisions_count, story_unit_id?}`. On any failure,
    `persisted=False` and the original state is unchanged.
    """
    if firestore is None or not hasattr(firestore, "collection"):
        return {"persisted": False, "revisions_count": 0, "story_unit_id": None}

    try:
        coll = firestore.collection("story_drafts")
    except Exception:
        return {"persisted": False, "revisions_count": 0, "story_unit_id": None}

    # Resolve the current draft state via doc-id lookup first; fall back to
    # a collection scan (the path the unit-test stub takes).
    current: dict | None = None
    doc_ref = None
    try:
        if hasattr(coll, "document"):
            doc_ref = coll.document(draft_id)
            snapshot = doc_ref.get() if hasattr(doc_ref, "get") else None
            if snapshot is not None:
                if asyncio.iscoroutine(snapshot) or hasattr(snapshot, "__await__"):
                    snapshot = await snapshot
                if snapshot is not None and getattr(snapshot, "exists", False):
                    current = (
                        snapshot.to_dict() if hasattr(snapshot, "to_dict") else None
                    )
    except Exception:
        logger.debug(
            "equity_editor._mutate_draft: doc-id lookup failed; falling back to scan",
            exc_info=True,
        )

    if current is None:
        try:
            stream = coll.stream() if hasattr(coll, "stream") else []
            if hasattr(stream, "__aiter__"):
                async for d in stream:
                    data = _doc_to_dict(d)
                    if data.get("id") == draft_id:
                        current = data
                        break
            else:
                for d in stream:
                    data = _doc_to_dict(d)
                    if data.get("id") == draft_id:
                        current = data
                        break
        except Exception:
            logger.exception("equity_editor._mutate_draft: scan failed")
            return {"persisted": False, "revisions_count": 0, "story_unit_id": None}

    if current is None:
        logger.warning(
            "equity_editor._mutate_draft: draft %s not found", draft_id
        )
        return {"persisted": False, "revisions_count": 0, "story_unit_id": None}

    equity_review = dict(current.get("equity_review") or {})
    revisions_count = int(equity_review.get("revisions_count") or 0)
    if increment_revisions:
        revisions_count += 1
    equity_review["cleared"] = bool(cleared)
    equity_review["feedback"] = feedback
    equity_review["revisions_count"] = revisions_count

    updated = dict(current)
    updated["equity_review"] = equity_review
    if publish_gate_decision is not None:
        updated["publish_gate_decision"] = publish_gate_decision
    updated["updated_at"] = datetime.now(timezone.utc).isoformat()

    persisted = await _persist_draft_update(
        coll=coll,
        doc_ref=doc_ref,
        draft_id=draft_id,
        current=current,
        updated=updated,
    )

    return {
        "persisted": persisted,
        "revisions_count": revisions_count,
        "story_unit_id": current.get("story_unit_id")
        or updated.get("story_unit_id"),
    }


async def _persist_draft_update(
    *,
    coll: Any,
    doc_ref: Any,
    draft_id: str,
    current: dict,
    updated: dict,
) -> bool:
    """Persist an updated draft. Tries .set() first, falls back to add().

    Returns True iff the write succeeded.
    """
    # Modern Firestore: doc_ref.set(updated, merge=False) replaces fields.
    if doc_ref is not None and hasattr(doc_ref, "set"):
        try:
            res = doc_ref.set(updated)
            if asyncio.iscoroutine(res) or hasattr(res, "__await__"):
                await res
            return True
        except Exception:
            logger.debug(
                "equity_editor._persist_draft_update: doc_ref.set failed; trying update",
                exc_info=True,
            )
    if doc_ref is not None and hasattr(doc_ref, "update"):
        try:
            res = doc_ref.update(
                {
                    "equity_review": updated.get("equity_review"),
                    "publish_gate_decision": updated.get("publish_gate_decision"),
                    "updated_at": updated.get("updated_at"),
                }
            )
            if asyncio.iscoroutine(res) or hasattr(res, "__await__"):
                await res
            return True
        except Exception:
            logger.debug(
                "equity_editor._persist_draft_update: doc_ref.update failed; falling back to add",
                exc_info=True,
            )

    # Fallback path used by the unit-test stub: append the updated state to
    # the collection's add() buffer. The test asserts on the most-recent
    # add() payload, which makes this a clean unit-test contract.
    if hasattr(coll, "add"):
        try:
            res = coll.add(updated)
            if asyncio.iscoroutine(res) or hasattr(res, "__await__"):
                await res
            return True
        except Exception:
            logger.exception(
                "equity_editor._persist_draft_update: coll.add fallback failed"
            )
    return False


# --- Wire emit helpers --------------------------------------------------------


async def _safe_emit_intervention(
    wire: Any,
    message: str,
    *,
    story_unit_id: str | None = None,
) -> None:
    """Emit a Wire `intervention` event without raising into the tool caller.

    `intervention` is the arrival-style message_type for this agent
    (streaming_profile.arrival_style = 'instant' per BUILD_SPEC §6.5).
    """
    if wire is None:
        return
    try:
        event: dict = {
            "agent": "equity_editor",
            "message": message,
            "message_type": "intervention",
            "mode": "live",
        }
        if story_unit_id is not None:
            event["story_unit_id"] = story_unit_id
        await wire.emit(event)
    except Exception:
        logger.exception("equity_editor: failed to emit Wire intervention event")


async def _safe_emit_milestone(
    wire: Any,
    message: str,
    *,
    story_unit_id: str | None = None,
) -> None:
    """Emit a Wire `milestone` event without raising into the tool caller."""
    if wire is None:
        return
    try:
        event: dict = {
            "agent": "equity_editor",
            "message": message,
            "message_type": "milestone",
            "mode": "live",
        }
        if story_unit_id is not None:
            event["story_unit_id"] = story_unit_id
        await wire.emit(event)
    except Exception:
        logger.exception("equity_editor: failed to emit Wire milestone event")


# --- Helpers ------------------------------------------------------------------


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
