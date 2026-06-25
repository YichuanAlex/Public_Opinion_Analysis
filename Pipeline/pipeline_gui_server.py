#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import csv
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows fallback uses in-process lock only.
    fcntl = None

from pipeline_paths import (
    DY_COMMENT_CSV,
    DY_DATA_TABLE_CSV,
    DY_HYPE_WORKBOOK,
    DY_ORIGIN_CSV,
    HYPE_ROOT,
    PIPELINE_DIR,
    PROJECT_ROOT,
    XHS_COMMENT_CSV,
    XHS_DATA_TABLE_CSV,
    XHS_HYPE_WORKBOOK,
    XHS_ORIGIN_CSV,
    migrate_legacy_xhs_files,
)


ROOT = PIPELINE_DIR
NOTE_SCRIPT = ROOT / "xhs_note_to_csv.py"
SEARCH_SCRIPT = ROOT / "xhs_search_to_csv.py"
COMMENT_SCRIPT = ROOT / "xhs_comment_to_csv.py"
AI_FILL_SCRIPT = ROOT / "xhs_ai_fill_table.py"
AMPLIFICATION_SCRIPT = ROOT / "xhs_amplification_export.py"
CLEAN_SCRIPT = ROOT / "clean_monitoring_tables.py"
ORIGIN_CSV = XHS_ORIGIN_CSV
DATA_TABLE_CSV = XHS_DATA_TABLE_CSV
COMMENT_CSV = XHS_COMMENT_CSV
HYPE_WORKBOOK = XHS_HYPE_WORKBOOK
DY_NOTE_SCRIPT = ROOT / "dy_note_to_csv.py"
DY_SEARCH_SCRIPT = ROOT / "dy_search_to_csv.py"
DY_COMMENT_SCRIPT = ROOT / "dy_comment_to_csv.py"
DY_AI_FILL_SCRIPT = ROOT / "dy_ai_fill_table.py"
DY_AMPLIFICATION_SCRIPT = ROOT / "dy_amplification_export.py"
EXPORT_DIR = ROOT / "gui_exports"
TEMP_DIR = EXPORT_DIR / "session_tmp"
TASK_LOCK_DIR = EXPORT_DIR / "task_locks"
WRITE_LOCKS = {
    "xhs": threading.Lock(),
    "dy": threading.Lock(),
}
TASK_LOCKS = {
    "xhs": threading.Lock(),
    "dy": threading.Lock(),
}
TASK_STATE_LOCK = threading.Lock()
TASK_STATE: dict[str, dict[str, str]] = {}

URL_RE = re.compile(r"https?://(?:www\.)?xiaohongshu\.com/[^\s，。！？,，）)】]+")
NOTE_ID_RE = re.compile(r"/(?:discovery/item|explore|search_result)/([0-9a-zA-Z]{24})")
DY_URL_RE = re.compile(r"https?://(?:(?:www|v)\.)?(?:douyin\.com|iesdouyin\.com)/[^\s，。！？,，）)】]+")
DY_NOTE_ID_RE = re.compile(r"(?:[?&]modal_id=|/(?:video|note|share/video)/)(\d{10,30})")

PLATFORM_CONFIGS = {
    "xhs": {
        "key": "xhs",
        "name": "小红书",
        "channel": "小红书",
        "note_script": NOTE_SCRIPT,
        "search_script": SEARCH_SCRIPT,
        "comment_script": COMMENT_SCRIPT,
        "ai_script": AI_FILL_SCRIPT,
        "amplification_script": AMPLIFICATION_SCRIPT,
        "origin_csv": ORIGIN_CSV,
        "data_table_csv": DATA_TABLE_CSV,
        "comment_csv": COMMENT_CSV,
        "hype_workbook": HYPE_WORKBOOK,
    },
    "dy": {
        "key": "dy",
        "name": "抖音",
        "channel": "抖音",
        "note_script": DY_NOTE_SCRIPT,
        "search_script": DY_SEARCH_SCRIPT,
        "comment_script": DY_COMMENT_SCRIPT,
        "ai_script": DY_AI_FILL_SCRIPT,
        "amplification_script": DY_AMPLIFICATION_SCRIPT,
        "origin_csv": DY_ORIGIN_CSV,
        "data_table_csv": DY_DATA_TABLE_CSV,
        "comment_csv": DY_COMMENT_CSV,
        "hype_workbook": DY_HYPE_WORKBOOK,
    },
}

TEN_FIELDS = [
    "笔记ID",
    "博主昵称",
    "笔记链接",
    "笔记标题",
    "笔记内容",
    "点赞量",
    "收藏量",
    "评论量",
    "分享量",
    "发布时间",
]

DATA_TABLE_FIELDS = [
    "发布时间",
    "笔记标题",
    "笔记链接",
    "笔记内容",
    "点赞量",
    "收藏量",
    "评论量",
    "分享量",
    "互动量",
    "博主昵称",
    "概括",
    "内容类型",
    "正负向",
    "业务线",
    "渠道类型",
    "具体产品/场景",
    "笔记ID",
    "是否剔除",
    "是否剔除.输出结果",
]


def python_module_score(python_bin: str, modules: list[str]) -> tuple[int, str]:
    code = (
        "import importlib, json, sys\n"
        f"mods = {json.dumps(modules)}\n"
        "ok = []\n"
        "errors = []\n"
        "for name in mods:\n"
        "    try:\n"
        "        importlib.import_module(name)\n"
        "        ok.append(name)\n"
        "    except Exception as exc:\n"
        "        errors.append(f'{name}: {exc}')\n"
        "print(json.dumps({'executable': sys.executable, 'ok': ok, 'errors': errors}, ensure_ascii=False))\n"
    )
    try:
        result = subprocess.run(
            [python_bin, "-c", code],
            cwd=str(PROJECT_ROOT),
            text=True,
            capture_output=True,
            check=False,
            timeout=10,
        )
    except Exception as exc:
        return 0, str(exc)
    detail = (result.stdout or result.stderr or "").strip()
    if result.returncode != 0:
        return 0, detail
    try:
        payload = json.loads(detail.splitlines()[-1])
        return len(payload.get("ok") or []), detail
    except Exception:
        return 0, detail


