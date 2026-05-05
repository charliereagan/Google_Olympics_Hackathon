"""Unit tests for the Day-7 full NIL Redaction Layer.

Covers BUILD_SPEC §5.7 process steps 1-6 plus the Day-3/4 over-redaction
regressions (Penn State, Monitoring, Chula Vista, Lake Placid).

Test fixtures use synthetic non-Team-USA names (e.g., 'Pelé', 'Diego
Maradona' from PROJECT_BRIEF §5 examples; 'Wexlonia Fertingdale' for a
distinctive long name) — kept disjoint from the production
athlete_registry per project convention. The Day-2 stub tests in
`test_nil_redaction_layer_stub.py` continue to pass; this file extends.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import pytest

from agents.publish_gate.nil_redaction_layer import (
    NilRedactionLayer,
    RegistryTooSmallError,
)


# --- Fixture helpers ---------------------------------------------------------


def _make_fixture_rows(n: int, *, seeds: list[dict] | None = None) -> list[dict]:
    """Build a fixture of n synthetic registry rows.

    Default seeds use non-Team-USA names; tests pass their own seeds when
    they need a specific shape (common name, short token, etc.).
    """
    base_seeds: list[dict] = seeds if seeds is not None else [
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
    rows = list(base_seeds)
    while len(rows) < n:
        i = len(rows)
        rows.append(
            {
                "full_name": f"Synthetic Person {i}",
                "first_name": f"Synthetic{i}",
                "last_name": f"Person{i}",
                "known_variants": [],
            }
        )
    return rows[:n]


def _stub_fetcher_returning(rows: list[dict]):
    def _f(_bq, _dataset, _table):
        return rows
    return _f


# --- Test stubs for the Flash-Lite client ------------------------------------


@dataclass
class _FakeUsage:
    prompt_token_count: int = 100
    candidates_token_count: int = 50


@dataclass
class _FakeResponse:
    text: str
    usage_metadata: Any = None

    def __post_init__(self):
        if self.usage_metadata is None:
            self.usage_metadata = _FakeUsage()


class _FakeFlashLiteClient:
    """Stub Flash-Lite client. The Layer calls
    `client.aio.models.generate_content(...)`. We expose `.aio.models` so
    the production code path is exercised without needing google-genai.

    `responses`: list of (text, exception) — pop on each call. If
    exception, raise; else return _FakeResponse(text).
    """

    def __init__(self, responses: list[tuple[str | None, Exception | None]]) -> None:
        self.responses = list(responses)
        self.calls: list[dict] = []

        client = self  # Closure capture for nested classes.

        class _Models:
            async def generate_content(self_inner, *, model, contents, config):  # noqa: N805
                client.calls.append({"model": model, "contents": contents})
                if not client.responses:
                    raise RuntimeError("no more stub responses")
                text, exc = client.responses.pop(0)
                if exc is not None:
                    raise exc
                return _FakeResponse(text=text or "")

        class _Aio:
            models = _Models()

        self.aio = _Aio()


# --- Bootstrap + lifecycle ---------------------------------------------------


def test_bootstrap_asserts_min_rows():
    """Registry below the threshold raises RegistryTooSmallError."""
    too_few = _make_fixture_rows(200)
    with pytest.raises(RegistryTooSmallError):
        NilRedactionLayer.bootstrap(
            bq_client=object(),
            dataset="x",
            row_fetcher=_stub_fetcher_returning(too_few),
        )


def test_bootstrap_unicode_normalization():
    """Needle 'Pelé' (with diacritic) must match 'Pele' input (without)."""
    layer = NilRedactionLayer(rows=_make_fixture_rows(600), min_rows=500)
    result = layer.scan_wire("Pele scored a goal")
    # 'Pele' is 4 chars (passes min length); not in common-name list; whole word.
    assert result.decision == "redact"
    assert "[redacted]" in result.redacted_message
    assert "Pele" not in result.redacted_message


def test_is_loaded_returns_false_until_bootstrap():
    """A Layer with rows=None (impossible via public API) is unloaded.

    Simulate by zeroing the automaton after construction.
    """
    layer = NilRedactionLayer(rows=_make_fixture_rows(600), min_rows=500)
    assert layer.is_loaded is True
    layer._automaton = None  # type: ignore[attr-defined]
    assert layer.is_loaded is False
    with pytest.raises(RuntimeError):
        layer.scan_wire("anything")


def test_refresh_preserves_prior_automaton_on_failure():
    """A refresh whose fetcher raises must not blank the prior automaton."""
    layer = NilRedactionLayer(rows=_make_fixture_rows(600), min_rows=500)
    prior_size = layer.registry_size
    prior_automaton_id = id(layer._automaton)  # type: ignore[attr-defined]
    # Wire a broken bq client + dataset so refresh actually runs.
    layer._bq_client = object()  # type: ignore[attr-defined]
    layer._dataset = "x"  # type: ignore[attr-defined]
    # Monkey-patch the fetcher used by refresh to raise.
    import agents.publish_gate.nil_redaction_layer as mod
    orig = mod._default_bigquery_row_fetcher  # type: ignore[attr-defined]
    def _broken(*_args, **_kwargs):
        raise RuntimeError("simulated bq failure")
    mod._default_bigquery_row_fetcher = _broken  # type: ignore[attr-defined]
    try:
        asyncio.run(layer.refresh())
    finally:
        mod._default_bigquery_row_fetcher = orig  # type: ignore[attr-defined]
    assert layer.registry_size == prior_size
    assert id(layer._automaton) == prior_automaton_id  # type: ignore[attr-defined]


# --- Direct match + disambiguation (Day-7 critical regressions) -------------


def test_short_token_2char_no_longer_redacted():
    """A 2-char registry needle ('Mo') must NOT redact 'Monitoring'.

    This is the Day-3 smoke regression: '[redacted]nitoring' was the
    Day-2 stub mis-firing on a short token. Day-7 disambiguation rejects
    matches under min_needle_length (default 4).
    """
    rows = _make_fixture_rows(
        600,
        seeds=[
            {"full_name": "Mo", "first_name": "Mo", "last_name": "", "known_variants": []},
            {"full_name": "Diego Maradona", "first_name": "Diego", "last_name": "Maradona", "known_variants": []},
        ],
    )
    layer = NilRedactionLayer(rows=rows, min_rows=500)
    result = layer.scan_wire("Monitoring the program")
    assert result.decision == "pass", f"unexpected redact: {result.redacted_message}"
    # The disambiguation pass should have logged a short-token rejection
    # if the automaton fired at all.
    assert "Monitoring" in result.redacted_message


def test_word_boundary_check_skips_substring_match():
    """Registry has 'Penn'; input 'Pennsylvania State pipeline' must pass.

    This is the Day-3 smoke regression: '[redacted] State'. With min
    needle length=4, 'Penn' is exactly at the floor; word-boundary check
    catches the substring.
    """
    rows = _make_fixture_rows(
        600,
        seeds=[
            {"full_name": "Penn", "first_name": "Penn", "last_name": "", "known_variants": []},
        ],
    )
    layer = NilRedactionLayer(rows=rows, min_rows=500)
    result = layer.scan_wire("Pennsylvania State pipeline modernized")
    assert result.decision == "pass", f"unexpected redact: {result.redacted_message}"


def test_chula_vista_does_not_over_redact():
    """Day-4 smoke regression: '[redacted]la [redacted]ta' for 'Chula Vista'.

    Even with short-token registry entries that COULD substring-match
    inside 'Chula Vista', the disambiguation pass rejects them on
    word-boundary + min-length grounds.
    """
    rows = _make_fixture_rows(
        600,
        seeds=[
            {"full_name": "la", "first_name": "la", "last_name": "", "known_variants": []},
            {"full_name": "Vis", "first_name": "Vis", "last_name": "", "known_variants": []},
        ],
    )
    layer = NilRedactionLayer(rows=rows, min_rows=500)
    result = layer.scan_wire("Chula Vista is a coastal city in Southern California")
    assert result.decision == "pass", f"unexpected redact: {result.redacted_message}"


def test_lake_placid_does_not_over_redact():
    """Day-4 smoke regression: '[redacted] Placid' for 'Lake Placid'.

    The Day-4 over-redaction was a substring match — a short registry
    needle matched inside 'Lake' or 'Placid' as a substring. With the
    Day-7 fixes (min_needle_length=4 + word-boundary discipline), short
    substring matches are filtered out.
    """
    rows = _make_fixture_rows(
        600,
        seeds=[
            # 3-char short token that COULD substring-match inside 'Placid'.
            {"full_name": "lac", "first_name": "lac", "last_name": "", "known_variants": []},
            # Common-name potential surface that COULD match elsewhere.
            {"full_name": "ake", "first_name": "ake", "last_name": "", "known_variants": []},
        ],
    )
    layer = NilRedactionLayer(rows=rows, min_rows=500)
    result = layer.scan_wire("Lake Placid 1980 modernization continues")
    assert result.decision == "pass", f"unexpected redact: {result.redacted_message}"
    assert "[redacted]" not in result.redacted_message


def test_distinctive_long_name_redacted_directly():
    """A distinctive 8+ char first+last name redacts without context check."""
    rows = _make_fixture_rows(
        600,
        seeds=[
            {
                "full_name": "Wexlonia Fertingdale",
                "first_name": "Wexlonia",
                "last_name": "Fertingdale",
                "known_variants": [],
            },
        ],
    )
    layer = NilRedactionLayer(rows=rows, min_rows=500)
    result = layer.scan_wire("Wexlonia Fertingdale won bronze in the 200m")
    assert result.decision == "redact"
    assert "Wexlonia" not in result.redacted_message
    assert "Fertingdale" not in result.redacted_message
    assert "[redacted]" in result.redacted_message


def test_common_name_requires_sport_context():
    """'Sarah Smith' as a registry entry: 'Sarah's Diner' passes; 'Sarah Smith won bronze' redacts."""
    rows = _make_fixture_rows(
        600,
        seeds=[
            {
                "full_name": "Sarah Smith",
                "first_name": "Sarah",
                "last_name": "Smith",
                "known_variants": [],
            },
        ],
    )
    layer = NilRedactionLayer(rows=rows, min_rows=500)

    # No sport context — common given name 'Sarah' isn't redacted; 'Smith'
    # is also a common surname so the full-name needle 'Sarah Smith' isn't
    # in the diner string.
    diner = layer.scan_wire("Sarah's Diner on Main Street is a town favorite")
    assert diner.decision == "pass", f"unexpected redact: {diner.redacted_message}"

    # Sport context present — 'Sarah Smith' full-name needle matches AND
    # the 50-char window contains 'won', 'bronze', '200m'. The full-name
    # match is distinctive (not on the common-name list) and redacts.
    medal = layer.scan_wire("Sarah Smith won bronze in the 200m")
    assert medal.decision == "redact"
    assert "Sarah Smith" not in medal.redacted_message


