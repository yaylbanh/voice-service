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
        self._models = {}
        self._voice = None
        self._current_voice_id: str | None = None

    def voices(self) -> list[Voice]:
        model_paths = self._model_paths()
        primary_model_path = self._primary_model_path(model_paths)
        dependency_available = self._dependency_available()
        available = bool(model_paths) and dependency_available
        notes = self._voice_notes(model_paths, dependency_available)
        voices = [
            Voice(
                voice_id="vneu:default",
                label=(
                    f"VieNeu Default [{primary_model_path.name}]"
                    if primary_model_path is not None
                    else "VieNeu Local Model"
                ),
                provider=self.provider_id,
                language="vi-VN",
                local_model=True,
                supports_formats=("wav",),
                available=available,
                notes=notes,
            )
        ]

        if primary_model_path is not None:
            for voice_id, label in self._preset_voices(primary_model_path):
                voices.append(
                    Voice(
                        voice_id=f"vneu:{voice_id}",
                        label=f"{label} [{primary_model_path.name}]",
                        provider=self.provider_id,
                        language="vi-VN",
                        local_model=True,
                        supports_formats=("wav",),
                        available=available,
                        notes=notes,
                    )
                )

        for model_path in model_paths:
            if primary_model_path is not None and model_path.resolve() == primary_model_path.resolve():
                continue
            for voice_id, label in self._preset_voices(model_path):
                voices.append(
                    Voice(
                        voice_id=f"vneu:{model_path.name}:{voice_id}",
                        label=f"{label} [{model_path.name}]",
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
        return bool(self._model_paths()) and self._dependency_available()

    async def unload(self, voice_id: str | None = None) -> None:
        await super().unload(voice_id)
        if voice_id is None or str(voice_id).startswith("vneu:"):
            for tts in self._models.values():
                try:
                    if hasattr(tts, "close"):
                        tts.close()
                except Exception:
                    pass
            self._models = {}
            self._voice = None
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
        model_path, preset_id = self._resolve_voice_id(voice_id)
        if model_path is None:
            raise ProviderError(
                "VNEU_MODEL_PATH/ZHAODI_MODEL_PATH is not set or no valid VieNeu model folder exists."
            )
        if not self._dependency_available():
            raise ProviderError(
                "VieNeu model needs the `vieneu` Python package installed in the Colab/runtime environment."
            )

        mode = str(options.get("mode", "standard"))
        device = str(options.get("device", "cuda" if self._cuda_available() else "cpu"))
        key = f"{model_path}|{mode}|{device}"
        if key not in self._models:
            try:
                from vieneu import Vieneu
            except Exception as exc:
                raise ProviderError(f"Could not import VieNeu dependency: {exc}") from exc

            self._models[key] = Vieneu(
                mode=mode,
                backbone_repo=str(model_path),
                backbone_device=device,
                codec_device=device,
            )

        tts = self._models[key]
        self._voice = tts.get_preset_voice(preset_id)
        self._current_voice_id = voice_id
        return tts

    def _configured_model_path(self) -> Path | None:
        if not self.settings.vneu_model_path:
            return None
        path = Path(self.settings.vneu_model_path).expanduser()
        return path if self._is_valid_model_dir(path) else None

    def _model_paths(self) -> list[Path]:
        paths: list[Path] = []

        configured = self._configured_model_path()
        if configured is not None:
            paths.append(configured)

        root_raw = self.settings.zhaodi_model_path
        if root_raw:
            root = Path(root_raw).expanduser()
            if root.is_dir():
                candidates = [item for item in root.iterdir() if item.is_dir()]
                candidates.extend(path.parent for path in root.rglob("voices.json"))
                for candidate in sorted(candidates, key=lambda item: str(item).lower()):
                    if not self._is_valid_model_dir(candidate):
                        continue
                    if candidate.name.endswith("_gguf"):
                        non_gguf_name = candidate.name.removesuffix("_gguf")
                        if (candidate.parent / non_gguf_name).is_dir():
                            continue
                    paths.append(candidate)

        result: list[Path] = []
        seen: set[str] = set()
        for path in paths:
            try:
                key = str(path.resolve())
            except OSError:
                key = str(path.absolute())
            if key in seen:
                continue
            seen.add(key)
            result.append(path)
        return result

    def _primary_model_path(self, model_paths: list[Path] | None = None) -> Path | None:
        configured = self._configured_model_path()
        if configured is not None:
            return configured
        model_paths = model_paths if model_paths is not None else self._model_paths()
        return model_paths[0] if model_paths else None

    def _resolve_voice_id(self, voice_id: str) -> tuple[Path | None, str | None]:
        model_paths = self._model_paths()
        primary_model_path = self._primary_model_path(model_paths)
        raw = voice_id.split("vneu:", 1)[1] if voice_id.startswith("vneu:") else voice_id
        raw = raw.strip()

        if raw in {"", "default"}:
            return primary_model_path, None

        if ":" in raw:
            model_name, preset_id = raw.split(":", maxsplit=1)
            for model_path in model_paths:
                if model_path.name == model_name:
                    return model_path, preset_id.strip() or None

        return primary_model_path, raw

    @staticmethod
    def _dependency_available() -> bool:
        return importlib.util.find_spec("vieneu") is not None

    @staticmethod
    def _is_valid_model_dir(path: Path) -> bool:
        if not path.is_dir() or not (path / "voices.json").is_file():
            return False
        return (path / "model.safetensors").is_file() or any(path.glob("*.gguf"))

    @staticmethod
    def _cuda_available() -> bool:
        try:
            import torch

            return torch.cuda.is_available()
        except Exception:
            return False

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
    def _voice_notes(model_paths: list[Path], dependency_available: bool) -> str | None:
        if not model_paths:
            return (
                "Set VNEU_MODEL_PATH to one VieNeu model folder or ZHAODI_MODEL_PATH "
                "to models/vieneu."
            )
        if not dependency_available:
            return "Install the `vieneu` package in this runtime before using VieNeu."
        return None
