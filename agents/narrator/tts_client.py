"""Direct Vertex AI Gemini 3.1 Flash TTS client.

This is NOT an ADK agent — TTS is a deterministic synthesis call, not an
LLM-Runner pattern. Mirrors `scripts/list_tts_voices.py::tts_generate` but as
an async function so it integrates with the runtime's asyncio loop.

Endpoint shape (verified Day-1, tech_snapshot.md §3):
  POST https://aiplatform.googleapis.com/v1beta1/projects/{project}/locations/global/publishers/google/models/gemini-3.1-flash-tts-preview:generateContent
  body: {
    "contents": [{"role": "user", "parts": [{"text": "..."}]}],
    "generationConfig": {
      "responseModalities": ["AUDIO"],
      "speechConfig": {
        "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": "Algenib"}}
      }
    }
  }

Returns base64-encoded `audio/l16; rate=24000; channels=1` PCM in
`candidates[0].content.parts[*].inlineData.data`.

Auth: google.auth.default() + creds.refresh(...). The token is cached and
refreshed on `expiry` (best-effort — google-auth refresh handles this).

The client raises `TTSGenerationError` on any HTTP failure; the Narrator
handles retry policy.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import re
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


_AIPLATFORM_HOST = "https://aiplatform.googleapis.com"
_TTS_API_VERSION = "v1beta1"
_DEFAULT_MODEL = "gemini-3.1-flash-tts-preview"
_DEFAULT_LOCATION = "global"  # HOE-DEC-015: Gemini 3.x = global only.
_AUTH_SCOPE = "https://www.googleapis.com/auth/cloud-platform"


class TTSGenerationError(RuntimeError):
    """Raised on any HTTP failure while synthesizing audio.

    `status_code` is set when we got a response back; None on transport
    failure (timeout, DNS, etc.).
    """

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class GeminiFlashTTSClient:
    """Async HTTP client for the Vertex AI Gemini Flash TTS endpoint.

    The client is stateless except for an httpx connection pool + an access
    token cache. Construction cost is trivial; one client per runtime is fine.
    """

    def __init__(
        self,
        *,
        project: str,
        location: str = _DEFAULT_LOCATION,
        model_id: str = _DEFAULT_MODEL,
        clock: Any | None = None,
        http_client: Any | None = None,
        credentials: Any | None = None,
    ) -> None:
        self._project = project
        self._location = location
        self._model_id = model_id
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        # Optional pre-built httpx.AsyncClient (tests pass a mock-transport one).
        # When None, we lazily build one on first use — and hold a single
        # shared instance for the lifetime of the client.
        self._http: Any | None = http_client
        # Optional pre-built google.auth credentials (tests pass a fake).
        self._credentials: Any | None = credentials
        self._token: str | None = None
        self._token_expiry: datetime | None = None
        # Serialize token-refresh + lazy-http-build so concurrent callers
        # don't all kick off an auth round-trip.
        self._token_lock: asyncio.Lock = asyncio.Lock()

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def url(self) -> str:
        return (
            f"{_AIPLATFORM_HOST}/{_TTS_API_VERSION}/projects/{self._project}"
            f"/locations/{self._location}/publishers/google/models/"
            f"{self._model_id}:generateContent"
        )

    # -- Public synthesis API -------------------------------------------------

    async def synthesize(
        self,
        text: str,
        *,
        voice_name: str,
        speaking_rate: float | None = None,
        timeout_s: float = 30.0,
    ) -> tuple[bytes, str]:
        """Synthesize one chunk. Returns (audio_bytes, mime_type).

        Bytes are typically `audio/l16; rate=24000; channels=1` PCM. Caller is
        responsible for chunking + WAV-wrapping if needed.

        Args:
            text: the prompt text. May contain Gemini TTS inline tags like
                `[short pause]`, `[long pause]`, `[emphasis]` (BUILD_SPEC §3.5).
            voice_name: bare prebuilt voice name — `'Algenib'` or `'Fenrir'`
                per HOE-DEC-025. (Cloud TTS FQN form `'en-US-Chirp3-HD-Algenib'`
                is NOT used for Vertex AI invocation.)
            speaking_rate: optional scalar; included in the request body if
                provided. Note: BUILD_SPEC §5.6 says inline `[slow]` /
                `[pause=N]` tags supersede the legacy speaking_rate knob for
                Gemini 3.1 Flash TTS, but we forward it so callers can probe
                whether the API still honors it.
            timeout_s: per-call request timeout. Vertex TTS for ~25-40 word
                sentences typically returns in 1-3s; 30s leaves headroom.

        Raises:
            TTSGenerationError: any HTTP non-200 or transport failure. The
                caller (NarratorAgent) handles retry policy.
        """
        body = self._build_request_body(
            text=text, voice_name=voice_name, speaking_rate=speaking_rate
        )
        headers = await self._build_headers()
        http = await self._ensure_http_client()

        try:
            response = await http.post(
                self.url, headers=headers, json=body, timeout=timeout_s
            )
        except Exception as e:  # transport failure
            raise TTSGenerationError(
                f"TTS transport failure: {type(e).__name__}: {e}",
                status_code=None,
            ) from e

        status = getattr(response, "status_code", 0)
        if status != 200:
            text_excerpt = ""
            try:
                text_excerpt = response.text[:300] if hasattr(response, "text") else ""
            except Exception:
                text_excerpt = "<unreadable response body>"
            raise TTSGenerationError(
                f"TTS HTTP {status}: {text_excerpt}",
                status_code=status,
            )

        try:
            payload = response.json()
        except Exception as e:
            raise TTSGenerationError(
                f"TTS response not JSON: {e}", status_code=status
            ) from e

        return self._extract_audio(payload)

    async def aclose(self) -> None:
        """Best-effort: close the underlying httpx connection pool."""
        if self._http is None:
            return
        try:
            await self._http.aclose()
        except Exception:
            logger.debug("tts_client.aclose: httpx aclose raised", exc_info=True)
        self._http = None

    # -- Internals ------------------------------------------------------------

    def _build_request_body(
        self,
        *,
        text: str,
        voice_name: str,
        speaking_rate: float | None,
    ) -> dict:
        """Build the `:generateContent` body per tech_snapshot.md §3.

        speechConfig uses the bare prebuilt voice name — Vertex AI invocation
        form (HOE-DEC-025).
        """
        speech_config: dict = {
            "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice_name}}
        }
        if speaking_rate is not None:
            # BUILD_SPEC §5.6 says inline tags supersede speaking_rate for
            # Gemini 3.1 Flash TTS; we still forward when callers ask.
            speech_config["speakingRate"] = float(speaking_rate)

        return {
            "contents": [{"role": "user", "parts": [{"text": text}]}],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": speech_config,
            },
        }

    async def _build_headers(self) -> dict[str, str]:
        token = await self._get_access_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-Goog-User-Project": self._project,
        }

    async def _get_access_token(self) -> str:
        """Cache the GCP access token and refresh on expiry.

        google-auth's `creds.refresh(...)` is synchronous; we hop to a thread
        so the event loop isn't blocked.
        """
        async with self._token_lock:
            if self._token and not self._token_needs_refresh():
                return self._token
            creds = self._credentials
            if creds is None:
                # Lazy import — google.auth is heavyweight + only needed in real
                # boot paths. Tests inject a credentials stub so this branch
                # isn't taken there.
                import google.auth  # type: ignore[import-untyped]
                creds, _ = google.auth.default(scopes=[_AUTH_SCOPE])
                self._credentials = creds
            try:
                import google.auth.transport.requests  # type: ignore[import-untyped]
                request = google.auth.transport.requests.Request()
                await asyncio.to_thread(creds.refresh, request)
            except ImportError:
                # Tests / dev sandbox without google-auth: rely on a stub
                # credentials object that exposes .token directly.
                pass
            token = getattr(creds, "token", None)
            if not token:
                raise TTSGenerationError(
                    "tts_client: google.auth credentials returned no token after refresh",
                    status_code=None,
                )
            self._token = token
            self._token_expiry = getattr(creds, "expiry", None)
            return token

    def _token_needs_refresh(self) -> bool:
        if self._token_expiry is None:
            return False  # No expiry info → trust the cache; google-auth will
            # raise on stale tokens at the next refresh and we'll catch then.
        # google-auth `expiry` is naive UTC datetime per its docs.
        try:
            now = self._clock()
            expiry = self._token_expiry
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=timezone.utc)
            return (expiry - now).total_seconds() < 60
        except Exception:
            return True

    async def _ensure_http_client(self) -> Any:
        if self._http is not None:
            return self._http
        async with self._token_lock:
            if self._http is not None:
                return self._http
            import httpx  # type: ignore[import-untyped]
            self._http = httpx.AsyncClient(timeout=httpx.Timeout(30.0))
            return self._http

    def _extract_audio(self, payload: dict) -> tuple[bytes, str]:
        """Walk `candidates[0].content.parts` for the first inlineData audio.

        Mirrors `scripts/list_tts_voices.py::tts_generate` exactly so behavior
        is consistent with the proven Day-1 implementation.
        """
        candidates = payload.get("candidates") or []
        for c in candidates:
            content = c.get("content") or {}
            for p in content.get("parts") or []:
                inline = p.get("inlineData") or p.get("inline_data")
                if not inline:
                    continue
                mime = inline.get("mimeType") or inline.get("mime_type") or ""
                data_b64 = inline.get("data")
                if data_b64 and isinstance(mime, str) and mime.startswith("audio/"):
                    try:
                        audio = base64.b64decode(data_b64)
                    except Exception as e:
                        raise TTSGenerationError(
                            f"TTS inline data not valid base64: {e}",
                            status_code=200,
                        ) from e
                    return audio, mime
        raise TTSGenerationError(
            f"TTS response had no inlineData audio. payload keys: "
            f"{sorted(payload.keys())}",
            status_code=200,
        )


# -- Helpers -------------------------------------------------------------------


def parse_l16_rate(mime: str, default: int = 24000) -> int:
    """Pull `rate=NNNN` out of a mime like 'audio/l16; rate=24000; channels=1'.

    Mirrors `scripts/list_tts_voices.py::_parse_l16_rate` so audio-handling
    code can use the same parser regardless of which surface produced the
    bytes.
    """
    m = re.search(r"rate\s*=\s*(\d+)", mime)
    return int(m.group(1)) if m else default
