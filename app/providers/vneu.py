from __future__ import annotations

import gc
import importlib.util
import json
from pathlib import Path

from app.providers.base import ProviderError, SynthesisResult, TTSProvider, Voice
from app.schemas import TTSRequest
from app.utils.audio import probe_duration


class VieNeuProvider(TTSProvider):
    provider_id = "vneu"

    def __init__(self, settings):
        super().__init__(settings)
        self._tts = None
        self._voice = None
        self._loaded_model_key: str | None = None
        self._current_voice_id: str | None = None

    def voices(self) -> list[Voice]:
        model_path = self._model_path()
        dependency_available = self._dependency_available()
        available = model_path is not None and dependency_available
        notes = self._voice_notes(model_path, dependency_available)
        voices = [
            Voice(
                voice_id="vneu:default",
                label="VieNeu Local Model",
                provider=self.provider_id,
                language="vi-VN",
                local_model=True,
                supports_formats=("wav",),
                available=available,
                notes=notes,
            )
        ]

        if model_path is not None:
            for voice_id, label in self._preset_voices(model_path):
                voices.append(
                    Voice(
                        voice_id=f"vneu:{voice_id}",
                        label=label,
                        provider=self.provider_id,
                        language="vi-VN",
                        local_model=True,
                        supports_formats=("wav",),
                        available=available,
                        notes=notes,
                    )
                )
        return voices

    def is_available(self, voice_id: str) -> bool:
        self._voice_by_id(voice_id)
        return self._model_path() is not None and self._dependency_available()

    async def unload(self, voice_id: str | None = None) -> None:
        await super().unload(voice_id)
        if voice_id is None or str(voice_id).startswith("vneu:"):
            if self._tts is not None and hasattr(self._tts, "close"):
                try:
                    self._tts.close()
                except Exception:
                    pass
            self._tts = None
            self._voice = None
            self._loaded_model_key = None
            self._current_voice_id = None
            gc.collect()

    async def preload_voice(self, voice_id: str) -> None:
        self._voice_by_id(voice_id)
        self._load_model(voice_id, {})
        self._loaded_voice_ids.add(voice_id)

    async def synthesize(self, request: TTSRequest, output_path: Path) -> SynthesisResult:
        voice = self._voice_by_id(request.voice_id)
        self._ensure_output_format(voice, request.output_format.value)
        tts = self._load_model(request.voice_id, request.provider_options)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        audio = tts.infer(text=request.text, voice=self._voice)
        tts.save(audio, str(output_path))
        self._loaded_voice_ids.add(request.voice_id)
        return SynthesisResult(
            output_path=output_path,
            duration=probe_duration(output_path),
            output_format="wav",
        )

    def _load_model(self, voice_id: str, options: dict):
        model_path = self._model_path()
        if model_path is None:
            raise ProviderError("VNEU_MODEL_PATH is not set or directory does not exist.")
        if not self._dependency_available():
            raise ProviderError(
                "VieNeu model needs the `vieneu` Python package installed in the Colab/runtime environment."
            )

        preset_id = self._preset_id_from_voice_id(voice_id)
        mode = str(options.get("mode", "standard"))
        device = str(options.get("device", "cuda" if self._cuda_available() else "cpu"))
        key = f"{model_path}|{mode}|{device}"
        if self._tts is not None and self._loaded_model_key == key:
            self._voice = self._tts.get_preset_voice(preset_id)
            self._current_voice_id = voice_id
            return self._tts

        try:
            from vieneu import Vieneu
        except Exception as exc:
            raise ProviderError(f"Could not import VieNeu dependency: {exc}") from exc

        self._tts = Vieneu(
            mode=mode,
            backbone_repo=str(model_path),
            backbone_device=device,
            codec_device=device,
        )
        self._voice = self._tts.get_preset_voice(preset_id)
        self._loaded_model_key = key
        self._current_voice_id = voice_id
        return self._tts

    def _model_path(self) -> Path | None:
        if not self.settings.vneu_model_path:
            return None
        path = Path(self.settings.vneu_model_path).expanduser()
        return path if path.is_dir() else None

    @staticmethod
    def _dependency_available() -> bool:
        return importlib.util.find_spec("vieneu") is not None

    @staticmethod
    def _cuda_available() -> bool:
        try:
            import torch

            return torch.cuda.is_available()
        except Exception:
            return False

    @staticmethod
    def _preset_id_from_voice_id(voice_id: str) -> str | None:
        raw = voice_id.split("vneu:", 1)[1] if voice_id.startswith("vneu:") else voice_id
        raw = raw.strip()
        return None if raw in {"", "default"} else raw

    @staticmethod
    def _preset_voices(model_path: Path) -> list[tuple[str, str]]:
        voices_json = model_path / "voices.json"
        if not voices_json.is_file():
            return []
        try:
            payload = json.loads(voices_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []

        presets = payload.get("presets", {})
        if not isinstance(presets, dict):
            return []

        result: list[tuple[str, str]] = []
        for voice_id, meta in presets.items():
            resolved = str(voice_id or "").strip()
            if not resolved:
                continue
            description = ""
            if isinstance(meta, dict):
                description = str(meta.get("description") or "").strip()
            result.append((resolved, description or resolved))
        return result

    @staticmethod
    def _voice_notes(model_path: Path | None, dependency_available: bool) -> str | None:
        if model_path is None:
            return "Set VNEU_MODEL_PATH to a VieNeu model folder, for example models/vieneu/ngoc_huyen."
        if not dependency_available:
            return "Install the `vieneu` package in this runtime before using VieNeu."
        return None
