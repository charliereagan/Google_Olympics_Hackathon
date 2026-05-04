"""Day-2 stub of the NIL Redaction Layer.

The full Layer (with disambiguation, near-id Flash-Lite check, small-aggregate
detection, and return-to-Storyteller actions) lands Days 6-7. This stub
implements just the direct-match-and-redact path so the WireEmitter proxy is
correctness-complete: Wire-level enforcement of CONSTITUTION Law 4.

API surface matches the full Layer's eventual public API (plan §A.11), so the
Day-6/7 work is a drop-in replacement.

Fail-closed contract (HOE-DEC-019):
  - On bootstrap, if the registry has fewer than `min_rows` rows, raise
    RegistryTooSmallError. The runtime must exit 1 — the Layer cannot be
    partially loaded.
  - `is_loaded` returns False until bootstrap completes. The proxy refuses to
    write before that.

Aho-Corasick library pick (HOE-DEC-027):
  - Primary: `ahocorasick_rs` (Rust-backed). Falls back to `pyahocorasick` if
    the rs wheel isn't on the runtime base image. Falls back to a pure-Python
    automaton if neither library is present (slower but correct — used for
    local unit tests on machines without either library installed).
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
import unicodedata
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Literal, Sequence

from agents.wire.types import NilLog, WireScanResult

logger = logging.getLogger(__name__)


# --- Errors -------------------------------------------------------------------


class RegistryTooSmallError(RuntimeError):
    """Raised when the athlete registry has fewer rows than `min_rows`.

    Per HOE-DEC-019: the Layer fails closed. An empty registry would
    silently pass everything through, which is exactly the failure the
    Layer exists to prevent. The runtime exits 1 on this exception.
    """


# --- Tiny pure-Python automaton fallback --------------------------------------


class _PurePythonAutomaton:
    """Pure-Python multi-pattern matcher.

    Used only when neither `ahocorasick_rs` nor `pyahocorasick` is importable.
    O(N * M) on text length × needle count, which is fine for unit tests and
    Day-2 stub correctness. Production runs the rs library.
    """

    def __init__(self, needles: Sequence[str]) -> None:
        # Sort longest-first so 'Wilma Rudolph' matches before 'Wilma'.
        self._needles = sorted(set(needles), key=len, reverse=True)

    def find_matches(self, haystack: str) -> list[tuple[int, int, str]]:
        """Return non-overlapping (start, end, needle) tuples.

        Case-insensitive matching against the lowercased haystack.
        """
        out: list[tuple[int, int, str]] = []
        consumed = [False] * len(haystack)
        lower = haystack.lower()
        for needle in self._needles:
            if not needle:
                continue
            n_lower = needle.lower()
            idx = 0
            while True:
                pos = lower.find(n_lower, idx)
                if pos < 0:
                    break
                end = pos + len(n_lower)
                # Skip if any character in this span is already consumed by a
                # longer overlapping match.
                if any(consumed[pos:end]):
                    idx = pos + 1
                    continue
                # Word-boundary check: don't match inside a longer token.
                # e.g. needle "Tom" should not match "Tomato".
                if pos > 0 and (haystack[pos - 1].isalnum() or haystack[pos - 1] == "_"):
                    idx = pos + 1
                    continue
                if end < len(haystack) and (
                    haystack[end].isalnum() or haystack[end] == "_"
                ):
                    idx = pos + 1
                    continue
                out.append((pos, end, needle))
                for i in range(pos, end):
                    consumed[i] = True
                idx = end
        out.sort(key=lambda t: t[0])
        return out


# --- Aho-Corasick adapter -----------------------------------------------------


@dataclass
class _Automaton:
    """Adapter over whichever Aho-Corasick backend is available.

    Always returns matches as `(start, end, needle)` regardless of backend.
    """

    backend: Literal["ahocorasick_rs", "pyahocorasick", "pure_python"]
    impl: Any

    def find_matches(self, haystack: str) -> list[tuple[int, int, str]]:
        if self.backend == "ahocorasick_rs":
            # ahocorasick_rs.AhoCorasick.find_matches_as_indexes returns
            # list[tuple[pattern_index, start, end]]; we resolve pattern.
            patterns: list[str] = self._patterns or []
            return [
                (start, end, patterns[idx])
                for (idx, start, end) in self.impl.find_matches_as_indexes(haystack)
            ]
        if self.backend == "pyahocorasick":
            # pyahocorasick.Automaton.iter(haystack) yields (end_index, value)
            out: list[tuple[int, int, str]] = []
            for end_idx, value in self.impl.iter(haystack):
                # value is the needle stored at construction time
                start = end_idx - len(value) + 1
                out.append((start, end_idx + 1, value))
            return out
        # Pure-Python fallback
        return self.impl.find_matches(haystack)

    # patterns list (only used by ahocorasick_rs which doesn't track values)
    _patterns: list[str] | None = None


def _build_automaton(needles: Sequence[str]) -> _Automaton:
    """Build the fastest automaton available on this machine.

    Logs the pick. If only the pure-Python fallback is available, logs a
    warning so production deploys notice.
    """
    # Try ahocorasick_rs first (HOE-DEC-027 primary).
    try:
        import ahocorasick_rs  # type: ignore[import-untyped]

        patterns = list(needles)
        impl = ahocorasick_rs.AhoCorasick(patterns)
        logger.info("nil_redaction_layer: using ahocorasick_rs backend (%d needles)", len(patterns))
        return _Automaton(backend="ahocorasick_rs", impl=impl, _patterns=patterns)
    except ImportError:
        pass

    # Fall back to pyahocorasick.
    try:
        import ahocorasick  # type: ignore[import-untyped]

        a = ahocorasick.Automaton()
        for needle in needles:
            if needle:
                a.add_word(needle, needle)
        a.make_automaton()
        logger.info("nil_redaction_layer: using pyahocorasick backend (%d needles)", len(list(needles)))
        return _Automaton(backend="pyahocorasick", impl=a)
    except ImportError:
        pass

    # Pure-Python fallback (unit test / dev-machine path).
    logger.warning(
        "nil_redaction_layer: NEITHER ahocorasick_rs NOR pyahocorasick is installed; "
        "falling back to pure-Python matcher. Slow but correct. "
        "Install ahocorasick_rs in production."
    )
    return _Automaton(backend="pure_python", impl=_PurePythonAutomaton(list(needles)))


# --- Registry row + normalization helpers -------------------------------------


def _nfc_fold(text: str) -> str:
    """Unicode NFC + accent-fold. 'Pelé' -> 'Pele'."""
    nfkd = unicodedata.normalize("NFKD", text)
    folded = "".join(ch for ch in nfkd if not unicodedata.combining(ch))
    return unicodedata.normalize("NFC", folded)


def _flatten_needles(rows: Iterable[dict]) -> list[str]:
    """Project registry rows into a deduped needle list.

    Each row may have `full_name`, `first_name`, `last_name`, and a list of
    `known_variants`. Empty values dropped. NFC-folded so 'Pelé' / 'Pele' both
    match.
    """
    seen: set[str] = set()
    needles: list[str] = []
    for row in rows:
        for key in ("full_name", "first_name", "last_name"):
            v = row.get(key)
            if v:
                folded = _nfc_fold(str(v)).strip()
                if folded and folded not in seen:
                    seen.add(folded)
                    needles.append(folded)
        for variant in row.get("known_variants") or []:
            folded = _nfc_fold(str(variant)).strip()
            if folded and folded not in seen:
                seen.add(folded)
                needles.append(folded)
    return needles


# --- The Layer ----------------------------------------------------------------


# A "BigQuery-like" client interface — supports the methods we use. We don't
# import google.cloud.bigquery here because unit tests pass in a stub object
# with the same shape; a hard import would force the dep on dev machines.
class _BigQueryLike:  # pragma: no cover — protocol-only documentation
    def query(self, sql: str) -> Any: ...


class NilRedactionLayer:
    """Day-2 stub: direct-match-and-redact path only.

    Public API matches the full Layer's eventual API (plan §A.11) — Day-6/7
    drop-in replacement.
    """

    def __init__(
        self,
        *,
        rows: Sequence[dict],
        bq_client: Any | None = None,
        dataset: str | None = None,
        table: str = "athlete_registry",
        min_rows: int = 500,
    ) -> None:
        # Directly-constructed instances (used by tests + the Day-6/7 unified
        # constructor) build the automaton from rows passed in.
        self._bq_client = bq_client
        self._dataset = dataset
        self._table = table
        self._min_rows = min_rows
        self._registry_size = 0
        self._automaton: _Automaton | None = None
        self._loaded_at: float | None = None
        self._last_refresh_at: float | None = None
        self._needle_pattern: re.Pattern[str] | None = None
        if rows is not None:
            self._load_from_rows(rows)

    # -- Bootstrap ----------------------------------------------------------

    @classmethod
    def bootstrap(
        cls,
        bq_client: Any,
        *,
        dataset: str,
        table: str = "athlete_registry",
        min_rows: int = 500,
        row_fetcher: Callable[[Any, str, str], list[dict]] | None = None,
    ) -> "NilRedactionLayer":
        """Build a Layer from BigQuery `{dataset}.{table}`.

        Args:
            bq_client: a BigQuery client (real or stub). If `row_fetcher` is
                provided, this client is passed through to it; otherwise the
                default fetcher runs `SELECT ... FROM {dataset}.{table}`.
            dataset: BigQuery dataset name (e.g., 'storytellers_room').
            table: registry table name (default 'athlete_registry').
            min_rows: fail-closed threshold (HOE-DEC-019, default 500).
            row_fetcher: optional callable for unit tests; signature
                `(bq_client, dataset, table) -> list[dict]`.

        Raises:
            RegistryTooSmallError: registry returned fewer than `min_rows`.
        """
        fetcher = row_fetcher or _default_bigquery_row_fetcher
        rows = fetcher(bq_client, dataset, table)
        if len(rows) < min_rows:
            raise RegistryTooSmallError(
                f"athlete_registry has {len(rows)} rows; need >= {min_rows} "
                "(HOE-DEC-019 fail-closed contract)"
            )
        return cls(
            rows=rows,
            bq_client=bq_client,
            dataset=dataset,
            table=table,
            min_rows=min_rows,
        )

    def _load_from_rows(self, rows: Sequence[dict]) -> None:
        if len(rows) < self._min_rows:
            raise RegistryTooSmallError(
                f"athlete_registry has {len(rows)} rows; need >= {self._min_rows} "
                "(HOE-DEC-019 fail-closed contract)"
            )
        needles = _flatten_needles(rows)
        if not needles:
            raise RegistryTooSmallError("athlete_registry produced zero needles after normalization")
        self._automaton = _build_automaton(needles)
        # Build a regex that matches any needle for the redaction-rewrite step.
        # word-boundary anchored, case-insensitive.
        escaped = [re.escape(n) for n in sorted(needles, key=len, reverse=True)]
        self._needle_pattern = re.compile(
            r"(?<![A-Za-z0-9_])(?:" + "|".join(escaped) + r")(?![A-Za-z0-9_])",
            re.IGNORECASE,
        )
        self._registry_size = len(rows)
        self._loaded_at = time.time()
        self._last_refresh_at = self._loaded_at

    # -- Properties ---------------------------------------------------------

    @property
    def is_loaded(self) -> bool:
        return self._automaton is not None

    @property
    def registry_size(self) -> int:
        return self._registry_size

    @property
    def loaded_at(self) -> float | None:
        return self._loaded_at

    @property
    def last_refresh_at(self) -> float | None:
        return self._last_refresh_at

    # -- Scan ---------------------------------------------------------------

    def scan_wire(
        self,
        text: str,
        *,
        surface: Literal["wire"] = "wire",
        context: dict | None = None,  # noqa: ARG002 — reserved for Day 6/7
    ) -> WireScanResult:
        """Scan a Wire-bound message for direct athlete-name matches.

        Day-2 stub: direct-match-and-redact only. Aggregation /
        return-to-Storyteller flows arrive Day 6-7. The API shape is final.
        """
        if not self.is_loaded:
            raise RuntimeError(
                "NilRedactionLayer not loaded — bootstrap() must succeed before scan_wire()"
            )

        # NFC + accent-fold the input so 'Pelé' input matches 'Pele' needle.
        # We scan the FOLDED text but rewrite the ORIGINAL text via regex (so
        # the displayed message preserves the user's original characters minus
        # the redacted span).
        folded = _nfc_fold(text)
        assert self._automaton is not None  # for type narrowing
        matches = self._automaton.find_matches(folded)

        if not matches:
            return WireScanResult(
                decision="pass",
                redacted_message=text,
                log=NilLog(direct_matches_redacted=0, aggregations_applied=0),
            )

        # Distinct needles matched (de-dup so "Pele Pele" counts as 1 needle).
        unique_needles = sorted({m[2] for m in matches})

        # Rewrite the original (unfolded) text. We use the regex constructed at
        # load time; it's case-insensitive and word-boundary anchored.
        assert self._needle_pattern is not None
        redacted = self._needle_pattern.sub("[redacted]", text)

        # Edge case: if the regex misses (e.g., diacritic-only input), fall
        # back to redacting based on offsets in the FOLDED string. The
        # offsets line up character-for-character with the original because
        # NFKD-then-strip-combining preserves base character indices for the
        # canonical case, and if it doesn't we still produce SOMETHING
        # redacted rather than letting the name through.
        if redacted == text:
            chars = list(text)
            for start, end, _needle in sorted(matches, key=lambda t: -t[0]):
                if 0 <= start < len(chars) and 0 < end <= len(chars):
                    chars[start:end] = list("[redacted]")
            redacted = "".join(chars)

        return WireScanResult(
            decision="redact",
            redacted_message=redacted,
            log=NilLog(
                direct_matches_redacted=len(matches),
                aggregations_applied=0,
                needles_matched=unique_needles,
            ),
        )

    # -- Refresh ------------------------------------------------------------

    async def refresh(self) -> None:
        """Re-query BigQuery and atomic-swap the automaton.

        On failure: keep the prior automaton (HOE-DEC-019). The runtime
        schedules this every 6 hours from `runtime.py` lifespan setup.
        """
        if self._bq_client is None or self._dataset is None:
            logger.info("nil_redaction_layer: refresh() called but no BQ client; skipping")
            return
        try:
            rows = await asyncio.to_thread(
                _default_bigquery_row_fetcher,
                self._bq_client,
                self._dataset,
                self._table,
            )
        except Exception:
            logger.exception("nil_redaction_layer: refresh failed; keeping prior automaton")
            return
        if len(rows) < self._min_rows:
            logger.error(
                "nil_redaction_layer: refresh got %d rows (< %d); keeping prior automaton",
                len(rows), self._min_rows,
            )
            return
        try:
            self._load_from_rows(rows)
            logger.info("nil_redaction_layer: refresh complete (%d rows)", len(rows))
        except Exception:
            logger.exception("nil_redaction_layer: refresh load failed; keeping prior automaton")


# --- Default BigQuery row fetcher ---------------------------------------------


def _default_bigquery_row_fetcher(bq_client: Any, dataset: str, table: str) -> list[dict]:
    """Run the registry SELECT against BigQuery.

    Pulled out as a free function so unit tests can pass a `row_fetcher=`
    that returns a fixture instead of hitting BigQuery.
    """
    sql = (
        f"SELECT full_name, first_name, last_name, known_variants "
        f"FROM `{dataset}.{table}`"
    )
    job = bq_client.query(sql)
    return [dict(row) for row in job.result()]
