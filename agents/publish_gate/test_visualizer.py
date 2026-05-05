"""Unit tests for the Visualizer tool.

The Vertex AI image-gen endpoint and the GCS bucket are both mocked at
the boundary so unit tests don't hit live services. The patterns mirror
`agents/narrator/test_tts_client.py` (httpx mock) and
`agents/narrator/test_agent.py` (storage stub).
"""

from __future__ import annotations

import asyncio
import base64
from typing import Any
from unittest import mock

import pytest

from agents.publish_gate.visualizer import (
    GeminiImageGenError,
    Visualizer,
)


# --- Fakes -------------------------------------------------------------------


class _FakeCredentials:
    """Stub that satisfies the ADC token contract without google-auth."""

    def __init__(self, token: str = "fake-token") -> None:
        self.token = token
        self.expiry = None

    def refresh(self, _request: Any) -> None:
        # No-op; tests pre-populate `.token`.
        return None


class _FakeBlob:
    def __init__(self, name: str) -> None:
        self.name = name
        self.uploaded: bytes | None = None
        self.content_type: str | None = None
        self._exists = False

    def upload_from_string(self, data: bytes, content_type: str = "") -> None:
        self.uploaded = data
        self.content_type = content_type

    def exists(self) -> bool:
        return self._exists


class _FakeBucket:
    def __init__(self, name: str, *, prefilled_blobs: set[str] | None = None) -> None:
        self.name = name
        self.blobs: dict[str, _FakeBlob] = {}
        self._prefilled = prefilled_blobs or set()

    def blob(self, blob_name: str) -> _FakeBlob:
        b = self.blobs.get(blob_name)
        if b is None:
            b = _FakeBlob(blob_name)
            if blob_name in self._prefilled:
                b._exists = True
            self.blobs[blob_name] = b
        return b


class _FakeStorageClient:
    def __init__(self, *, prefilled: dict[str, set[str]] | None = None) -> None:
        # Map: bucket_name -> set of blob_names that exist.
        self._prefilled = prefilled or {}
        self.buckets: dict[str, _FakeBucket] = {}

    def bucket(self, bucket_name: str) -> _FakeBucket:
        bucket = self.buckets.get(bucket_name)
        if bucket is None:
            bucket = _FakeBucket(
                bucket_name,
                prefilled_blobs=self._prefilled.get(bucket_name, set()),
            )
            self.buckets[bucket_name] = bucket
        return bucket


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.text = "" if payload is None else "ok"

    def json(self) -> dict:
        return self._payload


class _FakeHttpClient:
    """Records POST calls; returns canned responses."""

    def __init__(
        self,
        *,
        responses: list[_FakeResponse] | None = None,
    ) -> None:
        self.calls: list[dict] = []
        self._responses = list(responses or [])

    async def post(self, url: str, *, headers: dict, json: dict, timeout: float = 60.0):
        self.calls.append(
            {"url": url, "headers": dict(headers), "json": dict(json), "timeout": timeout}
        )
        if not self._responses:
            return _FakeResponse(200, _ok_payload())
        return self._responses.pop(0)

    async def aclose(self) -> None:
        return None


def _ok_payload(mime: str = "image/png", data_bytes: bytes = b"\x89PNG\r\n\x1a\n_test_") -> dict:
    """Successful Vertex AI image-gen response shape (tech_snapshot §3)."""
    return {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "inlineData": {
                                "mimeType": mime,
                                "data": base64.b64encode(data_bytes).decode("ascii"),
                            }
                        }
                    ]
                }
            }
        ]
    }


# --- Helpers -----------------------------------------------------------------


def _build_visualizer(
    *,
    http_client: Any | None = None,
    storage: Any | None = None,
    cost_counter: Any | None = None,
    bucket_name: str = "storytellers-room-hero-images",
    fallback_bucket: str = "storytellers-room-fallback-heroes",
    max_regenerations: int = 3,
) -> Visualizer:
    return Visualizer(
        project="test-project",
        location="global",
        bucket_name=bucket_name,
        fallback_bucket=fallback_bucket,
        cost_counter=cost_counter,
        max_regenerations=max_regenerations,
        storage=storage if storage is not None else _FakeStorageClient(),
        http_client=http_client if http_client is not None else _FakeHttpClient(),
        credentials=_FakeCredentials(),
    )


