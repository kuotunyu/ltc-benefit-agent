"""在 Windows 以官方權重、llama.cpp release 與 Ollama 建立 F1 Q4_K_M。

預設只做資源、token 與 gated access dry-run。真正下載與轉檔必須同時傳入
``--execute`` 與 ``--accepted-license``，避免無意取得受條款約束的權重。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from huggingface_hub import HfApi, snapshot_download
from huggingface_hub.errors import GatedRepoError, HfHubHTTPError


REPO_ID = "twinkle-ai/Llama-3.2-3B-F1-Instruct"
LLAMA_CPP_TAG = "b9637"
MODEL_NAME = "ltc-f1:q4_k_m"
MIN_FREE_BYTES = 30 * 1024**3
MODEL_PATTERNS = (
    "*.json",
    "*.safetensors",
    "*.model",
    "tokenizer*",
    "LICENSE*",
    "README.md",
)


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_work_dir() -> Path:
    base = Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return base / "ltc-benefit-agent" / "f1-build"


def run(command: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    printable = ["<redacted>" if "hf_" in item.lower() else item for item in command]
    print("RUN", " ".join(printable))
    subprocess.run(command, cwd=cwd, env=env, check=True)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_extract(archive: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    resolved_destination = destination.resolve()
    with zipfile.ZipFile(archive) as source:
        for member in source.infolist():
            target = (destination / member.filename).resolve()
            if target != resolved_destination and resolved_destination not in target.parents:
                raise ValueError(f"拒絕解壓越界路徑：{member.filename}")
        source.extractall(destination)


def download(url: str, destination: Path) -> None:
    if destination.exists():
        print(f"REUSE {destination}")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    print(f"DOWNLOAD {url}")
    with urllib.request.urlopen(url, timeout=60) as response, destination.open("wb") as output:
        shutil.copyfileobj(response, output)


def resource_report(work_dir: Path) -> None:
    free = shutil.disk_usage(work_dir.parent if work_dir.parent.exists() else Path.home()).free
    print(f"work_dir={work_dir.resolve()}")
    print(f"disk_free_gib={free / 1024**3:.1f}")
    if free < MIN_FREE_BYTES:
        raise RuntimeError("可用磁碟低於 30 GiB，停止轉檔")
    subprocess.run(
        [
            "nvidia-smi",
            "--query-gpu=name,memory.total,memory.used,utilization.gpu",
            "--format=csv,noheader",
        ],
        check=True,
    )
    subprocess.run(["ollama", "list"], check=True)
    subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq python.exe", "/FO", "TABLE"],
        check=False,
    )


def check_hub_access(token: str | None) -> tuple[str, int]:
    if not token:
        raise PermissionError("找不到 HF_TOKEN；請在本機 .env 設定，腳本不會輸出其值")
    try:
        info = HfApi(token=token).model_info(REPO_ID)
        dry_run = snapshot_download(
            repo_id=REPO_ID,
            revision=info.sha,
            token=token,
            allow_patterns=list(MODEL_PATTERNS),
            dry_run=True,
        )
    except GatedRepoError as exc:
        raise PermissionError(
            "尚未取得 gated 權重；請登入模型頁接受條款後再執行"
        ) from exc
    except HfHubHTTPError as exc:
        raise ConnectionError("模型存取驗證失敗；未輸出 token 或回應內容") from exc
    total = sum(
        int(getattr(item, "file_size", getattr(item, "size", 0)) or 0)
        for item in dry_run
    )
    print(f"hf_revision={info.sha}")
    print(f"hf_dry_run_bytes={total}")
    return str(info.sha), total


def fetch_llama_cpp(work_dir: Path) -> tuple[Path, Path]:
    downloads = work_dir / "downloads"
    source_zip = downloads / f"llama.cpp-{LLAMA_CPP_TAG}.zip"
    cuda_zip = downloads / f"llama-{LLAMA_CPP_TAG}-bin-win-cuda-12.4-x64.zip"
    cudart_zip = downloads / "cudart-llama-bin-win-cuda-12.4-x64.zip"
    download(
        f"https://github.com/ggml-org/llama.cpp/archive/refs/tags/{LLAMA_CPP_TAG}.zip",
        source_zip,
    )
    download(
        f"https://github.com/ggml-org/llama.cpp/releases/download/{LLAMA_CPP_TAG}/{cuda_zip.name}",
        cuda_zip,
    )
    download(
        f"https://github.com/ggml-org/llama.cpp/releases/download/{LLAMA_CPP_TAG}/{cudart_zip.name}",
        cudart_zip,
    )
    source_root = work_dir / "llama-source"
    binaries_root = work_dir / "llama-bin"
    if not source_root.exists():
        safe_extract(source_zip, source_root)
    if not binaries_root.exists():
        safe_extract(cuda_zip, binaries_root)
        safe_extract(cudart_zip, binaries_root)
    converter = next(source_root.rglob("convert_hf_to_gguf.py"))
    quantizer = next(binaries_root.rglob("llama-quantize.exe"))
    return converter, quantizer


def ollama_capabilities(model_name: str) -> list[str]:
    request = urllib.request.Request(
        "http://127.0.0.1:11434/api/show",
        data=json.dumps({"model": model_name}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload: dict[str, Any] = json.load(response)
    return [str(item) for item in payload.get("capabilities", [])]


def execute_build(work_dir: Path, token: str, revision: str) -> None:
    model_dir = work_dir / "hf-model"
    snapshot_download(
        repo_id=REPO_ID,
        revision=revision,
        token=token,
        allow_patterns=list(MODEL_PATTERNS),
        local_dir=model_dir,
    )
    converter, quantizer = fetch_llama_cpp(work_dir)
    f16_path = work_dir / "Llama-3.2-3B-F1-Instruct-F16.gguf"
    q4_path = work_dir / "Llama-3.2-3B-F1-Instruct-Q4_K_M.gguf"
    requirements = converter.parent / "requirements.txt"
    if not f16_path.exists():
        converter_env = dict(os.environ)
        converter_env.pop("VIRTUAL_ENV", None)
        run(
            [
                "uv",
                "run",
                "--python",
                "3.11",
                "--managed-python",
                "--with-requirements",
                str(requirements),
                "python",
                str(converter),
                str(model_dir),
                "--outfile",
                str(f16_path),
                "--outtype",
                "f16",
            ],
            cwd=converter.parent,
            env=converter_env,
        )
    if not q4_path.exists():
        quant_env = dict(os.environ)
        binaries_root = work_dir / "llama-bin"
        dll_dirs = {str(path.parent) for path in binaries_root.rglob("*.dll")}
        quant_env["PATH"] = os.pathsep.join([*dll_dirs, quant_env.get("PATH", "")])
        run([str(quantizer), str(f16_path), str(q4_path), "Q4_K_M"], env=quant_env)

    template_path = project_root() / "deploy" / "ollama" / "f1-tools.Modelfile.template"
    modelfile = work_dir / "F1.Modelfile"
    modelfile.write_text(
        template_path.read_text(encoding="utf-8").replace(
            "__GGUF_PATH__", str(q4_path.resolve())
        ),
        encoding="utf-8",
    )
    run(["ollama", "create", MODEL_NAME, "-f", str(modelfile)])
    capabilities = ollama_capabilities(MODEL_NAME)
    if "tools" not in capabilities:
        raise RuntimeError("匯入模型未宣告 tools capability，停止評估")

    manifest = {
        "repo_id": REPO_ID,
        "revision": revision,
        "llama_cpp_tag": LLAMA_CPP_TAG,
        "f16_sha256": sha256(f16_path),
        "q4_k_m_sha256": sha256(q4_path),
        "ollama_model": MODEL_NAME,
        "ollama_capabilities": capabilities,
    }
    manifest_path = work_dir / "build-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"manifest={manifest_path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, default=default_work_dir())
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--accepted-license", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    work_dir = args.work_dir.resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    resource_report(work_dir)
    load_dotenv(project_root() / ".env", override=False)
    token = os.getenv("HF_TOKEN")
    try:
        revision, _ = check_hub_access(token)
    except (PermissionError, ConnectionError) as exc:
        print(f"GATE: {exc}")
        return 3
    if not args.execute:
        print("CHECK_ONLY_OK：未下載權重、未轉檔、未匯入模型")
        return 0
    if not args.accepted_license:
        print("GATE: 真正下載需同時傳入 --accepted-license")
        return 4
    assert token is not None
    execute_build(work_dir, token, revision)
    return 0


if __name__ == "__main__":
    sys.exit(main())
