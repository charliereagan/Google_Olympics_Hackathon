"""Smoke tests for `scripts/probe_full_chain.py`.

The probe itself runs against live GCP and costs money — these tests
exercise the *plumbing* (argparse, httpx call shape, Firestore poll
timeout) without any network or cloud calls.
"""

from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path
from unittest import mock

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
PROBE_SCRIPT = SCRIPTS_DIR / "probe_full_chain.py"


def _load_probe_module():
    spec = importlib.util.spec_from_file_location("probe_full_chain", PROBE_SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


# --- 1. argparse ------------------------------------------------------------


def test_argparse_accepts_required_flags():
    """All advertised flags parse cleanly with reasonable defaults."""
    probe = _load_probe_module()
    args = probe._parse_args(
        [
            "--url",
            "http://localhost:9999",
            "--prompt",
            "test prompt",
            "--timeout-min",
            "8",
            "--dry-run",
            "--cleanup",
            "--audio-bucket",
            "my-bucket",
            "--compression-factor",
            "0.25",
        ]
    )
    assert args.url == "http://localhost:9999"
    assert args.prompt == "test prompt"
    assert args.timeout_min == 8
    assert args.dry_run is True
    assert args.cleanup is True
    assert args.audio_bucket == "my-bucket"
    assert args.compression_factor == 0.25


def test_argparse_defaults():
    """Zero-arg invocation yields sane defaults."""
    probe = _load_probe_module()
    args = probe._parse_args([])
    assert args.url == probe.DEFAULT_URL
    assert args.prompt == probe.DEFAULT_PROMPT
    assert args.timeout_min == probe.DEFAULT_TIMEOUT_MIN
    assert args.dry_run is False
    assert args.cleanup is False
    assert args.audio_bucket == probe.DEFAULT_AUDIO_BUCKET
    assert args.compression_factor == 1.0


# --- 2. POST /api/investigate ----------------------------------------------


@pytest.mark.asyncio
async def test_post_investigate_returns_investigation_id():
    """The probe's POST helper extracts the investigation_id from a 202."""
    probe = _load_probe_module()

    fake_response = mock.Mock()
    fake_response.status_code = 202
    fake_response.json = mock.Mock(
        return_value={
            "investigation_id": "inv-test-abc123",
            "status": "started",
        }
    )
    fake_response.text = "{}"

    fake_client = mock.AsyncMock()
    fake_client.post = mock.AsyncMock(return_value=fake_response)
    fake_client.__aenter__ = mock.AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = mock.AsyncMock(return_value=False)

    fake_httpx = mock.MagicMock()
    fake_httpx.AsyncClient = mock.MagicMock(return_value=fake_client)

    # ConnectError / HTTPError must still be classes for `except` clauses.
    class _Stub(Exception):
        pass

    fake_httpx.ConnectError = _Stub
    fake_httpx.HTTPError = _Stub

    with mock.patch.dict("sys.modules", {"httpx": fake_httpx}):
        body = await probe.post_investigate(
            "http://localhost:8080",
            "test prompt",
        )

    assert body["investigation_id"] == "inv-test-abc123"
    fake_client.post.assert_awaited_once()
    call_args = fake_client.post.await_args
    assert call_args.args[0] == "http://localhost:8080/api/investigate"
    assert call_args.kwargs["json"]["prompt"] == "test prompt"
    assert call_args.kwargs["json"]["compression_factor"] == 1.0
    assert call_args.kwargs["json"]["source"] == "probe"


@pytest.mark.asyncio
async def test_post_investigate_raises_on_5xx():
    """A non-2xx response surfaces as RuntimeError (probe exit code 2)."""
    probe = _load_probe_module()

    fake_response = mock.Mock()
    fake_response.status_code = 500
    fake_response.text = "internal server error"
    fake_response.json = mock.Mock(side_effect=ValueError("not json"))

    fake_client = mock.AsyncMock()
    fake_client.post = mock.AsyncMock(return_value=fake_response)
    fake_client.__aenter__ = mock.AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = mock.AsyncMock(return_value=False)

    fake_httpx = mock.MagicMock()
    fake_httpx.AsyncClient = mock.MagicMock(return_value=fake_client)

    class _Stub(Exception):
        pass

    fake_httpx.ConnectError = _Stub
    fake_httpx.HTTPError = _Stub

    with mock.patch.dict("sys.modules", {"httpx": fake_httpx}):
        with pytest.raises(RuntimeError, match="status=500"):
            await probe.post_investigate("http://localhost:8080", "test prompt")


@pytest.mark.asyncio
async def test_post_investigate_raises_on_connect_error():
    """A connection failure raises ConnectionError (probe exit code 3)."""
    probe = _load_probe_module()

    class _Stub(Exception):
        pass

    fake_httpx = mock.MagicMock()

    fake_client = mock.AsyncMock()
    fake_client.post = mock.AsyncMock(side_effect=_Stub("could not connect"))
    fake_client.__aenter__ = mock.AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = mock.AsyncMock(return_value=False)

    fake_httpx.AsyncClient = mock.MagicMock(return_value=fake_client)
    fake_httpx.ConnectError = _Stub
    fake_httpx.HTTPError = _Stub

    with mock.patch.dict("sys.modules", {"httpx": fake_httpx}):
        with pytest.raises(ConnectionError, match="not reachable"):
            await probe.post_investigate(
                "http://nonexistent.example", "test prompt"
            )


# --- 3. poll_for_doc -------------------------------------------------------


@pytest.mark.asyncio
async def test_poll_for_doc_returns_false_on_timeout():
    """Polling against an empty Firestore stub times out cleanly."""
    probe = _load_probe_module()

    # `_query_first_doc` always returns None — no doc ever appears.
    started = time.monotonic()
    with mock.patch.object(probe, "_query_first_doc", return_value=None):
        found, doc, elapsed = await probe.poll_for_doc(
            fs=mock.Mock(),  # never inspected
            collection="lead_reports",
            investigation_id="inv-nothere",
            timeout_s=1,
            started_at=started,
            poll_interval_s=1,  # one short interval is enough
        )
    assert found is False
    assert doc is None
    assert elapsed >= 1.0


@pytest.mark.asyncio
async def test_poll_for_doc_returns_true_when_doc_appears():
    """Polling returns the first-found doc and an elapsed measurement."""
    probe = _load_probe_module()

    # First call returns None; second call returns a doc.
    call_n = {"n": 0}

    def _fake_query(fs, coll, *, investigation_id):
        call_n["n"] += 1
        if call_n["n"] == 1:
            return None
        return {"id": "found-it", "investigation_id": investigation_id}

    started = time.monotonic()
    with mock.patch.object(probe, "_query_first_doc", side_effect=_fake_query):
        found, doc, elapsed = await probe.poll_for_doc(
            fs=mock.Mock(),
            collection="lead_reports",
            investigation_id="inv-test",
            timeout_s=10,
            started_at=started,
            poll_interval_s=1,
        )
    assert found is True
    assert doc is not None
    assert doc["id"] == "found-it"
    assert elapsed >= 1.0