def test_initial_pattern_redacts():
    """'M. Phelps' should redact — last-name needle survives even if short.

    The relief valve `_is_initial_pattern` lets 'Phelps' through even at
    the min-length boundary.
    """
    rows = _make_fixture_rows(
        600,
        seeds=[
            {
                "full_name": "Michael Phelps",
                "first_name": "Michael",
                "last_name": "Phelps",
                "known_variants": [],
            },
        ],
    )
    layer = NilRedactionLayer(rows=rows, min_rows=500)
    result = layer.scan_wire("M. Phelps swept the event")
    # 'Phelps' is 6 chars, above min length, distinctive — redacts.
    assert result.decision == "redact"
    assert "Phelps" not in result.redacted_message


# --- Near-identification (broadcast surface only) ----------------------------


def test_near_id_check_skipped_on_wire_surface():
    """`scan_wire(surface='wire')` must NOT call Flash-Lite."""
    rows = _make_fixture_rows(600)
    fake_client = _FakeFlashLiteClient(responses=[])
    layer = NilRedactionLayer(
        rows=rows, min_rows=500, flash_lite_client=fake_client
    )
    text = "the small town built a community gym in 1976. it has produced two paralympians."
    result = layer.scan_wire(text, surface="wire")
    assert result.decision == "pass"
    assert fake_client.calls == []


