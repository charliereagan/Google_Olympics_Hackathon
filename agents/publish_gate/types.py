"""Typed shapes for the Publish Gate.

Pinned to BUILD_SPEC §8.6 (PublishAudit) plus per-sub-stage results that
the orchestrator (`agents/publish_gate/orchestrator.py`) writes into the
audit doc.

`total=False` on every TypedDict so per-sub-stage classes can return a
partial dict without TypedDict-validation noise — the orchestrator fills
the rest.
"""

from __future__ import annotations

from typing import Literal, TypedDict


# --- Per-sub-stage result shapes ---------------------------------------------


class FactCheckResult(TypedDict, total=False):
    """Sub-stage 1 — Fact Check (BUILD_SPEC §5.7).

    Every factual claim verified against the Investigation Packet's sources.
    Hard rules per PROJECT_BRIEF §6:
      - Any claim referencing a finish time = REMOVED.
      - Any claim referencing a specific scoring result = REMOVED.
      - Any claim with a numeric statistic must trace to a source — else REMOVED.
    """

    claims_checked: int
    claims_removed: int
    claims_softened: int
    removed_claims: list[str]   # the actual claim text removed (for audit)
    softened_claims: list[str]  # for audit visibility
    passed: bool
    error: str                  # set on Runner failure → orchestrator interprets


class SourceReviewResult(TypedDict, total=False):
    """Sub-stage 2 — Source Review (BUILD_SPEC §5.7 + §9).

    Pure deterministic count + outlet aggregation. Pass criteria:
    >=2 sources AND >=2 distinct outlets (BUILD_SPEC §9 — "sources must be
    public and citable").
    """

    source_count: int
    outlets: list[str]   # alphabetized, distinct
    passed: bool


class ParityReviewResult(TypedDict, total=False):
    """Sub-stage 3 — Parity Review (BUILD_SPEC §5.7).

    Pass-through of the Equity Editor's earlier decision on the draft.
    No LLM call. (CONSTITUTION Law 3 — Parity is a System Property.)
    """

    equity_cleared: bool
    equity_feedback: str
    passed: bool


class SafetyReviewResult(TypedDict, total=False):
    """Sub-stage 5 — Safety Review (BUILD_SPEC §5.7 + §8.6).

    Two checks, one Flash-Lite call:
      1. Invented-quotes — direct quote in body NOT in packet.sources?
      2. Private/medical info — references to medical conditions, private
         records, non-public personal details?
    """

    invented_quotes: int
    private_info_flags: int
    failed_reasons: list[str]
    fallback_used: bool       # True if Flash-Lite fell back to deterministic
    passed: bool


class LanguageReviewResult(TypedDict, total=False):
    """Sub-stage 6 — Language Review (BUILD_SPEC §5.7 + §8.6, PROJECT_BRIEF §10/§11).

    Pure-Python regex check. NO LLM call. Constitution Law 5 lives here.
    """

    restricted_terms_flagged: int
    flagged_terms: list[str]
    predictive_phrases_softened: int
    passed: bool


class NilRedactionResult(TypedDict, total=False):
    """Sub-stage 4 — NIL Redaction Review (BUILD_SPEC §5.7 + CONSTITUTION §7).

    The Day-2 stub only does direct match + redact. Full Layer (with
    disambiguation, near-id, small-aggregate) lands Day 7.
    """

    individual_refs_reviewed: int
    direct_matches: int
    near_identifications: int
    small_aggregates: int
    aggregated: int
    redacted: int
    returned_to_storyteller: int
    passed: bool


class VisualReviewResult(TypedDict, total=False):
    """Sub-stage 7 — Visual Review (BUILD_SPEC §5.7).

    Day-7 work. Day-6 ships a stub that auto-passes.
    """

    regenerations: int
    passed: bool
    stub: bool   # True until Day-7 implements the real check


# --- Audit envelope ----------------------------------------------------------


class PublishAudit(TypedDict, total=False):
    """The Firestore doc shape persisted to `/publish_audits/{auto_id}`.

    Keyed sub-stages dict matches BUILD_SPEC §8.6:
      'fact_check', 'source_review', 'parity_review', 'nil_redaction_review',
      'safety_review', 'language_review', 'visual_review'.
    """

    audit_id: str
    story_id: str
    investigation_packet_id: str
    sub_stages: dict
    final_decision: Literal["cleared", "returned", "killed"]
    completed_at: str
    revisions_requested: list[str]   # which sub-stages requested revisions
    kill_reason: str                 # set when final_decision == 'killed'
