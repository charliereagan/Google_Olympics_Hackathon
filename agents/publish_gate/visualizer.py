"""The Visualizer tool — Nano Banana Pro / Flash Image generation.

Per CONSTITUTION Rule 2 + HOE-DEC-020: the Visualizer is a Python
tool the Publish Gate calls — NOT an agent and NOT a sub-stage.
Two model paths per BUILD_SPEC §3.4:

  * Hero (Nano Banana Pro = `gemini-3-pro-image-preview`): cinematic
    editorial illustration for the Broadcast page. Subject is ALWAYS a
    place, landscape, community, or facility — NEVER a person.
  * Utility (Gemini 3.1 Flash Image = `gemini-3.1-flash-image-preview`):
    hometown panel maps + historical echo silhouettes.

Both endpoints are Vertex AI v1beta1 `:generateContent` with
`responseModalities=["IMAGE"]`. Auth via google-auth ADC token —
same pattern as the Narrator's TTS client (`agents/narrator/tts_client.py`).

Output: a GCS URL (`gs://{bucket}/{story_unit_id}/{asset}.png`). The
Publish Gate orchestrator then hands those URLs to the Visual Review
sub-stage (sub-stage 7) for validation.

Failure handling per HOE-DEC-020 + BUILD_SPEC §17.2:
  - Up to 3 regenerations on Visual Review failure (managed by the
    orchestrator, not the Visualizer itself).
  - On the 4th failure: fallback to `gs://storytellers-room-fallback-heroes/
    {story_unit_id}.png` (or `default.png` if no anchor-specific fallback
    exists). `Visualizer.fallback_hero(...)` returns that URL.

Constitution Law 6 enforcement: every prompt template in this module
EXPLICITLY says NO PEOPLE, NO identifiable likeness, NO Olympic rings /
Agitos / torch / LA28 / Team USA marks / third-party logos. The Visual
Review sub-stage is the second filter; this is the first.
"""

from __future__ import annotations

import asyncio
import base64
import logging
from datetime import datetime, timezone
from typing import Any

from agents.cost.counters import CostCeilingExceeded

logger = logging.getLogger(__name__)


# --- Endpoint constants (same shape as `tts_client.py`) ----------------------

_AIPLATFORM_HOST = "https://aiplatform.googleapis.com"
_IMAGE_API_VERSION = "v1beta1"  # Both image models live on v1beta1 (tech_snapshot §3).
_DEFAULT_LOCATION = "global"  # HOE-DEC-015: Gemini 3.x is global-only.
_AUTH_SCOPE = "https://www.googleapis.com/auth/cloud-platform"

# Verified model IDs (BUILD_SPEC §3.4 + tech_snapshot §3).
_DEFAULT_HERO_MODEL = "gemini-3-pro-image-preview"
_DEFAULT_UTILITY_MODEL = "gemini-3.1-flash-image-preview"

# Cost axes (BUILD_SPEC §15.3, data/bq_schemas/agent_call_counters.json).
_HERO_COST_AXIS = "image_pro"
_UTILITY_COST_AXIS = "image_flash"

# Default GCS buckets.
_DEFAULT_HERO_BUCKET = "storytellers-room-hero-images"
_DEFAULT_FALLBACK_BUCKET = "storytellers-room-fallback-heroes"


# --- Errors ------------------------------------------------------------------


class GeminiImageGenError(RuntimeError):
    """Raised on any HTTP / parse / safety failure during image generation.

    `status_code` is set on HTTP non-200; None on transport / parse failure.
    """

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class VisualizerSafetyError(RuntimeError):
    """Raised when the regeneration budget is exhausted.

    Currently unused by the Visualizer itself — the Publish Gate
    orchestrator owns the regeneration loop and falls back via
    `Visualizer.fallback_hero(...)` instead of raising. We export the
    class so callers can match on it if the policy ever changes.
    """


# --- Prompt templates (BUILD_SPEC §7.4 verbatim) -----------------------------