def test_near_id_check_runs_on_broadcast_surface_with_zero_direct_matches():
    """Long broadcast text, zero direct matches → Flash-Lite is called."""
    rows = _make_fixture_rows(600)
    fake_client = _FakeFlashLiteClient(
        responses=[("[]", None)]  # empty findings array
    )
    layer = NilRedactionLayer(
        rows=rows, min_rows=500, flash_lite_client=fake_client
    )
    text = (
        "The town's wrestling program has produced four olympians since 1972. "
        "Their training facility is a converted high school gym in the eastern "
        "valley, where successive generations have built a regional pipeline."
    )
    result = asyncio.run(layer.scan_broadcast(text))
    assert result.decision == "pass"
    assert len(fake_client.calls) == 1


def test_near_id_returns_decision_when_flash_lite_finds_high_confidence_match():
    """confidence >= 0.7 on broadcast surface → decision='return'."""
    rows = _make_fixture_rows(600)
    finding = (
        '[{"sentence": "the only sprinter from this hamlet to medal in 2020", '
        '"identification_basis": "sport+place+year", "confidence_0_to_1": 0.92}]'
    )
    fake_client = _FakeFlashLiteClient(responses=[(finding, None)])
    layer = NilRedactionLayer(
        rows=rows, min_rows=500, flash_lite_client=fake_client
    )
    text = (
        "The town's track program is small but distinctive. The only sprinter "
        "from this hamlet to medal in 2020 came up through that program. The "
        "facility is a converted parking lot."
    )
    result = asyncio.run(layer.scan_broadcast(text))
    assert result.decision == "return"
    assert result.log.near_identifications == 1
    assert result.log.return_reason


