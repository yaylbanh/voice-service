from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

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

