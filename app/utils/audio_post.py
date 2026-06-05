from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

from pydub import AudioSegment
from pydub.effects import compress_dynamic_range, normalize
from pydub.silence import detect_nonsilent


def _ffmpeg_atempo_chain(speed: float) -> str:
    factors = []
    value = max(0.25, min(4.0, float(speed or 1.0)))
    while value > 2.0:
        factors.append(2.0)
        value /= 2.0
    while value < 0.5:
        factors.append(0.5)
        value /= 0.5
    factors.append(value)
    return ",".join(f"atempo={factor:.6g}" for factor in factors)


def _speed_change_segment_ffmpeg(audio_segment: AudioSegment, speed: float) -> AudioSegment:
    if abs(float(speed or 1.0) - 1.0) <= 0.001:
        return audio_segment

    with tempfile.TemporaryDirectory(prefix="voice_service_audio_") as temp_dir:
        input_path = os.path.join(temp_dir, "input.wav")
        output_path = os.path.join(temp_dir, "output.wav")
        audio_segment.export(input_path, format="wav")
        command = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            input_path,
            "-filter:a",
            _ffmpeg_atempo_chain(speed),
            output_path,
        ]
        try:
            subprocess.run(command, check=True)
            return AudioSegment.from_file(output_path)
        except Exception:
            return audio_segment


def _auto_silence_thresh(segment: AudioSegment, offset_db: int = 18) -> float:
    if len(segment) == 0 or segment.dBFS == float("-inf"):
        return -45
    return max(-55, min(-28, segment.dBFS - offset_db))


def _trim_edge_silence(
    segment: AudioSegment,
    *,
    keep_ms: int = 25,
    chunk_ms: int = 5,
    silence_thresh: float | None = None,
) -> AudioSegment:
    if len(segment) == 0:
        return segment
    silence_thresh = _auto_silence_thresh(segment) if silence_thresh is None else silence_thresh

    start = 0
    while start < len(segment) and segment[start : start + chunk_ms].dBFS < silence_thresh:
        start += chunk_ms

    end = len(segment)
    while end > start and segment[end - chunk_ms : end].dBFS < silence_thresh:
        end -= chunk_ms

    start = max(0, start - keep_ms)
    end = min(len(segment), end + keep_ms)
    return segment[start:end] if end > start else segment


def _compress_internal_silence(
    segment: AudioSegment,
    *,
    max_silence_ms: int = 80,
    chunk_ms: int = 10,
    silence_thresh: float | None = None,
) -> AudioSegment:
    if len(segment) == 0 or max_silence_ms < 0:
        return segment
    silence_thresh = _auto_silence_thresh(segment) if silence_thresh is None else silence_thresh

    output = AudioSegment.empty()
    pos = 0
    silence_start = None
    index = 0

    while index < len(segment):
        chunk = segment[index : index + chunk_ms]
        if chunk.dBFS < silence_thresh:
            if silence_start is None:
                silence_start = index
        elif silence_start is not None:
            output += segment[pos:silence_start]
            silence_len = index - silence_start
            keep = min(silence_len, max_silence_ms)
            if keep > 0:
                output += AudioSegment.silent(duration=keep)
            pos = index
            silence_start = None
        index += chunk_ms

    if silence_start is not None:
        output += segment[pos:silence_start]
        keep = min(len(segment) - silence_start, max_silence_ms)
        if keep > 0:
            output += AudioSegment.silent(duration=keep)
    else:
        output += segment[pos:]
    return output


def _trim_tts_silence(
    segment: AudioSegment,
    *,
    keep_ms: int = 70,
    silence_db_offset: int = 18,
    min_silence_len: int = 80,
) -> AudioSegment:
    if len(segment) <= 0 or segment.dBFS == float("-inf"):
        return segment
    silence_thresh = max(-50, segment.dBFS - silence_db_offset)
    ranges = detect_nonsilent(
        segment,
        min_silence_len=min_silence_len,
        silence_thresh=silence_thresh,
        seek_step=5,
    )
    if not ranges:
        return segment
    start = max(0, ranges[0][0] - keep_ms)
    end = min(len(segment), ranges[-1][1] + keep_ms)
    return segment[start:end] if end > start else segment


def _master_audio(segment: AudioSegment, *, speed: float = 1.0, strong: bool = True) -> AudioSegment:
    segment = segment.high_pass_filter(90).low_pass_filter(10000)
    if strong:
        segment = compress_dynamic_range(segment, threshold=-20.0, ratio=3.0)
    segment = normalize(segment)
    segment = _speed_change_segment_ffmpeg(segment, speed)
    return normalize(segment)


def postprocess_tts_wav(path: Path, *, speed: float = 1.0, strong: bool = True) -> None:
    segment = AudioSegment.from_file(path)
    segment = _trim_tts_silence(segment, keep_ms=70)
    segment = _trim_edge_silence(segment, keep_ms=20)
    segment = _compress_internal_silence(segment, max_silence_ms=80)
    segment = _master_audio(segment, speed=speed, strong=strong)
    segment = segment.set_frame_rate(44100).set_channels(2)
    temp_path = path.with_suffix(path.suffix + ".post.tmp")
    segment.export(str(temp_path), format="wav")
    temp_path.replace(path)