def test_near_id_passes_when_flash_lite_finds_low_confidence():
    """confidence < 0.7 → not high-confidence → decision='pass'."""
    rows = _make_fixture_rows(600)
    finding = (
        '[{"sentence": "the small town wrestler from 2008", '
        '"identification_basis": "sport+place+year", "confidence_0_to_1": 0.45}]'
    )
    fake_client = _FakeFlashLiteClient(responses=[(finding, None)])
    layer = NilRedactionLayer(
        rows=rows, min_rows=500, flash_lite_client=fake_client
    )
    text = (
        "The town's wrestling program has produced two olympians since 1972. "
        "The training facility is a converted high school gym."
    )
    result = asyncio.run(layer.scan_broadcast(text))
    assert result.decision == "pass"
    assert result.log.near_identifications == 0


def test_near_id_fails_open_when_flash_lite_call_errors_twice():
    """Both Flash-Lite attempts raise → decision='pass' with flag in log."""
    rows = _make_fixture_rows(600)
    fake_client = _FakeFlashLiteClient(
        responses=[
            (None, RuntimeError("flash-lite 500")),
            (None, RuntimeError("flash-lite 500 again")),
        ]
    )
    layer = NilRedactionLayer(
        rows=rows, min_rows=500, flash_lite_client=fake_client
    )
    text = (
        "The town's wrestling program is small but storied. It has produced "
        "two olympians since 1972 and a coach who runs the regional pipeline."
    )
    result = asyncio.run(layer.scan_broadcast(text))
    assert result.decision == "pass"
    assert result.log.flash_lite_unavailable is True
    assert len(fake_client.calls) == 2


# --- Small-aggregate ---------------------------------------------------------


def test_small_aggregate_three_names_replaced_with_count():
    """[A], [B], and [C] from the registry → 'three Olympians from this town'."""
    rows = _make_fixture_rows(
        600,
        seeds=[
            {
                "full_name": "Alpha Onefoot",
                "first_name": "Alpha",
                "last_name": "Onefoot",
                "known_variants": [],
            },
            {
                "full_name": "Bravo Twostep",
                "first_name": "Bravo",
                "last_name": "Twostep",
                "known_variants": [],
            },
            {
                "full_name": "Charlie Threejump",
                "first_name": "Charlie",
                "last_name": "Threejump",
                "known_variants": [],
            },
        ],
    )
    fake_client = _FakeFlashLiteClient(responses=[("[]", None)])
    layer = NilRedactionLayer(
        rows=rows, min_rows=500, flash_lite_client=fake_client
    )
    text = (
        "The hamlet has produced Alpha Onefoot, Bravo Twostep, and Charlie "
        "Threejump in recent years. Their olympic medals decorate the town hall."
    )
    result = asyncio.run(layer.scan_broadcast(text))
    assert result.decision == "aggregate"
    # The aggregate phrase replaces the list.
    assert "Olympians from this town" in result.redacted_message
    assert "Alpha" not in result.redacted_message
    assert "Bravo" not in result.redacted_message
    assert "Charlie" not in result.redacted_message
    assert result.log.small_aggregates >= 1


