[CmdletBinding()]
param(
    [string]$ReviewDramaRoot = "E:\Phim Trung\tools\review-drama",
    [string]$Destination = "E:\Phim Trung\tools\voice-service-drive",
    [switch]$IncludeNgocHuyenGgufFolder,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Copy-RequiredFile {
    param(
        [string]$Source,
        [string]$TargetDir
    )

    if (-not (Test-Path -LiteralPath $Source -PathType Leaf)) {
        throw "Missing required file: $Source"
    }

    $target = Join-Path $TargetDir (Split-Path -Leaf $Source)
    if ($DryRun) {
        Write-Host "[dry-run] copy file $Source -> $target"
        return
    }

    New-Item -ItemType Directory -Force -Path $TargetDir | Out-Null
    Copy-Item -LiteralPath $Source -Destination $target -Force
    Write-Host "Copied file: $target"
}

function Copy-OptionalFile {
    param(
        [string]$Source,
        [string]$TargetDir
    )

    if (-not (Test-Path -LiteralPath $Source -PathType Leaf)) {
        Write-Host "Optional file not found, skipped: $Source" -ForegroundColor Yellow
        return
    }

    Copy-RequiredFile -Source $Source -TargetDir $TargetDir
}

function Copy-ModelDirectory {
    param(
        [string]$SourceDir,
        [string]$TargetDir
    )

    if (-not (Test-Path -LiteralPath $SourceDir -PathType Container)) {
        throw "Missing model directory: $SourceDir"
    }

    if ($DryRun) {
        Write-Host "[dry-run] copy directory $SourceDir -> $TargetDir"
        return
    }

    New-Item -ItemType Directory -Force -Path $TargetDir | Out-Null
    & robocopy $SourceDir $TargetDir /E /XD ".cache" "__pycache__" "temp_audio" "HoanThanh_TruyenAudio" /XF "*.pyc" | Out-Host
    if ($LASTEXITCODE -gt 7) {
        throw "robocopy failed with exit code $LASTEXITCODE"
    }
    Write-Host "Copied directory: $TargetDir"
}

$reviewVoiceRoot = Join-Path $ReviewDramaRoot "voice"
$zhaodiModelsRoot = Join-Path $reviewVoiceRoot "zhaodi_unified\models"
$bundleRoot = Join-Path $Destination "voice-service"
$pthTarget = Join-Path $bundleRoot "models\pth"
$vneuTargetRoot = Join-Path $bundleRoot "models\vieneu"

Write-Step "Preparing Google Drive model folder"
Write-Host "Review-drama root: $ReviewDramaRoot"
Write-Host "Bundle root:       $bundleRoot"

Write-Step "Copy PTH local model"
Copy-RequiredFile -Source (Join-Path $reviewVoiceRoot "model.pth") -TargetDir $pthTarget
Copy-RequiredFile -Source (Join-Path $reviewVoiceRoot "config.json") -TargetDir $pthTarget
Copy-OptionalFile -Source (Join-Path $reviewVoiceRoot "non-vietnamese-words.csv") -TargetDir $pthTarget

Write-Step "Copy VieNeu Ngoc Huyen model"
Copy-ModelDirectory `
    -SourceDir (Join-Path $zhaodiModelsRoot "ngoc_huyen") `
    -TargetDir (Join-Path $vneuTargetRoot "ngoc_huyen")

Write-Step "Copy VieNeu base model with built-in voices"
Copy-ModelDirectory `
    -SourceDir (Join-Path $zhaodiModelsRoot "VieNeu-TTS-0.3B") `
    -TargetDir (Join-Path $vneuTargetRoot "VieNeu-TTS-0.3B")

if ($IncludeNgocHuyenGgufFolder) {
    Write-Step "Copy optional ngoc_huyen_gguf folder"
    Copy-ModelDirectory `
        -SourceDir (Join-Path $zhaodiModelsRoot "ngoc_huyen_gguf") `
        -TargetDir (Join-Path $vneuTargetRoot "ngoc_huyen_gguf")
}

$colabNote = @'
Upload/copy the inner folder named voice-service to Google Drive:

Google Drive target:
MyDrive/voice-service/

Colab paths:
PTH_MODEL_PATH=/content/drive/MyDrive/voice-service/models/pth/model.pth
PTH_CONFIG_PATH=/content/drive/MyDrive/voice-service/models/pth/config.json
PTH_DICTIONARY_PATH=/content/drive/MyDrive/voice-service/models/pth/non-vietnamese-words.csv
VNEU_MODEL_PATH=/content/drive/MyDrive/voice-service/models/vieneu/ngoc_huyen
ZHAODI_MODEL_PATH=/content/drive/MyDrive/voice-service/models/vieneu
OUTPUT_DIR=/content/drive/MyDrive/voice-service/outputs

Colab command:
python scripts/start_colab.py --mount-drive --drive-root /content/drive/MyDrive/voice-service --tunnel cloudflared
'@

if ($DryRun) {
    Write-Host ""
    Write-Host "[dry-run] would write COLAB_PATHS.txt"
} else {
    New-Item -ItemType Directory -Force -Path $bundleRoot | Out-Null
    Set-Content -LiteralPath (Join-Path $bundleRoot "COLAB_PATHS.txt") -Value $colabNote -Encoding UTF8
}

Write-Step "Done"
Write-Host "Folder to upload/sync: $bundleRoot" -ForegroundColor Green
Write-Host "Expected Drive path:   MyDrive/voice-service" -ForegroundColor Green
