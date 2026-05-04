"""Audio handling utilities for the Narrator.

Three helpers:
  - `wrap_pcm_as_wav`: minimal RIFF/WAV header for raw L16 PCM. Lifted
    verbatim from `scripts/list_tts_voices.py` (proven against real Gemini
    Flash TTS output).
  - `estimate_audio_duration_ms`: byte-count → milliseconds for raw PCM.
  - `split_into_sentences`: conservative sentence splitter (under-splits is
    preferred to over-splits).
"""

from __future__ import annotations

import re
import struct


# -- WAV wrapping --------------------------------------------------------------


def wrap_pcm_as_wav(
    pcm: bytes,
    sample_rate: int = 24000,
    channels: int = 1,
    sample_width: int = 2,
) -> bytes:
    """Wrap raw little-endian PCM (l16) bytes in a minimal RIFF/WAV header.

    Args:
        pcm: raw PCM bytes from Gemini TTS (`audio/l16; rate=24000; channels=1`).
        sample_rate: hertz; defaults to 24kHz (Gemini Flash TTS default).
        channels: 1 (mono) for Gemini TTS output.
        sample_width: 2 (16-bit signed) for L16 PCM.

    Returns:
        A complete WAV file as bytes (RIFF header + fmt chunk + data chunk),
        ready to write to a file or upload to Cloud Storage.

    Implementation lifted verbatim from `scripts/list_tts_voices.py` —
    proven against real Gemini Flash TTS output on Day-1.
    """
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


# -- Duration estimation -------------------------------------------------------


def estimate_audio_duration_ms(
    pcm_bytes: int,
    sample_rate: int = 24000,
    channels: int = 1,
    sample_width: int = 2,
) -> int:
    """Compute duration in ms from raw PCM byte count.

    formula: bytes / (sample_rate * channels * sample_width) seconds.

    For 24kHz mono 16-bit: 48,000 bytes/sec → ~20.83 ms/byte... no wait:
        bytes_per_ms = sample_rate * channels * sample_width / 1000
                     = 24000 * 1 * 2 / 1000 = 48 bytes/ms
        duration_ms = bytes / 48
    """
    if pcm_bytes <= 0:
        return 0
    bytes_per_second = sample_rate * channels * sample_width
    if bytes_per_second <= 0:
        return 0
    # Use integer math to keep results stable across platforms; round half-up.
    return int((pcm_bytes * 1000 + bytes_per_second // 2) // bytes_per_second)


# -- Sentence splitting --------------------------------------------------------


# Sentence-end matcher: terminator (. ! ?) NOT preceded by an abbreviation
# pattern, and followed by whitespace and (eventually) an uppercase letter or
# end-of-string. We use a non-greedy split rather than NLTK so the package
# stays stdlib-only.
#
# The regex's split points come from `_SENTENCE_END_PATTERN.finditer(text)` —
# split AFTER each match's terminator. This is a heuristic, not a full
# sentence parser. We accept under-splitting (longer sentences) over
# over-splitting; the BUILD_SPEC §5.6 docs note Storyteller writes ~25-40
# sentences per 400-700 word story, so a few merged adjacent sentences are
# fine.
_SENTENCE_END_PATTERN = re.compile(
    r"""
    (?<![A-Z][a-z])           # don't break on "Mr.", "Dr." (one upper + one lower)
    (?<![A-Z][a-z][a-z])      # don't break on "Mrs.", "Ave."
    (?<!\b[A-Z])              # don't break on a single capital initial like "U."
    (?<!\d\.\d)               # don't break inside decimals like "1.5"
    [.!?]+                    # one or more terminators
    (?:["\)\]'`]+)?           # optional trailing close-quotes / brackets
    (?=\s+[A-Z\[\(\"]|\s*$)   # followed by whitespace + capital / bracket / quote, or EOS
    """,
    re.VERBOSE,
)


def split_into_sentences(text: str) -> list[str]:
    """Split prose into sentences.

    Heuristic: split on `. ! ?` boundaries that look like real sentence ends
    (not abbreviations, not decimals, not initials). Returns a list of
    trimmed sentences with no empty strings.

    Args:
        text: source prose. May contain Gemini TTS inline tags like
            `[short pause]` which are preserved (the splitter doesn't strip
            them — the Narrator may want them back at synthesis time).

    Returns:
        List of sentences. Empty input → empty list.
    """
    if not text:
        return []
    s = text.strip()
    if not s:
        return []

    sentences: list[str] = []
    last_end = 0
    for m in _SENTENCE_END_PATTERN.finditer(s):
        end = m.end()
        chunk = s[last_end:end].strip()
        if chunk:
            sentences.append(chunk)
        last_end = end
    # Trailing fragment with no terminator: keep it as a sentence.
    tail = s[last_end:].strip()
    if tail:
        sentences.append(tail)
    # Defensive: some texts have nothing matched (no terminators at all). In
    # that case, return the whole string as a single sentence.
    if not sentences:
        sentences = [s]
    return sentences
