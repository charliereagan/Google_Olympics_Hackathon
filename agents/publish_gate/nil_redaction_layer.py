"""Day-7 full NIL Redaction Layer.

Drop-in replacement for the Day-2 stub at `nil_redaction_layer_stub.py`.
Same public API (`bootstrap`, `is_loaded`, `registry_size`, `loaded_at`,
`last_refresh_at`, `scan_wire`, `refresh`) PLUS a new async `scan_broadcast`
for the publish-pipeline full sweep.

Pipeline per BUILD_SPEC §5.7 process steps 1-6:

  1. Load registry (bootstrap; fail-closed if <500 rows). Inherited verbatim
     from the stub via re-use of `_build_automaton`, `_flatten_needles`,
     `_default_bigquery_row_fetcher`, `RegistryTooSmallError`, `_nfc_fold`.
  2. Direct match check (Aho-Corasick automaton). Inherited from the stub.
  3. Disambiguation pass — the most important Day-7 change. Filters
     Aho-Corasick matches by:
       - minimum needle length (default 4 chars; configurable),
       - whole-word boundaries (the rs / pyahocorasick backends return
         raw substring matches, so we add the word-boundary check
         uniformly here),
       - 50-char sport-context window for common given names (~50
         super-common names where context is REQUIRED to redact).
  4. Near-identification check — one Gemini Flash-Lite call per scan,
     gated: only on `surface='broadcast'` AND only when the direct-match
     pass found 0-3 matches AND text length >100 chars (the worry case).
     Two attempts; on double failure, fail-OPEN with a flag in the log
     (the Publish Gate's Safety Review is the second line of defense; this
     is the one place we let something through). Trade-off documented.
  5. Small-aggregate check — pure regex + registry lookup. Detects
     "[name], [name], and [name]" patterns where 2+ names are in the
     registry. Replaces the list with "<count> Olympians from this town".
  6. Decision: pass | aggregate | redact | return.
     - Wire surface (`scan_wire`) skips steps 4 and 5 — the Wire is
       in-flight and the Storyteller is the only thing that can fix a
       draft. Wire ALWAYS redacts on direct match (never returns).
     - Broadcast surface (`scan_broadcast`) runs the full pipeline.

Audit log: the structured log is richer for broadcast scans (records
disambiguation rejections, near-id outcome, aggregate count). For wire
scans we still surface direct-match counts.

Fail-closed contract (HOE-DEC-019): bootstrap raises RegistryTooSmallError
on <min_rows; the runtime exits 1. `is_loaded` returns False until
bootstrap completes; the proxy refuses to write before that.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
import unicodedata
from typing import Any, Callable, Iterable, Literal, Sequence

# Re-use the stub's pure-Python helpers verbatim. Importing private names is
# the deliberate design — the stub stays in place as a working fallback and
# we share its tested building blocks rather than fork them.
from agents.publish_gate.nil_redaction_layer_stub import (
    RegistryTooSmallError,
    _Automaton,
    _build_automaton,
    _default_bigquery_row_fetcher,
    _flatten_needles,
    _nfc_fold,
)
from agents.wire.types import NilLog, WireScanResult

logger = logging.getLogger(__name__)


# --- Disambiguation tunables -------------------------------------------------


# Minimum needle length to consider for redaction. Below this, the match is
# rejected unless it matches an explicit known-initial pattern. Default is 4
# chars per the Day-7 spec; "Mo", "la", "Vis" all under 4 = automatic reject.
_DEFAULT_MIN_NEEDLE_LENGTH = 4

# 50-char context window around each match: 25 before + 25 after. Used to
# look for sport-context keywords on common-name matches.
_CONTEXT_WINDOW_BEFORE = 25
_CONTEXT_WINDOW_AFTER = 25

# Common given names that REQUIRE sport context to redact. These are the
# top of the long-tail of US first names — coach names, town names, school
# names, generic protagonists in copy. Distinctive needles (the 11K+ rest
# of the registry) skip the context check and redact directly, accepting
# the rare false positive in exchange for simplicity. Trade-off:
#   - false negative on "Sarah won bronze" if "Sarah" is a registered
#     athlete with no last-name match nearby — we'd pass it. The Wire
#     surface's other safeguards (Safety Review's invented-quote check,
#     Storyteller revision loop) catch this.
#   - false positive avoided on "Sarah's Diner on Main Street".
# Lowercase comparison; the matching pass NFC-folds and lowercases.
_COMMON_GIVEN_NAMES: frozenset[str] = frozenset(
    {
        # Top US given names (M+F mixed) — kept short and uncontroversial.
        "michael", "sarah", "john", "mary", "robert", "patricia", "jennifer",
        "linda", "william", "elizabeth", "david", "barbara", "richard",
        "susan", "joseph", "jessica", "thomas", "karen", "charles", "nancy",
        "christopher", "lisa", "daniel", "betty", "matthew", "dorothy",
        "anthony", "sandra", "mark", "ashley", "donald", "kimberly", "steven",
        "donna", "paul", "carol", "andrew", "michelle", "joshua", "amanda",
        "kenneth", "melissa", "kevin", "deborah", "brian", "stephanie",
        "george", "rebecca", "edward", "laura",
    }
)

# Sport / family-relationship keywords that constitute "this is about an
# athlete, not a town/coach/diner/etc." Used in the 50-char context check.
# Lowercased; matched case-insensitively against the surrounding window.
_SPORT_CONTEXT_KEYWORDS: frozenset[str] = frozenset(
    {
        # Sports / disciplines (broad — the registry is multi-sport).
        "olympic", "olympics", "olympian", "paralympic", "paralympics",
        "paralympian", "team usa", "swim", "swimming", "swimmer",
        "gymnastics", "gymnast", "track", "field", "sprint", "marathon",
        "wrestling", "wrestler", "boxing", "boxer", "judo", "fencing",
        "rowing", "rower", "cycling", "cyclist", "diving", "diver",
        "hockey", "basketball", "volleyball", "soccer", "football",
        "softball", "baseball", "tennis", "golf", "skating", "skater",
        "skiing", "skier", "snowboard", "luge", "bobsled", "biathlon",
        "weightlifting", "weightlifter", "archery", "archer", "shooting",
        "sailing", "rugby", "wheelchair", "blind", "amputee",
        # Athletic-event verbs.
        "won", "winning", "wins", "medal", "medaled", "medals", "medalist",
        "competed", "competes", "competing", "qualified", "qualifies",
        "qualifying", "raced", "races", "racing", "scored", "scoring",
        "trains", "trained", "training", "career", "earned", "earning",
        "athlete", "athletes", "coach", "coaches", "coached", "coaching",
        # Date/era hints (often co-occur with an athlete reference).
        "bronze", "silver", "gold", "podium", "trials", "championship",
        "championships", "rio", "tokyo", "paris", "beijing", "london",
    }
)


# --- Common-name helpers -----------------------------------------------------


_ALNUM_OR_UNDERSCORE = re.compile(r"\w")


def _is_word_boundary(text: str, start: int, end: int) -> bool:
    """True iff the span `[start:end)` of `text` is a whole-word match.

    The character before `start` (if any) and the character at `end` (if
    any) must NOT be alnum or underscore. Mirrors the pure-Python
    automaton's logic so we apply it uniformly across the rs /
    pyahocorasick / pure-python backends.
    """
    if start < 0 or end > len(text) or start >= end:
        return False
    if start > 0 and _ALNUM_OR_UNDERSCORE.match(text[start - 1]):
        return False
    if end < len(text) and _ALNUM_OR_UNDERSCORE.match(text[end]):
        return False
    return True


def _is_initial_pattern(text: str, start: int, end: int) -> bool:
    """True if the match looks like an initialism preceded by `M.` or `M`+.

    Allows redaction of "M. Phelps" even though "Phelps" alone might be
    short — though typically last-name needles are >=5 chars, so this
    helper is a small belt-and-suspenders. Looks 5 chars before `start`
    for a pattern like `[A-Z]\\.\\s?`.
    """
    look_back = text[max(0, start - 5):start]
    return bool(re.search(r"[A-Z]\.\s?$", look_back))


def _surrounding_window_lower(text: str, start: int, end: int) -> str:
    """Return the 50-char window (25 before + 25 after) around a match,
    lowercased — used for keyword scanning."""
    win_start = max(0, start - _CONTEXT_WINDOW_BEFORE)
    win_end = min(len(text), end + _CONTEXT_WINDOW_AFTER)
    return text[win_start:win_end].lower()


def _has_sport_context(window: str) -> bool:
    """Cheap whole-word scan of `_SPORT_CONTEXT_KEYWORDS` against window."""
    if not window:
        return False
    # Whole-word match; tokenize on non-word chars, intersect with the set.
    tokens = re.findall(r"\w+", window)
    if not tokens:
        return False
    token_set = {t.lower() for t in tokens}
    return bool(token_set & _SPORT_CONTEXT_KEYWORDS)


# --- Small-aggregate detection ----------------------------------------------


# Match name-like tokens: capitalized first word, optional space + capitalized
# second word. Constrains to "First" or "First Last" form to avoid catching
# whole sentences. The pattern is greedy on first-word + optional last-name
# so "John Smith, Jane Doe, and Bob Jones" parses cleanly.
_NAMED_TOKEN = r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?"
_AGGREGATE_PATTERN = re.compile(
    # 3-name list:    A, B, and C   /   A, B, C   /   A, B, C, and D
    r"\b(" + _NAMED_TOKEN + r")"
    r"(?:,\s+(" + _NAMED_TOKEN + r"))"
    r"(?:,\s+(" + _NAMED_TOKEN + r"))?"
    r"(?:,?\s+(?:and|&)\s+(" + _NAMED_TOKEN + r"))?"
    r"\b"
)


def _detect_small_aggregates(
    text: str,
    needle_set_lower: frozenset[str],
) -> list[tuple[int, int, list[str]]]:
    """Find sequences of 3-4 capitalized name tokens where >=2 are in the registry.

    Returns a list of `(start, end, [names])` tuples — each represents a
    span in `text` to replace with a count phrase.
    """
    out: list[tuple[int, int, list[str]]] = []
    for m in _AGGREGATE_PATTERN.finditer(text):
        groups = [g for g in m.groups() if g]
        if len(groups) < 3:
            # 2-name sequences ("A and B") are not "small aggregate" — too
            # tight; they're often a coach + athlete pairing or two place
            # names. Spec calls for 3-4 named athletes specifically.
            continue
        in_registry = sum(
            1 for n in groups
            if _nfc_fold(n).lower() in needle_set_lower
        )
        if in_registry >= 2:
            out.append((m.start(), m.end(), groups))
    return out


# --- The Layer ----------------------------------------------------------------


class NilRedactionLayer:
    """Full NIL Redaction Layer (Day 7) — disambiguation + near-id + small-aggregate.

    Drop-in replacement for the Day-2 stub. Same public API plus an async
    `scan_broadcast` method for the publish-pipeline full sweep.
    """

    def __init__(
        self,
        *,
        rows: Sequence[dict],
        bq_client: Any | None = None,
        dataset: str | None = None,
        table: str = "athlete_registry",
        min_rows: int = 500,
        flash_lite_client: Any | None = None,
        flash_lite_model: str = "gemini-3.1-flash-lite-preview",
        cost_counter: Any | None = None,
        min_needle_length: int = _DEFAULT_MIN_NEEDLE_LENGTH,
    ) -> None:
        self._bq_client = bq_client
        self._dataset = dataset
        self._table = table
        self._min_rows = min_rows
        self._registry_size = 0
        self._automaton: _Automaton | None = None
        self._loaded_at: float | None = None
        self._last_refresh_at: float | None = None
        self._needle_pattern: re.Pattern[str] | None = None
        self._needle_set_lower: frozenset[str] = frozenset()
        self._flash_lite_client = flash_lite_client
        self._flash_lite_model = flash_lite_model
        self._cost_counter = cost_counter
        self._min_needle_length = int(min_needle_length)
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
        flash_lite_client: Any | None = None,
        flash_lite_model: str = "gemini-3.1-flash-lite-preview",
        cost_counter: Any | None = None,
        row_fetcher: Callable[[Any, str, str], list[dict]] | None = None,
        min_needle_length: int = _DEFAULT_MIN_NEEDLE_LENGTH,
    ) -> "NilRedactionLayer":
        """Build a Layer from BigQuery `{dataset}.{table}`.

        Args mirror the Day-2 stub plus three new params:
          - flash_lite_client: optional google-genai async client for the
            near-id check. If None, the Layer lazy-inits at first call.
          - flash_lite_model: model id for the near-id check.
          - cost_counter: when present, near-id calls are cost-counted on
            the `gemini_flash_lite` axis.

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
            flash_lite_client=flash_lite_client,
            flash_lite_model=flash_lite_model,
            cost_counter=cost_counter,
            min_needle_length=min_needle_length,
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
        # Word-boundary anchored, case-insensitive.
        escaped = [re.escape(n) for n in sorted(needles, key=len, reverse=True)]
        self._needle_pattern = re.compile(
            r"(?<![A-Za-z0-9_])(?:" + "|".join(escaped) + r")(?![A-Za-z0-9_])",
            re.IGNORECASE,
        )
        self._needle_set_lower = frozenset(n.lower() for n in needles)
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

    def attach_cost_counter(self, cost_counter: Any) -> None:
        """Late-binding hook: the runtime lifespan constructs the NIL Layer
        before the CostCounter (the layer's bootstrap is the fail-closed
        gate), so we set the counter after construction rather than
        threading a forward reference through.
        """
        self._cost_counter = cost_counter

    def attach_flash_lite_client(self, client: Any) -> None:
        """Late-binding hook for the Flash-Lite client used in near-id."""
        self._flash_lite_client = client

    # -- Public scan API ----------------------------------------------------

    def scan_wire(
        self,
        text: str,
        *,
        surface: Literal["wire", "broadcast"] = "wire",
        context: dict | None = None,
    ) -> WireScanResult:
        """Synchronous scan (per HOE-DEC-018 — wire.emit blocks on this).

        For surface='wire': fast path — direct match + disambiguation only.
        Returns decision='pass' OR 'redact' (Wire never returns; the
        Storyteller is the only thing that can fix a draft, and Wire events
        are in-flight).

        For surface='broadcast': runs the full pipeline. Because the
        near-id check is async (Flash-Lite), we drive it here via
        `asyncio.run(...)` if no event loop is currently running. The
        Publish Gate orchestrator should prefer `scan_broadcast` (async) so
        the broadcast pipeline doesn't block on a sync wrapper.
        """
        if not self.is_loaded:
            raise RuntimeError(
                "NilRedactionLayer not loaded — bootstrap() must succeed before scan_wire()"
            )
        if surface == "wire":
            return self._scan_wire_only(text, context=context)
        # surface == "broadcast" called synchronously — bridge to the async path.
        try:
            asyncio.get_running_loop()
            # We're already inside an event loop; the caller should use
            # scan_broadcast directly. As a defensive fallback, return the
            # wire-only result so we don't deadlock.
            logger.warning(
                "scan_wire(surface='broadcast') called from inside a running "
                "event loop; consider awaiting scan_broadcast(...) instead. "
                "Falling back to wire-only check."
            )
            return self._scan_wire_only(text, context=context)
        except RuntimeError:
            # No running loop — safe to drive the async pipeline.
            return asyncio.run(self.scan_broadcast(text, context=context))

    async def scan_broadcast(
        self,
        text: str,
        *,
        context: dict | None = None,
    ) -> WireScanResult:
        """Async variant for the publish pipeline. Runs the FULL pipeline:
        direct match → disambiguation → near-id Flash-Lite → small-aggregate
        → decision.

        Use from the Publish Gate orchestrator (sub-stage 4). The Layer's
        audit log entry is richer for broadcast scans (records all four
        checks).
        """
        if not self.is_loaded:
            raise RuntimeError(
                "NilRedactionLayer not loaded — bootstrap() must succeed before scan_broadcast()"
            )

        # Step 2 + 3: direct match + disambiguation.
        direct_result = self._direct_match_and_disambiguate(text)
        # Step 5: small-aggregate detection (broadcast surface).
        aggregates = _detect_small_aggregates(text, self._needle_set_lower)

        log = direct_result["log"]
        kept_matches = direct_result["kept"]

        # Step 4: near-identification check, gated.
        # Trigger condition: 0-3 direct matches AND text > 100 chars.
        near_id_findings: list[dict] = []
        flash_lite_unavailable = False
        if (
            len(kept_matches) <= 3
            and len(text) > 100
            and not aggregates  # if it's clearly an aggregate list, skip
        ):
            try:
                near_id_findings, flash_lite_unavailable = await self._run_near_id_check(text)
            except Exception:
                logger.exception("nil_redaction_layer: near-id check raised unexpectedly")
                flash_lite_unavailable = True

        log.near_identifications = sum(
            1 for f in near_id_findings if float(f.get("confidence_0_to_1", 0)) >= 0.7
        )
        log.flash_lite_unavailable = bool(flash_lite_unavailable)
        log.small_aggregates = len(aggregates)

        # Step 6: decision logic.
        # Order: aggregate > redact > return > pass.
        # If we have small aggregates AND direct matches inside them, the
        # aggregate phrase replacement supersedes individual redaction.
        if aggregates:
            redacted = self._apply_small_aggregate(text, aggregates, context or {})
            log.aggregations_applied = len(aggregates)
            return WireScanResult(
                decision="aggregate",
                redacted_message=redacted,
                log=log,
            )

        if kept_matches:
            redacted = self._rewrite_with_redactions(text, kept_matches)
            log.direct_matches_redacted = len(kept_matches)
            log.needles_matched = sorted({m["needle"] for m in kept_matches})
            return WireScanResult(
                decision="redact",
                redacted_message=redacted,
                log=log,
            )

        if log.near_identifications > 0:
            # Broadcast surface only — the Publish Gate orchestrator sees
            # decision='return' and triggers a draft return.
            high_conf = [
                f for f in near_id_findings
                if float(f.get("confidence_0_to_1", 0)) >= 0.7
            ]
            log.return_reason = (
                f"near-identification detected: {len(high_conf)} sentence(s) "
                f"uniquely identify an athlete"
            )
            return WireScanResult(
                decision="return",
                redacted_message=text,
                log=log,
            )

        return WireScanResult(
            decision="pass",
            redacted_message=text,
            log=log,
        )

    # -- Wire-only fast path ------------------------------------------------

    def _scan_wire_only(
        self,
        text: str,
        *,
        context: dict | None = None,  # noqa: ARG002 — reserved for future use
    ) -> WireScanResult:
        """Direct-match + disambiguation only. No async, no Flash-Lite, no
        small-aggregate. Wire surface always redacts (never returns)."""
        direct_result = self._direct_match_and_disambiguate(text)
        kept_matches = direct_result["kept"]
        log = direct_result["log"]

        if not kept_matches:
            return WireScanResult(
                decision="pass",
                redacted_message=text,
                log=log,
            )

        redacted = self._rewrite_with_redactions(text, kept_matches)
        log.direct_matches_redacted = len(kept_matches)
        log.needles_matched = sorted({m["needle"] for m in kept_matches})
        return WireScanResult(
            decision="redact",
            redacted_message=redacted,
            log=log,
        )

    # -- Direct match + disambiguation -------------------------------------

    def _direct_match_and_disambiguate(self, text: str) -> dict:
        """Run the automaton on the folded text, then filter through the
        disambiguation pass. Returns a dict with `kept` (list of match dicts)
        and `log` (NilLog with rejection counters).
        """
        assert self._automaton is not None  # type narrowing
        log = NilLog()

        if not text:
            return {"kept": [], "log": log}

        # NFC + accent-fold the input so 'Pelé' input matches 'Pele' needle.
        # Offsets in `folded` line up character-for-character with the
        # original because NFKD-then-strip-combining preserves base
        # character indices in the canonical case.
        folded = _nfc_fold(text)
        raw_matches = self._automaton.find_matches(folded)

        # First-pass: dedupe overlapping matches, longest-first wins. The
        # pure-Python automaton already does this; rs / pyahocorasick may
        # not — apply uniformly here.
        deduped = _dedupe_overlapping(raw_matches)

        kept: list[dict] = []
        for start, end, needle in deduped:
            # Disambiguation step 1: minimum needle length, with the
            # known-initial pattern as a relief valve.
            if len(needle) < self._min_needle_length:
                if not _is_initial_pattern(text, start, end):
                    log.rejected_short += 1
                    continue

            # Disambiguation step 2: word-boundary discipline. Reject
            # substring matches inside longer words.
            if not _is_word_boundary(text, start, end):
                log.rejected_no_word_boundary += 1
                continue

            # Disambiguation step 3: 50-char context window for common
            # given names. Distinctive names skip this check.
            needle_lower = needle.lower()
            if needle_lower in _COMMON_GIVEN_NAMES:
                window = _surrounding_window_lower(text, start, end)
                # Strip the matched needle itself from the window so the
                # presence of the name doesn't fake context.
                window_stripped = window.replace(needle_lower, " ")
                if not _has_sport_context(window_stripped):
                    log.rejected_no_context += 1
                    continue

            kept.append({
                "start": start,
                "end": end,
                "needle": needle,
            })

        return {"kept": kept, "log": log}

    # -- Redaction rewrite -------------------------------------------------

    def _rewrite_with_redactions(self, text: str, matches: list[dict]) -> str:
        """Replace each kept match span with `[redacted]`.

        We rewrite by direct offset replacement (NOT regex) so we only
        redact spans that survived the disambiguation pass. The stub used a
        regex over all needles — that re-redacts substrings the
        disambiguation pass deliberately spared.
        """
        if not matches:
            return text
        chars = list(text)
        for m in sorted(matches, key=lambda d: -d["start"]):
            start, end = m["start"], m["end"]
            if 0 <= start < len(chars) and 0 < end <= len(chars):
                chars[start:end] = list("[redacted]")
        return "".join(chars)

    # -- Small-aggregate replacement --------------------------------------

    def _apply_small_aggregate(
        self,
        text: str,
        aggregates: list[tuple[int, int, list[str]]],
        context: dict,
    ) -> str:
        """Replace each aggregate span with a count phrase.

        The count phrase pulls from the place's olympic + paralympic count
        if present in `context`; otherwise falls back to the literal name
        count in the matched span.
        """
        if not aggregates:
            return text
        # Sort descending by start so successive replacements don't shift offsets.
        for start, end, names in sorted(aggregates, key=lambda t: -t[0]):
            count = len(names)
            # Prefer an authoritative count from context if provided.
            place_olympic = int(context.get("olympic_count") or 0)
            place_paralympic = int(context.get("paralympic_count") or 0)
            if place_olympic + place_paralympic > 0:
                phrase = _english_count_phrase(place_olympic + place_paralympic) + " Olympians from this town"
            else:
                phrase = _english_count_phrase(count) + " Olympians from this town"
            text = text[:start] + phrase + text[end:]
        return text

    # -- Near-identification check ----------------------------------------

    async def _run_near_id_check(self, text: str) -> tuple[list[dict], bool]:
        """Run the Flash-Lite near-id check. Returns (findings, fail_open).

        - findings: list of {sentence, identification_basis, confidence_0_to_1}
        - fail_open: True if both attempts errored and we let the text
          through with a flag.

        Cost-counted on the `gemini_flash_lite` axis. On
        CostCeilingExceeded: log + return ([], True) so the broadcast pass
        treats it as fail-open with a flag (the Publish Gate's Safety
        Review and other sub-stages are the second line of defense).
        """
        # Cost ceiling check.
        if self._cost_counter is not None:
            try:
                from agents.cost.counters import CostCeilingExceeded  # type: ignore
                try:
                    await self._cost_counter.assert_under_ceiling(
                        axis="gemini_flash_lite", agent="publish_gate",
                    )
                except CostCeilingExceeded:
                    logger.info(
                        "nil_redaction_layer: near-id check skipped (cost ceiling)"
                    )
                    return [], True
            except ImportError:
                pass

        prompt = _build_near_id_prompt(text)
        last_exc: Exception | None = None
        parsed: list[dict] | None = None
        usage_in = 0
        usage_out = 0
        for attempt in range(2):
            try:
                parsed, usage_in, usage_out = await self._call_flash_lite(prompt)
                break
            except Exception as e:
                last_exc = e
                logger.warning(
                    "nil_redaction_layer: near-id attempt %d/2 failed: %s",
                    attempt + 1, e,
                )
        if parsed is None:
            logger.error(
                "nil_redaction_layer: flash-lite unavailable after retries; "
                "broadcast scan falls open with flag (last_exc=%s)",
                last_exc,
            )
            return [], True

        # Cost increment on success.
        if self._cost_counter is not None:
            try:
                await self._cost_counter.increment(
                    agent="publish_gate",
                    sub_agent=None,
                    axis="gemini_flash_lite",
                    model=self._flash_lite_model,
                    calls=1,
                    input_tokens=int(usage_in or 0),
                    output_tokens=int(usage_out or 0),
                )
            except Exception:
                logger.exception("nil_redaction_layer: cost_counter.increment failed")

        return parsed, False

    async def _call_flash_lite(self, prompt: str) -> tuple[list[dict], int, int]:
        """One Flash-Lite call returning (parsed_list, in_tokens, out_tokens)."""
        client = self._flash_lite_client
        # Lazy-init: build a default google-genai client if none provided.
        if client is None:
            try:
                from google import genai  # type: ignore[import-untyped]
                client = genai.Client()
                self._flash_lite_client = client
            except ImportError as e:
                raise RuntimeError("google-genai not installed") from e
        try:
            from google.genai import types as genai_types  # type: ignore[import-untyped]
        except ImportError:
            genai_types = None  # type: ignore[assignment]

        config = None
        if genai_types is not None:
            config = genai_types.GenerateContentConfig(
                temperature=0.0,
                response_mime_type="application/json",
            )

        # Support both the production async google-genai shape and the
        # test-injected stub shape (which exposes generate_content directly
        # as an awaitable).
        aio_models = getattr(getattr(client, "aio", None), "models", None)
        if aio_models is not None:
            response = await aio_models.generate_content(
                model=self._flash_lite_model,
                contents=prompt,
                config=config,
            )
        else:
            # Stub path used in unit tests.
            response = await client.generate_content(
                model=self._flash_lite_model,
                contents=prompt,
                config=config,
            )

        text = getattr(response, "text", "") or ""
        parsed = _parse_near_id_json(text)
        if parsed is None:
            raise RuntimeError(
                f"near_id_check: model returned non-JSON (head={text[:120]!r})"
            )
        usage = getattr(response, "usage_metadata", None)
        in_tokens = (
            int(getattr(usage, "prompt_token_count", 0) or 0)
            if usage is not None else 0
        )
        out_tokens = (
            int(getattr(usage, "candidates_token_count", 0) or 0)
            if usage is not None else 0
        )
        return parsed, in_tokens, out_tokens

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