def test_small_aggregate_only_two_names_passes_through():
    """Two names — too few for the aggregate pattern; falls back to direct redact."""
    rows = _make_fixture_rows(
        600,
        seeds=[
            {
                "full_name": "Alpha Onefoot",
                "first_name": "Alpha",
                "last_name": "Onefoot",
                "known_variants": [],
            },
            {
                "full_name": "Bravo Twostep",
                "first_name": "Bravo",
                "last_name": "Twostep",
                "known_variants": [],
            },
        ],
    )
    fake_client = _FakeFlashLiteClient(responses=[("[]", None)])
    layer = NilRedactionLayer(
        rows=rows, min_rows=500, flash_lite_client=fake_client
    )
    text = (
        "The hamlet has produced Alpha Onefoot and Bravo Twostep in recent "
        "years. Their olympic medals decorate the town hall through which "
        "kids walk every morning to school."
    )
    result = asyncio.run(layer.scan_broadcast(text))
    # Two names trip direct-match redact, not the aggregate pattern.
    assert result.decision == "redact"
    assert result.log.small_aggregates == 0


# --- Audit log entries -------------------------------------------------------


def test_audit_log_records_disambiguation_rejections():
    """Rejected matches show up in the log counters.

    Note: the pure-Python automaton fallback does its own word-boundary
    filtering during matching, so substring rejections inside longer
    words are caught at the backend level. The disambiguation pass adds
    UNIFORM coverage when the rs / pyahocorasick backends emit raw
    substring matches. This test exercises rejections that the
    disambiguation pass sees regardless of backend.
    """
    rows = _make_fixture_rows(
        600,
        seeds=[
            # 2-char short token, whole-word in input → caught by min-length.
            {"full_name": "Mo", "first_name": "Mo", "last_name": "", "known_variants": []},
            # Common-name needle, no sport context → rejected by context check.
            {"full_name": "Sarah", "first_name": "Sarah", "last_name": "", "known_variants": []},
        ],
    )
    layer = NilRedactionLayer(rows=rows, min_rows=500)
    # 'Mo' as a whole word triggers length rejection; 'Sarah' as a whole
    # word with no sport context triggers context rejection.
    result = layer.scan_wire("Mo dropped by Sarah's diner on Main Street today")
    assert result.decision == "pass", (
        f"unexpected redact: {result.redacted_message}"
    )
    # 'Mo' is 2 chars — rejected on length.
    assert result.log.rejected_short >= 1
    # 'Sarah' is on the common-name list and there's no sport context in
    # the surrounding 50-char window — rejected on context.
    assert result.log.rejected_no_context >= 1


def test_audit_log_records_near_id_check_outcome():
    """Broadcast scan log records the near-id high-confidence count."""
    rows = _make_fixture_rows(600)
    finding = (
        '[{"sentence": "x", "identification_basis": "sport+year", '
        '"confidence_0_to_1": 0.85}]'
    )
    fake_client = _FakeFlashLiteClient(responses=[(finding, None)])
    layer = NilRedactionLayer(
        rows=rows, min_rows=500, flash_lite_client=fake_client
    )
    text = (
        "The town's small adaptive sport program has been a regional "
        "pipeline for two decades. The training pool is a converted "
        "community center. Each cohort produces a paralympian."
    )
    result = asyncio.run(layer.scan_broadcast(text))
    assert result.log.near_identifications == 1


# --- Surface gating ----------------------------------------------------------


def test_scan_wire_synchronous():
    """`scan_wire(surface='wire')` is a sync method — no await needed."""
    rows = _make_fixture_rows(600)
    layer = NilRedactionLayer(rows=rows, min_rows=500)
    # Calling without await works (returns a WireScanResult, not a coroutine).
    result = layer.scan_wire("a quiet town in the valley", surface="wire")
    assert result.decision == "pass"


