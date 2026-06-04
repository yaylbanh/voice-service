from __future__ import annotations

from pathlib import Path

from app.providers.base import ProviderError, SynthesisResult, TTSProvider, Voice
from app.schemas import TTSRequest
from app.utils.audio import generate_placeholder_wav


class PTHLocalProvider(TTSProvider):
    provider_id = "pth_local"

    def voices(self) -> list[Voice]:
        configured = bool(self.settings.pth_model_path)
        return [
            Voice(
                voice_id="pth:stub",
                label="PTH Stub WAV Test Voice",
                provider=self.provider_id,
                language="vi-VN",
                local_model=False,
                supports_formats=("wav",),
                available=True,
                notes="Synthetic WAV generator for API tests. It is not a real TTS model.",
            ),
            Voice(
                voice_id="pth:default",
                label="PTH Local Model",
                provider=self.provider_id,
                language="vi-VN",
                local_model=True,
                supports_formats=("wav",),
                available=False,
                notes=(
                    "Stub only. Set PTH_MODEL_PATH and implement the PTH adapter."
                    if configured
                    else "Stub only. Put model files under models/ and set PTH_MODEL_PATH."
                ),
            ),
        ]

    async def synthesize(self, request: TTSRequest, output_path: Path) -> SynthesisResult:
        voice = self._voice_by_id(request.voice_id)
        self._ensure_output_format(voice, request.output_format.value)
        if request.voice_id != "pth:stub":
            raise ProviderError(
                "PTH local provider is configured as a stub. Add the real model loader before using this voice."
            )

        await self.load_voice(request.voice_id)
        duration = generate_placeholder_wav(
            request.text,
            output_path,
            speed=request.speed,
            seed=request.seed,
            base_frequency=210.0,
        )
        return SynthesisResult(output_path=output_path, duration=duration, output_format="wav")

