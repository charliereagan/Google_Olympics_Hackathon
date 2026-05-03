#!/usr/bin/env python3
"""Day-1 hard gate: probe all seven Vertex AI Gemini model IDs on location='global'.

Sends a minimal request to each verified model ID (per Docs/Engineering/tech_snapshot.md
section 3) and asserts a 200 + non-empty response. Also sanity-checks the Cloud TTS
voice catalog reports the 30 en-US-Chirp3-HD-* voices used by the Narrator.

Exits 0 if everything responds, 1 on any failure. Cost is sub-cent (maxOutputTokens=8
on the text models, tiny image/audio prompts that won't trip safety filters).

Block all downstream agent work on green. (HOE-DEC-016, BUILD_SPEC §3.1, §13.)
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass, field
from typing import Any

import google.auth
import google.auth.transport.requests
import requests

PROJECT = "predictive-fx-495200-j4"
LOCATION = "global"
AIPLATFORM_HOST = "https://aiplatform.googleapis.com"
TTS_HOST = "https://texttospeech.googleapis.com"
REQUEST_TIMEOUT_SECONDS = 60

# Image/TTS prompts kept place-only and safety-safe. No people. No athlete names.
IMAGE_PROMPT = "stylized navy gold landscape, no people"
TTS_PROMPT = "Hello."


@dataclass
class ModelProbe:
    model_id: str
    api_version: str  # "v1" | "v1beta1"
    verb_config: str  # short human description for the report table
    body: dict[str, Any]
    notes: str = ""

    def url(self) -> str:
        return (
            f"{AIPLATFORM_HOST}/{self.api_version}/projects/{PROJECT}"
            f"/locations/{LOCATION}/publishers/google/models/{self.model_id}:generateContent"
        )


@dataclass
class ProbeResult:
    label: str
    api_version: str
    verb_config: str
    status: str  # "OK" | "FAIL"
    latency_ms: int
    notes: str = ""
    error: str = ""
    usage: dict[str, Any] = field(default_factory=dict)


def _text_body() -> dict[str, Any]:
    return {
        "contents": [{"role": "user", "parts": [{"text": "Reply with the single word: ok."}]}],
        "generationConfig": {"maxOutputTokens": 8},
    }


def _image_body() -> dict[str, Any]:
    return {
        "contents": [{"role": "user", "parts": [{"text": IMAGE_PROMPT}]}],
        "generationConfig": {"responseModalities": ["IMAGE"]},
    }


def _tts_body() -> dict[str, Any]:
    return {
        "contents": [{"role": "user", "parts": [{"text": TTS_PROMPT}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": "Charon"}}
            },
        },
    }


# Verified URL shapes from tech_snapshot.md §3 — do not edit without re-verification.
PROBES: list[ModelProbe] = [
    ModelProbe(
        model_id="gemini-3.1-pro-preview",
        api_version="v1",
        verb_config=":generateContent (text)",
        body=_text_body(),
        notes="Pro reasoning enabled by default; MAX_TOKENS finish reason expected at maxOutputTokens=8",
    ),
    ModelProbe(
        model_id="gemini-3-flash-preview",
        api_version="v1beta1",
        verb_config=":generateContent (text)",
        body=_text_body(),
    ),
    ModelProbe(
        model_id="gemini-3.1-flash-lite-preview",
        api_version="v1beta1",
        verb_config=":generateContent (text)",
        body=_text_body(),
    ),
    ModelProbe(
        model_id="gemini-3-pro-image-preview",
        api_version="v1beta1",
        verb_config=":generateContent (IMAGE)",
        body=_image_body(),
        notes="Nano Banana Pro; expects inlineData.mimeType image/png",
    ),
    ModelProbe(
        model_id="gemini-3.1-flash-image-preview",
        api_version="v1beta1",
        verb_config=":generateContent (IMAGE)",
        body=_image_body(),
    ),
    ModelProbe(
        model_id="gemini-3.1-flash-tts-preview",
        api_version="v1beta1",
        verb_config=":generateContent (AUDIO, Charon)",
        body=_tts_body(),
        notes="Bare voice name 'Charon'; expects audio/l16",
    ),
]


def get_access_token() -> str:
    """Get a fresh access token via google-auth ADC. Refresh once."""
    creds, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    creds.refresh(google.auth.transport.requests.Request())
    if not creds.token:
        raise RuntimeError("google.auth returned creds but no token after refresh")
    return creds.token


def _response_is_non_empty_text(resp: dict[str, Any]) -> bool:
    """Accept both real text and MAX_TOKENS-empty (Pro reasoning eats the budget at maxOutputTokens=8)."""
    candidates = resp.get("candidates") or []
    if not candidates:
        return False
    for c in candidates:
        # MAX_TOKENS finish reason on Pro is acceptable per tech_snapshot.md §3
        if c.get("finishReason") in {"MAX_TOKENS", "STOP"}:
            return True
        parts = (c.get("content") or {}).get("parts") or []
        for p in parts:
            if p.get("text"):
                return True
    return False


def _response_has_image(resp: dict[str, Any]) -> bool:
    for c in resp.get("candidates") or []:
        parts = (c.get("content") or {}).get("parts") or []
        for p in parts:
            inline = p.get("inlineData") or p.get("inline_data")
            if inline and inline.get("mimeType", inline.get("mime_type", "")).startswith("image/"):
                return True
    return False


def _response_has_audio(resp: dict[str, Any]) -> bool:
    for c in resp.get("candidates") or []:
        parts = (c.get("content") or {}).get("parts") or []
        for p in parts:
            inline = p.get("inlineData") or p.get("inline_data")
            mime = (inline or {}).get("mimeType", (inline or {}).get("mime_type", ""))
            if inline and (mime.startswith("audio/") or "l16" in mime):
                return True
    return False


def probe_model(probe: ModelProbe, token: str) -> ProbeResult:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-Goog-User-Project": PROJECT,
    }
    started = time.time()
    try:
        r = requests.post(
            probe.url(),
            headers=headers,
            data=json.dumps(probe.body),
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException as e:
        return ProbeResult(
            label=probe.model_id,
            api_version=probe.api_version,
            verb_config=probe.verb_config,
            status="FAIL",
            latency_ms=int((time.time() - started) * 1000),
            error=f"network: {e}",
        )
    latency_ms = int((time.time() - started) * 1000)

    if r.status_code != 200:
        body_excerpt = r.text[:300].replace("\n", " ")
        return ProbeResult(
            label=probe.model_id,
            api_version=probe.api_version,
            verb_config=probe.verb_config,
            status="FAIL",
            latency_ms=latency_ms,
            error=f"HTTP {r.status_code}: {body_excerpt}",
        )

    try:
        body = r.json()
    except ValueError as e:
        return ProbeResult(
            label=probe.model_id,
            api_version=probe.api_version,
            verb_config=probe.verb_config,
            status="FAIL",
            latency_ms=latency_ms,
            error=f"non-JSON response: {e}",
        )

    # Modality-aware non-empty check.
    is_image = "IMAGE" in (probe.body.get("generationConfig", {}).get("responseModalities") or [])
    is_audio = "AUDIO" in (probe.body.get("generationConfig", {}).get("responseModalities") or [])

    if is_image:
        ok = _response_has_image(body)
        modality = "image"
    elif is_audio:
        ok = _response_has_audio(body)
        modality = "audio"
    else:
        ok = _response_is_non_empty_text(body)
        modality = "text"

    if not ok:
        return ProbeResult(
            label=probe.model_id,
            api_version=probe.api_version,
            verb_config=probe.verb_config,
            status="FAIL",
            latency_ms=latency_ms,
            error=f"200 but no {modality} content in response",
        )

    usage = body.get("usageMetadata") or {}
    notes = probe.notes
    if usage:
        bits = []
        for k in ("promptTokenCount", "candidatesTokenCount", "thoughtsTokenCount", "totalTokenCount"):
            if k in usage:
                bits.append(f"{k.replace('TokenCount','').replace('Count','')}={usage[k]}")
        if bits:
            notes = (notes + "; " if notes else "") + " ".join(bits)

    return ProbeResult(
        label=probe.model_id,
        api_version=probe.api_version,
        verb_config=probe.verb_config,
        status="OK",
        latency_ms=latency_ms,
        notes=notes,
        usage=usage,
    )


def probe_tts_catalog(token: str) -> ProbeResult:
    """Sanity-check the Cloud TTS catalog and count en-US-Chirp3-HD voices."""
    started = time.time()
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Goog-User-Project": PROJECT,
    }
    try:
        r = requests.get(
            f"{TTS_HOST}/v1/voices",
            headers=headers,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException as e:
        return ProbeResult(
            label="Cloud TTS catalog",
            api_version="v1",
            verb_config="GET /voices",
            status="FAIL",
            latency_ms=int((time.time() - started) * 1000),
            error=f"network: {e}",
        )
    latency_ms = int((time.time() - started) * 1000)

    if r.status_code != 200:
        return ProbeResult(
            label="Cloud TTS catalog",
            api_version="v1",
            verb_config="GET /voices",
            status="FAIL",
            latency_ms=latency_ms,
            error=f"HTTP {r.status_code}: {r.text[:200]}",
        )

    try:
        voices = (r.json().get("voices") or [])
    except ValueError as e:
        return ProbeResult(
            label="Cloud TTS catalog",
            api_version="v1",
            verb_config="GET /voices",
            status="FAIL",
            latency_ms=latency_ms,
            error=f"non-JSON: {e}",
        )

    chirp3_en_us = [v for v in voices if (v.get("name") or "").startswith("en-US-Chirp3-HD-")]
    count = len(chirp3_en_us)
    expected = 30

    if count != expected:
        return ProbeResult(
            label="Cloud TTS catalog",
            api_version="v1",
            verb_config="GET /voices",
            status="FAIL",
            latency_ms=latency_ms,
            error=f"expected {expected} en-US-Chirp3-HD voices, found {count}",
        )

    return ProbeResult(
        label="Cloud TTS catalog",
        api_version="v1",
        verb_config="GET /voices",
        status="OK",
        latency_ms=latency_ms,
        notes=f"found {count} en-US-Chirp3-HD-* voices (total={len(voices)})",
    )


def render_table(results: list[ProbeResult]) -> str:
    headers = ["MODEL_ID", "API_VERSION", "VERB_CONFIG", "STATUS", "LATENCY_MS", "NOTES"]
    rows = []
    for r in results:
        notes = r.notes if r.status == "OK" else (r.error or r.notes)
        rows.append([r.label, r.api_version, r.verb_config, r.status, str(r.latency_ms), notes])

    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(widths):
                widths[i] = max(widths[i], len(cell))
    # Cap notes column to keep one line readable.
    widths[-1] = min(widths[-1], 80)

    def fmt(row: list[str]) -> str:
        cells = []
        for i, cell in enumerate(row):
            w = widths[i]
            cells.append(cell[:w].ljust(w) if i == len(row) - 1 else cell.ljust(w))
        return " | ".join(cells)

    sep = "-+-".join("-" * w for w in widths)
    lines = [fmt(headers), sep]
    lines.extend(fmt(r) for r in rows)
    return "\n".join(lines)


def main() -> int:
    print(f"[verify_models] project={PROJECT} location={LOCATION}")
    try:
        token = get_access_token()
    except Exception as e:  # noqa: BLE001 — top-level surface
        print(f"FAIL: could not obtain access token via google.auth.default(): {e}", file=sys.stderr)
        print("Hint: run `gcloud auth application-default login` and `gcloud auth application-default set-quota-project predictive-fx-495200-j4`", file=sys.stderr)
        return 1

    results: list[ProbeResult] = []
    for probe in PROBES:
        print(f"[verify_models] probing {probe.model_id} ({probe.api_version}) ...")
        results.append(probe_model(probe, token))

    print("[verify_models] probing Cloud TTS catalog ...")
    results.append(probe_tts_catalog(token))

    print()
    print(render_table(results))
    print()

    fails = [r for r in results if r.status != "OK"]
    if fails:
        print(f"FAIL: {len(fails)}/{len(results)} probes failed.", file=sys.stderr)
        for r in fails:
            print(f"  - {r.label}: {r.error or 'unknown failure'}", file=sys.stderr)
        return 1

    print(f"OK: all {len(results)} probes passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