_PROMPT_HERO_TEMPLATE = """\
Cinematic editorial illustration in the style of an Olympic broadcast
opening package. Subject: a stylized landscape / townscape /
community facility — {place_type}. NO PEOPLE in the image. Setting:
{environmental_cue}. Mood: reverent, slow, emotional. Color palette:
deep navy, warm gold accents, subdued. Texture: painterly, like a
Sports Illustrated cover from the 1990s. NO photorealistic faces. NO
identifiable likeness. NO Olympic rings or marks. NO logos. NO Team
USA marks. NO Paralympic Agitos. NO LA28 logomark. NO Olympic torch.
NO third-party corporate logos. Aspect ratio: 16:9, 4K.{stricter}"""

_PROMPT_HOMETOWN_TEMPLATE = """\
Stylized illustrated map of {town_name}, {state}. Editorial Olympic
broadcast graphics style. Single accent color (warm gold) over deep
navy base. Show approximate region with simple geographic markers.
Town indicated with a single warm-gold star. Subdued, cartographic,
NOT photorealistic. NO people. NO logos.{stricter}"""

_PROMPT_ECHO_TEMPLATE = """\
Side-by-side stylized illustrations: left side, modern sport scene
silhouette / equipment / facility (representing the present-day
pattern: {modern_pattern}); right side, parallel historical-era sport
scene silhouette / equipment / facility (representing the {era_year}
{era_sport} era). Same painterly editorial style for both. Connected
by a subtle gold thread or geometric line. NO PEOPLE in either side.
NO faces. NO likenesses. NO logos. NO Olympic rings. NO Agitos. NO
torch. Deep navy background with warm gold accents.{stricter}"""

# Stricter clauses appended on regeneration. The orchestrator passes
# `stricter_level=N` (1, 2, or 3) when re-invoking after a Visual Review
# failure. Level 0 = baseline prompt; higher levels add more negative
# phrasing per BUILD_SPEC §17.2.
_STRICTER_CLAUSES: dict[int, str] = {
    0: "",
    1: (
        "\n\nIMPORTANT: this image was previously rejected for being too "
        "photorealistic or containing a likeness. Render in an EXPLICITLY "
        "STYLIZED, NON-PHOTOREALISTIC, painterly editorial style. Subject "
        "is a place / landscape / facility — NEVER a person."
    ),
    2: (
        "\n\nIMPORTANT: this image was rejected twice. Render as a flat "
        "graphic illustration with visible brush texture; deliberately "
        "abstract; NO HUMAN FIGURES whatsoever, even in silhouette in "
        "any prominent position. NO likenesses. NO photographic detail. "
        "NO logos or marks of any kind."
    ),
    3: (
        "\n\nFINAL ATTEMPT: image was rejected three times. Render as a "
        "minimalist geometric editorial illustration — wide landscape or "
        "facility composition only, NO HUMAN FIGURES of any kind, NO "
        "PHOTOGRAPHIC TEXTURE, NO likenesses, NO logos, NO protected marks. "
        "Heavy painterly abstraction in deep navy and warm gold."
    ),
}


# --- The Visualizer tool -----------------------------------------------------


