"""Sub-stage 2: Source Review.

Pure-deterministic count + outlet aggregation. NO LLM call.

Pass criteria per BUILD_SPEC §9 ("sources must be public and citable") +
§5.7 (Source Review = "total public sources cited, citation links
collected"):
  - source_count >= 2.
  - distinct outlets >= 2.

The Investigator's Investigation Packet (BUILD_SPEC §8.4) carries the
canonical `sources: [{url, outlet, relevance_note}]` array. We dedupe on
`url` first (defensive — same URL listed twice shouldn't double-count) then
project the distinct `outlet` strings.
"""

from __future__ import annotations

import logging
from typing import Any

from agents.publish_gate.types import SourceReviewResult

logger = logging.getLogger(__name__)


# Pass criteria thresholds (BUILD_SPEC §9 + §5.7).
_MIN_SOURCES = 2
_MIN_OUTLETS = 2


class SourceReviewSubstage:
    """Sub-stage 2 — count public sources cited; collect outlets.

    Synchronous, no LLM, no I/O. Cheap to run.
    """

    def __init__(self) -> None:  # noqa: D401 — empty by design
        pass

    def review(
        self,
        *,
        story_draft: dict,            # noqa: ARG002 — reserved for future use
        investigation_packet: dict,
    ) -> SourceReviewResult:
        """Count sources + collect distinct outlets from the Investigation Packet.

        Args:
            story_draft: the StoryDraft dict per BUILD_SPEC §8.5. Not read
                today; reserved so the API surface matches the LLM-backed
                sub-stages (Fact Check, Safety Review).
            investigation_packet: the InvestigationPacket dict per
                BUILD_SPEC §8.4. We read `sources` only.

        Returns:
            `SourceReviewResult` with `source_count`, `outlets` (alphabetized
            distinct), and `passed`.
        """
        sources = (investigation_packet or {}).get("sources") or []
        if not isinstance(sources, list):
            logger.warning(
                "source_review: sources is not a list (got %s); treating as empty",
                type(sources).__name__,
            )
            sources = []

        # Dedupe on url. A missing `url` field falls back to the outlet name
        # (defensive — packets without urls would otherwise all collapse to
        # the empty key).
        seen_urls: set[str] = set()
        unique_sources: list[dict] = []
        for src in sources:
            if not isinstance(src, dict):
                continue
            url = (src.get("url") or src.get("outlet") or "").strip()
            if not url:
                continue
            if url in seen_urls:
                continue
            seen_urls.add(url)
            unique_sources.append(src)

        # Distinct outlets, alphabetized for stable audit output.
        outlets_set: set[str] = set()
        for src in unique_sources:
            outlet = (src.get("outlet") or "").strip()
            if outlet:
                outlets_set.add(outlet)

        outlets_sorted = sorted(outlets_set, key=lambda s: s.lower())
        source_count = len(unique_sources)
        passed = source_count >= _MIN_SOURCES and len(outlets_sorted) >= _MIN_OUTLETS

        return SourceReviewResult(
            source_count=source_count,
            outlets=outlets_sorted,
            passed=passed,
        )
