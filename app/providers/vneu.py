from __future__ import annotations

from pathlib import Path

from app.providers.base import ProviderError, SynthesisResult, TTSProvider, Voice
from app.schemas import TTSRequest


class VieNeuProvider(TTSProvider):
    provider_id = "vneu"

    def voices(self) -> list[Voice]:
        configured = bool(self.settings.vneu_model_path)
        return [
            Voice(
                voice_id="vneu:default",
                label="VieNeu Local Model",
                provider=self.provider_id,
                language="vi-VN",
                local_model=True,
                supports_formats=("wav",),
                available=False,
                notes=(
                    "Stub only. VNEU_MODEL_PATH is set, but the model adapter is not implemented yet."
                    if configured
                    else "Stub only. Put VieNeu files under models/ and set VNEU_MODEL_PATH."
                ),
            )
        ]

    async def synthesize(self, request: TTSRequest, output_path: Path) -> SynthesisResult:
        self._voice_by_id(request.voice_id)
        raise ProviderError(
            "VieNeu provider is a stub in this scaffold. Add the real model loader before using this voice."
        )

