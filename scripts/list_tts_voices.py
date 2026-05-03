#!/usr/bin/env python3
"""Day-1 voice audition harness for Broadcast Narrator + Wire Dispatcher.

Step 1: enumerate the 30 en-US-Chirp3-HD-* voices from the Cloud TTS catalog.
Step 2: for 6 curated candidates (3 Narrator, 3 Dispatcher), generate a 30-second
TTS sample reading the same Broadcast paragraph via Vertex AI gemini-3.1-flash-tts-preview
so Charlie can A/B audition with identical content. Saves WAV files to
audio/voice_audition/. Does NOT pick a voice — that's a human listening exercise.

(HOE-DEC-017, BUILD_SPEC §3.5.)
"""

from __future__ import annotations

import base64
import json
import os
import re
import struct
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import google.auth
import google.auth.transport.requests
import requests

PROJECT = "predictive-fx-495200-j4"
LOCATION = "global"
AIPLATFORM_HOST = "https://aiplatform.googleapis.com"
TTS_HOST = "https://texttospeech.googleapis.com"
TTS_MODEL = "gemini-3.1-flash-tts-preview"
TTS_API_VERSION = "v1beta1"
REQUEST_TIMEOUT_SECONDS = 120

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "audio" / "voice_audition"

# Place-only sample text. Reviewed for NIL/branding; no athlete names. Inline
# tags exercise the [short pause] and [emphasis] controls per tech_snapshot §5.
SAMPLE_TEXT = (
    "Every Team USA athlete comes from somewhere. [short pause] "
    "The town of Mount Pleasant, Iowa, has produced [emphasis] eight Olympians "
    "and Paralympians [/emphasis] since 1976. [short pause] "
    "The earliest pipeline trace is to a single high-school coach who built the "
    "program from nothing. [short pause] "
    "The newest Paralympian from the region competed in 2024. [short pause] "
    "This is what the room finds."
)


@dataclass
class VoiceCandidate:
    name: str  # bare name, e.g. "Charon"
    profile: str  # "Broadcast Narrator" | "Wire Dispatcher"
    note: str  # what we're listening for


# 3 Narrator + 3 Dispatcher = 6 candidates. Mix from each pool per tech_snapshot
# notes: Narrator candidates Charon/Algenib/Iapetus/Schedar; Dispatcher
# candidates Puck/Fenrir/Orus/Umbriel.
CANDIDATES: list[VoiceCandidate] = [
    VoiceCandidate("Charon", "Broadcast Narrator", "warm mid-tone, documentary register (v1.2 placeholder)"),
    VoiceCandidate("Algenib", "Broadcast Narrator", "alternate warm/mid-tone candidate"),
    VoiceCandidate("Iapetus", "Broadcast Narrator", "alternate warm/lower-mid candidate"),
    VoiceCandidate("Puck", "Wire Dispatcher", "clipped, control-room (v1.2 placeholder)"),
    VoiceCandidate("Fenrir", "Wire Dispatcher", "lower-register dispatcher alternate"),
    VoiceCandidate("Orus", "Wire Dispatcher", "clipped/radio dispatcher alternate"),
]


def get_access_token() -> str:
    creds, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    creds.refresh(google.auth.transport.requests.Request())
    if not creds.token:
        raise RuntimeError("google.auth returned creds but no token after refresh")
    return creds.token


def list_chirp3_voices(token: str) -> list[dict[str, Any]]:
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Goog-User-Project": PROJECT,
    }
    r = requests.get(f"{TTS_HOST}/v1/voices", headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
    r.raise_for_status()
    voices = r.json().get("voices") or []
    return [v for v in voices if (v.get("name") or "").startswith("en-US-Chirp3-HD-")]


def tts_generate(token: str, voice_name: str, text: str) -> tuple[bytes, str]:
    """Generate audio via Vertex AI Gemini Flash TTS. Returns (raw_bytes, mime_type)."""
    url = (
        f"{AIPLATFORM_HOST}/{TTS_API_VERSION}/projects/{PROJECT}"
        f"/locations/{LOCATION}/publishers/google/models/{TTS_MODEL}:generateContent"
    )
    body = {
        "contents": [{"role": "user", "parts": [{"text": text}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice_name}}
            },
        },
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-Goog-User-Project": PROJECT,
    }
    r = requests.post(url, headers=headers, data=json.dumps(body), timeout=REQUEST_TIMEOUT_SECONDS)
    if r.status_code != 200:
        raise RuntimeError(f"TTS HTTP {r.status_code}: {r.text[:300]}")
    payload = r.json()
    for c in payload.get("candidates") or []:
        for p in (c.get("content") or {}).get("parts") or []:
            inline = p.get("inlineData") or p.get("inline_data")
            if not inline:
                continue
            mime = inline.get("mimeType") or inline.get("mime_type") or ""
            data_b64 = inline.get("data")
            if data_b64:
                return base64.b64decode(data_b64), mime
    raise RuntimeError(f"TTS response had no inlineData audio. payload keys: {list(payload.keys())}")


