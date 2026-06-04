from __future__ import annotations

from pathlib import Path

from app.providers.base import ProviderError, SynthesisResult, TTSProvider, Voice
from app.schemas import TTSRequest


class ZhaodiProvider(TTSProvider):
    provider_id = "zhaodi"

    def voices(self) -> list[Voice]:
        configured = bool(self.settings.zhaodi_model_path)
        return [
            Voice(
                voice_id="zhaodi:default",
                label="Zhaodi Local Model",
                provider=self.provider_id,
                language="zh-CN",
                local_model=True,
                supports_formats=("wav",),
                available=False,
                notes=(
                    "Stub only. ZHAODI_MODEL_PATH is set, but the model adapter is not implemented yet."
                    if configured
                    else "Stub only. Put Zhaodi files under models/ and set ZHAODI_MODEL_PATH."
                ),
            )
        ]

    async def synthesize(self, request: TTSRequest, output_path: Path) -> SynthesisResult:
        self._voice_by_id(request.voice_id)
        raise ProviderError(
            "Zhaodi provider is a stub in this scaffold. Add the real model loader before using this voice."
        )

