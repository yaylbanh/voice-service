from __future__ import annotations

import mimetypes
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from app.config import detect_device, get_settings
from app.model_manager import ModelManager
from app.providers.base import ProviderError
from app.schemas import (
    HealthResponse,
    TTSBatchItemResponse,
    TTSBatchRequest,
    TTSBatchResponse,
    TTSRequest,
    TTSResponse,
    VoicesResponse,
)
from app.utils.paths import build_audio_url, resolve_output_path
from app.utils.security import require_api_key


settings = get_settings()
model_manager = ModelManager(settings)
TESTER_PATH = Path(__file__).resolve().parents[1] / "web" / "voice_tester.html"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.ensure_directories()
    app.state.model_manager = model_manager
    await model_manager.preload_startup_voices()
    yield


app = FastAPI(
    title="Voice Service",
    version=settings.service_version,
    description="Local/Colab TTS service with lazy provider loading.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_model_manager(request: Request) -> ModelManager:
    return request.app.state.model_manager


@app.get("/tester", include_in_schema=False)
async def tester() -> FileResponse:
    if not TESTER_PATH.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tester UI not found.")
    return FileResponse(TESTER_PATH, media_type="text/html; charset=utf-8")


@app.get("/health", response_model=HealthResponse, dependencies=[Depends(require_api_key)])
async def health(manager: ModelManager = Depends(get_model_manager)) -> HealthResponse:
    return HealthResponse(
        success=True,
        device=detect_device(),
        version=settings.service_version,
        loaded=manager.loaded_summary(),
        preload=manager.preload_status,
    )


@app.get("/voices", response_model=VoicesResponse, dependencies=[Depends(require_api_key)])
async def voices(manager: ModelManager = Depends(get_model_manager)) -> VoicesResponse:
    return VoicesResponse(success=True, voices=manager.list_voices())


@app.post("/tts", response_model=TTSResponse, dependencies=[Depends(require_api_key)])
async def tts(
    payload: TTSRequest,
    request: Request,
    manager: ModelManager = Depends(get_model_manager),
) -> TTSResponse:
    return await _synthesize_one(payload, request, manager)


@app.post("/tts/batch", response_model=TTSBatchResponse, dependencies=[Depends(require_api_key)])
async def tts_batch(
    payload: TTSBatchRequest,
    request: Request,
    manager: ModelManager = Depends(get_model_manager),
) -> TTSBatchResponse:
    if len(payload.items) > settings.max_batch_items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Batch has {len(payload.items)} items; max is {settings.max_batch_items}.",
        )

    results: list[TTSBatchItemResponse] = []
    for item in payload.items:
        request_payload = TTSRequest(**item.model_dump(exclude={"item_id"}))
        response = await _synthesize_one(request_payload, request, manager)
        results.append(TTSBatchItemResponse(item_id=item.item_id, **response.model_dump()))

    return TTSBatchResponse(success=all(result.success for result in results), results=results)


@app.get("/outputs/{file_name}", dependencies=[Depends(require_api_key)])
async def outputs(file_name: str) -> FileResponse:
    try:
        path = resolve_output_path(settings.output_dir, file_name)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Output file not found.")

    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return FileResponse(path, media_type=media_type, filename=path.name)


async def _synthesize_one(
    payload: TTSRequest,
    request: Request,
    manager: ModelManager,
) -> TTSResponse:
    provider_id = manager.provider_id_for_voice(payload.voice_id) or ""
    try:
        result, provider_id = await manager.synthesize(payload)
        file_name = result.output_path.name
        return TTSResponse(
            success=True,
            audio_url=build_audio_url(request, settings, file_name),
            audio_path=str(result.output_path),
            duration=result.duration,
            voice_id=payload.voice_id,
            provider=provider_id,
        )
    except ProviderError as exc:
        return TTSResponse(
            success=False,
            voice_id=payload.voice_id,
            provider=provider_id,
            error=str(exc),
        )
    except Exception as exc:
        return TTSResponse(
            success=False,
            voice_id=payload.voice_id,
            provider=provider_id,
            error=f"Unexpected {type(exc).__name__}: {exc}",
        )