# --- Tests -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_hero_calls_correct_url_and_body():
    """Hero generation hits the v1beta1 endpoint with responseModalities=['IMAGE']."""
    http = _FakeHttpClient(responses=[_FakeResponse(200, _ok_payload())])
    storage = _FakeStorageClient()
    viz = _build_visualizer(http_client=http, storage=storage)

    url = await viz.generate_hero(
        place_type="empty community gym at dusk",
        environmental_cue="small Iowa town",
        story_unit_id="us-ia-mt-pleasant",
    )

    assert url.startswith("gs://storytellers-room-hero-images/")
    assert "us-ia-mt-pleasant/hero.png" in url

    # Endpoint shape.
    assert len(http.calls) == 1
    call = http.calls[0]
    assert call["url"] == (
        "https://aiplatform.googleapis.com/v1beta1/projects/test-project/"
        "locations/global/publishers/google/models/"
        "gemini-3-pro-image-preview:generateContent"
    )
    # Body shape.
    body = call["json"]
    assert body["generationConfig"] == {"responseModalities": ["IMAGE"]}
    assert body["contents"][0]["role"] == "user"
    prompt_text = body["contents"][0]["parts"][0]["text"]
    # The hero prompt template MUST contain CONSTITUTION Law 6 negative phrasing.
    assert "NO PEOPLE" in prompt_text
    assert "NO Olympic rings" in prompt_text
    assert "NO photorealistic faces" in prompt_text
    assert "empty community gym at dusk" in prompt_text
    # Headers carry the bearer token + per-project header.
    headers = call["headers"]
    assert headers["Authorization"] == "Bearer fake-token"
    assert headers["X-Goog-User-Project"] == "test-project"


@pytest.mark.asyncio
async def test_generate_hero_uploads_to_gcs():
    """Hero generation writes the returned PNG bytes to the configured bucket."""
    expected_bytes = b"\x89PNG\r\n\x1a\nfake_pro_image"
    http = _FakeHttpClient(
        responses=[_FakeResponse(200, _ok_payload(data_bytes=expected_bytes))]
    )
    storage = _FakeStorageClient()
    viz = _build_visualizer(http_client=http, storage=storage)

    url = await viz.generate_hero(
        place_type="empty community gym at dusk",
        environmental_cue="rural Iowa",
        story_unit_id="us-ia-mt-pleasant",
    )

    assert url == (
        "gs://storytellers-room-hero-images/us-ia-mt-pleasant/hero.png"
    )
    bucket = storage.buckets["storytellers-room-hero-images"]
    blob = bucket.blobs["us-ia-mt-pleasant/hero.png"]
    assert blob.uploaded == expected_bytes
    assert blob.content_type == "image/png"


@pytest.mark.asyncio
async def test_generate_hero_uses_pro_image_model_id():
    """Hero MUST hit `gemini-3-pro-image-preview` (Nano Banana Pro)."""
    http = _FakeHttpClient(responses=[_FakeResponse(200, _ok_payload())])
    viz = _build_visualizer(http_client=http)

    await viz.generate_hero(
        place_type="empty gym",
        environmental_cue="rural town",
        story_unit_id="x",
    )
    assert "gemini-3-pro-image-preview" in http.calls[0]["url"]
    assert viz.hero_model == "gemini-3-pro-image-preview"


@pytest.mark.asyncio
async def test_generate_hometown_uses_flash_image_model_id():
    """Hometown panel MUST hit `gemini-3.1-flash-image-preview` (utility)."""
    http = _FakeHttpClient(responses=[_FakeResponse(200, _ok_payload())])
    viz = _build_visualizer(http_client=http)

    await viz.generate_hometown_panel(
        town_name="Mt Pleasant",
        state="Iowa",
        story_unit_id="us-ia-mt-pleasant",
    )
    assert "gemini-3.1-flash-image-preview" in http.calls[0]["url"]
    assert viz.utility_model == "gemini-3.1-flash-image-preview"

    # The hometown prompt template must NOT name any individual.
    prompt_text = http.calls[0]["json"]["contents"][0]["parts"][0]["text"]
    assert "NO people" in prompt_text or "NO PEOPLE" in prompt_text
    assert "Mt Pleasant" in prompt_text


@pytest.mark.asyncio
async def test_generate_assets_runs_three_in_parallel():
    """`generate_assets` calls all three single-asset methods concurrently."""
    viz = _build_visualizer()

    call_log: list[str] = []

    async def _hero(**_kwargs):
        call_log.append("hero_start")
        await asyncio.sleep(0)
        call_log.append("hero_done")
        return "gs://hero-bucket/x/hero.png"

    async def _hometown(**_kwargs):
        call_log.append("hometown_start")
        await asyncio.sleep(0)
        call_log.append("hometown_done")
        return "gs://hero-bucket/x/hometown.png"

    async def _echo(**_kwargs):
        call_log.append("echo_start")
        await asyncio.sleep(0)
        call_log.append("echo_done")
        return "gs://hero-bucket/x/echo.png"

    with mock.patch.object(viz, "generate_hero", side_effect=_hero) as h, \
         mock.patch.object(viz, "generate_hometown_panel", side_effect=_hometown) as ht, \
         mock.patch.object(viz, "generate_historical_echo", side_effect=_echo) as e:

        story_draft = {
            "story_unit_id": "us-ia-mt-pleasant",
            "place_name": "Mt Pleasant",
            "state": "Iowa",
            "modern_pattern": "regional sport pipeline",
            "era_year": 1960,
            "era_sport": "track and field",
            "environmental_cue": "rural Iowa",
            "hero_place_type": "empty community gym at dusk",
        }
        result = await viz.generate_assets(
            story_draft=story_draft,
            investigation_packet={},
        )

    # All three were invoked exactly once.
    assert h.call_count == 1
    assert ht.call_count == 1
    assert e.call_count == 1

    # Returned dict carries every URL key.
    assert result["hero_url"] == "gs://hero-bucket/x/hero.png"
    assert result["hometown_panel_url"] == "gs://hero-bucket/x/hometown.png"
    assert result["echo_panel_url"] == "gs://hero-bucket/x/echo.png"
    assert result["regenerations"] == 0

    # Concurrency: all three started before any completed (asyncio.gather
    # interleaves at the first `await`).
    starts = [s for s in call_log if s.endswith("_start")]
    dones = [s for s in call_log if s.endswith("_done")]
    assert starts.index("hero_start") < call_log.index("hero_done")
    assert starts.index("hometown_start") < call_log.index("hometown_done")
    assert len(starts) == 3 and len(dones) == 3


