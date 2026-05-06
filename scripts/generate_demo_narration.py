#!/usr/bin/env python3
"""One-shot CLI: generate the Mount Pleasant narration MP3 for the demo.

Mirrors `agents/narrator/` exactly (same model ID, same voice, same
sentence-by-sentence chunking, same inline-tag handling). The only
deviation: writes the resulting audio to a local `web/public/` path
as a single concatenated MP3 instead of uploading per-chunk WAVs to
GCS — this is a demo asset for the Next.js dev server, not a runtime
narration.

Voice: Algenib (HOE-DEC-025, pinned).
Model: gemini-3.1-flash-tts-preview (tech_snapshot §3).

Output: /web/public/fixture/narration-mount-pleasant.mp3

Cost: 5 paragraphs × ~30 sentences × short Pro TTS call ≈ ~$0.30 total.

Usage:
    .venv/bin/python scripts/generate_demo_narration.py
"""

from __future__ import annotations

import asyncio
import json
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import httpx  # type: ignore[import-untyped]

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# Reuse the Narrator's audio helpers — sentence splitting, WAV wrapping,
# duration estimation. These are the exact same functions the runtime
# uses (agents/narrator/audio.py).
from agents.narrator.audio import (  # noqa: E402
    estimate_audio_duration_ms,
    split_into_sentences,
    wrap_pcm_as_wav,
)
from agents.narrator.tts_client import parse_l16_rate  # noqa: E402

PROJECT = "predictive-fx-495200-j4"
LOCATION = "global"
TTS_MODEL = "gemini-3.1-flash-tts-preview"
API_VERSION = "v1beta1"
AUTH_SCOPE = "https://www.googleapis.com/auth/cloud-platform"
VOICE_NAME = "Algenib"  # HOE-DEC-025 — pinned for Broadcast Narrator.

OUTPUT_PATH = (
    REPO_ROOT / "web" / "public" / "fixture" / "narration-mount-pleasant.mp3"
)
FIXTURE_PATH = REPO_ROOT / "web" / "lib" / "story-fixture.ts"


# --- TS fixture parser -------------------------------------------------------


def load_body_paragraphs() -> list[str]:
    """Pull `body_paragraphs` from the TS fixture without a TS compiler.

    The fixture is hand-edited literal data; a regex over the
    `body_paragraphs: [...]` block + a JSON parse of the array contents is
    sufficient. We tolerate single-quoted strings and escape sequences.
    """
    src = FIXTURE_PATH.read_text(encoding="utf-8")
    m = re.search(
        r"body_paragraphs:\s*\[(?P<body>.*?)\],\s*pull_quote",
        src,
        re.DOTALL,
    )
    if not m:
        raise RuntimeError("could not locate body_paragraphs in fixture")
    block = m.group("body")
    # Match each "..." or '...' literal allowing escaped backslashes.
    paragraphs: list[str] = []
    for lit in re.finditer(r'"((?:[^"\\]|\\.)*)"|\'((?:[^\'\\]|\\.)*)\'', block):
        raw = lit.group(1) if lit.group(1) is not None else lit.group(2)
        # Unescape common JS escapes (\', \", \\, \n).
        cleaned = (
            raw.replace("\\'", "'")
            .replace('\\"', '"')
            .replace("\\\\", "\\")
            .replace("\\n", "\n")
        )
        paragraphs.append(cleaned)
    if not paragraphs:
        raise RuntimeError("body_paragraphs parsed empty")
    return paragraphs


# --- TTS auth + call --------------------------------------------------------


def get_access_token() -> str:
    import google.auth  # type: ignore[import-untyped]
    import google.auth.transport.requests  # type: ignore[import-untyped]

    creds, _ = google.auth.default(scopes=[AUTH_SCOPE])
    creds.refresh(google.auth.transport.requests.Request())
    if not creds.token:
        raise RuntimeError("google.auth returned creds but no token after refresh")
    return creds.token


def tts_url() -> str:
    return (
        f"https://aiplatform.googleapis.com/{API_VERSION}/projects/{PROJECT}"
        f"/locations/{LOCATION}/publishers/google/models/"
        f"{TTS_MODEL}:generateContent"
    )


