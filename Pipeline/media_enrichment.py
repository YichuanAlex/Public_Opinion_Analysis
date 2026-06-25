#!/usr/bin/env python3
from __future__ import annotations

import json
import mimetypes
import os
import re
import site
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

try:
    from ocr_adapter import OcrAdapterError, format_ocr_block, ocr_image
    from pipeline_paths import CACHE_DIR, MODEL_DIR, PROJECT_ROOT
except ModuleNotFoundError:
    from Pipeline.ocr_adapter import OcrAdapterError, format_ocr_block, ocr_image
    from Pipeline.pipeline_paths import CACHE_DIR, MODEL_DIR, PROJECT_ROOT


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".gif"}
AUDIO_EXTS = {".mp3", ".m4a", ".aac", ".wav", ".flac", ".ogg", ".opus"}
VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


@dataclass(frozen=True)
class MediaItem:
    kind: str
    url: str
    label: str


def media_log(message: str) -> None:
    print(f"MEDIA_ENRICH: {message}", flush=True)


def clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def load_raw_json(flat: dict[str, Any]) -> dict[str, Any]:
    raw = flat.get("raw_json")
    if not raw:
        return {}
    try:
        data = json.loads(str(raw))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def iter_urls(value: Any, path: tuple[str, ...] = ()) -> Iterable[tuple[str, tuple[str, ...]]]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield from iter_urls(child, path + (str(key),))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from iter_urls(child, path + (str(index),))
    elif isinstance(value, str) and value.startswith(("http://", "https://")):
        yield value, path


def path_text(path: tuple[str, ...]) -> str:
    return ".".join(path).lower()


def is_auxiliary_media_path(text: str) -> bool:
    return any(token in text for token in (
        "author.",
        "avatar",
        "music.",
        "share_qrcode",
        "qrcode",
        "big_thumbs",
        "gaussian_cover",
        "dynamic_cover",
    ))


def ensure_user_site_packages() -> None:
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


def url_ext(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    ext = Path(parsed.path).suffix.lower()
    if ext:
        return ext
    guessed = mimetypes.guess_extension(urllib.parse.parse_qs(parsed.query).get("mime_type", [""])[0])
    return guessed or ""


def looks_like_image(url: str, path: tuple[str, ...]) -> bool:
    text = path_text(path)
    if is_auxiliary_media_path(text):
        return False
    if ".video." in text or text.startswith("video."):
        return False
    if "avatar" in text or "user" in text and "cover" not in text:
        return False
    if any(token in text for token in ("image_list", "images", "note_card.image_list", "origin_cover", "cover")):
        return True
    ext = url_ext(url)
    return ext in IMAGE_EXTS and any(host in url for host in ("xhscdn", "douyinpic", "douyincdn"))


def looks_like_audio(url: str, path: tuple[str, ...]) -> bool:
    text = path_text(path)
    if "music" in text:
        return False
    if "bit_rate_audio" in text or "media-audio" in url:
        return True
    return url_ext(url) in AUDIO_EXTS and any(token in text for token in ("audio", "play_addr", "url_list"))


def looks_like_video(url: str, path: tuple[str, ...]) -> bool:
    text = path_text(path)
    if is_auxiliary_media_path(text):
        return False
    if "cover" in text or "avatar" in text:
        return False
    if any(token in text for token in ("play_addr", "download_addr")) and (".video." in text or text.startswith("video.") or "stream" in text):
        return True
    if "video" in text and any(token in text for token in ("url_list", "uri", "stream")) and "image" not in text:
        return True
    return url_ext(url) in VIDEO_EXTS


def unique_items(items: Iterable[MediaItem]) -> list[MediaItem]:
    seen: set[str] = set()
    out: list[MediaItem] = []
    for item in items:
        if not item.url or item.url in seen:
            continue
        seen.add(item.url)
        out.append(item)
    return out


def extract_media_items(platform: str, flat: dict[str, Any]) -> list[MediaItem]:
    raw = load_raw_json(flat)
    items: list[MediaItem] = []
    for url, path in iter_urls(raw):
        label = ".".join(path)
        if looks_like_image(url, path):
            items.append(MediaItem("image", url, label))
        elif looks_like_audio(url, path):
            items.append(MediaItem("audio", url, label))
        elif looks_like_video(url, path):
            items.append(MediaItem("video", url, label))

    if platform == "xhs":
        # Xiaohongshu sometimes stores media in flattened fields even when raw_json omits a URL branch.
        for key, value in flat.items():
            url = str(value or "")
            path = tuple(str(key).split("."))
            if url.startswith(("http://", "https://")):
                if looks_like_image(url, path):
                    items.append(MediaItem("image", url, key))
                elif looks_like_video(url, path):
                    items.append(MediaItem("video", url, key))

    return unique_items(items)


def safe_ext(item: MediaItem) -> str:
    ext = url_ext(item.url)
    if ext in IMAGE_EXTS | AUDIO_EXTS | VIDEO_EXTS:
        return ext
    return ".jpg" if item.kind == "image" else ".mp4"


def download_url(url: str, path: Path, referer: str = "") -> Path:
    headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    if referer:
        headers["Referer"] = referer
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=45) as response:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as handle:
            shutil.copyfileobj(response, handle)
    return path


def ffmpeg_path() -> str:
    found = shutil.which("ffmpeg")
    if not found:
        raise RuntimeError("未检测到 ffmpeg，无法从视频中提取语音。请先安装 ffmpeg。")
    return found


