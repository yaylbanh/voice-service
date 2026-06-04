from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

from app.config import Settings
from app.providers.base import ProviderError, SynthesisResult, TTSProvider
from app.providers.edge_tts import EdgeTTSProvider
from app.providers.pth_local import PTHLocalProvider
from app.providers.tiktok_tts import TikTokTTSProvider
from app.providers.vneu import VieNeuProvider
from app.providers.zhaodi import ZhaodiProvider
from app.schemas import TTSRequest, VoiceInfo
from app.utils.paths import make_output_filename


class ModelManager:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.providers: dict[str, TTSProvider] = {}
        self.voice_to_provider: dict[str, str] = {}
        self.preload_status: dict[str, Any] = {
            "mode": settings.preload_voices,
            "started": False,
            "completed": False,
            "voices": {},
            "errors": {},
        }
        self._register_provider(EdgeTTSProvider(settings))
        self._register_provider(TikTokTTSProvider(settings))
        self._register_provider(PTHLocalProvider(settings))
        self._register_provider(VieNeuProvider(settings))
        self._register_provider(ZhaodiProvider(settings))

    def list_voices(self) -> list[VoiceInfo]:
        voices: list[VoiceInfo] = []
        for provider in self.providers.values():
            for voice in provider.voices():
                payload = asdict(voice)
                payload["loaded"] = provider.is_loaded(voice.voice_id)
                payload["available"] = provider.is_available(voice.voice_id)
                payload.pop("supports_formats", None)
                voices.append(VoiceInfo(**payload))
        return voices

    def loaded_summary(self) -> dict[str, list[str]]:
        return {
            provider_id: provider.loaded_voice_ids()
            for provider_id, provider in self.providers.items()
            if provider.loaded_voice_ids()
        }

    async def preload_startup_voices(self) -> None:
        voice_ids = self._preload_voice_ids()
        self.preload_status = {
            "mode": self.settings.preload_voices,
            "started": True,
            "completed": False,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "voices": {voice_id: "pending" for voice_id in voice_ids},
            "errors": {},
        }

        started = perf_counter()
        for voice_id in voice_ids:
            provider_id = self.provider_id_for_voice(voice_id)
            if provider_id is None:
                self.preload_status["voices"][voice_id] = "skipped"
                self.preload_status["errors"][voice_id] = "Voice is not registered."
                continue

            try:
                await self.providers[provider_id].preload_voice(voice_id)
                self.preload_status["voices"][voice_id] = "loaded"
            except Exception as exc:
                self.preload_status["voices"][voice_id] = "error"
                self.preload_status["errors"][voice_id] = str(exc)

        self.preload_status["completed"] = True
        self.preload_status["completed_at"] = datetime.now(timezone.utc).isoformat()
        self.preload_status["elapsed_seconds"] = round(perf_counter() - started, 3)

    def provider_id_for_voice(self, voice_id: str) -> str | None:
        return self.voice_to_provider.get(voice_id)

    async def unload(self, provider_id: str | None = None, voice_id: str | None = None) -> None:
        if provider_id is not None:
            provider = self.providers.get(provider_id)
            if provider is None:
                raise ProviderError(f"Provider '{provider_id}' is not registered.")
            await provider.unload(voice_id)
            return

        for provider in self.providers.values():
            await provider.unload(voice_id)

    async def synthesize(self, request: TTSRequest) -> tuple[SynthesisResult, str]:
        provider_id = self.provider_id_for_voice(request.voice_id)
        if provider_id is None:
            raise ProviderError(f"Voice '{request.voice_id}' is not registered.")

        provider = self.providers[provider_id]
        file_name = make_output_filename(request.voice_id, request.output_format.value)
        output_path = Path(self.settings.output_dir) / file_name
        result = await provider.synthesize(request, output_path)
        return result, provider_id

    def _register_provider(self, provider: TTSProvider) -> None:
        if provider.provider_id in self.providers:
            raise RuntimeError(f"Provider '{provider.provider_id}' is already registered.")
        self.providers[provider.provider_id] = provider
        for voice in provider.voices():
            if voice.voice_id in self.voice_to_provider:
                raise RuntimeError(f"Voice '{voice.voice_id}' is already registered.")
            self.voice_to_provider[voice.voice_id] = provider.provider_id

    def _preload_voice_ids(self) -> list[str]:
        mode = (self.settings.preload_voices or "auto").strip()
        if not mode or mode.lower() in {"0", "false", "no", "none", "off"}:
            return []

        if mode.lower() in {"auto", "all"}:
            return [
                voice.voice_id
                for voice in self.list_voices()
                if voice.available and voice.local_model
            ]

        requested = [item.strip() for item in mode.split(",") if item.strip()]
        available = {voice.voice_id for voice in self.list_voices() if voice.available}
        return [voice_id for voice_id in requested if voice_id in available]