def candidate_python_bins() -> list[str]:
    raw = [
        os.environ.get("PIPELINE_PYTHON"),
        str(PROJECT_ROOT / ".venv" / "bin" / "python"),
        "/Library/Developer/CommandLineTools/usr/bin/python3",
        "/usr/bin/python3",
        shutil.which("python3.9"),
        shutil.which("python3"),
        sys.executable,
        "python3",
    ]
    seen: set[str] = set()
    candidates: list[str] = []
    for value in raw:
        if not value:
            continue
        resolved = value
        if "/" not in value:
            resolved = shutil.which(value) or value
        if resolved in seen:
            continue
        if "/" in resolved and not Path(resolved).exists():
            continue
        seen.add(resolved)
        candidates.append(resolved)
    return candidates


def choose_script_python() -> str:
    required = ["openpyxl", "faster_whisper", "av"]
    if sys.platform == "darwin":
        required.append("Vision")
    best = sys.executable
    best_score = -1
    best_detail = ""
    for candidate in candidate_python_bins():
        score, detail = python_module_score(candidate, required)
        if score > best_score:
            best = candidate
            best_score = score
            best_detail = detail
        if score == len(required):
            print(f"Pipeline child Python: {candidate}", flush=True)
            return candidate
    print(
        "Pipeline child Python warning: no candidate imported all optional modules; "
        f"using {best}. Probe: {best_detail}",
        flush=True,
    )
    return best


SCRIPT_PYTHON = choose_script_python()


def number_value(value: Any) -> int:
    text = str(value or "").strip().replace(",", "")
    if not text:
        return 0
    for suffix, factor in (("万", 10000), ("千", 1000), ("k", 1000), ("K", 1000), ("w", 10000), ("W", 10000)):
        if text.endswith(suffix):
            try:
                return int(float(text[:-len(suffix)]) * factor)
            except Exception:
                return 0
    try:
        return int(float(text))
    except Exception:
        return 0


def interaction_total(row: dict[str, Any]) -> str:
    total = sum(number_value(row.get(field)) for field in ["点赞量", "收藏量", "评论量", "分享量"])
    return str(total)


def log_value(value: Any, limit: int = 180) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) > limit:
        return text[:limit] + "..."
    return text


