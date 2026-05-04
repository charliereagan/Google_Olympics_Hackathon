"""Day-2 end-to-end integration test (Editor -> Wire).

Per plan §F + §H step 13. Boots a stripped runtime against the Firestore
emulator and asserts:

  - >=3 wire_events documents persisted.
  - All contain `nil_redaction_log` field.
  - None contain the test fixture's redacted name in `message`.
  - All have `mode='live'` and `compression_factor=1.0`.

The test SKIPS cleanly if:
  - The Firestore emulator isn't running (FIRESTORE_EMULATOR_HOST unset).
  - `google.cloud.firestore` is not importable.

This is intentional — the unit-test suite is the primary correctness signal
for Day 2; the integration test is the lap-around-the-track confidence check
once the dev loop is up.

How to run locally:
  gcloud emulators firestore start --host-port=localhost:8087 &
  export FIRESTORE_EMULATOR_HOST=localhost:8087
  pytest tests/integration/test_editor_to_wire_e2e.py -v
"""

from __future__ import annotations

import os
from typing import Any

import pytest

EMULATOR_ENV = "FIRESTORE_EMULATOR_HOST"


def _emulator_running() -> bool:
    if not os.environ.get(EMULATOR_ENV):
        return False
    try:
        import google.cloud.firestore  # type: ignore[import-untyped]  # noqa: F401
    except ImportError:
        return False
    return True


pytestmark = pytest.mark.skipif(
    not _emulator_running(),
    reason=(
        "Firestore emulator not detected (set FIRESTORE_EMULATOR_HOST and "
        "ensure google.cloud.firestore is installed). "
        "See module docstring for setup."
    ),
)


@pytest.mark.asyncio
async def test_editor_to_wire_three_events_persist_with_redaction_log(tmp_path):
    """One pass: Editor emits 3+ Wire events; all NIL-scanned + persisted."""
    from google.cloud import firestore  # type: ignore[import-untyped]

    from agents.publish_gate.nil_redaction_layer_stub import NilRedactionLayer
    from agents.wire.emit import WireEmitter

    # 600-row fixture (synthetic + non-Team-USA names; see test_nil_redaction_layer_stub.py).
    rows: list[dict] = []
    rows.extend([
        {"full_name": "Pelé", "first_name": "Pelé", "last_name": "", "known_variants": []},
        {"full_name": "Diego Maradona", "first_name": "Diego", "last_name": "Maradona", "known_variants": []},
    ])
    while len(rows) < 600:
        i = len(rows)
        rows.append(
            {
                "full_name": f"Synthetic Person {i}",
                "first_name": f"Synthetic{i}",
                "last_name": f"Person{i}",
                "known_variants": [],
            }
        )

    nil_layer = NilRedactionLayer(rows=rows, min_rows=500)
    fs = firestore.AsyncClient()
    emitter = WireEmitter(fs, nil_layer)

    # Three events: one clean, one redacted, one with story_unit_id.
    ids: list[str] = []
    ids.append(await emitter.emit({"agent": "editor", "message": "going with this place", "message_type": "decision"}))
    ids.append(await emitter.emit({"agent": "scout_desk", "sub_agent": "hometown", "message": "Diego Maradona played", "message_type": "thinking"}))
    ids.append(await emitter.emit({"agent": "investigator", "message": "pulling sources", "message_type": "thinking", "story_unit_id": "us-ia-mt-pleasant"}))

    assert len(ids) == 3 and all(i for i in ids)

    # Read back from Firestore.
    docs = []
    async for snap in fs.collection("wire_events").stream():
        d = snap.to_dict()
        if snap.id in ids:
            docs.append(d)

    assert len(docs) >= 3
    for d in docs:
        assert "nil_redaction_log" in d, f"missing nil_redaction_log: {d}"
        assert d.get("mode") == "live"
        assert d.get("compression_factor") == 1.0
        # No raw fixture name should leak through.
        assert "Diego Maradona" not in (d.get("message") or "")