def test_scan_broadcast_async():
    """`scan_broadcast` is `async` — calling it returns a coroutine."""
    rows = _make_fixture_rows(600)
    fake_client = _FakeFlashLiteClient(responses=[("[]", None)])
    layer = NilRedactionLayer(
        rows=rows, min_rows=500, flash_lite_client=fake_client
    )
    coro = layer.scan_broadcast(
        "the town has a small community gym and a wrestling pipeline that has "
        "produced two olympians since 1976."
    )
    # It's a coroutine — must be awaited / run.
    import inspect
    assert inspect.iscoroutine(coro)
    result = asyncio.run(coro)
    assert result.decision == "pass"


def test_scan_broadcast_runs_full_pipeline():
    """`scan_broadcast` must call Flash-Lite when the gating conditions hold."""
    rows = _make_fixture_rows(600)
    fake_client = _FakeFlashLiteClient(responses=[("[]", None)])
    layer = NilRedactionLayer(
        rows=rows, min_rows=500, flash_lite_client=fake_client
    )
    text = (
        "The town's wrestling program has produced four olympians since 1972. "
        "Their training facility is a converted high school gym in the eastern "
        "valley, where successive generations have built a regional pipeline."
    )
    asyncio.run(layer.scan_broadcast(text))
    assert len(fake_client.calls) == 1


def test_scan_wire_skips_near_id_and_aggregate():
    """Wire surface must NOT trigger the broadcast-only checks even when
    the text would qualify."""
    rows = _make_fixture_rows(
        600,
        seeds=[
            {"full_name": "Alpha Onefoot", "first_name": "Alpha", "last_name": "Onefoot", "known_variants": []},
            {"full_name": "Bravo Twostep", "first_name": "Bravo", "last_name": "Twostep", "known_variants": []},
            {"full_name": "Charlie Threejump", "first_name": "Charlie", "last_name": "Threejump", "known_variants": []},
        ],
    )
    fake_client = _FakeFlashLiteClient(responses=[])  # would error if called
    layer = NilRedactionLayer(
        rows=rows, min_rows=500, flash_lite_client=fake_client
    )
    text = (
        "The hamlet has produced Alpha Onefoot, Bravo Twostep, and Charlie "
        "Threejump in recent years. Their medals decorate the town hall."
    )
    result = layer.scan_wire(text, surface="wire")
    # Wire never aggregates — direct-match redact only.
    assert result.decision == "redact"
    assert fake_client.calls == []
    # Aggregate flag stays at zero on the wire path.
    assert result.log.aggregations_applied == 0
    assert result.log.small_aggregates == 0


# --- Performance + correctness -----------------------------------------------


def test_scan_wire_handles_8000_char_text():
    """Long Storyteller body — direct-match scan is fast (sub-50ms target)."""
    import time as _time
    rows = _make_fixture_rows(600)
    layer = NilRedactionLayer(rows=rows, min_rows=500)
    body = " ".join(["a quiet town in the valley with a community gym"] * 200)
    assert len(body) > 8000
    t0 = _time.perf_counter()
    result = layer.scan_wire(body, surface="wire")
    elapsed_ms = (_time.perf_counter() - t0) * 1000
    assert result.decision == "pass"
    # Sub-50ms target for the sync direct-match path. Pure-Python
    # automaton on this input on a dev machine sees ~1-5ms; we leave room.
    assert elapsed_ms < 100, f"scan_wire took {elapsed_ms:.1f}ms"


def test_decision_redact_rewrites_in_order_no_overlap():
    """Multiple distinct matches in one body all get rewritten, in-order, no overlap."""
    rows = _make_fixture_rows(
        600,
        seeds=[
            {"full_name": "Diego Maradona", "first_name": "Diego", "last_name": "Maradona", "known_variants": []},
            {"full_name": "Roger Federer", "first_name": "Roger", "last_name": "Federer", "known_variants": []},
        ],
    )
    layer = NilRedactionLayer(rows=rows, min_rows=500)
    text = "Diego Maradona played and Roger Federer played later"
    result = layer.scan_wire(text, surface="wire")
    assert result.decision == "redact"
    assert "Diego" not in result.redacted_message
    assert "Maradona" not in result.redacted_message
    assert "Roger" not in result.redacted_message
    assert "Federer" not in result.redacted_message
    # Two distinct full-name matches; counters reflect.
    assert result.log.direct_matches_redacted >= 2
