#!/usr/bin/env python3
"""One-shot CLI: generate the Birmingham hero image for the demo.

Mirrors `scripts/generate_demo_hero.py` exactly (same model ID, same
endpoint, same `responseModalities=["IMAGE"]` shape, same auth pattern,
same retry/fallback flow). Only the prompt and output path differ.

Hard guards (PROJECT_BRIEF §6 / §7 / CONSTITUTION Law 6):
  - NO PEOPLE, NO faces, NO uniforms with names, NO silhouettes of people
  - Stylized editorial illustration; explicitly NOT photorealistic
  - NO Olympic rings / Agitos / torch / LA28 / Team USA / third-party logos
  - Subject: an empty adaptive-sports facility interior at dawn

Output: /web/public/fixture/heroes/birmingham-alabama.png

Cost: one Nano Banana Pro call ~ $0.05.

Usage:
    .venv/bin/python scripts/generate_demo_hero_birmingham.py
"""

from __future__ import annotations

import asyncio
import base64
import json
import sys
import time
from pathlib import Path

import httpx  # type: ignore[import-untyped]

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = (
    REPO_ROOT / "web" / "public" / "fixture" / "heroes" / "birmingham-alabama.png"
)

PROJECT = "predictive-fx-495200-j4"
LOCATION = "global"  # HOE-DEC-015
HERO_MODEL = "gemini-3-pro-image-preview"
API_VERSION = "v1beta1"
AUTH_SCOPE = "https://www.googleapis.com/auth/cloud-platform"

PROMPT_PRIMARY = """\
Cinematic editorial illustration in the style of an Olympic broadcast
opening package. Subject: the empty interior of an adaptive-sports
training facility at dawn — a wide-angle interior view of a hardwood
gymnasium with the four 'try' zones and goal zones of a wheelchair
rugby court painted on the floor in faded baseline tape, a single
empty wheelchair-rugby chair (the low-slung competition kind with
heavily angled wheels) parked at the edge of the court — chair only,
no rider, no stickers, no numbers. Industrial steel rafters above with
exposed truss work. Low morning sun coming through high clerestory
windows on the long wall, casting long parallel shafts of warm amber
light across the hardwood floor. The polished floor reflects the gold
light faintly. A coiled push-rim handling glove resting on a wooden
bench in the foreground; a hand-painted schedule chart pinned to a
corkboard on the back wall, illegible at this distance. NO PEOPLE in
the image. NO faces, NO bodies, NO silhouettes of people, NO uniforms,
NO names, NO numbers, NO scoreboards. Mood: reverent, slow, the quiet
of a facility that opens at six in the morning every day. Color
palette: deep navy (#0A1428) base in the shadows and rafters, warm
gold accents (#D4A84A) for the window light only, weathered cream
walls. Texture: painterly, like a Sports Illustrated cover from the
1990s, visible brush stroke, NOT photographic. Aspect ratio: 16:9,
full-bleed editorial. NO photorealistic faces, NO identifiable
likeness, NO Olympic rings, NO Paralympic Agitos, NO Olympic torch,
NO LA28 marks, NO Team USA marks, NO third-party corporate logos, NO
brand marks of any kind. Render the facility itself as the
protagonist."""

PROMPT_FALLBACK = """\
Stylized editorial illustration of an empty hardwood gymnasium interior
at dawn with wheelchair-rugby court markings on the floor and a single
empty competition wheelchair parked at the edge. Steel rafters above,
clerestory windows casting warm gold parallel light shafts. NO PEOPLE,
NO faces, NO bodies, NO silhouettes, NO uniforms, NO names, NO logos.
Painterly, NOT photorealistic. Deep navy base with warm gold accents.
16:9. The facility is the subject."""


def get_access_token() -> str:
    import google.auth  # type: ignore[import-untyped]
    import google.auth.transport.requests  # type: ignore[import-untyped]

    creds, _ = google.auth.default(scopes=[AUTH_SCOPE])
    creds.refresh(google.auth.transport.requests.Request())
    if not creds.token:
        raise RuntimeError("google.auth returned creds but no token after refresh")
    return creds.token


def url_for(model_id: str) -> str:
    return (
        f"https://aiplatform.googleapis.com/{API_VERSION}/projects/{PROJECT}"
        f"/locations/{LOCATION}/publishers/google/models/"
        f"{model_id}:generateContent"
    )


def extract_png(payload: dict) -> bytes:
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
                return base64.b64decode(data_b64)
    finish_reasons = []
    for c in candidates:
        fr = c.get("finishReason") or c.get("finish_reason")
        if fr:
            finish_reasons.append(fr)
    if finish_reasons:
        raise RuntimeError(
            f"image-gen returned no inlineData; finishReason={finish_reasons}"
        )
    raise RuntimeError(
        f"image-gen returned no inlineData. payload keys: {sorted(payload.keys())}"
    )


async def generate_hero(prompt: str, timeout_s: float = 180.0) -> tuple[bytes, float]:
    token = get_access_token()
    url = url_for(HERO_MODEL)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-Goog-User-Project": PROJECT,
    }
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"responseModalities": ["IMAGE"]},
    }
    t0 = time.monotonic()
    async with httpx.AsyncClient(timeout=httpx.Timeout(timeout_s)) as http:
        response = await http.post(url, headers=headers, json=body)
    latency = time.monotonic() - t0

    if response.status_code != 200:
        raise RuntimeError(
            f"image-gen HTTP {response.status_code}: {response.text[:300]}"
        )
    payload = response.json()
    png = extract_png(payload)
    return png, latency


async def amain() -> int:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    print(f"[generate_demo_hero_birmingham] project={PROJECT} model={HERO_MODEL}")
    print(f"[generate_demo_hero_birmingham] output={OUTPUT_PATH}")
    print("[generate_demo_hero_birmingham] attempt 1/2 — primary prompt")
    try:
        png, latency = await generate_hero(PROMPT_PRIMARY)
        prompt_used = "primary"
    except Exception as e:
        print(f"[generate_demo_hero_birmingham] primary failed: {e}")
        print("[generate_demo_hero_birmingham] attempt 2/2 — fallback prompt")
        try:
            png, latency = await generate_hero(PROMPT_FALLBACK)
            prompt_used = "fallback"
        except Exception as e2:
            print("\n=== FAILURE ===")
            print(f"  primary failed: {e}")
            print(f"  fallback failed: {e2}")
            return 2

    OUTPUT_PATH.write_bytes(png)
    print(
        f"[generate_demo_hero_birmingham] OK prompt={prompt_used} bytes={len(png)} "
        f"latency={latency:.1f}s -> {OUTPUT_PATH}"
    )
    print(json.dumps({
        "ok": True,
        "model": HERO_MODEL,
        "prompt": prompt_used,
        "latency_s": round(latency, 2),
        "bytes": len(png),
        "path": str(OUTPUT_PATH.relative_to(REPO_ROOT)),
    }))
    return 0


def main() -> int:
    return asyncio.run(amain())


if __name__ == "__main__":
    sys.exit(main())
