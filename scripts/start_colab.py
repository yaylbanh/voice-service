from __future__ import annotations

import argparse
import os
import re
import stat
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLOUDFLARED_URL = (
    "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start voice-service on Google Colab.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=7860)
    parser.add_argument("--tunnel", choices=["cloudflared", "ngrok", "none"], default="cloudflared")
    parser.add_argument("--public-base-url", default=os.getenv("PUBLIC_BASE_URL", ""))
    parser.add_argument("--mount-drive", action="store_true")
    parser.add_argument("--drive-root", default="/content/drive/MyDrive/voice-service")
    return parser.parse_args()


def maybe_mount_drive(enabled: bool) -> None:
    if not enabled:
        return
    try:
        from google.colab import drive  # type: ignore

        drive.mount("/content/drive")
    except Exception as exc:
        print(f"Could not mount Google Drive: {exc}", flush=True)


def maybe_download_hf_models() -> None:
    repo_id = os.getenv("HF_MODEL_REPO", "")
    if not repo_id:
        return

    files = [item.strip() for item in os.getenv("HF_MODEL_FILES", "").split(",") if item.strip()]
    if not files:
        print("HF_MODEL_REPO is set, but HF_MODEL_FILES is empty. Skipping model download.", flush=True)
        return

    try:
        from huggingface_hub import hf_hub_download  # type: ignore
    except Exception:
        print("Install huggingface_hub before using HF_MODEL_REPO.", flush=True)
        return

    models_dir = Path(os.getenv("MODELS_DIR", str(ROOT / "models"))).resolve()
    models_dir.mkdir(parents=True, exist_ok=True)
    for filename in files:
        path = hf_hub_download(repo_id=repo_id, filename=filename, local_dir=models_dir)
        print(f"Downloaded model file: {path}", flush=True)


def configure_drive_paths(drive_root: str) -> None:
    root = Path(drive_root).expanduser()
    if not root.exists():
        print(f"Drive model root not found yet: {root}", flush=True)
        return

    models_root = root / "models"
    pth_root = models_root / "pth"
    pth_model = pth_root / "model.pth"
    pth_config = pth_root / "config.json"
    pth_dictionary = pth_root / "non-vietnamese-words.csv"

    if not os.getenv("PTH_MODEL_PATH") and pth_model.is_file():
        os.environ["PTH_MODEL_PATH"] = str(pth_model)
    if not os.getenv("PTH_CONFIG_PATH") and pth_config.is_file():
        os.environ["PTH_CONFIG_PATH"] = str(pth_config)
    if not os.getenv("PTH_DICTIONARY_PATH") and pth_dictionary.is_file():
        os.environ["PTH_DICTIONARY_PATH"] = str(pth_dictionary)

    vieneu_candidates = [
        models_root / "vieneu" / "ngoc_huyen",
        models_root / "vieneu" / "VieNeu-TTS-0.3B",
    ]
    if not os.getenv("VNEU_MODEL_PATH"):
        for candidate in vieneu_candidates:
            has_weights = (candidate / "model.safetensors").is_file() or any(candidate.glob("*.gguf"))
            if (candidate / "voices.json").is_file() and has_weights:
                os.environ["VNEU_MODEL_PATH"] = str(candidate)
                break

    zhaodi_models_root = models_root / "vieneu"
    if not os.getenv("ZHAODI_MODEL_PATH") and zhaodi_models_root.exists():
        os.environ["ZHAODI_MODEL_PATH"] = str(zhaodi_models_root)

    output_dir = root / "outputs"
    if not os.getenv("OUTPUT_DIR"):
        output_dir.mkdir(parents=True, exist_ok=True)
        os.environ["OUTPUT_DIR"] = str(output_dir)

    for name in (
        "PTH_MODEL_PATH",
        "PTH_CONFIG_PATH",
        "PTH_DICTIONARY_PATH",
        "VNEU_MODEL_PATH",
        "ZHAODI_MODEL_PATH",
        "OUTPUT_DIR",
    ):
        value = os.getenv(name)
        if value:
            print(f"{name}={value}", flush=True)


def ensure_cloudflared() -> Path:
    candidate = Path(tempfile.gettempdir()) / "cloudflared"
    if candidate.exists():
        return candidate

    print("Downloading cloudflared...", flush=True)
    urllib.request.urlretrieve(CLOUDFLARED_URL, candidate)
    candidate.chmod(candidate.stat().st_mode | stat.S_IEXEC)
    return candidate


def start_cloudflared(port: int) -> tuple[subprocess.Popen[str], str]:
    cloudflared = ensure_cloudflared()
    process = subprocess.Popen(
        [str(cloudflared), "tunnel", "--url", f"http://127.0.0.1:{port}", "--no-autoupdate"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd=str(ROOT),
    )

    public_url_pattern = re.compile(r"https://[a-zA-Z0-9.-]+\.trycloudflare\.com")
    started_at = time.time()
    while time.time() - started_at < 60:
        line = process.stdout.readline() if process.stdout else ""
        if line:
            print(line.rstrip(), flush=True)
            match = public_url_pattern.search(line)
            if match:
                return process, match.group(0)
        if process.poll() is not None:
            raise RuntimeError("cloudflared exited before providing a public URL.")

    raise RuntimeError("Timed out waiting for cloudflared public URL.")


def start_ngrok(port: int) -> tuple[object, str]:
    try:
        from pyngrok import ngrok  # type: ignore
    except Exception as exc:
        raise RuntimeError("Install pyngrok or use --tunnel cloudflared.") from exc

    tunnel = ngrok.connect(port, "http")
    return tunnel, tunnel.public_url


def start_uvicorn(host: str, port: int) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", host, "--port", str(port)],
        cwd=str(ROOT),
        text=True,
    )


def main() -> None:
    args = parse_args()
    os.chdir(ROOT)
    maybe_mount_drive(args.mount_drive)
    configure_drive_paths(args.drive_root)
    maybe_download_hf_models()

    tunnel_handle: object | None = None
    public_url = args.public_base_url.rstrip("/")
    if not public_url and args.tunnel == "cloudflared":
        tunnel_handle, public_url = start_cloudflared(args.port)
    elif not public_url and args.tunnel == "ngrok":
        tunnel_handle, public_url = start_ngrok(args.port)

    if public_url:
        os.environ["PUBLIC_BASE_URL"] = public_url

    server = start_uvicorn(args.host, args.port)
    local_url = f"http://127.0.0.1:{args.port}"
    print(f"Local API URL: {local_url}", flush=True)
    if public_url:
        print(f"Public API URL: {public_url}", flush=True)
        print(f"Health: {public_url}/health", flush=True)

    try:
        server.wait()
    finally:
        server.terminate()
        if isinstance(tunnel_handle, subprocess.Popen):
            tunnel_handle.terminate()


if __name__ == "__main__":
    main()
