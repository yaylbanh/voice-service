from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.config import Settings
from app.schemas import TTSRequest


class ProviderError(RuntimeError):
    """Raised when a provider cannot synthesize a request."""


@dataclass(frozen=True)
class Voice:
    voice_id: str
    label: str
    provider: str
    language: str
    local_model: bool
    supports_formats: tuple[str, ...] = ("wav",)
    available: bool = True
    notes: str | None = None


@dataclass(frozen=True)
class SynthesisResult:
    output_path: Path
    duration: float | None
    output_format: str


class TTSProvider:
    provider_id = "base"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._loaded_voice_ids: set[str] = set()

    def voices(self) -> list[Voice]:
        raise NotImplementedError

    def is_loaded(self, voice_id: str) -> bool:
        return voice_id in self._loaded_voice_ids

    def is_available(self, voice_id: str) -> bool:
        return self._voice_by_id(voice_id).available

    def loaded_voice_ids(self) -> list[str]:
        return sorted(self._loaded_voice_ids)

    async def load_voice(self, voice_id: str) -> None:
        self._voice_by_id(voice_id)
        self._loaded_voice_ids.add(voice_id)

    async def preload_voice(self, voice_id: str) -> None:
        await self.load_voice(voice_id)

    async def unload(self, voice_id: str | None = None) -> None:
        if voice_id is None:
            self._loaded_voice_ids.clear()
            return
        self._loaded_voice_ids.discard(voice_id)

    async def synthesize(self, request: TTSRequest, output_path: Path) -> SynthesisResult:
        raise NotImplementedError

    def _voice_by_id(self, voice_id: str) -> Voice:
        for voice in self.voices():
            if voice.voice_id == voice_id:
                return voice
        raise ProviderError(f"Voice '{voice_id}' is not registered for provider '{self.provider_id}'.")

    def _ensure_output_format(self, voice: Voice, output_format: str) -> None:
        if output_format not in voice.supports_formats:
            supported = ", ".join(voice.supports_formats)
            raise ProviderError(
                f"Voice '{voice.voice_id}' does not support '{output_format}'. "
                f"Supported formats: {supported}."
            )
