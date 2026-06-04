# Colab model folders

Do not push model weights to GitHub. Put them in Google Drive with this exact structure:

```text
MyDrive/
  voice-service/
    models/
      pth/
        model.pth
        config.json
        non-vietnamese-words.csv
      vieneu/
        ngoc_huyen/
          model.safetensors
          voices.json
          config.json
          generation_config.json
          tokenizer.json
          tokenizer_config.json
          added_tokens.json
          special_tokens_map.json
          merges.txt
          vocab.json
          VieNeu-TTS-0.3B-ngoc-huyen-Q4_0.gguf
    outputs/
```

## Make the folder on Windows

From `E:\Phim Trung\tools\voice-service`:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\prepare_drive_models.ps1
```

It creates:

```text
E:\Phim Trung\tools\voice-service-drive\voice-service
```

Upload or sync the inner `voice-service` folder to Google Drive so it becomes:

```text
MyDrive/voice-service
```

If you also want the base `VieNeu-TTS-0.3B` folder:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\prepare_drive_models.ps1 -IncludeVieNeuBase
```

Dry run without copying:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\prepare_drive_models.ps1 -DryRun
```

## Colab command

After the repo is cloned and requirements are installed:

```python
!pip install -U -r requirements.txt
!pip install -U -r requirements-local-models.txt
!python scripts/start_colab.py --mount-drive --drive-root /content/drive/MyDrive/voice-service --tunnel cloudflared
```

The launcher auto-detects and sets:

```text
PTH_MODEL_PATH=/content/drive/MyDrive/voice-service/models/pth/model.pth
PTH_CONFIG_PATH=/content/drive/MyDrive/voice-service/models/pth/config.json
PTH_DICTIONARY_PATH=/content/drive/MyDrive/voice-service/models/pth/non-vietnamese-words.csv
VNEU_MODEL_PATH=/content/drive/MyDrive/voice-service/models/vieneu/ngoc_huyen
ZHAODI_MODEL_PATH=/content/drive/MyDrive/voice-service/models/vieneu
OUTPUT_DIR=/content/drive/MyDrive/voice-service/outputs
```

`pth:default` uses `PTH_MODEL_PATH`, `PTH_CONFIG_PATH`, and `PTH_DICTIONARY_PATH`.

`vneu:default` and `vneu:{preset_id}` use `VNEU_MODEL_PATH`. The VieNeu adapter also needs the `vieneu` Python package to be available in the Colab/runtime environment.

By default, startup uses:

```text
PRELOAD_VOICES=auto
```

That means available local model voices are loaded before the API starts serving requests. Check `/health`; `preload.completed` should be `true`, and loaded voices appear under `loaded`.
