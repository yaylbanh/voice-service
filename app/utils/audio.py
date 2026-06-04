from __future__ import annotations

import hashlib
import math
import struct
import wave
from pathlib import Path


def generate_placeholder_wav(
    text: str,
    output_path: Path,
    *,
    speed: float = 1.0,
    seed: int | None = None,
    base_frequency: float = 220.0,
) -> float:
    """Generate a small deterministic WAV file for API and pipeline testing."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    safe_speed = max(speed, 0.25)
    word_count = max(1, len(text.split()))
    duration = max(0.55, min(30.0, (word_count * 0.28) / safe_speed))
    sample_rate = 24_000
    sample_count = int(sample_rate * duration)
    digest = hashlib.sha256(f"{seed}:{text}".encode("utf-8")).digest()
    offset = int.from_bytes(digest[:2], "big") % 90
    carrier = base_frequency + offset
    amplitude = 0.22

    with wave.open(str(output_path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)

        for index in range(sample_count):
            t = index / sample_rate
            envelope = min(1.0, index / 1200, (sample_count - index) / 1200)
            cadence = 0.58 + 0.42 * math.sin(2 * math.pi * 4.0 * t)
            harmonic = 0.35 * math.sin(2 * math.pi * (carrier * 1.5) * t)
            sample = amplitude * envelope * cadence
            sample *= math.sin(2 * math.pi * carrier * t) + harmonic
            wav_file.writeframes(struct.pack("<h", int(sample * 32767)))

    return round(duration, 3)


def probe_wav_duration(path: Path) -> float | None:
    try:
        with wave.open(str(path), "rb") as wav_file:
            frames = wav_file.getnframes()
            rate = wav_file.getframerate()
            if rate <= 0:
                return None
            return round(frames / float(rate), 3)
    except Exception:
        return None


def probe_duration(path: Path) -> float | None:
    if path.suffix.lower() == ".wav":
        return probe_wav_duration(path)
    return None

