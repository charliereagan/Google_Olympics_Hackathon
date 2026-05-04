"""Unit tests for `agents/narrator/tts_client.py`.

Uses `httpx.MockTransport` to stub the Vertex AI Gemini Flash TTS endpoint
without hitting the network. The client is constructed with an explicit
`http_client` and `credentials` so we don't need google-auth installed in
the test sandbox.
"""

from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import pytest

from agents.narrator.tts_client import (
    GeminiFlashTTSClient,
    TTSGenerationError,
    parse_l16_rate,
)


# -- Fakes --------------------------------------------------------------------


class _FakeCredentials:
    """Stand-in for `google.auth.credentials.Credentials`.

    The TTS client only reads `.token` and `.expiry`. `refresh(request)` is
    invoked through `asyncio.to_thread`; we make it a plain method that
    simply rotates the token. No real auth surface used.
    """

    def __init__(self, token: str = "fake-token") -> None:
        self.token = token
        self.expiry = datetime.now(timezone.utc) + timedelta(hours=1)
        self.refresh_count = 0

    def refresh(self, request: Any) -> None:  # noqa: D401
        self.refresh_count += 1


def _build_client(
    *, transport: httpx.MockTransport, project: str = "test-project"
) -> GeminiFlashTTSClient:
    return GeminiFlashTTSClient(
        project=project,
        location="global",
        http_client=httpx.AsyncClient(transport=transport),
        credentials=_FakeCredentials(),
    )


def _b64_audio(payload: bytes = b"\x00\x00\x01\x02\x03\x04\x05\x06") -> str:
    return base64.b64encode(payload).decode("ascii")


# -- Tests --------------------------------------------------------------------


@pytest.mark.asyncio
async def test_synthesize_calls_correct_url_and_body() -> None:
    """URL contains the project, location, model id; body is the verified
    Vertex AI shape (BUILD_SPEC §3.5 + tech_snapshot §3)."""
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "inlineData": {
                                        "mimeType": "audio/l16; rate=24000; channels=1",
                                        "data": _b64_audio(),
                                    }
                                }
                            ]
                        }
                    }
                ]
            },
        )

    client = _build_client(transport=httpx.MockTransport(handler))
    audio, mime = await client.synthesize("hello world", voice_name="Algenib")

    assert audio == b"\x00\x00\x01\x02\x03\x04\x05\x06"
    assert mime.startswith("audio/l16")

    url = captured["url"]
    assert "aiplatform.googleapis.com" in url
    assert "v1beta1" in url
    assert "test-project" in url
    assert "/locations/global/" in url
    assert "gemini-3.1-flash-tts-preview:generateContent" in url

    body = captured["body"]
    assert body["contents"][0]["parts"][0]["text"] == "hello world"
    assert body["generationConfig"]["responseModalities"] == ["AUDIO"]
    assert (
        body["generationConfig"]["speechConfig"]["voiceConfig"][
            "prebuiltVoiceConfig"
        ]["voiceName"]
        == "Algenib"
    )

    headers = captured["headers"]
    assert headers["authorization"] == "Bearer fake-token"
    assert headers["x-goog-user-project"] == "test-project"


@pytest.mark.asyncio
async def test_synthesize_extracts_inline_data_audio() -> None:
    """Decode the base64 inlineData and return raw bytes + mime."""
    expected = b"raw-pcm-bytes"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {"text": "ignored"},
                                {
                                    "inlineData": {
                                        "mimeType": "audio/l16; rate=24000",
                                        "data": _b64_audio(expected),
                                    }
                                },
                            ]
                        }
                    }
                ]
            },
        )

    client = _build_client(transport=httpx.MockTransport(handler))
    audio, mime = await client.synthesize("test", voice_name="Fenrir")
    assert audio == expected
    assert "audio/l16" in mime


@pytest.mark.asyncio
async def test_synthesize_raises_on_http_error() -> None:
    """A 500 response raises TTSGenerationError with status_code populated."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="internal error: cluster overloaded")

    client = _build_client(transport=httpx.MockTransport(handler))
    with pytest.raises(TTSGenerationError) as ei:
        await client.synthesize("test", voice_name="Algenib")
    assert ei.value.status_code == 500
    assert "TTS HTTP 500" in str(ei.value)


@pytest.mark.asyncio
async def test_synthesize_uses_voice_name_in_speechconfig() -> None:
    """Voice name flows through to `speechConfig.voiceConfig.prebuiltVoiceConfig.voiceName`."""
    captured_voice: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        captured_voice.append(
            body["generationConfig"]["speechConfig"]["voiceConfig"][
                "prebuiltVoiceConfig"
            ]["voiceName"]
        )
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "inlineData": {
                                        "mimeType": "audio/l16; rate=24000",
                                        "data": _b64_audio(),
                                    }
                                }
                            ]
                        }
                    }
                ]
            },
        )

    client = _build_client(transport=httpx.MockTransport(handler))
    await client.synthesize("a", voice_name="Algenib")
    await client.synthesize("b", voice_name="Fenrir")
    assert captured_voice == ["Algenib", "Fenrir"]


@pytest.mark.asyncio
async def test_synthesize_raises_when_no_audio_in_response() -> None:
    """Response without inlineData audio raises a clear error."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "candidates": [{"content": {"parts": [{"text": "no audio here"}]}}]
            },
        )

    client = _build_client(transport=httpx.MockTransport(handler))
    with pytest.raises(TTSGenerationError) as ei:
        await client.synthesize("t", voice_name="Algenib")
    assert "no inlineData audio" in str(ei.value)


@pytest.mark.asyncio
async def test_synthesize_forwards_speaking_rate_when_provided() -> None:
    """Optional `speaking_rate` lands as `speechConfig.speakingRate`."""
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "inlineData": {
                                        "mimeType": "audio/l16; rate=24000",
                                        "data": _b64_audio(),
                                    }
                                }
                            ]
                        }
                    }
                ]
            },
        )

    client = _build_client(transport=httpx.MockTransport(handler))
    await client.synthesize("x", voice_name="Algenib", speaking_rate=0.85)
    assert captured["body"]["generationConfig"]["speechConfig"]["speakingRate"] == 0.85


# -- Helpers ------------------------------------------------------------------


def test_parse_l16_rate_extracts_rate() -> None:
    assert parse_l16_rate("audio/l16; rate=24000; channels=1") == 24000
    assert parse_l16_rate("audio/l16; rate=16000") == 16000


def test_parse_l16_rate_returns_default_when_missing() -> None:
    assert parse_l16_rate("audio/wav") == 24000
    assert parse_l16_rate("", default=22050) == 22050
