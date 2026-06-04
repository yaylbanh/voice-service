from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class OutputFormat(str, Enum):
    wav = "wav"
    mp3 = "mp3"


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1)
    voice_id: str = Field(..., min_length=1)
    language: str | None = None
    speed: float = Field(default=1.0, ge=0.25, le=4.0)
    output_format: OutputFormat = OutputFormat.wav
    seed: int | None = None
    provider_options: dict[str, Any] = Field(default_factory=dict)
    extra: dict[str, Any] = Field(default_factory=dict)


class TTSBatchItem(TTSRequest):
    item_id: str | None = None


class TTSBatchRequest(BaseModel):
    items: list[TTSBatchItem] = Field(..., min_length=1)


class TTSResponse(BaseModel):
    success: bool
    audio_url: str | None = None
    audio_path: str | None = None
    duration: float | None = None
    voice_id: str
    provider: str
    error: str | None = None


class TTSBatchItemResponse(TTSResponse):
    item_id: str | None = None


class TTSBatchResponse(BaseModel):
    success: bool
    results: list[TTSBatchItemResponse]


class VoiceInfo(BaseModel):
    voice_id: str
    label: str
    provider: str
    language: str
    local_model: bool
    loaded: bool | None = None
    available: bool = True
    notes: str | None = None


class VoicesResponse(BaseModel):
    success: bool
    voices: list[VoiceInfo]


class HealthResponse(BaseModel):
    success: bool
    device: str
    version: str
    loaded: dict[str, list[str]]