class Visualizer:
    """Generates hero + utility images for Storyteller drafts.

    Stateless except for an httpx connection pool + an access-token
    cache (mirrors `GeminiFlashTTSClient`). One instance per runtime is
    fine.

    Construction takes everything the runtime injects; tests pass stubs
    for `http_client`, `credentials`, `storage`, and `cost_counter`.

    HOE-DEC-020 / BUILD_SPEC §17.2:
      - The Visualizer itself does NOT loop on Visual Review failure;
        the orchestrator does. The Visualizer's `generate_hero` accepts
        a `stricter_level` arg so the orchestrator can re-invoke with
        progressively more restrictive prompts.
      - `fallback_hero(...)` returns the curated Day-9 fallback URL
        when the orchestrator exhausts its regeneration budget.
    """

    def __init__(
        self,
        *,
        project: str,
        location: str = _DEFAULT_LOCATION,
        hero_model: str = _DEFAULT_HERO_MODEL,
        utility_model: str = _DEFAULT_UTILITY_MODEL,
        bucket_name: str = _DEFAULT_HERO_BUCKET,
        fallback_bucket: str = _DEFAULT_FALLBACK_BUCKET,
        cost_counter: Any | None = None,
        max_regenerations: int = 3,
        storage: Any | None = None,
        http_client: Any | None = None,
        credentials: Any | None = None,
        clock: Any | None = None,
    ) -> None:
        self._project = project
        self._location = location
        self._hero_model = hero_model
        self._utility_model = utility_model
        self._bucket_name = bucket_name
        self._fallback_bucket = fallback_bucket
        self._cost_counter = cost_counter
        self._max_regenerations = int(max_regenerations)
        # Optional pre-built clients (tests pass mocks).
        self._storage = storage
        self._http: Any | None = http_client
        self._credentials: Any | None = credentials
        self._token: str | None = None
        self._token_expiry: datetime | None = None
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._token_lock: asyncio.Lock = asyncio.Lock()

    # -- Public surface -----------------------------------------------------

    @property
    def hero_model(self) -> str:
        return self._hero_model

    @property
    def utility_model(self) -> str:
        return self._utility_model

    @property
    def bucket_name(self) -> str:
        return self._bucket_name

    @property
    def fallback_bucket(self) -> str:
        return self._fallback_bucket

    @property
    def max_regenerations(self) -> int:
        return self._max_regenerations

    def url_for(self, model_id: str) -> str:
        """Vertex AI generateContent URL for the given image model."""
        return (
            f"{_AIPLATFORM_HOST}/{_IMAGE_API_VERSION}/projects/{self._project}"
            f"/locations/{self._location}/publishers/google/models/"
            f"{model_id}:generateContent"
        )

    # -- Hero generation ----------------------------------------------------

    async def generate_hero(
        self,
        *,
        place_type: str,
        environmental_cue: str,
        story_unit_id: str,
        stricter_level: int = 0,
        timeout_s: float = 120.0,
    ) -> str:
        """Generate the cinematic Broadcast hero image.

        Subject is ALWAYS a place / landscape / community / facility —
        never a person. Per CONSTITUTION Law 6 the prompt explicitly
        says NO PEOPLE and NO logos.

        Args:
            place_type: short noun phrase describing the place subject
                (e.g., "small-town main street at dusk", "empty community
                gym at twilight"). Inserted into the BUILD_SPEC §7.4
                hero template verbatim.
            environmental_cue: one-line hometown environmental detail
                (e.g., "rural Iowa cornfields under a winter sky").
            story_unit_id: used as the GCS path segment.
            stricter_level: 0..3 — orchestrator passes higher values on
                regeneration to add stricter negative phrasing.
            timeout_s: per-call request timeout. Nano Banana Pro typically generates in 20-30s but can spike to 60-90s on long prompts; 120s default leaves headroom (HoE bumped from 60s after Day-7 smoke saw a ReadTimeout).
                returns in 5-15s; 60s leaves headroom.

        Returns:
            GCS URL of the uploaded PNG (`gs://{bucket}/{story_unit_id}/hero.png`).

        Raises:
            CostCeilingExceeded: pre-check failure on `image_pro` axis.
            GeminiImageGenError: HTTP / parse / safety failure.
            RuntimeError: GCS upload failure.
        """
        prompt = _PROMPT_HERO_TEMPLATE.format(
            place_type=place_type,
            environmental_cue=environmental_cue,
            stricter=_STRICTER_CLAUSES.get(stricter_level, _STRICTER_CLAUSES[3]),
        )
        return await self._generate_one(
            prompt=prompt,
            model_id=self._hero_model,
            cost_axis=_HERO_COST_AXIS,
            blob_name=f"{story_unit_id}/hero.png",
            timeout_s=timeout_s,
        )

    # -- Hometown panel -----------------------------------------------------

    async def generate_hometown_panel(
        self,
        *,
        town_name: str,
        state: str,
        story_unit_id: str,
        stricter_level: int = 0,
        timeout_s: float = 45.0,
    ) -> str:
        """Generate the stylized hometown map panel (BUILD_SPEC §7.4).

        Uses the utility (Flash Image) model. Subject is the geographic
        region rendered cartographically — never a person.

        Returns the GCS URL of the uploaded PNG.
        """
        prompt = _PROMPT_HOMETOWN_TEMPLATE.format(
            town_name=town_name,
            state=state,
            stricter=_STRICTER_CLAUSES.get(stricter_level, _STRICTER_CLAUSES[3]),
        )
        return await self._generate_one(
            prompt=prompt,
            model_id=self._utility_model,
            cost_axis=_UTILITY_COST_AXIS,
            blob_name=f"{story_unit_id}/hometown.png",
            timeout_s=timeout_s,
        )

    # -- Historical echo panel ---------------------------------------------

    async def generate_historical_echo(
        self,
        *,
        modern_pattern: str,
        era_year: int,
        era_sport: str,
        story_unit_id: str,
        stricter_level: int = 0,
        timeout_s: float = 45.0,
    ) -> str:
        """Generate the side-by-side historical echo panel (BUILD_SPEC §7.4).

        Subject is sport equipment / facility silhouettes — never named
        athletes. Per PROJECT_BRIEF §5 the Echo Scout cites eras /
        regions / sports / patterns, not individuals.
        """
        prompt = _PROMPT_ECHO_TEMPLATE.format(
            modern_pattern=modern_pattern,
            era_year=int(era_year),
            era_sport=era_sport,
            stricter=_STRICTER_CLAUSES.get(stricter_level, _STRICTER_CLAUSES[3]),
        )
        return await self._generate_one(
            prompt=prompt,
            model_id=self._utility_model,
            cost_axis=_UTILITY_COST_AXIS,
            blob_name=f"{story_unit_id}/echo.png",
            timeout_s=timeout_s,
        )

    # -- Generate all three (orchestrator entrypoint) ----------------------

    async def generate_assets(
        self,
        *,
        story_draft: dict,
        investigation_packet: dict,
        wire: Any | None = None,
        investigation_id: str = "ambient",
        stricter_level: int = 0,
    ) -> dict:
        """Generate hero + hometown panel + historical echo in parallel.

        Returns:
            {
              "hero_url": gs://...,
              "hometown_panel_url": gs://...,
              "echo_panel_url": gs://...,
              "regenerations": int,
              "stricter_level": int,
            }

        On individual asset failure: emits a Wire `thinking` event for
        visibility, retries that asset once, then sets that URL to None
        in the result so the orchestrator can decide to regenerate or
        fall back.

        The `regenerations` field is populated by the orchestrator, not
        by the Visualizer (which is stateless across calls). This method
        always returns 0 in that field; the orchestrator increments.
        """
        story_unit_id = (
            (story_draft or {}).get("story_unit_id")
            or (story_draft or {}).get("id")
            or f"sd-{int(self._clock().timestamp())}"
        )
        place_type = _derive_place_type(story_draft, investigation_packet)
        environmental_cue = _derive_environmental_cue(
            story_draft, investigation_packet
        )
        town_name, state = _derive_town_state(story_draft, investigation_packet)
        modern_pattern, era_year, era_sport = _derive_echo_fields(
            story_draft, investigation_packet
        )

        # Run the three in parallel — they share auth + GCS but the
        # endpoint is idempotent enough that concurrent calls don't
        # interfere. Each task wraps its own retry-once.
        async def _hero():
            return await self._with_retry(
                wire=wire,
                investigation_id=investigation_id,
                asset_label="hero",
                coro_factory=lambda: self.generate_hero(
                    place_type=place_type,
                    environmental_cue=environmental_cue,
                    story_unit_id=story_unit_id,
                    stricter_level=stricter_level,
                ),
            )

        async def _hometown():
            return await self._with_retry(
                wire=wire,
                investigation_id=investigation_id,
                asset_label="hometown_panel",
                coro_factory=lambda: self.generate_hometown_panel(
                    town_name=town_name,
                    state=state,
                    story_unit_id=story_unit_id,
                    stricter_level=stricter_level,
                ),
            )

        async def _echo():
            return await self._with_retry(
                wire=wire,
                investigation_id=investigation_id,
                asset_label="historical_echo",
                coro_factory=lambda: self.generate_historical_echo(
                    modern_pattern=modern_pattern,
                    era_year=era_year,
                    era_sport=era_sport,
                    story_unit_id=story_unit_id,
                    stricter_level=stricter_level,
                ),
            )

        hero_url, hometown_url, echo_url = await asyncio.gather(
            _hero(), _hometown(), _echo(), return_exceptions=False
        )

        return {
            "hero_url": hero_url,
            "hometown_panel_url": hometown_url,
            "echo_panel_url": echo_url,
            "regenerations": 0,
            "stricter_level": stricter_level,
        }

    # -- Fallback -----------------------------------------------------------

    async def fallback_hero(self, *, story_unit_id: str) -> str:
        """Return the GCS URL of the curated Day-9 fallback hero.

        Lookup order (HOE-DEC-020):
          1. `gs://{fallback_bucket}/{story_unit_id}.png` — anchor-specific
          2. `gs://{fallback_bucket}/default.png` — repo-wide default

        We don't mutate any URL — we just check existence and return the
        first one that resolves. Logs which path was used.
        """
        candidates = [
            f"{story_unit_id}.png",
            "default.png",
        ]
        if self._storage is None:
            # No client — return the anchor-specific path optimistically;
            # the orchestrator can show a placeholder if the bucket is
            # genuinely empty. Logged as a warning so we know.
            logger.warning(
                "visualizer.fallback_hero: no storage client; returning "
                "optimistic anchor-specific URL for story_unit_id=%s",
                story_unit_id,
            )
            return f"gs://{self._fallback_bucket}/{candidates[0]}"

        try:
            bucket = self._storage.bucket(self._fallback_bucket)
        except Exception:
            logger.exception(
                "visualizer.fallback_hero: bucket(%s) failed",
                self._fallback_bucket,
            )
            return f"gs://{self._fallback_bucket}/{candidates[0]}"

        for name in candidates:
            try:
                blob = bucket.blob(name)
                exists_callable = getattr(blob, "exists", None)
                if exists_callable is None:
                    # Storage stub without exists — return optimistically.
                    logger.info(
                        "visualizer.fallback_hero: storage stub without "
                        "exists(); returning %s",
                        name,
                    )
                    return f"gs://{self._fallback_bucket}/{name}"
                if asyncio.iscoroutinefunction(exists_callable):
                    found = await exists_callable()
                else:
                    found = await asyncio.to_thread(exists_callable)
                if found:
                    logger.info(
                        "visualizer.fallback_hero: using %s for "
                        "story_unit_id=%s",
                        name,
                        story_unit_id,
                    )
                    return f"gs://{self._fallback_bucket}/{name}"
            except Exception:
                logger.debug(
                    "visualizer.fallback_hero: exists() check raised for %s",
                    name,
                    exc_info=True,
                )
                continue

        # Neither candidate resolved — return the default path anyway so
        # the renderer has SOMETHING to show. Logged as a warning.
        logger.warning(
            "visualizer.fallback_hero: no fallback found in bucket=%s for "
            "story_unit_id=%s; returning default.png anyway",
            self._fallback_bucket,
            story_unit_id,
        )
        return f"gs://{self._fallback_bucket}/default.png"

    async def aclose(self) -> None:
        """Best-effort: close the underlying httpx connection pool."""
        if self._http is None:
            return
        try:
            await self._http.aclose()
        except Exception:
            logger.debug(
                "visualizer.aclose: httpx aclose raised", exc_info=True
            )
        self._http = None

    # -- Internals: single-asset generation --------------------------------

    async def _generate_one(
        self,
        *,
        prompt: str,
        model_id: str,
        cost_axis: str,
        blob_name: str,
        timeout_s: float,
    ) -> str:
        """Pre-check cost ceiling, POST to Vertex AI, parse, upload, return URL."""
        # 1. Cost-counter pre-check.
        if self._cost_counter is not None:
            try:
                await self._cost_counter.assert_under_ceiling(
                    axis=cost_axis, agent="publish_gate"
                )
            except CostCeilingExceeded:
                raise

        # 2. Build + POST.
        body = self._build_request_body(prompt)
        headers = await self._build_headers()
        http = await self._ensure_http_client()
        url = self.url_for(model_id)

        try:
            response = await http.post(
                url, headers=headers, json=body, timeout=timeout_s
            )
        except Exception as e:
            raise GeminiImageGenError(
                f"image-gen transport failure: {type(e).__name__}: {e}",
                status_code=None,
            ) from e

        status = getattr(response, "status_code", 0)
        if status != 200:
            text_excerpt = ""
            try:
                text_excerpt = (
                    response.text[:300]
                    if hasattr(response, "text")
                    else ""
                )
            except Exception:
                text_excerpt = "<unreadable response body>"
            raise GeminiImageGenError(
                f"image-gen HTTP {status}: {text_excerpt}",
                status_code=status,
            )

        try:
            payload = response.json()
        except Exception as e:
            raise GeminiImageGenError(
                f"image-gen response not JSON: {e}", status_code=status
            ) from e

        png_bytes, mime = self._extract_image(payload)

        # 3. Upload to GCS.
        gcs_url = await self._upload_image(blob_name=blob_name, data=png_bytes)

        # 4. Cost-counter increment (after success).
        if self._cost_counter is not None:
            try:
                await self._cost_counter.increment(
                    agent="publish_gate",
                    sub_agent=None,
                    axis=cost_axis,
                    model=model_id,
                    calls=1,
                    images=1,
                )
            except Exception:
                logger.exception(
                    "visualizer: cost_counter.increment failed (axis=%s)",
                    cost_axis,
                )

        logger.info(
            "visualizer.generate_one: ok mime=%s bytes=%d url=%s",
            mime, len(png_bytes), gcs_url,
        )
        return gcs_url

    # -- HTTP / auth (mirrors tts_client.py) -------------------------------

    def _build_request_body(self, prompt: str) -> dict:
        """The verified Vertex AI image-gen body shape (tech_snapshot §3)."""
        return {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"responseModalities": ["IMAGE"]},
        }

    async def _build_headers(self) -> dict[str, str]:
        token = await self._get_access_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-Goog-User-Project": self._project,
        }

    async def _get_access_token(self) -> str:
        """Cache the GCP access token; refresh on expiry. Mirrors tts_client.py."""
        async with self._token_lock:
            if self._token and not self._token_needs_refresh():
                return self._token
            creds = self._credentials
            if creds is None:
                import google.auth  # type: ignore[import-untyped]

                creds, _ = google.auth.default(scopes=[_AUTH_SCOPE])
                self._credentials = creds
            try:
                import google.auth.transport.requests  # type: ignore[import-untyped]

                request = google.auth.transport.requests.Request()
                await asyncio.to_thread(creds.refresh, request)
            except ImportError:
                # Tests inject a credentials stub with .token directly set.
                pass
            token = getattr(creds, "token", None)
            if not token:
                raise GeminiImageGenError(
                    "visualizer: google.auth credentials returned no token after refresh",
                    status_code=None,
                )
            self._token = token
            self._token_expiry = getattr(creds, "expiry", None)
            return token

    def _token_needs_refresh(self) -> bool:
        if self._token_expiry is None:
            return False
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

            self._http = httpx.AsyncClient(timeout=httpx.Timeout(120.0))
            return self._http

    # -- Image extraction --------------------------------------------------

    def _extract_image(self, payload: dict) -> tuple[bytes, str]:
        """Walk `candidates[0].content.parts` for the first `image/*` inlineData.

        Mirrors the TTS client's `_extract_audio` exactly so behavior is
        consistent with the proven Day-1 implementation.
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
                if data_b64 and isinstance(mime, str) and mime.startswith("image/"):
                    try:
                        img = base64.b64decode(data_b64)
                    except Exception as e:
                        raise GeminiImageGenError(
                            f"image-gen inlineData not valid base64: {e}",
                            status_code=200,
                        ) from e
                    return img, mime

        # Vertex AI's image safety filter sometimes returns a candidate
        # with no inline data and `finishReason: SAFETY`. Surface that
        # cleanly so the orchestrator can regenerate with stricter prompt.
        finish_reasons = []
        for c in candidates:
            fr = c.get("finishReason") or c.get("finish_reason")
            if fr:
                finish_reasons.append(fr)
        if any(_is_safety_block(fr) for fr in finish_reasons):
            raise GeminiImageGenError(
                f"image-gen blocked by safety filter (finishReason={finish_reasons})",
                status_code=200,
            )
        raise GeminiImageGenError(
            f"image-gen response had no inlineData image. "
            f"payload keys: {sorted(payload.keys())}",
            status_code=200,
        )

    # -- GCS upload --------------------------------------------------------

    async def _upload_image(self, *, blob_name: str, data: bytes) -> str:
        """Upload PNG bytes to `gs://{bucket}/{blob_name}`. Returns the URL."""
        if self._storage is None:
            raise RuntimeError("visualizer: storage client not configured")
        try:
            bucket = self._storage.bucket(self._bucket_name)
        except Exception as e:
            raise RuntimeError(
                f"visualizer: storage.bucket({self._bucket_name}) failed: {e}"
            ) from e
        await asyncio.to_thread(_upload_blob, bucket, blob_name, data)
        return f"gs://{self._bucket_name}/{blob_name}"

    # -- Per-asset retry-once wrapper --------------------------------------

    async def _with_retry(
        self,
        *,
        wire: Any | None,
        investigation_id: str,
        asset_label: str,
        coro_factory,  # zero-arg callable returning a coroutine
    ) -> str | None:
        """Run an asset-generation coroutine; retry once on failure.

        Emits a Wire `thinking` event before the retry so the failure is
        visible (BUILD_SPEC §17.2 — "visual review failed, regenerating
        with stricter prompt"). On second failure returns None and lets
        the orchestrator decide to fall back.
        """
        for attempt in (1, 2):
            try:
                return await coro_factory()
            except CostCeilingExceeded:
                # No retry on cost ceiling — propagate.
                raise
            except Exception as e:
                logger.warning(
                    "visualizer.%s: attempt %d/2 failed: %s",
                    asset_label, attempt, e,
                )
                if attempt == 1 and wire is not None:
                    try:
                        await wire.emit(
                            {
                                "agent": "publish_gate",
                                "message": (
                                    f"*hold — {asset_label} generation stalled, "
                                    "retrying with stricter prompt*"
                                ),
                                "message_type": "thinking",
                                "mode": "live",
                            },
                            investigation_id=investigation_id,
                        )
                    except Exception:
                        logger.debug(
                            "visualizer: wire.emit on retry failed",
                            exc_info=True,
                        )
        # Both attempts failed — return None so the orchestrator can
        # decide to regenerate at a higher stricter level or fall back.
        return None


# --- Helpers -----------------------------------------------------------------


def _upload_blob(bucket: Any, blob_name: str, data: bytes) -> None:
    """Synchronous GCS upload helper (mirrors narrator/_upload_blob)."""
    blob = bucket.blob(blob_name)
    blob.upload_from_string(data, content_type="image/png")


def _is_safety_block(finish_reason: Any) -> bool:
    """True when a finishReason indicates a safety-filter rejection.

    Vertex AI returns either `SAFETY`, `BLOCKED`, or `IMAGE_SAFETY`
    depending on the model + the filter that fired.
    """
    if finish_reason is None:
        return False
    text = str(finish_reason).upper()
    return any(x in text for x in ("SAFETY", "BLOCKED", "IMAGE_SAFETY", "PROHIBITED"))


# --- Prompt-input derivation --------------------------------------------------
#
# These pull short noun phrases out of the StoryDraft + InvestigationPacket
# without naming any individual. CONSTITUTION Law 4: protagonists are places.
# We never substitute athlete names — these helpers exist precisely so the
# prompt sees place / region / sport, not person.


def _derive_place_type(story_draft: dict, _packet: dict) -> str:
    """Derive a place noun phrase for the hero prompt.

    Falls back to a generic 'small-town main street at dusk' if the draft
    doesn't carry an explicit `hero_place_type` hint. The Storyteller is
    expected to populate this on Day 8+; for now, we synthesize from
    available structured fields.
    """
    if not isinstance(story_draft, dict):
        return "small-town main street at dusk"
    explicit = (story_draft.get("hero_place_type") or "").strip()
    if explicit:
        return explicit
    place_name = (story_draft.get("place_name") or "").strip()
    if place_name:
        return f"small-town main street at dusk in the region of {place_name}"
    return "small-town main street at dusk"


def _derive_environmental_cue(story_draft: dict, packet: dict) -> str:
    """Derive a one-line environmental cue for the hero prompt."""
    if isinstance(story_draft, dict):
        explicit = (story_draft.get("environmental_cue") or "").strip()
        if explicit:
            return explicit
        place_name = (story_draft.get("place_name") or "").strip()
        if place_name:
            return f"the rural region around {place_name}"
    if isinstance(packet, dict):
        region = (packet.get("region") or packet.get("place_name") or "").strip()
        if region:
            return f"the rural region around {region}"
    return "a quiet American town landscape"


def _derive_town_state(story_draft: dict, packet: dict) -> tuple[str, str]:
    """Pull (town_name, state) for the hometown panel prompt."""
    town = ""
    state = ""
    if isinstance(story_draft, dict):
        town = (story_draft.get("place_name") or story_draft.get("town_name") or "").strip()
        state = (story_draft.get("state") or "").strip()
    if not town and isinstance(packet, dict):
        town = (packet.get("place_name") or packet.get("town_name") or "").strip()
    if not state and isinstance(packet, dict):
        state = (packet.get("state") or "").strip()
    return (town or "the region", state or "USA")


def _derive_echo_fields(
    story_draft: dict, packet: dict
) -> tuple[str, int, str]:
    """Pull (modern_pattern, era_year, era_sport) for the echo prompt."""
    modern = ""
    era_year: int = 1960
    era_sport: str = "track and field"
    if isinstance(story_draft, dict):
        modern = (story_draft.get("modern_pattern") or "").strip()
        try:
            era_year = int(story_draft.get("era_year") or era_year)
        except (TypeError, ValueError):
            pass
        era_sport = (
            (story_draft.get("era_sport") or era_sport).strip() or era_sport
        )
        if not modern:
            echo_text = (story_draft.get("historical_echo") or "").strip()
            if echo_text:
                # First clause of the echo paragraph as a noun phrase.
                modern = echo_text.split(".")[0][:120]
    if not modern and isinstance(packet, dict):
        modern = (packet.get("modern_pattern") or "regional sport pipeline").strip()
    return (modern or "regional sport pipeline", era_year, era_sport)


__all__ = [
    "Visualizer",
    "GeminiImageGenError",
    "VisualizerSafetyError",
]
