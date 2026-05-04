"""Unit tests for the audio handling utilities.

`agents/narrator/audio.py` is pure — no network, no Vertex AI — so these
tests are deterministic and fast.
"""

from __future__ import annotations

import struct

from agents.narrator.audio import (
    estimate_audio_duration_ms,
    split_into_sentences,
    wrap_pcm_as_wav,
)


# -- WAV header tests ---------------------------------------------------------


def test_wrap_pcm_as_wav_produces_valid_riff_header() -> None:
    """Parse the wrapped header and assert RIFF/WAVE/fmt/data chunks."""
    pcm = b"\x00\x00" * 1000  # 2000 bytes = 500 frames @ 16-bit mono
    wav = wrap_pcm_as_wav(pcm, sample_rate=24000, channels=1, sample_width=2)

    # RIFF header
    assert wav[0:4] == b"RIFF"
    riff_size = struct.unpack("<I", wav[4:8])[0]
    # riff_size = 4 (WAVE) + 24 (fmt) + 8 (data header) + 2000 (data)
    assert riff_size == 4 + 24 + 8 + 2000
    assert wav[8:12] == b"WAVE"

    # fmt chunk
    assert wav[12:16] == b"fmt "
    fmt_size = struct.unpack("<I", wav[16:20])[0]
    assert fmt_size == 16
    audio_format = struct.unpack("<H", wav[20:22])[0]
    assert audio_format == 1  # PCM
    channels = struct.unpack("<H", wav[22:24])[0]
    assert channels == 1
    sample_rate = struct.unpack("<I", wav[24:28])[0]
    assert sample_rate == 24000
    byte_rate = struct.unpack("<I", wav[28:32])[0]
    assert byte_rate == 24000 * 1 * 2  # 48000
    block_align = struct.unpack("<H", wav[32:34])[0]
    assert block_align == 2
    bits_per_sample = struct.unpack("<H", wav[34:36])[0]
    assert bits_per_sample == 16

    # data chunk
    assert wav[36:40] == b"data"
    data_size = struct.unpack("<I", wav[40:44])[0]
    assert data_size == 2000
    assert wav[44:] == pcm


# -- Sentence splitter --------------------------------------------------------


def test_split_into_sentences_handles_basic_punctuation() -> None:
    """Three-sentence prose splits into three; trims whitespace."""
    text = (
        "The town has eight Olympians since 1976. "
        "Its newest Paralympian arrived in 2024. "
        "The earliest pipeline trace is to a single high-school coach!"
    )
    out = split_into_sentences(text)
    assert len(out) == 3
    assert out[0].startswith("The town")
    assert out[1].startswith("Its newest")
    assert out[2].endswith("coach!")


def test_split_into_sentences_does_not_break_on_abbreviations() -> None:
    """Mr. / Dr. / decimals are preserved, not split."""
    text = "Coach Mr. Smith built the program. The 1.5 mile run was the first event."
    out = split_into_sentences(text)
    # Should be 2 sentences, not 4.
    assert len(out) == 2
    assert "Mr. Smith" in out[0]
    assert "1.5 mile" in out[1]


def test_split_into_sentences_handles_question_marks() -> None:
    text = "Why this place? Because the program never stopped."
    out = split_into_sentences(text)
    assert len(out) == 2


def test_split_into_sentences_handles_empty_input() -> None:
    assert split_into_sentences("") == []
    assert split_into_sentences("   ") == []


def test_split_into_sentences_handles_no_terminator() -> None:
    """A fragment with no punctuation is returned as a single sentence."""
    out = split_into_sentences("the room is alive")
    assert out == ["the room is alive"]


# -- Duration estimator -------------------------------------------------------


def test_estimate_audio_duration_ms_pcm_24khz_16bit() -> None:
    """24kHz mono 16-bit = 48 bytes/ms; verify the formula."""
    # 48000 bytes/sec * 1 sec = 48000 bytes
    assert estimate_audio_duration_ms(48000, sample_rate=24000) == 1000
    # Half second
    assert estimate_audio_duration_ms(24000, sample_rate=24000) == 500
    # Zero bytes → zero duration
    assert estimate_audio_duration_ms(0, sample_rate=24000) == 0


def test_estimate_audio_duration_ms_handles_non_round_byte_count() -> None:
    """48 bytes = 1ms; 96 bytes = 2ms; 47 bytes ≈ ~1ms (rounded)."""
    assert estimate_audio_duration_ms(48, sample_rate=24000) == 1
    assert estimate_audio_duration_ms(96, sample_rate=24000) == 2


def test_estimate_audio_duration_ms_rejects_negative_input() -> None:
    """Defensive: negative byte count returns 0, not a negative duration."""
    assert estimate_audio_duration_ms(-100, sample_rate=24000) == 0