# --- Helpers -----------------------------------------------------------------


def _dedupe_overlapping(
    matches: list[tuple[int, int, str]],
) -> list[tuple[int, int, str]]:
    """Drop matches that overlap a longer / earlier-emitted match.

    The pure-Python backend already does this; rs / pyahocorasick may emit
    overlapping spans (e.g., "Diego" and "Diego Maradona" both fire).
    Longest-first wins; ties broken by smaller start.
    """
    if not matches:
        return []
    # Sort by length desc, then start asc, so longer matches consume their
    # spans first.
    sorted_matches = sorted(
        matches, key=lambda t: (-(t[1] - t[0]), t[0])
    )
    consumed_ranges: list[tuple[int, int]] = []
    kept: list[tuple[int, int, str]] = []
    for s, e, n in sorted_matches:
        overlap = False
        for cs, ce in consumed_ranges:
            if s < ce and e > cs:
                overlap = True
                break
        if overlap:
            continue
        consumed_ranges.append((s, e))
        kept.append((s, e, n))
    kept.sort(key=lambda t: t[0])
    return kept


def _english_count_phrase(n: int) -> str:
    """Tiny number-to-word for the small-aggregate count phrase.

    n>10 falls back to numeric — we never hit that for an aggregate replacement.
    """
    words = {
        2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven",
        8: "eight", 9: "nine", 10: "ten",
    }
    if n in words:
        return words[n]
    if n <= 1:
        return "one"
    return str(n)


