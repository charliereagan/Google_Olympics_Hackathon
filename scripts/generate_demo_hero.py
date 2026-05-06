#!/usr/bin/env python3
"""One-shot CLI: generate the Mount Pleasant hero image for the demo.

Mirrors `agents/publish_gate/visualizer.py` exactly (same model ID, same
endpoint, same `responseModalities=["IMAGE"]` shape, same auth pattern).
The only deviation: writes the resulting PNG bytes to a local `web/public/`
path instead of uploading to GCS — this is a demo asset for the Next.js
dev server, not a runtime-generated story.

Hard guards (PROJECT_BRIEF §6 / §7 / CONSTITUTION Law 6):
  - NO PEOPLE, NO faces, NO uniforms with names
  - Stylized editorial illustration; explicitly NOT photorealistic
  - NO Olympic rings / Agitos / torch / LA28 / Team USA / third-party logos
  - Subject: a wrestling-room interior (place, not person)

Output: /web/public/fixture/heroes/mount-pleasant.png

Cost: one Nano Banana Pro call ~ $0.05.

Usage:
    .venv/bin/python scripts/generate_demo_hero.py
"""

from __future__ import annotations

import asyncio
import base64
import json
import sys
import time
from pathlib import Path

# Visualizer imports — we use its url helper + prompt registry where it
# helps, but bypass GCS upload for this local-asset path.
import httpx  # type: ignore[import-untyped]

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = REPO_ROOT / "web" / "public" / "fixture" / "heroes" / "mount-pleasant.png"

PROJECT = "predictive-fx-495200-j4"
LOCATION = "global"  # HOE-DEC-015: Gemini 3.x family is global-only.
HERO_MODEL = "gemini-3-pro-image-preview"  # Nano Banana Pro (tech_snapshot §3).
API_VERSION = "v1beta1"
AUTH_SCOPE = "https://www.googleapis.com/auth/cloud-platform"

# Bespoke prompt for Mount Pleasant — wrestling-room atmosphere. Documentary
# register, navy + warm-gold palette to match the design system tokens. Built
# from the BUILD_SPEC §7.4 hero template skeleton, but with explicit
# wrestling-specific environmental detail. ALL the negative phrasing from
# the visualizer's `_PROMPT_HERO_TEMPLATE` is preserved verbatim.
PROMPT_PRIMARY = """\
Cinematic editorial illustration in the style of an Olympic broadcast
opening package. Subject: the empty interior of a small high-school
wrestling room at the south end of a Midwestern American school
building. Sun-bleached wrestling mats covering the floor, faintly
visible scuff lines and tape repair marks. Bare cinder-block walls in
weathered cream paint. A single high window casting low, late-afternoon
amber light across the canvas. Painted lane lines and a single faded
wrestling circle on the mat. Quiet visual texture: a stopwatch resting
on a wooden bleacher silhouette in the background, a coiled jump rope
hanging on a nail. NO PEOPLE in the image. NO faces, NO bodies, NO
silhouettes of people, NO uniforms, NO names, NO numbers, NO scoreboards.
Mood: reverent, slow, emotional, the quiet of a room that has been used
every weekday afternoon for fifty years. Color palette: deep navy
(#0A1428) base, warm gold accents (#D4A84A) for the window light only,
weathered cream walls, very subdued. Texture: painterly, like a Sports
Illustrated cover from the 1990s, visible brush stroke, NOT photographic.
Aspect ratio: 16:9, full-bleed editorial. NO photorealistic faces, NO
identifiable likeness, NO Olympic rings, NO Paralympic Agitos, NO
Olympic torch, NO LA28 marks, NO Team USA marks, NO third-party
corporate logos, NO brand marks of any kind. Render the room itself as
the protagonist."""

# Simpler retry prompt if Nano Banana Pro times out or safety-blocks the
# primary. Same constraints; less environmental detail to lower model load.
PROMPT_FALLBACK = """\
Stylized editorial illustration of an empty small-town American
wrestling-room interior at late afternoon. Sun-bleached mats, bare
cinder-block walls, single high window, warm amber light. NO PEOPLE,
NO faces, NO bodies, NO silhouettes, NO uniforms, NO names, NO logos.
Painterly, NOT photorealistic. Deep navy base with warm gold accents.
16:9. The room is the subject."""


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
    """Walk candidates[0].content.parts for the first image/* inlineData.

    Mirrors `Visualizer._extract_image` exactly so behavior is consistent.
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
                return base64.b64decode(data_b64)
    # Surface safety blocks distinctly.
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
    """POST one image-gen request; return (png_bytes, latency_seconds)."""
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

    print(f"[generate_demo_hero] project={PROJECT} model={HERO_MODEL}")
    print(f"[generate_demo_hero] output={OUTPUT_PATH}")
    print("[generate_demo_hero] attempt 1/2 — primary prompt (~280 tokens)")
    try:
        png, latency = await generate_hero(PROMPT_PRIMARY)
        prompt_used = "primary"
    except Exception as e:
        print(f"[generate_demo_hero] primary failed after timeout/parse: {e}")
        print("[generate_demo_hero] attempt 2/2 — fallback (simpler) prompt")
        try:
            png, latency = await generate_hero(PROMPT_FALLBACK)
            prompt_used = "fallback"
        except Exception as e2:
            # Surface the actionable failure mode for HoE.
            print("\n=== FAILURE ===")
            print(f"  primary failed: {e}")
            print(f"  fallback failed: {e2}")
            print("\nSuggested HoE manual probe:")
            print("  TOK=$(gcloud auth application-default print-access-token)")
            print(f"  URL='{url_for(HERO_MODEL)}'")
            print("  curl -sS -X POST -H \"Authorization: Bearer $TOK\" \\")
            print("    -H 'Content-Type: application/json' \\")
            print(f"    -H 'X-Goog-User-Project: {PROJECT}' \\")
            print("    -d '{\"contents\":[{\"role\":\"user\",\"parts\":[{\"text\":\"...prompt...\"}]}],\"generationConfig\":{\"responseModalities\":[\"IMAGE\"]}}' \\")
            print("    \"$URL\"")
            return 2

    OUTPUT_PATH.write_bytes(png)
    print(
        f"[generate_demo_hero] OK prompt={prompt_used} bytes={len(png)} "
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
