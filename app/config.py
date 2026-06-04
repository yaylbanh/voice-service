from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    service_version: str
    output_dir: Path
    models_dir: Path
    logs_dir: Path
    public_base_url: str
    api_key: str
    protect_outputs: bool
    max_batch_items: int
    pth_model_path: str
    pth_config_path: str
    pth_dictionary_path: str
    vneu_model_path: str
    zhaodi_model_path: str

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            service_version=os.getenv("VOICE_SERVICE_VERSION", "0.1.0"),
            output_dir=Path(os.getenv("OUTPUT_DIR", str(BASE_DIR / "outputs"))).resolve(),
            models_dir=Path(os.getenv("MODELS_DIR", str(BASE_DIR / "models"))).resolve(),
            logs_dir=Path(os.getenv("LOGS_DIR", str(BASE_DIR / "logs"))).resolve(),
            public_base_url=os.getenv("PUBLIC_BASE_URL", "").rstrip("/"),
            api_key=os.getenv("VOICE_SERVICE_API_KEY", ""),
            protect_outputs=_bool_env("PROTECT_OUTPUTS", True),
            max_batch_items=_int_env("MAX_BATCH_ITEMS", 100),
            pth_model_path=os.getenv("PTH_MODEL_PATH", ""),
            pth_config_path=os.getenv("PTH_CONFIG_PATH", ""),
            pth_dictionary_path=os.getenv("PTH_DICTIONARY_PATH", ""),
            vneu_model_path=os.getenv("VNEU_MODEL_PATH", ""),
            zhaodi_model_path=os.getenv("ZHAODI_MODEL_PATH", ""),
        )

    def ensure_directories(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings.from_env()
    settings.ensure_directories()
    return settings


def detect_device() -> str:
    try:
        import torch  # type: ignore

        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"
