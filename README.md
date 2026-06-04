# voice-service

Standalone FastAPI TTS service for local Windows usage and Google Colab/GPU usage.

The goal is to keep heavy voice models out of `review-drama`. The main app can call this service over HTTP, while model loading and audio generation stay isolated here.

## Features

- `GET /health`
- `GET /voices`
- `POST /tts`
- `POST /tts/batch`
- `GET /outputs/{file_name}`
- Lazy provider loading through `app/model_manager.py`
- Optional API key through `VOICE_SERVICE_API_KEY`
- Public URL support through `PUBLIC_BASE_URL`
- Safe stubs for PTH, VieNeu, Zhaodi, and TikTok while real adapters are added later
- A working `pth:stub` WAV generator for API smoke tests

## Local Windows

From this folder:

```powershell
.\start_local.ps1
```

Manual setup:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 7860
```

The local API base URL is:

```text
http://127.0.0.1:7860
```

## API key

API key protection is disabled by default. To enable it:

```powershell
$env:VOICE_SERVICE_API_KEY = "change-me"
.\start_local.ps1
```

Then every request must send:

```text
X-API-Key: change-me
```

## Quick test

```powershell
Invoke-RestMethod http://127.0.0.1:7860/health
Invoke-RestMethod http://127.0.0.1:7860/voices
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:7860/tts `
  -ContentType "application/json" `
  -Body '{"text":"Xin chao, day la voice-service.","voice_id":"pth:stub","language":"vi-VN","speed":1.0,"output_format":"wav"}'
```

The response returns `audio_url` and `audio_path`. Open `audio_url` to download the generated file.

## Batch request

```json
{
  "items": [
    {
      "item_id": "line-1",
      "text": "Cau thu nhat.",
      "voice_id": "pth:stub",
      "language": "vi-VN",
      "output_format": "wav"
    },
    {
      "item_id": "line-2",
      "text": "Cau thu hai.",
      "voice_id": "pth:stub",
      "language": "vi-VN",
      "output_format": "wav"
    }
  ]
}
```

## Providers

`edge_tts` supports Microsoft Edge voices and currently writes MP3. The package is included in `requirements.txt`.

`pth_local`, `vneu`, and `zhaodi` are intentionally safe stubs for now. Put model files in `models/`, set the matching environment variable, then implement the adapter without changing the API contract:

```text
PTH_MODEL_PATH=models/pth/model.pth
VNEU_MODEL_PATH=models/vneu
ZHAODI_MODEL_PATH=models/zhaodi
```

Large files are ignored by git:

```text
models/
outputs/
logs/
*.pth
*.safetensors
*.ckpt
*.onnx
*.gguf
```

## Google Colab

This project is designed to live on GitHub. Colab should clone the repo and run it, not define the service cell by cell.

Use `notebooks/colab_launcher.ipynb`, or run:

```bash
git clone https://github.com/YOUR_USER/voice-service.git
cd voice-service
pip install -U -r requirements.txt
python scripts/start_colab.py --tunnel cloudflared
```

The launcher can:

- mount Google Drive with `--mount-drive`
- download model files from Hugging Face when `HF_MODEL_REPO` and `HF_MODEL_FILES` are set
- start Uvicorn
- expose the API with Cloudflared or ngrok
- set `PUBLIC_BASE_URL` so returned `audio_url` values use the public tunnel URL

For ngrok:

```bash
python scripts/start_colab.py --tunnel ngrok
```

For a known public URL:

```bash
python scripts/start_colab.py --tunnel none --public-base-url https://example-public-url
```

## Calling from review-drama later

`review-drama` should act only as an HTTP client. It does not need to import model code.

```python
import requests

base_url = "http://127.0.0.1:7860"
payload = {
    "text": "Noi dung can tao voice",
    "voice_id": "pth:stub",
    "language": "vi-VN",
    "speed": 1.0,
    "output_format": "wav",
}

response = requests.post(f"{base_url}/tts", json=payload, timeout=120)
data = response.json()
print(data["audio_url"])
```

If `VOICE_SERVICE_API_KEY` is enabled:

```python
headers = {"X-API-Key": "change-me"}
response = requests.post(f"{base_url}/tts", json=payload, headers=headers, timeout=120)
```