def extract_audio_for_asr(media_path: Path, work_dir: Path) -> Path:
    if media_path.suffix.lower() in AUDIO_EXTS:
        return media_path
    if not shutil.which("ffmpeg"):
        return media_path
    output = work_dir / f"{media_path.stem}_audio.wav"
    subprocess.run(
        [
            ffmpeg_path(),
            "-y",
            "-i",
            str(media_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-loglevel",
            "error",
            str(output),
        ],
        check=True,
    )
    return output


def local_faster_whisper_model() -> Path:
    direct = MODEL_DIR / "faster-whisper-small"
    if direct.exists():
        return direct
    raise RuntimeError(
        "未找到本地中文语音转写模型。请先运行："
        "python3 Pipeline/download_asr_model.py --model small"
    )


def transcribe_audio(audio_path: Path) -> str:
    try:
        try:
            from faster_whisper import WhisperModel  # type: ignore
        except Exception:
            ensure_user_site_packages()
            from faster_whisper import WhisperModel  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "未安装 faster-whisper。请运行 `python3 -m pip install -r requirements.txt` 后重试。"
        ) from exc

    model_path = local_faster_whisper_model()
    model = WhisperModel(str(model_path), device="cpu", compute_type="int8")
    segments, _info = model.transcribe(
        str(audio_path),
        language="zh",
        vad_filter=True,
        beam_size=3,
        condition_on_previous_text=False,
    )
    text = "".join(clean_text(segment.text) for segment in segments)
    return text.strip()


def append_media_text(body: str, image_ocr: str = "", video_transcript: str = "") -> str:
    parts = [str(body or "").strip()]
    if image_ocr:
        parts.append(image_ocr.strip())
    if video_transcript:
        parts.append(video_transcript.strip())
    return "\n\n".join(part for part in parts if part)


def enrich_flat_row(
    platform: str,
    flat: OrderedDict[str, Any] | dict[str, Any],
    *,
    max_images: int = 12,
    max_transcripts: int = 1,
) -> OrderedDict[str, Any]:
    out: OrderedDict[str, Any]
    if isinstance(flat, OrderedDict):
        out = flat
    else:
        out = OrderedDict(flat)

    note_id = clean_text(out.get("note_id") or out.get("aweme_id") or "note")
    media_items = extract_media_items(platform, out)
    images = [item for item in media_items if item.kind == "image"][:max_images]
    transcripts = [item for item in media_items if item.kind in {"audio", "video"}][:max_transcripts]
    errors: list[str] = []
    ocr_blocks: list[str] = []
    transcript_blocks: list[str] = []
    session_dir = CACHE_DIR / f"{platform}_{note_id}_{int(time.time() * 1000)}"
    media_log(
        f"{platform} {note_id}: 识别到图片 {len(images)} 个，"
        f"音/视频 {len(transcripts)} 个；临时缓存 {session_dir}"
    )

    try:
        for index, item in enumerate(images, start=1):
            try:
                media_log(f"{platform} {note_id}: 下载第 {index} 张图片并执行 OCR；字段 {item.label}")
                local = download_url(item.url, session_dir / f"image_{index}{safe_ext(item)}", str(out.get("source_url", "")))
                texts = ocr_image(local)
                block = format_ocr_block(texts, f"第{index}张图片中的文字内容")
                if block:
                    ocr_blocks.append(block)
                    media_log(f"{platform} {note_id}: 第 {index} 张图片 OCR 成功，文本 {len(block)} 字符")
                else:
                    media_log(f"{platform} {note_id}: 第 {index} 张图片 OCR 无可写入文本")
            except (OcrAdapterError, Exception) as exc:
                errors.append(f"image {index}: {exc}")
                media_log(f"{platform} {note_id}: 第 {index} 张图片 OCR 失败：{exc}")

        for index, item in enumerate(transcripts, start=1):
            try:
                media_log(f"{platform} {note_id}: 下载第 {index} 个音/视频并执行语音转文字；字段 {item.label}")
                local = download_url(item.url, session_dir / f"media_{index}{safe_ext(item)}", str(out.get("source_url", "")))
                audio = extract_audio_for_asr(local, session_dir)
                text = transcribe_audio(audio)
                if text:
                    transcript_blocks.append(f"【第{index}个视频中的语音内容】\n{text}")
                    media_log(f"{platform} {note_id}: 第 {index} 个音/视频语音转文字成功，文本 {len(text)} 字符")
                else:
                    media_log(f"{platform} {note_id}: 第 {index} 个音/视频语音转文字无可写入文本")
            except Exception as exc:
                errors.append(f"{item.kind} {index}: {exc}")
                media_log(f"{platform} {note_id}: 第 {index} 个音/视频语音转文字失败：{exc}")
    finally:
        shutil.rmtree(session_dir, ignore_errors=True)
        media_log(f"{platform} {note_id}: 已清理临时缓存 {session_dir}")

    image_ocr = "\n\n".join(ocr_blocks).strip()
    video_transcript = "\n\n".join(transcript_blocks).strip()
    out["media_enrichment.image_count"] = str(len(images))
    out["media_enrichment.transcript_source_count"] = str(len(transcripts))
    out["media_enrichment.image_ocr_text"] = image_ocr
    out["media_enrichment.video_transcript"] = video_transcript
    out["media_enrichment.errors"] = " | ".join(errors)
    media_log(
        f"{platform} {note_id}: 完成。OCR文本 {len(image_ocr)} 字符，"
        f"语音文本 {len(video_transcript)} 字符，错误 {len(errors)} 个"
    )
    return out


def main() -> int:
    print(json.dumps({
        "projectRoot": str(PROJECT_ROOT),
        "cacheDir": str(CACHE_DIR),
        "modelDir": str(MODEL_DIR),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
