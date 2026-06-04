from __future__ import annotations

from pathlib import Path

from app.providers.base import ProviderError, SynthesisResult, TTSProvider, Voice
from app.schemas import TTSRequest


class TikTokTTSProvider(TTSProvider):
    provider_id = "tiktok_tts"

    def voices(self) -> list[Voice]:
        return [
            Voice(
                voice_id="tiktok:vi_female_01",
                label="TikTok Vietnamese Female",
                provider=self.provider_id,
                language="vi-VN",
                local_model=False,
                supports_formats=("mp3",),
                available=False,
                notes="Stub only. Add a TikTok TTS adapter or dependency before using.",
            )
        ]

    async def synthesize(self, request: TTSRequest, output_path: Path) -> SynthesisResult:
        self._voice_by_id(request.voice_id)
        raise ProviderError(
            "TikTok provider is a stub in this scaffold. Add the real adapter before using this voice."
        )