def json_response(handler: SimpleHTTPRequestHandler, status: int, payload: dict) -> None:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def read_json(handler: SimpleHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length") or "0")
    raw = handler.rfile.read(length).decode("utf-8") if length else "{}"
    return json.loads(raw or "{}")


def platform_config(payload: dict | str | None = None) -> dict[str, Any]:
    value = payload.get("platform") if isinstance(payload, dict) else payload
    key = str(value or "xhs").strip().lower()
    if key in ("douyin", "抖音"):
        key = "dy"
    return PLATFORM_CONFIGS.get(key, PLATFORM_CONFIGS["xhs"])


class PlatformTaskBusy(RuntimeError):
    def __init__(self, config: dict[str, Any], current: dict[str, str] | None = None):
        self.config = config
        self.current = current or {}
        task = self.current.get("task") or "其他任务"
        started_at = self.current.get("startedAt") or ""
        suffix = f"，开始时间：{started_at}" if started_at else ""
        super().__init__(f"{config['name']}当前已有任务正在执行：{task}{suffix}。请等待该平台任务完成后再启动新的{config['name']}任务。")


def platform_task_lock_path(config: dict[str, Any]) -> Path:
    return TASK_LOCK_DIR / f"{config['key']}.lock"


def read_platform_lock_state(config: dict[str, Any]) -> dict[str, str]:
    path = platform_task_lock_path(config)
    try:
        text = path.read_text(encoding="utf-8").strip()
        value = json.loads(text) if text else {}
        return {str(key): str(item) for key, item in value.items()}
    except Exception:
        return {}


def probe_platform_file_lock(config: dict[str, Any]) -> dict[str, str] | None:
    if fcntl is None:
        return None
    path = platform_task_lock_path(config)
    if not path.exists():
        return None
    try:
        handle = path.open("r+", encoding="utf-8")
    except Exception:
        return None
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            return None
        except BlockingIOError:
            return read_platform_lock_state(config) or {"task": "其他任务"}
    finally:
        handle.close()


def task_state_snapshot() -> dict[str, dict[str, str]]:
    with TASK_STATE_LOCK:
        state = {key: dict(value) for key, value in TASK_STATE.items()}
    for key, config in PLATFORM_CONFIGS.items():
        if key not in state:
            external = probe_platform_file_lock(config)
            if external:
                state[key] = external
    return state


def acquire_platform_task(config: dict[str, Any], task_name: str) -> dict[str, Any]:
    thread_lock = TASK_LOCKS[config["key"]]
    if not thread_lock.acquire(blocking=False):
        raise PlatformTaskBusy(config, task_state_snapshot().get(config["key"]))
    file_handle = None
    started_at = time.strftime("%Y-%m-%d %H:%M:%S")
    state = {
        "task": task_name,
        "startedAt": started_at,
        "pid": str(os.getpid()),
    }
    if fcntl is not None:
        TASK_LOCK_DIR.mkdir(parents=True, exist_ok=True)
        file_handle = platform_task_lock_path(config).open("a+", encoding="utf-8")
        try:
            fcntl.flock(file_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            current = read_platform_lock_state(config) or task_state_snapshot().get(config["key"])
            file_handle.close()
            thread_lock.release()
            raise PlatformTaskBusy(config, current)
        file_handle.seek(0)
        file_handle.truncate()
        json.dump(state, file_handle, ensure_ascii=False)
        file_handle.flush()
        os.fsync(file_handle.fileno())
    with TASK_STATE_LOCK:
        TASK_STATE[config["key"]] = state
    return {"thread_lock": thread_lock, "file_handle": file_handle}


def release_platform_task(config: dict[str, Any], lock: dict[str, Any]) -> None:
    with TASK_STATE_LOCK:
        TASK_STATE.pop(config["key"], None)
    file_handle = lock.get("file_handle")
    if fcntl is not None and file_handle is not None:
        try:
            fcntl.flock(file_handle.fileno(), fcntl.LOCK_UN)
        finally:
            file_handle.close()
    lock["thread_lock"].release()


def run_locked_platform_task(payload: dict, task_name: str, runner: Any) -> dict:
    config = platform_config(payload)
    lock = acquire_platform_task(config, task_name)
    try:
        return runner(payload)
    finally:
        release_platform_task(config, lock)


def extract_platform_url(text: str, config: dict[str, Any]) -> str:
    regex = DY_URL_RE if config["key"] == "dy" else URL_RE
    match = regex.search(text or "")
    return match.group(0).rstrip("。；;，,）)】]") if match else ""


def note_id_from_url(url: str, config: dict[str, Any]) -> str:
    regex = DY_NOTE_ID_RE if config["key"] == "dy" else NOTE_ID_RE
    match = regex.search(url)
    return match.group(1) if match else time.strftime("%Y%m%d%H%M%S")


def safe_name(value: str, fallback: str = "xhs") -> str:
    cleaned = re.sub(r"[^\w.\-\u4e00-\u9fff]+", "_", value, flags=re.UNICODE).strip("_")
    return (cleaned or fallback)[:64]


def make_temp_outputs(config: dict[str, Any], prefix: str) -> tuple[Path, Path]:
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S") + f"_{int(time.time() * 1000) % 1000:03d}"
    slug = safe_name(f"{config['key']}_{prefix}")
    return (
        TEMP_DIR / f"{stamp}_{slug}_origin_data.csv",
        TEMP_DIR / f"{stamp}_{slug}_10_fields.csv",
    )


def make_comment_temp(config: dict[str, Any], prefix: str) -> Path:
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S") + f"_{int(time.time() * 1000) % 1000:03d}"
    return TEMP_DIR / f"{stamp}_{safe_name(config['key'] + '_' + prefix)}_comments.csv"


def read_csv(path: Path) -> tuple[list[str], list[dict[str, Any]]]:
    if not path.exists() or path.stat().st_size == 0:
        return [], []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        rows = [dict(row) for row in reader]
    return fields, rows


def write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def append_csv_union(target: Path, source: Path) -> int:
    source_fields, source_rows = read_csv(source)
    if not source_fields:
        return 0

    target_fields, target_rows = read_csv(target)
    fields = list(target_fields)
    for field in source_fields:
        if field not in fields:
            fields.append(field)
    if not fields:
        fields = list(source_fields)

    write_csv(target, fields, target_rows + source_rows)
    return len(source_rows)


def csv_union_write_details(target: Path, source: Path, label: str, limit: int = 8) -> dict[str, Any]:
    source_fields, source_rows = read_csv(source)
    target_fields, _target_rows = read_csv(target)
    new_fields = [field for field in source_fields if field not in target_fields]
    details: list[str] = []
    for index, row in enumerate(source_rows[:limit], start=1):
        non_empty = [field for field in source_fields if str(row.get(field, "")).strip()]
        preview_fields = non_empty[:12]
        details.append(
            f"{label}第{index}行：字段数 {len(source_fields)}，非空字段 {len(non_empty)}；"
            + "；".join(f"{field}={log_value(row.get(field))}" for field in preview_fields)
        )
    omitted = max(0, len(source_rows) - len(details))
    return {
        "sourceFieldCount": len(source_fields),
        "sourceRowCount": len(source_rows),
        "newFields": new_fields,
        "writeDetails": details,
        "writeDetailsOmitted": omitted,
    }


def ensure_table_headers(path: Path, required_fields: list[str]) -> list[str]:
    fields, rows = read_csv(path)
    if not fields:
        write_csv(path, required_fields, [])
        return list(required_fields)

    changed = False
    for field in required_fields:
        if field not in fields:
            fields.append(field)
            changed = True
    if changed:
        write_csv(path, fields, rows)
    return fields


def append_rows_to_data_table(target: Path, source: Path, channel: str) -> int:
    _, source_rows = read_csv(source)
    if not source_rows:
        ensure_table_headers(target, DATA_TABLE_FIELDS)
        return 0

    fields = ensure_table_headers(target, DATA_TABLE_FIELDS)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        for row in source_rows:
            out = {field: "" for field in fields}
            for field in TEN_FIELDS:
                out[field] = row.get(field, "")
            if "互动量" in fields:
                out["互动量"] = interaction_total(row)
            if "渠道类型" in fields:
                out["渠道类型"] = row.get("渠道类型", "") or channel
            writer.writerow(out)
    return len(source_rows)


def data_table_write_details(source: Path, channel: str, limit: int = 12) -> dict[str, Any]:
    _fields, source_rows = read_csv(source)
    details: list[str] = []
    for index, row in enumerate(source_rows[:limit], start=1):
        out = {field: "" for field in DATA_TABLE_FIELDS}
        for field in TEN_FIELDS:
            out[field] = row.get(field, "")
        out["互动量"] = interaction_total(row)
        out["渠道类型"] = row.get("渠道类型", "") or channel
        fields = [
            "笔记ID",
            "发布时间",
            "笔记标题",
            "博主昵称",
            "笔记链接",
            "点赞量",
            "收藏量",
            "评论量",
            "分享量",
            "互动量",
            "渠道类型",
            "笔记内容",
        ]
        details.append(
            f"监控总表第{index}行写入："
            + "；".join(f"{field}={log_value(out.get(field))}" for field in fields)
        )
    return {
        "dataTableWriteDetails": details,
        "dataTableWriteDetailsOmitted": max(0, len(source_rows) - len(details)),
    }


def comment_write_details(source: Path, limit: int = 12) -> dict[str, Any]:
    fields, rows = read_csv(source)
    details: list[str] = []
    for index, row in enumerate(rows[:limit], start=1):
        preferred = [
            "comment_id",
            "id",
            "note_id",
            "aweme_id",
            "user.nickname",
            "nickname",
            "content",
            "text",
            "like_count",
            "create_time",
        ]
        used = [field for field in preferred if field in fields and str(row.get(field, "")).strip()]
        if not used:
            used = [field for field in fields if str(row.get(field, "")).strip()][:10]
        details.append(
            f"评论总表第{index}行写入："
            + "；".join(f"{field}={log_value(row.get(field))}" for field in used)
        )
    return {
        "commentWriteDetails": details,
        "commentWriteDetailsOmitted": max(0, len(rows) - len(details)),
    }


def platform_write_lock(config: dict[str, Any]) -> threading.Lock:
    return WRITE_LOCKS.get(config["key"], threading.Lock())


def append_pipeline_outputs(config: dict[str, Any], origin_temp: Path, summary_temp: Path) -> dict:
    origin_details = csv_union_write_details(config["origin_csv"], origin_temp, "全量字段")
    table_details = data_table_write_details(summary_temp, config["channel"])
    with platform_write_lock(config):
        result = {
            "platform": config["key"],
            "platformName": config["name"],
            "originRows": append_csv_union(config["origin_csv"], origin_temp),
            "dataRows": append_rows_to_data_table(config["data_table_csv"], summary_temp, config["channel"]),
            "origin": str(config["origin_csv"]),
            "dataTable": str(config["data_table_csv"]),
            "tempOrigin": str(origin_temp),
            "tempSummary": str(summary_temp),
        }
    return {**origin_details, **table_details, **result}


def media_info_from_origin(origin_temp: Path) -> dict[str, Any]:
    _fields, rows = read_csv(origin_temp)
    if not rows:
        return {}
    media_rows = [row for row in rows if any(str(row.get(key, "")).strip() for key in (
        "media_enrichment.image_count",
        "media_enrichment.transcript_source_count",
        "media_enrichment.image_ocr_text",
        "media_enrichment.video_transcript",
        "media_enrichment.errors",
    ))]
    errors: list[str] = []
    for row in media_rows:
        text = str(row.get("media_enrichment.errors") or "").strip()
        if text:
            errors.extend([item.strip() for item in text.split("|") if item.strip()])
    image_errors = [item for item in errors if item.startswith("image ")]
    transcript_errors = [item for item in errors if item.startswith(("video ", "audio "))]
    other_errors = [item for item in errors if item not in image_errors and item not in transcript_errors]
    error_samples = (image_errors[:4] + transcript_errors[:4] + other_errors[:4])[:12]
    return {
        "mediaDetectedRows": len(media_rows),
        "mediaImageCount": sum(number_value(row.get("media_enrichment.image_count")) for row in rows),
        "mediaTranscriptSourceCount": sum(number_value(row.get("media_enrichment.transcript_source_count")) for row in rows),
        "mediaOcrRows": sum(1 for row in rows if str(row.get("media_enrichment.image_ocr_text") or "").strip()),
        "mediaTranscriptRows": sum(1 for row in rows if str(row.get("media_enrichment.video_transcript") or "").strip()),
        "mediaErrorCount": len(errors),
        "mediaErrors": error_samples,
    }


def append_comment_output(config: dict[str, Any], comment_temp: Path) -> dict:
    details = csv_union_write_details(config["comment_csv"], comment_temp, "评论全量")
    comment_details = comment_write_details(comment_temp)
    with platform_write_lock(config):
        result = {
            "platform": config["key"],
            "platformName": config["name"],
            "commentRows": append_csv_union(config["comment_csv"], comment_temp),
            "comments": str(config["comment_csv"]),
            "tempComments": str(comment_temp),
        }
    return {**details, **comment_details, **result}


def run_checked(cmd: list[str]) -> str:
    result = subprocess.run(
        cmd,
        cwd=str(PROJECT_ROOT),
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        command = " ".join(str(part) for part in cmd)
        raise RuntimeError(
            (
                detail
                or f"{Path(cmd[1]).name if len(cmd) > 1 else cmd[0]} exited with code {result.returncode}"
            )
            + f"\n命令：{command}\nServer Python：{sys.executable}\nScript Python：{cmd[0]}"
        )
    parts = []
    if result.stdout:
        parts.append(result.stdout.rstrip())
    if result.stderr:
        parts.append("STDERR:\n" + result.stderr.rstrip())
    return "\n".join(part for part in parts if part)


def parse_json_stdout(stdout: str) -> dict[str, Any]:
    text = (stdout or "").strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except Exception:
        pass
    for line in reversed(text.splitlines()):
        line = line.strip()
        if not line:
            continue
        if line.startswith("RESULT_JSON:"):
            line = line.split(":", 1)[1].strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                return json.loads(line)
            except Exception:
                continue
    match = re.search(r"(\{[\s\S]*\})\s*$", text)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            pass
    return {"stdout": stdout}


def platform_search_filters(payload: dict, config: dict[str, Any]) -> dict[str, str]:
    nested = payload.get("filtersByPlatform")
    source = payload
    if isinstance(nested, dict):
        candidate = nested.get(config["key"]) or nested.get(config["name"])
        if isinstance(candidate, dict):
            source = candidate
    return {
        "sortBy": str(source.get("sortBy") or ("综合排序" if config["key"] == "dy" else "综合")),
        "noteType": str(source.get("noteType") or "不限"),
        "publishTime": str(source.get("publishTime") or "不限"),
        "searchScope": str(source.get("searchScope") or "不限"),
        "location": str(source.get("location") or "不限"),
        "videoDuration": str(source.get("videoDuration") or "不限"),
    }


def run_search(payload: dict) -> dict:
    config = platform_config(payload)
    keyword = str(payload.get("keyword") or "").strip()
    if not keyword:
        raise ValueError("请输入关键词")
    max_notes = int(payload.get("maxNotes") or 0)
    scroll_rounds = int(payload.get("scrollRounds") or 10)
    filters = platform_search_filters(payload, config)
    sort_by = filters["sortBy"]
    note_type = filters["noteType"]
    publish_time = filters["publishTime"]
    search_scope = filters["searchScope"]
    location = filters["location"]
    video_duration = filters["videoDuration"]
    origin_temp, summary_temp = make_temp_outputs(config, f"search_{keyword}")
    cmd = [
        SCRIPT_PYTHON,
        str(config["search_script"]),
        keyword,
        "--output",
        str(origin_temp),
        "--summary-output",
        str(summary_temp),
        "--max-notes",
        str(max_notes),
        "--scroll-rounds",
        str(max(1, scroll_rounds)),
        "--search-load-timeout",
        "24",
        "--scroll-delay",
        "3.2",
        "--request-interval",
        "2.8",
        "--sort-by",
        sort_by,
        "--note-type",
        note_type,
        "--publish-time",
        publish_time,
        "--search-scope",
        search_scope,
        "--location",
        location,
        "--headed",
    ]
    if config["key"] == "dy":
        cmd.extend(["--video-duration", video_duration])
    stdout = run_checked(cmd)
    count = 0
    for line in stdout.splitlines():
        if line.startswith("Exported ") and " notes" in line:
            try:
                count = int(line.split()[1])
            except Exception:
                count = 0
    append_info = append_pipeline_outputs(config, origin_temp, summary_temp)
    return {
        "ok": True,
        "kind": "search",
        "count": count,
        "filters": {
            "sortBy": sort_by,
            "noteType": note_type,
            "publishTime": publish_time,
            "searchScope": search_scope,
            "location": location,
            "videoDuration": video_duration,
        },
        **media_info_from_origin(origin_temp),
        **append_info,
        "stdout": stdout,
    }


def run_parallel_platforms(payload: dict, runner: Any, label: str) -> dict:
    results: list[dict[str, Any]] = []
    errors: list[str] = []
    keys = ["xhs", "dy"]
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {
            executor.submit(run_locked_platform_task, {**payload, "platform": key}, label, runner): key
            for key in keys
        }
        for future in as_completed(futures):
            key = futures[future]
            config = PLATFORM_CONFIGS[key]
            try:
                results.append(future.result())
            except Exception as exc:
                errors.append(f"{config['name']}: {exc}")

    results.sort(key=lambda item: str(item.get("platform", "")))
    ok = bool(results)
    return {
        "ok": ok,
        "partialOk": bool(results),
        "kind": label,
        "platform": "all",
        "platformName": "双平台",
        "results": results,
        "errors": errors,
        "originRows": sum(int(item.get("originRows") or 0) for item in results),
        "dataRows": sum(int(item.get("dataRows") or 0) for item in results),
        "commentRows": sum(int(item.get("commentRows") or 0) for item in results),
        "aiUpdated": sum(int(item.get("aiUpdated") or 0) for item in results),
        "localFallbackUpdated": sum(int(item.get("localFallbackUpdated") or 0) for item in results),
        "failedAiRows": sum(int(item.get("failedAiRows") or 0) for item in results),
        "attemptedAiRows": sum(int(item.get("attemptedAiRows") or 0) for item in results),
        "missingAiBefore": sum(int(item.get("missingAiBefore") or 0) for item in results),
        "missingAiAfter": sum(int(item.get("missingAiAfter") or 0) for item in results),
    }


def run_note(payload: dict) -> dict:
    config = platform_config(payload)
    text = str(payload.get("text") or "")
    url = extract_platform_url(text, config)
    if not url:
        raise ValueError(f"链接框里没有识别到{config['name']}链接")
    note_id = note_id_from_url(url, config)
    origin_temp, summary_temp = make_temp_outputs(config, f"note_{note_id}")
    stdout = run_checked([
        SCRIPT_PYTHON,
        str(config["note_script"]),
        "--use-default-profile",
        "--output",
        str(origin_temp),
        "--summary-output",
        str(summary_temp),
        url,
    ])
    append_info = append_pipeline_outputs(config, origin_temp, summary_temp)
    return {
        "ok": True,
        "kind": "note",
        "count": append_info["dataRows"],
        **media_info_from_origin(origin_temp),
        **append_info,
        "stdout": stdout,
    }


def run_comments(payload: dict) -> dict:
    config = platform_config(payload)
    text = str(payload.get("text") or "")
    url = extract_platform_url(text, config)
    if not url:
        raise ValueError(f"链接框里没有识别到{config['name']}链接")
    note_id = note_id_from_url(url, config)
    limit = int(payload.get("limit") or 0)
    comment_temp = make_comment_temp(config, f"note_{note_id}")
    stdout = run_checked([
        SCRIPT_PYTHON,
        str(config["comment_script"]),
        "--use-default-profile",
        "--output",
        str(comment_temp),
        "--limit",
        str(max(0, limit)),
        url,
    ])
    count = 0
    for line in stdout.splitlines():
        if line.startswith("Exported ") and " comments" in line:
            try:
                count = int(line.split()[1])
            except Exception:
                count = 0
    append_info = append_comment_output(config, comment_temp)
    return {
        "ok": True,
        "kind": "comments",
        "count": count,
        **append_info,
        "stdout": stdout,
    }


def run_clean_data(payload: dict) -> dict:
    config = platform_config(payload)
    scope = str(payload.get("scope") or "current").strip().lower()
    platform = "all" if scope == "all" else config["key"]
    if platform == "all":
        return run_clean_data_parallel(payload)
    stdout = run_checked([
        SCRIPT_PYTHON,
        str(CLEAN_SCRIPT),
        "--platform",
        platform,
    ])
    result = parse_json_stdout(stdout)
    return {
        "ok": True,
        "kind": "clean-data",
        "platform": platform,
        "platformName": "双平台" if platform == "all" else config["name"],
        "stdout": stdout,
        **result,
    }


def run_clean_data_parallel(payload: dict) -> dict:
    def run_one(next_payload: dict) -> dict:
        config = platform_config(next_payload)
        stdout = run_checked([
            SCRIPT_PYTHON,
            str(CLEAN_SCRIPT),
            "--platform",
            config["key"],
        ])
        try:
            result = parse_json_stdout(stdout)
        except Exception:
            result = {"stdout": stdout}
        return {
            "ok": True,
            "kind": "clean-data",
            "platform": config["key"],
            "platformName": config["name"],
            "stdout": stdout,
            **result,
        }

    combined = run_parallel_platforms(payload, run_one, "双平台去重/脏数据清洗")
    combined["beforeRows"] = sum(int(item.get("beforeRows") or 0) for item in combined["results"])
    combined["afterRows"] = sum(int(item.get("afterRows") or 0) for item in combined["results"])
    combined["removedDuplicateRows"] = sum(int(item.get("removedDuplicateRows") or 0) for item in combined["results"])
    combined["removedDirtyRows"] = sum(int(item.get("removedDirtyRows") or 0) for item in combined["results"])
    combined["filledNoteIds"] = sum(int(item.get("filledNoteIds") or 0) for item in combined["results"])
    combined["tables"] = [item.get("table", "") for item in combined["results"] if item.get("table")]
    combined["backups"] = [item.get("backup", "") for item in combined["results"] if item.get("backup")]
    combined["ok"] = combined["partialOk"]
    return combined


def build_ai_fill_command(payload: dict, progress: bool = False) -> tuple[dict[str, Any], list[str]]:
    config = platform_config(payload)
    model = str(payload.get("model") or "kimi-k2.5-external")
    limit = int(payload.get("limit") or 0)
    concurrency = int(payload.get("concurrency") or 3)
    cmd = [
        SCRIPT_PYTHON,
        str(config["ai_script"]),
        "--table",
        str(config["data_table_csv"]),
        "--origin",
        str(config["origin_csv"]),
        "--model",
        model,
        "--limit",
        str(max(0, limit)),
        "--concurrency",
        str(max(1, min(8, concurrency))),
        "--retries",
        "3",
        "--retry-rounds",
        "3",
        "--retry-failed-delay",
        "5",
        "--timeout",
        "60",
    ]
    if payload.get("noAi"):
        cmd.append("--no-ai")
    if progress:
        cmd.append("--progress")
    return config, cmd


def parse_script_result(stdout: str) -> dict:
    for line in reversed(stdout.splitlines()):
        if line.startswith("RESULT_JSON:"):
            try:
                return json.loads(line.split(":", 1)[1].strip())
            except Exception:
                break
    try:
        return json.loads(stdout)
    except Exception:
        return {"stdout": stdout}


def run_ai_fill(payload: dict) -> dict:
    config, cmd = build_ai_fill_command(payload, progress=False)
    stdout = run_checked(cmd)
    result = parse_script_result(stdout)
    return {
        "ok": True,
        "kind": "ai-fill",
        "platform": config["key"],
        "platformName": config["name"],
        "table": str(config["data_table_csv"]),
        "origin": str(config["origin_csv"]),
        "stdout": stdout,
        **result,
    }


def write_stream_event(handler: SimpleHTTPRequestHandler, payload: dict[str, Any]) -> None:
    line = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n"
    handler.wfile.write(line)
    handler.wfile.flush()


def run_ai_fill_stream(handler: SimpleHTTPRequestHandler, payload: dict) -> None:
    config, cmd = build_ai_fill_command(payload, progress=True)
    lock = acquire_platform_task(config, "AI填写总表" if not payload.get("noAi") else "只回填ID/互动量")
    handler.send_response(200)
    handler.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
    handler.send_header("Cache-Control", "no-cache")
    handler.end_headers()
    write_stream_event(handler, {
        "type": "log",
        "message": f"启动 {config['name']} AI填写进程，目标表：{config['data_table_csv']}",
    })

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(PROJECT_ROOT),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
        )
        final_result: dict[str, Any] | None = None
        collected: list[str] = []
        assert proc.stdout is not None
        for raw_line in proc.stdout:
            line = raw_line.rstrip("\n")
            collected.append(line)
            if line.startswith("AI_PROGRESS "):
                try:
                    write_stream_event(handler, {"type": "progress", "payload": json.loads(line[len("AI_PROGRESS "):])})
                except Exception:
                    write_stream_event(handler, {"type": "log", "message": line})
            elif line.startswith("RESULT_JSON:"):
                try:
                    final_result = json.loads(line.split(":", 1)[1].strip())
                    write_stream_event(handler, {"type": "result", "payload": {
                        "ok": True,
                        "kind": "ai-fill",
                        "platform": config["key"],
                        "platformName": config["name"],
                        "table": str(config["data_table_csv"]),
                        "origin": str(config["origin_csv"]),
                        "stdout": "\n".join(collected),
                        **final_result,
                    }})
                except Exception as exc:
                    write_stream_event(handler, {"type": "log", "message": f"RESULT_JSON解析失败：{exc}"})
            elif line:
                write_stream_event(handler, {"type": "log", "message": line})

        return_code = proc.wait()
        if return_code != 0:
            detail = "\n".join(collected[-20:]).strip() or f"{Path(cmd[1]).name} exited with code {return_code}"
            write_stream_event(handler, {"type": "error", "error": detail})
        elif final_result is None:
            parsed = parse_script_result("\n".join(collected))
            write_stream_event(handler, {"type": "result", "payload": {
                "ok": True,
                "kind": "ai-fill",
                "platform": config["key"],
                "platformName": config["name"],
                "table": str(config["data_table_csv"]),
                "origin": str(config["origin_csv"]),
                "stdout": "\n".join(collected),
                **parsed,
            }})
        write_stream_event(handler, {"type": "done"})
    finally:
        release_platform_task(config, lock)


def aggregate_ai_stream_results(results: list[dict[str, Any]], errors: list[str]) -> dict[str, Any]:
    return {
        "ok": bool(results),
        "partialOk": bool(results),
        "kind": "ai-fill-all",
        "platform": "all",
        "platformName": "双平台",
        "results": results,
        "errors": errors,
        "table": " | ".join(str(item.get("table", "")) for item in results if item.get("table")),
        "origin": " | ".join(str(item.get("origin", "")) for item in results if item.get("origin")),
        "stdout": "\n".join(str(item.get("stdout", "")).strip() for item in results if item.get("stdout")),
        "scannedRows": sum(int(item.get("scannedRows") or 0) for item in results),
        "deterministicChanged": sum(int(item.get("deterministicChanged") or 0) for item in results),
        "aiUpdated": sum(int(item.get("aiUpdated") or 0) for item in results),
        "localFallbackUpdated": sum(int(item.get("localFallbackUpdated") or 0) for item in results),
        "attemptedAiRows": sum(int(item.get("attemptedAiRows") or 0) for item in results),
        "failedAiRows": sum(int(item.get("failedAiRows") or 0) for item in results),
        "missingAiBefore": sum(int(item.get("missingAiBefore") or 0) for item in results),
        "missingAiAfter": sum(int(item.get("missingAiAfter") or 0) for item in results),
        "concurrency": sum(int(item.get("concurrency") or 0) for item in results),
        "retryRounds": max([int(item.get("retryRounds") or 0) for item in results] or [0]),
        "model": " | ".join(sorted({str(item.get("model", "")) for item in results if item.get("model")})),
    }


def stream_ai_fill_worker(platform_key: str, payload: dict, event_queue: queue.Queue[dict[str, Any]]) -> None:
    config, cmd = build_ai_fill_command({**payload, "platform": platform_key}, progress=True)
    try:
        lock = acquire_platform_task(config, "AI填写总表" if not payload.get("noAi") else "只回填ID/互动量")
    except PlatformTaskBusy as exc:
        event_queue.put({
            "type": "platform_done",
            "platform": config["key"],
            "platformName": config["name"],
            "error": str(exc),
            "result": None,
        })
        return
    collected: list[str] = []
    final_result: dict[str, Any] | None = None
    event_queue.put({
        "type": "log",
        "platform": config["key"],
        "platformName": config["name"],
        "message": f"【{config['name']}】启动 AI填写进程，目标表：{config['data_table_csv']}",
    })
    try:
        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(PROJECT_ROOT),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=1,
            )
        except Exception as exc:
            event_queue.put({
                "type": "platform_done",
                "platform": config["key"],
                "platformName": config["name"],
                "error": f"启动失败：{exc}",
                "result": None,
            })
            return

        assert proc.stdout is not None
        for raw_line in proc.stdout:
            line = raw_line.rstrip("\n")
            collected.append(line)
            if line.startswith("AI_PROGRESS "):
                try:
                    progress = json.loads(line[len("AI_PROGRESS "):])
                    progress["platform"] = config["key"]
                    progress["platformName"] = config["name"]
                    event_queue.put({"type": "progress", "payload": progress})
                except Exception:
                    event_queue.put({
                        "type": "log",
                        "platform": config["key"],
                        "platformName": config["name"],
                        "message": f"【{config['name']}】{line}",
                    })
            elif line.startswith("RESULT_JSON:"):
                try:
                    final_result = json.loads(line.split(":", 1)[1].strip())
                except Exception as exc:
                    event_queue.put({
                        "type": "log",
                        "platform": config["key"],
                        "platformName": config["name"],
                        "message": f"【{config['name']}】RESULT_JSON解析失败：{exc}",
                    })
            elif line:
                event_queue.put({
                    "type": "log",
                    "platform": config["key"],
                    "platformName": config["name"],
                    "message": f"【{config['name']}】{line}",
                })

        return_code = proc.wait()
        if return_code != 0:
            detail = "\n".join(collected[-20:]).strip() or f"{Path(cmd[1]).name} exited with code {return_code}"
            event_queue.put({
                "type": "platform_done",
                "platform": config["key"],
                "platformName": config["name"],
                "error": detail,
                "result": None,
            })
            return

        if final_result is None:
            final_result = parse_script_result("\n".join(collected))
        event_queue.put({
            "type": "platform_done",
            "platform": config["key"],
            "platformName": config["name"],
            "error": "",
            "result": {
                "ok": True,
                "kind": "ai-fill",
                "platform": config["key"],
                "platformName": config["name"],
                "table": str(config["data_table_csv"]),
                "origin": str(config["origin_csv"]),
                "stdout": "\n".join(collected),
                **final_result,
            },
        })
    finally:
        release_platform_task(config, lock)


def run_ai_fill_all_stream(handler: SimpleHTTPRequestHandler, payload: dict) -> None:
    handler.send_response(200)
    handler.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
    handler.send_header("Cache-Control", "no-cache")
    handler.end_headers()

    event_queue: queue.Queue[dict[str, Any]] = queue.Queue()
    threads = [
        threading.Thread(target=stream_ai_fill_worker, args=(key, payload, event_queue), daemon=True)
        for key in ("xhs", "dy")
    ]
    for thread in threads:
        thread.start()

    remaining = len(threads)
    results: list[dict[str, Any]] = []
    errors: list[str] = []
    while remaining:
        event = event_queue.get()
        if event.get("type") == "platform_done":
            remaining -= 1
            platform_name = str(event.get("platformName") or event.get("platform") or "")
            if event.get("result"):
                results.append(event["result"])
                write_stream_event(handler, {
                    "type": "log",
                    "message": f"【{platform_name}】AI填写进程结束，AI填写 {event['result'].get('aiUpdated', 0)} 行，失败 {event['result'].get('failedAiRows', 0)} 行。",
                })
            else:
                error = f"{platform_name}: {event.get('error') or '未知错误'}"
                errors.append(error)
                write_stream_event(handler, {"type": "log", "message": f"【{platform_name}】ERROR: {event.get('error') or '未知错误'}"})
            continue
        write_stream_event(handler, event)

    for thread in threads:
        thread.join(timeout=1)

    results.sort(key=lambda item: str(item.get("platform", "")))
    final_result = aggregate_ai_stream_results(results, errors)
    write_stream_event(handler, {"type": "result", "payload": final_result})
    write_stream_event(handler, {"type": "done"})


def run_amplification_export(payload: dict) -> dict:
    config = platform_config(payload)
    method = str(payload.get("method") or "hype")
    if method not in {"hype", "ai", "both"}:
        method = "hype"
    model = str(payload.get("model") or "kimi-k2.5-external")
    min_decision = str(payload.get("minDecision") or "worth")
    if min_decision not in {"worth", "test"}:
        min_decision = "worth"
    limit = int(payload.get("limit") or 0)
    start_date = str(payload.get("startDate") or "")
    end_date = str(payload.get("endDate") or "")
    cmd = [
        SCRIPT_PYTHON,
        str(config["amplification_script"]),
        "--source",
        str(config["data_table_csv"]),
        "--workbook",
        str(config["hype_workbook"]),
        "--start-date",
        start_date,
        "--end-date",
        end_date,
        "--method",
        method,
        "--model",
        model,
        "--min-decision",
        min_decision,
        "--limit",
        str(max(0, limit)),
    ]
    if payload.get("dryRun"):
        cmd.append("--dry-run")
    stdout = run_checked(cmd)
    result = {}
    result = parse_json_stdout(stdout)
    return {
        "ok": True,
        "kind": "amplification",
        "platform": config["key"],
        "platformName": config["name"],
        "stdout": stdout,
        **result,
    }


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        print("[%s] %s" % (self.log_date_time_string(), fmt % args))

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if path in ("/", "/index.html"):
            return self.serve_file(ROOT / "pipeline_gui.html", "text/html; charset=utf-8")
        if path in ("/pipeline_gui.css", "/xhs_gui.css"):
            return self.serve_file(ROOT / "pipeline_gui.css", "text/css; charset=utf-8")
        if path in ("/pipeline_gui.js", "/xhs_gui.js"):
            return self.serve_file(ROOT / "pipeline_gui.js", "text/javascript; charset=utf-8")
        if path == "/hype/styles.css":
            return self.serve_file(HYPE_ROOT / "styles.css", "text/css; charset=utf-8")
        if path == "/api/status":
            return json_response(self, 200, {
                "ok": True,
                "busy": task_state_snapshot(),
                "python": {
                    "server": sys.executable,
                    "scripts": SCRIPT_PYTHON,
                },
                "platforms": {
                    key: {
                        "name": value["name"],
                        "origin": str(value["origin_csv"]),
                        "dataTable": str(value["data_table_csv"]),
                        "comments": str(value["comment_csv"]),
                        "workbook": str(value["hype_workbook"]),
                    }
                    for key, value in PLATFORM_CONFIGS.items()
                },
            })
        self.send_error(404, "Not found")

    def do_POST(self) -> None:
        try:
            payload = read_json(self)
            if self.path == "/api/search":
                return json_response(self, 200, run_locked_platform_task(payload, "关键词批量数目查询", run_search))
            if self.path == "/api/search-all":
                return json_response(self, 200, run_parallel_platforms(payload, run_search, "关键词批量数目查询"))
            if self.path == "/api/note":
                return json_response(self, 200, run_locked_platform_task(payload, "单帖子单查询", run_note))
            if self.path == "/api/comments":
                return json_response(self, 200, run_locked_platform_task(payload, "评论爬取", run_comments))
            if self.path == "/api/clean-data":
                if str(payload.get("scope") or "current").strip().lower() == "all":
                    return json_response(self, 200, run_clean_data(payload))
                return json_response(self, 200, run_locked_platform_task(payload, "去重/脏数据清洗", run_clean_data))
            if self.path == "/api/ai-fill-all":
                return json_response(self, 200, run_parallel_platforms(payload, run_ai_fill, "AI填写总表" if not payload.get("noAi") else "只回填ID/互动量"))
            if self.path == "/api/ai-fill-all-stream":
                return run_ai_fill_all_stream(self, payload)
            if self.path == "/api/ai-fill-stream":
                return run_ai_fill_stream(self, payload)
            if self.path == "/api/ai-fill":
                return json_response(self, 200, run_locked_platform_task(payload, "AI填写总表" if not payload.get("noAi") else "只回填ID/互动量", run_ai_fill))
            if self.path == "/api/amplification-export":
                return json_response(self, 200, run_locked_platform_task(payload, "口碑加热候选写入", run_amplification_export))
            if self.path == "/api/open-hype":
                config = platform_config(payload)
                subprocess.Popen(["open", str(HYPE_ROOT / "start_tool.command")])
                return json_response(self, 200, {
                    "ok": True,
                    "platform": config["key"],
                    "hype": str(HYPE_ROOT),
                    "workbook": str(config["hype_workbook"]),
                    "url": "http://localhost:5173",
                })
            if self.path == "/api/open-dir":
                subprocess.run(["open", str(ROOT)], check=False)
                return json_response(self, 200, {"ok": True})
            self.send_error(404, "Not found")
        except PlatformTaskBusy as exc:
            return json_response(self, 409, {
                "ok": False,
                "error": str(exc),
                "platform": exc.config["key"],
                "platformName": exc.config["name"],
                "busy": exc.current,
                "alert": True,
            })
        except Exception as exc:
            return json_response(self, 500, {"ok": False, "error": str(exc)})

    def serve_file(self, path: Path, content_type: str) -> None:
        if not path.exists():
            self.send_error(404, "Not found")
            return
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def find_port(start: int = 8765) -> int:
    import socket

    for port in range(start, start + 80):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("No free local port found")


def main() -> int:
    moved = migrate_legacy_xhs_files()
    for item in moved:
        print(f"已迁移旧版小红书文件命名：{item}", flush=True)
    port = int(os.environ.get("PIPELINE_GUI_PORT") or os.environ.get("XHS_GUI_PORT") or find_port())
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print(f"Public Opinion Pipeline GUI running at {url}")
    if os.environ.get("PIPELINE_GUI_NO_OPEN") != "1":
        threading.Timer(0.35, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