@pytest.mark.asyncio
async def test_fallback_hero_returns_default_when_story_unit_fallback_absent():
    """`fallback_hero` returns `default.png` when no anchor-specific blob exists."""
    storage = _FakeStorageClient(
        prefilled={
            "storytellers-room-fallback-heroes": {"default.png"},
        }
    )
    viz = _build_visualizer(storage=storage)

    url = await viz.fallback_hero(story_unit_id="us-ia-no-such-anchor")
    assert url == "gs://storytellers-room-fallback-heroes/default.png"


@pytest.mark.asyncio
async def test_fallback_hero_prefers_anchor_specific_when_present():
    """When the anchor-specific blob exists, it wins over default.png."""
    storage = _FakeStorageClient(
        prefilled={
            "storytellers-room-fallback-heroes": {
                "us-ia-mt-pleasant.png",
                "default.png",
            }
        }
    )
    viz = _build_visualizer(storage=storage)
    url = await viz.fallback_hero(story_unit_id="us-ia-mt-pleasant")
    assert url == "gs://storytellers-room-fallback-heroes/us-ia-mt-pleasant.png"


@pytest.mark.asyncio
async def test_generate_hero_increments_cost_counter_on_image_pro_axis():
    """Cost counter increments with axis='image_pro' + images=1 after success."""

    class _CostStub:
        def __init__(self) -> None:
            self.under_calls: list[dict] = []
            self.increment_calls: list[dict] = []

        async def assert_under_ceiling(self, *, axis: str, agent: str | None = None,
                                       sub_agent: str | None = None) -> None:
            self.under_calls.append({"axis": axis, "agent": agent})

        async def increment(self, **kwargs) -> None:
            self.increment_calls.append(kwargs)

    cost = _CostStub()
    http = _FakeHttpClient(responses=[_FakeResponse(200, _ok_payload())])
    viz = _build_visualizer(http_client=http, cost_counter=cost)

    await viz.generate_hero(
        place_type="empty gym",
        environmental_cue="rural town",
        story_unit_id="x",
    )

    # Pre-check fired on image_pro.
    assert cost.under_calls == [{"axis": "image_pro", "agent": "publish_gate"}]
    # Post-success increment carries images=1 + axis=image_pro.
    assert len(cost.increment_calls) == 1
    inc = cost.increment_calls[0]
    assert inc["axis"] == "image_pro"
    assert inc["images"] == 1
    assert inc["model"] == "gemini-3-pro-image-preview"


@pytest.mark.asyncio
async def test_generate_hero_raises_on_safety_filter_block():
    """A `finishReason: SAFETY` response surfaces as `GeminiImageGenError`."""
    blocked_payload = {
        "candidates": [
            {"finishReason": "IMAGE_SAFETY", "content": {"parts": []}}
        ]
    }
    http = _FakeHttpClient(responses=[_FakeResponse(200, blocked_payload)])
    viz = _build_visualizer(http_client=http)

    with pytest.raises(GeminiImageGenError) as ex:
        await viz.generate_hero(
            place_type="empty gym",
            environmental_cue="rural town",
            story_unit_id="x",
        )
    assert "blocked by safety filter" in str(ex.value).lower()


@pytest.mark.asyncio
async def test_stricter_level_appends_negative_phrasing_on_regeneration():
    """Higher `stricter_level` adds explicit re-rejection clauses to the prompt."""
    http = _FakeHttpClient(
        responses=[_FakeResponse(200, _ok_payload()) for _ in range(4)]
    )
    viz = _build_visualizer(http_client=http)

    for level in (0, 1, 2, 3):
        await viz.generate_hero(
            place_type="empty gym",
            environmental_cue="rural town",
            story_unit_id=f"x-{level}",
            stricter_level=level,
        )

    prompts = [
        c["json"]["contents"][0]["parts"][0]["text"] for c in http.calls
    ]
    # Level-0 baseline lacks the "previously rejected" clause.
    assert "previously rejected" not in prompts[0].lower()
    # Levels 1+ all include increasingly stringent negative phrasing.
    assert "rejected" in prompts[1].lower()
    assert "rejected twice" in prompts[2].lower()
    assert "final attempt" in prompts[3].lower()