def extract_audio(payload: dict) -> tuple[bytes, str]:
    """Walk candidates[0].content.parts for the first audio inlineData."""
    import base64

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
                return base64.b64decode(data_b64), mime
    raise RuntimeError(
        f"TTS response had no inlineData audio. payload keys: {sorted(payload.keys())}"
    )


async def synthesize_one(
    http: Any, token: str, text: str, *, timeout_s: float = 60.0
) -> tuple[bytes, str]:
    """Synthesize one sentence; return (pcm_bytes, mime_type)."""
    body = {
        "contents": [{"role": "user", "parts": [{"text": text}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {
                    "prebuiltVoiceConfig": {"voiceName": VOICE_NAME}
                }
            },
        },
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-Goog-User-Project": PROJECT,
    }
    response = await http.post(
        tts_url(), headers=headers, json=body, timeout=timeout_s
    )
    if response.status_code != 200:
        raise RuntimeError(
            f"TTS HTTP {response.status_code}: {response.text[:300]}"
        )
    payload = response.json()
    return extract_audio(payload)


# --- Narration assembly -----------------------------------------------------


def apply_inline_tags(sentences: list[str]) -> list[str]:
    """Append [short pause] to each sentence; [long pause] for paragraph
    boundaries. Mirrors NarratorAgent._apply_inline_tags but without the
    place-name [emphasis] wrap (the Mount Pleasant emphasis lives in the
    onscreen prose; the audio doesn't need to over-egg it).
    """
    out: list[str] = []
    for raw in sentences:
        paragraph_break = raw.endswith("​")
        text = raw.rstrip("​").strip()
        if not text:
            continue
        tag = "[long pause]" if paragraph_break else "[short pause]"
        out.append(f"{text} {tag}")
    return out


def build_sentences(paragraphs: list[str]) -> list[str]:
    """Sentence-split each paragraph; mark paragraph boundaries with
    a zero-width sentinel so apply_inline_tags can swap to [long pause].
    """
    sentences: list[str] = []
    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        para_sents = split_into_sentences(paragraph)
        if not para_sents:
            continue
        sentences.extend(para_sents)
        sentences[-1] = sentences[-1] + "​"  # zero-width sentinel
    return sentences


# --- Encoding ---------------------------------------------------------------


def write_wav(pcm_concat: bytes, sample_rate: int, dest: Path) -> None:
    wav = wrap_pcm_as_wav(
        pcm_concat, sample_rate=sample_rate, channels=1, sample_width=2
    )
    dest.write_bytes(wav)


def encode_mp3(wav_path: Path, mp3_path: Path) -> None:
    """ffmpeg WAV -> MP3 at 96 kbps mono (~1MB/min — broadcast-quality voice)."""
    if shutil.which("ffmpeg") is None:
        raise RuntimeError(
            "ffmpeg not found in PATH; cannot encode MP3. "
            "Install ffmpeg (`brew install ffmpeg`) and retry."
        )
    cmd = [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-i",
        str(wav_path),
        "-codec:a",
        "libmp3lame",
        "-b:a",
        "96k",
        "-ac",
        "1",
        str(mp3_path),
    ]
    subprocess.run(cmd, check=True)


def probe_duration_s(path: Path) -> float | None:
    """ffprobe -> duration in seconds. Returns None on failure."""
    if shutil.which("ffprobe") is None:
        return None
    try:
        out = subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=nw=1:nk=1",
                str(path),
            ],
            text=True,
        )
        return float(out.strip())
    except Exception:
        return None


# --- Main -------------------------------------------------------------------


