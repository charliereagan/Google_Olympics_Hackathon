"""Scout Desk: wraps the four sub-scouts in an ADK `ParallelAgent`.

Public API:
  - `ScoutDesk(prompts=, wire=, bigquery=, firestore=, hnd=)`
  - `await desk.run_pass(candidates, ctx=)` — one parallel pass; returns leads
  - `desk.parallel_agent` — the underlying ADK ParallelAgent (or placeholder)

Result aggregation: Firestore as the rendezvous (plan §A.6 + §B). Each sub-
scout's `write_lead_report` tool persists to `/lead_reports/{id}`. `run_pass`
queries Firestore for reports created in this pass-window. Decoupled, retry-
safe, isolates the runtime from `ParallelAgent` aggregation quirks in ADK
2.0 Beta.

Backup pattern (per plan §B): if `ParallelAgent` empirically misbehaves,
swap in `asyncio.gather([scout.run() for scout in subscouts])` — identical
latency, no API surprise.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from agents.scouts.cinderella import build_cinderella_scout
from agents.scouts.comeback import build_comeback_scout
from agents.scouts.echo import build_echo_scout
from agents.scouts.hnd_detector import HndDetector
from agents.scouts.hometown import build_hometown_scout
from agents.wire.types import InvestigationContext, LeadReport

logger = logging.getLogger(__name__)


class ScoutDesk:
    def __init__(
        self,
        *,
        prompts: dict[str, str],
        wire: Any,
        bigquery: Any | None = None,
        firestore: Any | None = None,
        hnd: HndDetector | None = None,
        scout_model: str = "gemini-3-flash-preview",
    ) -> None:
        self._wire = wire
        self._bigquery = bigquery
        self._firestore = firestore
        self._hnd = hnd

        # Construct sub-scout LlmAgents (or placeholder shells when ADK is
        # not installed). Tools list is empty here; the Day-3 work wires the
        # `grounded_search`, `query_candidates`, `write_lead_report`, and
        # `wire_emit` tools into each agent's tool surface.
        self._cinderella = build_cinderella_scout(
            prompt=prompts["cinderella_scout"], model=scout_model
        )
        self._comeback = build_comeback_scout(
            prompt=prompts["comeback_scout"], model=scout_model
        )
        self._hometown = build_hometown_scout(
            prompt=prompts["hometown_scout"], model=scout_model
        )
        self._echo = build_echo_scout(
            prompt=prompts["echo_scout"], model=scout_model
        )

        self._sub_scouts = [self._cinderella, self._comeback, self._hometown, self._echo]
        self._parallel = self._build_parallel()

    @property
    def parallel_agent(self) -> Any:
        return self._parallel

    @property
    def sub_scouts(self) -> list[Any]:
        return list(self._sub_scouts)

    async def run_pass(
        self,
        candidates: list[Any],  # list of StoryUnitRef (Day-3 schema)
        *,
        ctx: InvestigationContext,
    ) -> list[LeadReport]:
        """Run all four scouts in parallel against the candidate set.

        Day-2: shell. The real per-scout `Runner.run()` invocations land
        Day-3 once we've empirically validated whether `ParallelAgent` returns
        outputs or whether we need to read them out of Firestore.

        Returns the list of Lead Reports written during this pass-window
        (queried back from Firestore on completion).
        """
        pass_start = datetime.now(timezone.utc)
        logger.info(
            "scout_desk: run_pass start (investigation=%s candidates=%d)",
            ctx.investigation_id, len(candidates),
        )
        # Day-3: invoke parallel_agent.run(...) or asyncio.gather(...)
        # See plan §B for the empirical-validation step.
        # Day-2: shell — return [] so the Editor's loop completes.
        return self._read_back_reports_since(pass_start)

    def _build_parallel(self) -> Any:
        """Construct the ADK ParallelAgent (or a placeholder if ADK absent)."""
        try:
            from google.adk.agents import ParallelAgent  # type: ignore[import-untyped]

            return ParallelAgent(
                name="scout_desk",
                sub_agents=self._sub_scouts,
            )
        except ImportError:
            logger.warning(
                "google.adk not installed; ScoutDesk parallel_agent is a placeholder"
            )
            return _PlaceholderParallel(name="scout_desk", sub_agents=self._sub_scouts)

    def _read_back_reports_since(self, pass_start: datetime) -> list[LeadReport]:
        """Query Firestore for lead_reports created at/after `pass_start`."""
        if self._firestore is None or not hasattr(self._firestore, "collection"):
            return []
        try:
            coll = self._firestore.collection("lead_reports")
            query = getattr(coll, "where", None)
            if query is None:
                # Stub firestore — scan all and filter in-process.
                docs = []
                for d in coll.stream() if hasattr(coll, "stream") else []:
                    docs.append(d)
            else:
                # Day-3 wires the real where() filter.
                docs = []
            return []  # Day-3 fills this in
        except Exception:
            logger.exception("scout_desk: lead_report read-back failed")
            return []


class _PlaceholderParallel:
    def __init__(self, *, name: str, sub_agents: list[Any]) -> None:
        self.name = name
        self.sub_agents = sub_agents