def _parse_l16_rate(mime: str) -> int:
    """Pull rate=NNNN out of a mime like 'audio/l16; rate=24000; channels=1'."""
    m = re.search(r"rate\s*=\s*(\d+)", mime)
    return int(m.group(1)) if m else 24000


def wrap_pcm_as_wav(pcm: bytes, sample_rate: int, channels: int = 1, sample_width: int = 2) -> bytes:
    """Wrap raw little-endian PCM (l16) bytes in a minimal RIFF/WAV header."""
    byte_rate = sample_rate * channels * sample_width
    block_align = channels * sample_width
    data_size = len(pcm)
    fmt_chunk = struct.pack(
        "<4sIHHIIHH",
        b"fmt ",
        16,  # fmt chunk size
        1,  # PCM format
        channels,
        sample_rate,
        byte_rate,
        block_align,
        sample_width * 8,
    )
    data_chunk = struct.pack("<4sI", b"data", data_size) + pcm
    riff_size = 4 + len(fmt_chunk) + len(data_chunk)
    riff = struct.pack("<4sI4s", b"RIFF", riff_size, b"WAVE")
    return riff + fmt_chunk + data_chunk


def save_audio(audio: bytes, mime: str, voice_name: str) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if "l16" in mime or mime.startswith("audio/l16") or mime.startswith("audio/pcm"):
        rate = _parse_l16_rate(mime)
        wav = wrap_pcm_as_wav(audio, sample_rate=rate)
        path = OUTPUT_DIR / f"{voice_name}.wav"
        path.write_bytes(wav)
    elif "mpeg" in mime or "mp3" in mime:
        path = OUTPUT_DIR / f"{voice_name}.mp3"
        path.write_bytes(audio)
    elif "wav" in mime:
        path = OUTPUT_DIR / f"{voice_name}.wav"
        path.write_bytes(audio)
    else:
        ext = mime.split("/")[-1].split(";")[0].strip() or "bin"
        path = OUTPUT_DIR / f"{voice_name}.{ext}"
        path.write_bytes(audio)
    return path


def main() -> int:
    print(f"[list_tts_voices] project={PROJECT} location={LOCATION}")
    print(f"[list_tts_voices] output dir: {OUTPUT_DIR}")

    try:
        token = get_access_token()
    except Exception as e:  # noqa: BLE001
        print(f"FAIL: could not obtain access token: {e}", file=sys.stderr)
        print(
            "Hint: run `gcloud auth application-default login` and "
            "`gcloud auth application-default set-quota-project predictive-fx-495200-j4`",
            file=sys.stderr,
        )
        return 1

    # Step 1: enumerate Chirp3 voices.
    print("\n=== Step 1: en-US-Chirp3-HD-* catalog ===")
    try:
        voices = list_chirp3_voices(token)
    except requests.RequestException as e:
        print(f"FAIL: TTS catalog fetch failed: {e}", file=sys.stderr)
        return 1
    if not voices:
        print("FAIL: zero en-US-Chirp3-HD voices returned", file=sys.stderr)
        return 1
    for v in sorted(voices, key=lambda x: x.get("name", "")):
        print(f"  {v.get('name')}  ({v.get('ssmlGender', 'UNSPECIFIED')})")
    print(f"  total: {len(voices)} voices")

    available = {v.get("name") for v in voices}
    missing = [c for c in CANDIDATES if f"en-US-Chirp3-HD-{c.name}" not in available]
    if missing:
        names = ", ".join(c.name for c in missing)
        print(f"\nWARNING: candidates not in catalog: {names}", file=sys.stderr)

    # Step 2: generate 30-second samples for each candidate.
    print("\n=== Step 2: generating 30s audition samples ===")
    saved: list[tuple[VoiceCandidate, Path]] = []
    failures: list[tuple[VoiceCandidate, str]] = []
    for c in CANDIDATES:
        print(f"  -> {c.name} ({c.profile})...", end=" ", flush=True)
        started = time.time()
        try:
            audio, mime = tts_generate(token, c.name, SAMPLE_TEXT)
            path = save_audio(audio, mime, c.name)
            saved.append((c, path))
            print(f"OK {len(audio)} bytes ({mime}) -> {path.name} [{int((time.time()-started)*1000)}ms]")
        except Exception as e:  # noqa: BLE001
            failures.append((c, str(e)))
            print(f"FAIL: {e}")

    # Summary.
    print("\n=== Summary ===")
    if saved:
        print("Saved samples (open in audio/voice_audition/ for A/B audition):")
        for c, p in saved:
            print(f"  [{c.profile}] {c.name:<10} -> {p}")
            print(f"      profile target: {c.note}")
    if failures:
        print("\nFailures:")
        for c, err in failures:
            print(f"  - {c.name} ({c.profile}): {err}")
        return 1

    print(
        "\nNext step: Charlie listens to the 6 samples and picks Broadcast Narrator + "
        "Wire Dispatcher voice strings. Pin the picks into BUILD_SPEC §3.5 and §5.6."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
