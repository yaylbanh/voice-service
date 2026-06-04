from __future__ import annotations

import importlib.util
from pathlib import Path

from app.providers.base import ProviderError, SynthesisResult, TTSProvider, Voice
from app.schemas import TTSRequest
from app.utils.audio import probe_duration


class EdgeTTSProvider(TTSProvider):
    provider_id = "edge_tts"

    def voices(self) -> list[Voice]:
        available = self._dependency_available()
        notes = None if available else "Install edge-tts to enable this provider."
        return [
            Voice(
                voice_id="edge:vi-VN-HoaiMyNeural",
                label="Microsoft Edge Vietnamese Female",
                provider=self.provider_id,
                language="vi-VN",
                local_model=False,
                supports_formats=("mp3",),
                available=available,
                notes=notes,
            ),
            Voice(
                voice_id="edge:vi-VN-NamMinhNeural",
                label="Microsoft Edge Vietnamese Male",
                provider=self.provider_id,
                language="vi-VN",
                local_model=False,
                supports_formats=("mp3",),
                available=available,
                notes=notes,
            ),
        ]

    def is_available(self, voice_id: str) -> bool:
        self._voice_by_id(voice_id)
        return self._dependency_available()

    async def synthesize(self, request: TTSRequest, output_path: Path) -> SynthesisResult:
        voice = self._voice_by_id(request.voice_id)
        self._ensure_output_format(voice, request.output_format.value)
        if not self._dependency_available():
            raise ProviderError("edge-tts is not installed. Run: pip install edge-tts")

        import edge_tts  # type: ignore

        await self.load_voice(request.voice_id)
        edge_voice = request.voice_id.split("edge:", 1)[1]
        rate = self._speed_to_rate(request.speed)
        communicate = edge_tts.Communicate(request.text, voice=edge_voice, rate=rate)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        await communicate.save(str(output_path))
        return SynthesisResult(
            output_path=output_path,
            duration=probe_duration(output_path),
            output_format=request.output_format.value,
        )

    @staticmethod
    def _dependency_available() -> bool:
        return importlib.util.find_spec("edge_tts") is not None

    @staticmethod
    def _speed_to_rate(speed: float) -> str:
        percent = max(-50, min(100, round((speed - 1.0) * 100)))
        return f"{percent:+d}%"