async def amain() -> int:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    print(f"[generate_demo_narration] project={PROJECT} model={TTS_MODEL} voice={VOICE_NAME}")
    print(f"[generate_demo_narration] output={OUTPUT_PATH}")

    # Step 1: parse fixture body.
    paragraphs = load_body_paragraphs()
    print(f"[generate_demo_narration] paragraphs={len(paragraphs)}")

    # Step 2: sentence-split + apply pause tags.
    sentences_raw = build_sentences(paragraphs)
    sentences_for_tts = apply_inline_tags(sentences_raw)
    total_chars = sum(len(s) for s in sentences_for_tts)
    print(
        f"[generate_demo_narration] sentences={len(sentences_for_tts)} chars={total_chars}"
    )

    # Step 3: get access token + persistent http client.
    token = get_access_token()

    # Step 4: synthesize each chunk; concat raw PCM.
    pcm_buf = bytearray()
    sample_rate: int | None = None
    failures: list[tuple[int, str]] = []
    t0 = time.monotonic()
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as http:
        for idx, sentence in enumerate(sentences_for_tts):
            attempt_text = sentence
            for attempt in (1, 2):
                try:
                    pcm, mime = await synthesize_one(http, token, attempt_text)
                    rate = parse_l16_rate(mime, default=24000)
                    if sample_rate is None:
                        sample_rate = rate
                    elif rate != sample_rate:
                        # Don't expect this; if it happens we keep first rate.
                        print(
                            f"  ! sentence {idx} rate mismatch ({rate} vs {sample_rate}); keeping first"
                        )
                    pcm_buf.extend(pcm)
                    print(
                        f"  [{idx+1:02d}/{len(sentences_for_tts)}] {len(pcm)/1024:.0f}KB ({mime}) -- {attempt_text[:60]}{'...' if len(attempt_text)>60 else ''}"
                    )
                    break
                except Exception as e:
                    if attempt == 1:
                        # Retry with tags stripped (BUILD_SPEC §17.5).
                        attempt_text = re.sub(r"\[[^\[\]]*\]", "", sentence).strip()
                        print(f"  ! sentence {idx} attempt 1 failed ({e}); retrying without tags")
                        continue
                    failures.append((idx, str(e)))
                    print(f"  X sentence {idx} both attempts failed: {e}")
    elapsed = time.monotonic() - t0
    print(f"[generate_demo_narration] synthesis elapsed={elapsed:.1f}s pcm_bytes={len(pcm_buf):,}")

    if failures:
        # Hard fail — single sentence dropping out would noticeably break
        # the narration. Surface the failure and let HoE intervene.
        print("\n=== FAILURE ===")
        for idx, err in failures:
            print(f"  sentence {idx}: {err}")
        return 2

    if sample_rate is None or not pcm_buf:
        print("=== FAILURE: no audio synthesized ===")
        return 2

    # Step 5: encode WAV -> MP3.
    with tempfile.TemporaryDirectory() as tmpdir:
        wav_path = Path(tmpdir) / "narration.wav"
        write_wav(bytes(pcm_buf), sample_rate, wav_path)
        wav_size = wav_path.stat().st_size
        wav_duration_ms = estimate_audio_duration_ms(
            len(pcm_buf), sample_rate=sample_rate
        )
        print(f"[generate_demo_narration] wav={wav_size:,} bytes ({wav_duration_ms/1000:.1f}s estimated)")
        encode_mp3(wav_path, OUTPUT_PATH)

    mp3_size = OUTPUT_PATH.stat().st_size
    duration_s = probe_duration_s(OUTPUT_PATH)
    if duration_s is None:
        # Fall back to estimate.
        duration_s = wav_duration_ms / 1000.0

    in_target = 90.0 <= duration_s <= 180.0
    print(
        f"[generate_demo_narration] OK mp3={mp3_size:,} bytes duration={duration_s:.1f}s "
        f"target=90-180s in_target={in_target} -> {OUTPUT_PATH}"
    )
    print(json.dumps({
        "ok": True,
        "model": TTS_MODEL,
        "voice": VOICE_NAME,
        "synthesis_elapsed_s": round(elapsed, 1),
        "sentences": len(sentences_for_tts),
        "pcm_bytes": len(pcm_buf),
        "mp3_bytes": mp3_size,
        "duration_s": round(duration_s, 2),
        "path": str(OUTPUT_PATH.relative_to(REPO_ROOT)),
        "in_target_window_90_180": in_target,
    }))
    return 0


def main() -> int:
    return asyncio.run(amain())


if __name__ == "__main__":
    sys.exit(main())