_NEAR_ID_PROMPT = """\
You are a NIL safety check for a place-focused sports newsroom.

Given the following text about a place or program, identify any sentence
that uniquely identifies a single Team USA athlete by combination of
facts (sport + hometown + event + year, or any equivalent identifying
combination). Return a JSON array of objects with this shape:

  [{{"sentence": str, "identification_basis": str, "confidence_0_to_1": float}}]

Empty array if no near-identifications. Do NOT explain. Output JSON only.

## Text
{text}
"""


def _build_near_id_prompt(text: str) -> str:
    return _NEAR_ID_PROMPT.format(text=text)


def _parse_near_id_json(text: str) -> list[dict] | None:
    """Extract a JSON array from `text`. Returns None on parse failure."""
    if not text:
        return []
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        obj = json.loads(cleaned)
        if isinstance(obj, list):
            return [d for d in obj if isinstance(d, dict)]
        # Some models wrap in {"findings": [...]}
        if isinstance(obj, dict):
            for key in ("findings", "results", "near_identifications"):
                v = obj.get(key)
                if isinstance(v, list):
                    return [d for d in v if isinstance(d, dict)]
            return []
    except json.JSONDecodeError:
        pass
    # Fallback: pick out the first array literal.
    match = re.search(r"\[.*\]", cleaned, re.DOTALL)
    if not match:
        return None
    try:
        obj = json.loads(match.group(0))
        if isinstance(obj, list):
            return [d for d in obj if isinstance(d, dict)]
    except json.JSONDecodeError:
        return None
    return None


# Re-export the registry-too-small error so callers importing from this
# module get the same exception class as the Day-2 stub raises.
__all__ = [
    "NilRedactionLayer",
    "RegistryTooSmallError",
]
