from __future__ import annotations

import csv
import gc
import importlib.util
import re
from pathlib import Path

from app.providers.base import ProviderError, SynthesisResult, TTSProvider, Voice
from app.schemas import TTSRequest
from app.utils.audio import generate_placeholder_wav, probe_duration


class PTHLocalProvider(TTSProvider):
    provider_id = "pth_local"

    def __init__(self, settings):
        super().__init__(settings)
        self._tts = None
        self._loaded_model_key: str | None = None
        self._patterns: list[tuple[re.Pattern[str], str]] = []

    def voices(self) -> list[Voice]:
        model_path = self._model_path()
        config_path = self._config_path()
        configured = model_path is not None and config_path is not None
        dependency_available = self._dependency_available()
        real_notes = self._real_voice_notes(model_path, config_path, dependency_available)
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
                available=configured and dependency_available,
                notes=real_notes,
            ),
        ]

    def is_available(self, voice_id: str) -> bool:
        voice = self._voice_by_id(voice_id)
        if voice.voice_id == "pth:stub":
            return True
        return self._model_path() is not None and self._config_path() is not None and self._dependency_available()

    async def unload(self, voice_id: str | None = None) -> None:
        await super().unload(voice_id)
        if voice_id in {None, "pth:default"}:
            self._tts = None
            self._loaded_model_key = None
            self._patterns = []
            gc.collect()
            try:
                import torch

                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:
                pass

    async def synthesize(self, request: TTSRequest, output_path: Path) -> SynthesisResult:
        voice = self._voice_by_id(request.voice_id)
        self._ensure_output_format(voice, request.output_format.value)
        if request.voice_id == "pth:stub":
            await self.load_voice(request.voice_id)
            duration = generate_placeholder_wav(
                request.text,
                output_path,
                speed=request.speed,
                seed=request.seed,
                base_frequency=210.0,
            )
            return SynthesisResult(output_path=output_path, duration=duration, output_format="wav")

        tts = self._load_real_model(request)
        clean_text = self._process_text(request.text)
        noise_scale = float(request.provider_options.get("noise_scale", 0.6))
        length_scale = float(request.provider_options.get("length_scale", 1.0 / request.speed))

        output_path.parent.mkdir(parents=True, exist_ok=True)
        wav_data = tts.tts(
            clean_text,
            length_scale=length_scale,
            noise_scale=noise_scale,
        )
        tts.save_wav(wav_data, str(output_path))
        self._loaded_voice_ids.add(request.voice_id)
        return SynthesisResult(
            output_path=output_path,
            duration=probe_duration(output_path),
            output_format="wav",
        )

    def _load_real_model(self, request: TTSRequest):
        model_path = self._model_path()
        config_path = self._config_path()
        if model_path is None:
            raise ProviderError("PTH_MODEL_PATH is not set or file does not exist.")
        if config_path is None:
            raise ProviderError("PTH_CONFIG_PATH is not set and config.json was not found next to model.pth.")
        if not self._dependency_available():
            raise ProviderError(
                "PTH real model needs optional dependencies. Run: pip install -r requirements-local-models.txt"
            )

        key = f"{model_path}|{config_path}"
        if self._tts is not None and self._loaded_model_key == key:
            return self._tts

        try:
            import torch
            import transformers.pytorch_utils
            from TTS.utils.synthesizer import Synthesizer
        except Exception as exc:
            raise ProviderError(f"Could not import PTH dependencies: {exc}") from exc

        if not hasattr(transformers.pytorch_utils, "isin_mps_friendly"):
            transformers.pytorch_utils.isin_mps_friendly = torch.isin

        threads = int(request.provider_options.get("threads", 2))
        torch.set_num_threads(max(1, threads))
        use_cuda = bool(request.provider_options.get("use_cuda", torch.cuda.is_available()))
        self._tts = Synthesizer(
            tts_checkpoint=str(model_path),
            tts_config_path=str(config_path),
            use_cuda=use_cuda,
        )
        self._loaded_model_key = key
        self._patterns = self._load_dictionary_patterns()
        return self._tts

    def _model_path(self) -> Path | None:
        if not self.settings.pth_model_path:
            return None
        path = Path(self.settings.pth_model_path).expanduser()
        return path if path.is_file() else None

    def _config_path(self) -> Path | None:
        candidates: list[Path] = []
        if self.settings.pth_config_path:
            candidates.append(Path(self.settings.pth_config_path).expanduser())
        model_path = self._model_path()
        if model_path is not None:
            candidates.append(model_path.with_name("config.json"))

        for path in candidates:
            if path.is_file():
                return path
        return None

    def _dictionary_path(self) -> Path | None:
        candidates: list[Path] = []
        if self.settings.pth_dictionary_path:
            candidates.append(Path(self.settings.pth_dictionary_path).expanduser())
        model_path = self._model_path()
        if model_path is not None:
            candidates.append(model_path.with_name("non-vietnamese-words.csv"))

        for path in candidates:
            if path.is_file():
                return path
        return None

    def _load_dictionary_patterns(self) -> list[tuple[re.Pattern[str], str]]:
        dictionary_path = self._dictionary_path()
        if dictionary_path is None:
            return []

        replacements: dict[str, str] = {}
        with dictionary_path.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            for row in reader:
                values = [str(value or "").strip() for value in row.values()]
                if len(values) >= 2 and values[0]:
                    replacements[values[0]] = values[1]

        return [
            (re.compile(r"\b" + re.escape(key) + r"\b", re.IGNORECASE), value)
            for key, value in replacements.items()
        ]

    def _process_text(self, text: str) -> str:
        cleaned = re.sub(r"[*~_\[\]()<>{}]", "", text or "")
        cleaned = (
            cleaned.replace('"', "")
            .replace("'", "")
            .replace("“", "")
            .replace("”", "")
            .replace("‘", "")
            .replace("’", "")
        )
        cleaned = re.sub(r"\.{2,}", ".", cleaned).replace("!+", ".").replace("?+", ".")
        cleaned = re.sub(r"-+", ",", cleaned)

        for pattern, replacement in self._patterns:
            cleaned = pattern.sub(replacement, cleaned)

        try:
            from num2words import num2words

            cleaned = re.sub(r"\d+", lambda match: num2words(int(match.group()), lang="vi"), cleaned)
        except Exception:
            pass

        return re.sub(r"\s+", " ", cleaned).strip()

    @staticmethod
    def _dependency_available() -> bool:
        return (
            importlib.util.find_spec("TTS") is not None
            and importlib.util.find_spec("torch") is not None
            and importlib.util.find_spec("num2words") is not None
        )

    @staticmethod
    def _real_voice_notes(
        model_path: Path | None,
        config_path: Path | None,
        dependency_available: bool,
    ) -> str | None:
        if model_path is None:
            return "Set PTH_MODEL_PATH to models/pth/model.pth."
        if config_path is None:
            return "Set PTH_CONFIG_PATH or place config.json next to model.pth."
        if not dependency_available:
            return "Install optional local model dependencies: pip install -r requirements-local-models.txt"
        return None
