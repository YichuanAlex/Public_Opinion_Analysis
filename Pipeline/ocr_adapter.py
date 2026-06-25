#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import platform
import re
import site
import sys
from pathlib import Path
from typing import Iterable, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WECHAT_OCR_ROOTS = [
    PROJECT_ROOT / "Wechat_OCR",
    PROJECT_ROOT / "wechat_ocr",
]

MAC_VISION_LANGUAGES = ["zh-Hans", "zh-Hant", "en-US"]


class OcrAdapterError(RuntimeError):
    pass


def _ensure_user_site_packages() -> None:
    version_tag = f"{sys.version_info.major}.{sys.version_info.minor}"

    def compatible(candidate: Path) -> bool:
        text = str(candidate).lower()
        versions = re.findall(r"python[/\\]?(\d+\.\d+)", text)
        return not versions or version_tag in versions

    candidates: list[Path] = []
    try:
        candidates.append(Path(site.getusersitepackages()))
    except Exception:
        pass
    try:
        candidates.extend(Path(item) for item in site.getsitepackages())
    except Exception:
        pass
    candidates.extend(Path.home().glob("Library/Python/*/lib/python/site-packages"))
    candidates.extend(Path.home().glob(".local/lib/python*/site-packages"))
    for candidate in candidates:
        text = str(candidate)
        if candidate.exists() and compatible(candidate) and text not in sys.path:
            sys.path.insert(0, text)


def _existing_image_path(image_path: str | Path) -> Path:
    path = Path(image_path).expanduser().resolve()
    if not path.exists():
        raise OcrAdapterError(f"OCR image does not exist: {path}")
    if not path.is_file():
        raise OcrAdapterError(f"OCR image path is not a file: {path}")
    return path


def _wechat_ocr_root() -> Path:
    for root in WECHAT_OCR_ROOTS:
        if (root / "OCR").exists():
            return root
    raise OcrAdapterError(
        "Windows WeChat OCR folder was not found. Expected one of: "
        + ", ".join(str(root / "OCR") for root in WECHAT_OCR_ROOTS)
    )


def _windows_wechat_ocr(image_path: Path) -> list[str]:
    root = _wechat_ocr_root()
    sys.path.insert(0, str(root))
    try:
        import OCR  # type: ignore
    except Exception as exc:
        raise OcrAdapterError(
            "Windows platform must use the bundled WeChatOCR directly, but importing `OCR` failed. "
            f"Root: {root}; error: {exc}"
        ) from exc

    try:
        texts = OCR.wechat_ocr(str(image_path))
    except Exception as exc:
        raise OcrAdapterError(
            "Windows platform must use the bundled WeChatOCR directly, but OCR execution failed. "
            f"Image: {image_path}; error: {exc}"
        ) from exc
    return [str(item).strip() for item in texts if str(item).strip()]


def _macos_vision_ocr(image_path: Path, languages: Optional[list[str]] = None) -> list[str]:
    try:
        try:
            import Vision  # type: ignore
            import Quartz  # type: ignore  # noqa: F401 - imported to ensure image/URL bridging is available.
            from Foundation import NSURL  # type: ignore
        except Exception:
            _ensure_user_site_packages()
            import Vision  # type: ignore
            import Quartz  # type: ignore  # noqa: F401 - imported to ensure image/URL bridging is available.
            from Foundation import NSURL  # type: ignore
    except Exception as exc:
        raise OcrAdapterError(
            "macOS OCR uses Apple's native Vision framework through PyObjC. "
            "Please install dependencies first: `python3 -m pip install -r requirements.txt`. "
            f"Original import error: {exc}"
        ) from exc

    request = Vision.VNRecognizeTextRequest.alloc().init()
    if hasattr(Vision, "VNRequestTextRecognitionLevelAccurate"):
        request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    request.setUsesLanguageCorrection_(True)
    request.setRecognitionLanguages_(languages or MAC_VISION_LANGUAGES)

    url = NSURL.fileURLWithPath_(str(image_path))
    handler = Vision.VNImageRequestHandler.alloc().initWithURL_options_(url, {})
    ok, error = handler.performRequests_error_([request], None)
    if not ok:
        raise OcrAdapterError(f"macOS Vision OCR failed: {error}")

    texts: list[str] = []
    for observation in request.results() or []:
        candidates = observation.topCandidates_(1)
        if candidates:
            text = str(candidates[0].string()).strip()
            if text:
                texts.append(text)
    return texts


def ocr_image(image_path: str | Path, languages: Optional[list[str]] = None) -> list[str]:
    """Return OCR text blocks for one image.

    Platform policy:
    - Windows: always use bundled WeChatOCR directly. No fallback is allowed.
    - macOS: use Apple's native Vision OCR through PyObjC.
    - Other platforms: fail explicitly.
    """

    image = _existing_image_path(image_path)
    system = platform.system().lower()
    if system == "windows":
        return _windows_wechat_ocr(image)
    if system == "darwin":
        return _macos_vision_ocr(image, languages=languages)
    raise OcrAdapterError(f"Unsupported OCR platform: {platform.system()}")


def format_ocr_block(texts: list[str], source_label: str = "图片中的文字内容") -> str:
    clean = [line.strip() for line in texts if line and line.strip()]
    if not clean:
        return ""
    return f"【{source_label}】\n" + "\n".join(clean)


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Cross-platform OCR adapter: WeChatOCR on Windows, macOS Vision OCR on macOS.")
    parser.add_argument("image", help="Image file path.")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of plain text.")
    parser.add_argument("--language", action="append", help="macOS Vision recognition language, e.g. zh-Hans. Can be repeated.")
    args = parser.parse_args(argv)

    try:
        texts = ocr_image(args.image, languages=args.language)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr, flush=True)
        return 1

    if args.json:
        print(json.dumps({"image": str(Path(args.image).resolve()), "texts": texts}, ensure_ascii=False, indent=2), flush=True)
    else:
        print(format_ocr_block(texts), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
