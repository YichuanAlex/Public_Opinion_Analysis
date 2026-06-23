#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from pipeline_paths import MODEL_DIR, PROJECT_ROOT


MODEL_REPOS = {
    "small": "Systran/faster-whisper-small",
    "base": "Systran/faster-whisper-base",
    "tiny": "Systran/faster-whisper-tiny",
}


def download_with_huggingface(repo_id: str, target: Path) -> None:
    try:
        from huggingface_hub import snapshot_download  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "缺少 huggingface-hub。请先运行 `python3 -m pip install -r requirements.txt`。"
        ) from exc

    target.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=repo_id,
        local_dir=str(target),
        local_dir_use_symlinks=False,
        resume_download=True,
    )


def download_with_buzz(model: str) -> None:
    buzz_script = PROJECT_ROOT / "BUZZ" / "scripts" / "download-models.py"
    if not buzz_script.exists():
        raise RuntimeError(f"BUZZ 下载脚本不存在：{buzz_script}")
    env = os.environ.copy()
    env["BUZZ_MODEL_ROOT"] = str(MODEL_DIR)
    subprocess.run(
        [
            sys.executable,
            str(buzz_script),
            "--model-type",
            "fasterwhisper",
            "--model-size",
            model,
        ],
        cwd=str(PROJECT_ROOT / "BUZZ"),
        env=env,
        check=True,
    )


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Download local Chinese ASR model for media enrichment.")
    parser.add_argument("--model", choices=sorted(MODEL_REPOS), default="small", help="Default small balances Chinese quality and local speed.")
    parser.add_argument("--backend", choices=["huggingface", "buzz"], default="huggingface")
    args = parser.parse_args(argv)

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    target = MODEL_DIR / f"faster-whisper-{args.model}"
    if target.exists() and any(target.iterdir()):
        print(f"模型已存在，跳过下载：{target}")
        return 0

    try:
        if args.backend == "buzz":
            download_with_buzz(args.model)
        else:
            download_with_huggingface(MODEL_REPOS[args.model], target)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"ASR 模型已准备完成：{target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
