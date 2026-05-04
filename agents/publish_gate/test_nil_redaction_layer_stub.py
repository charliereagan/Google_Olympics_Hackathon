"""Unit tests for the NIL Redaction Layer (Day-2 stub).

Covers plan §F:
  - bootstrap raises RegistryTooSmallError on < min_rows.
  - Unicode normalization: 'Pelé' needle matches 'Pele' input.
  - Direct match → decision='redact' with the message rewritten in place.
  - 'Pass' on no-match.

Test fixtures are synthetic non-Team-USA names (e.g., 'Pelé', 'Diego Maradona')
plus invented placeholder strings — kept disjoint from the production
athlete_registry per project convention (PROJECT_BRIEF §5).
"""

from __future__ import annotations

import pytest

from agents.publish_gate.nil_redaction_layer_stub import (
    NilRedactionLayer,
    RegistryTooSmallError,
)


def _make_fixture_rows(n: int) -> list[dict]:
    """Build a fixture of n synthetic registry rows.

    Uses non-Team-USA names (so no Team-USA NIL is in our test fixtures, per
    PROJECT_BRIEF §5) plus generated 'Athlete N' placeholders to hit the
    min_rows threshold.
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
    # Pad to n with synthetic names.
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


def _stub_fetcher_returning(rows: list[dict]):
    def _f(_bq, _dataset, _table):
        return rows
    return _f


# --- bootstrap fail-closed ----------------------------------------------------


def test_bootstrap_asserts_min_rows():
    """Registry below the threshold raises RegistryTooSmallError."""
    too_few = _make_fixture_rows(200)
    with pytest.raises(RegistryTooSmallError):
        NilRedactionLayer.bootstrap(
            bq_client=object(),
            dataset="x",
            row_fetcher=_stub_fetcher_returning(too_few),
        )


def test_bootstrap_succeeds_at_threshold():
    rows = _make_fixture_rows(600)
    layer = NilRedactionLayer.bootstrap(
        bq_client=object(),
        dataset="x",
        row_fetcher=_stub_fetcher_returning(rows),
    )
    assert layer.is_loaded
    assert layer.registry_size == 600


def test_direct_constructor_below_threshold_raises():
    with pytest.raises(RegistryTooSmallError):
        NilRedactionLayer(rows=_make_fixture_rows(10), min_rows=500)


# --- scan_wire ---------------------------------------------------------------


@pytest.fixture
def loaded_layer() -> NilRedactionLayer:
    return NilRedactionLayer(rows=_make_fixture_rows(600), min_rows=500)


def test_scan_pass_on_no_match(loaded_layer: NilRedactionLayer):
    result = loaded_layer.scan_wire("the small town built a community gym in 1976")
    assert result.decision == "pass"
    assert result.redacted_message == "the small town built a community gym in 1976"
    assert result.log.direct_matches_redacted == 0


def test_scan_redacts_direct_match(loaded_layer: NilRedactionLayer):
    """A direct hit redacts inline AND populates the log."""
    text = "Diego Maradona played"
    result = loaded_layer.scan_wire(text)
    assert result.decision == "redact"
    assert "[redacted]" in result.redacted_message
    assert "Diego Maradona" not in result.redacted_message
    assert result.log.direct_matches_redacted >= 1


def test_unicode_normalization_pele_pele(loaded_layer: NilRedactionLayer):
    """Needle 'Pelé' (with diacritic) must match 'Pele' input (without).

    This is the worked example in plan §D test fixtures.
    """
    result = loaded_layer.scan_wire("Pele scored a goal")
    assert result.decision == "redact"
    assert "Pele" not in result.redacted_message
    assert "[redacted]" in result.redacted_message


def test_unloaded_layer_raises_on_scan():
    """A Layer constructed with no rows refuses to scan."""
    # We can't build an unloaded layer via the public constructor (it would
    # raise), so we simulate the internal state.
    layer = NilRedactionLayer(rows=_make_fixture_rows(500), min_rows=500)
    layer._automaton = None  # type: ignore[attr-defined]
    with pytest.raises(RuntimeError):
        layer.scan_wire("anything")


def test_word_boundary_no_false_match_inside_token(loaded_layer: NilRedactionLayer):
    """Needle 'Pelé' should not match 'Pelican' (substring within longer word)."""
    result = loaded_layer.scan_wire("the pelican gymnasium")
    assert result.decision == "pass", f"unexpected match in: {result.redacted_message}"
