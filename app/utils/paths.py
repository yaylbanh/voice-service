from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

from fastapi import Request

from app.config import Settings


_SAFE_NAME_PATTERN = re.compile(r"[^a-zA-Z0-9_.-]+")


def slugify(value: str) -> str:
    slug = _SAFE_NAME_PATTERN.sub("-", value.strip()).strip("-")
    return slug[:48] or "voice"


def make_output_filename(voice_id: str, output_format: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}_{slugify(voice_id)}_{uuid4().hex[:10]}.{output_format}"


def resolve_output_path(output_dir: Path, file_name: str) -> Path:
    if file_name != Path(file_name).name:
        raise ValueError("Invalid output file name.")

    root = output_dir.resolve()
    target = (root / file_name).resolve()

    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError("Invalid output file path.") from exc

    return target


def build_audio_url(request: Request, settings: Settings, file_name: str) -> str:
    base_url = settings.public_base_url or str(request.base_url).rstrip("/")
    return f"{base_url}/outputs/{quote(file_name)}"

