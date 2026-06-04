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

At the moment these paths prepare the service for the real adapters. The scaffold still uses `pth:stub` for successful smoke tests until the PTH/VieNeu provider code is moved into `voice-service`.
