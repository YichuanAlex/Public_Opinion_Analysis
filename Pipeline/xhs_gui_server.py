#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import csv
import re
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
HYPE_ROOT = PROJECT_ROOT / "Hype_Something"
NOTE_SCRIPT = ROOT / "xhs_note_to_csv.py"
SEARCH_SCRIPT = ROOT / "xhs_search_to_csv.py"
COMMENT_SCRIPT = ROOT / "xhs_comment_to_csv.py"
AI_FILL_SCRIPT = ROOT / "xhs_ai_fill_table.py"
AMPLIFICATION_SCRIPT = ROOT / "xhs_amplification_export.py"
ORIGIN_CSV = ROOT / "origin_data.csv"
DATA_TABLE_CSV = ROOT / "Data_Table_on_Channel_Public_Opinion_Monitoring_2026.csv"
COMMENT_CSV = ROOT / "xhs_comments.csv"
HYPE_WORKBOOK = HYPE_ROOT / "2026_Didi_Xiaohongshu_Daily_Word-of-Mouth_Amplification.xlsx"
DY_NOTE_SCRIPT = ROOT / "dy_note_to_csv.py"
DY_SEARCH_SCRIPT = ROOT / "dy_search_to_csv.py"
DY_COMMENT_SCRIPT = ROOT / "dy_comment_to_csv.py"
DY_AI_FILL_SCRIPT = ROOT / "dy_ai_fill_table.py"
DY_AMPLIFICATION_SCRIPT = ROOT / "dy_amplification_export.py"
DY_ORIGIN_CSV = ROOT / "dy_origin_data.csv"
DY_DATA_TABLE_CSV = ROOT / "dy_Data_Table_on_Channel_Public_Opinion_Monitoring_2026.csv"
DY_COMMENT_CSV = ROOT / "dy_comments.csv"
DY_HYPE_WORKBOOK = HYPE_ROOT / "2026_Didi_Douyin_Daily_Word-of-Mouth_Amplification.xlsx"
EXPORT_DIR = ROOT / "gui_exports"
TEMP_DIR = EXPORT_DIR / "session_tmp"
WRITE_LOCK = threading.Lock()

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


def append_pipeline_outputs(config: dict[str, Any], origin_temp: Path, summary_temp: Path) -> dict:
    with WRITE_LOCK:
        return {
            "platform": config["key"],
            "platformName": config["name"],
            "originRows": append_csv_union(config["origin_csv"], origin_temp),
            "dataRows": append_rows_to_data_table(config["data_table_csv"], summary_temp, config["channel"]),
            "origin": str(config["origin_csv"]),
            "dataTable": str(config["data_table_csv"]),
            "tempOrigin": str(origin_temp),
            "tempSummary": str(summary_temp),
        }


def append_comment_output(config: dict[str, Any], comment_temp: Path) -> dict:
    with WRITE_LOCK:
        return {
            "platform": config["key"],
            "platformName": config["name"],
            "commentRows": append_csv_union(config["comment_csv"], comment_temp),
            "comments": str(config["comment_csv"]),
            "tempComments": str(comment_temp),
        }


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
        raise RuntimeError(detail or f"{Path(cmd[1]).name} exited with code {result.returncode}")
    return result.stdout or ""


def run_search(payload: dict) -> dict:
    config = platform_config(payload)
    keyword = str(payload.get("keyword") or "").strip()
    if not keyword:
        raise ValueError("请输入关键词")
    max_notes = int(payload.get("maxNotes") or 0)
    scroll_rounds = int(payload.get("scrollRounds") or 10)
    sort_by = str(payload.get("sortBy") or "综合")
    note_type = str(payload.get("noteType") or "不限")
    publish_time = str(payload.get("publishTime") or "不限")
    search_scope = str(payload.get("searchScope") or "不限")
    location = str(payload.get("location") or "不限")
    origin_temp, summary_temp = make_temp_outputs(config, f"search_{keyword}")
    stdout = run_checked([
        sys.executable,
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
    ])
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
        },
        **append_info,
        "stdout": stdout,
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
        sys.executable,
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
        sys.executable,
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


def run_ai_fill(payload: dict) -> dict:
    config = platform_config(payload)
    model = str(payload.get("model") or "kimi-k2.5-external")
    limit = int(payload.get("limit") or 0)
    concurrency = int(payload.get("concurrency") or 3)
    cmd = [
        sys.executable,
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
    ]
    if payload.get("noAi"):
        cmd.append("--no-ai")
    stdout = run_checked(cmd)
    result = {}
    try:
        result = json.loads(stdout)
    except Exception:
        result = {"stdout": stdout}
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
        sys.executable,
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
    try:
        result = json.loads(stdout)
    except Exception:
        result = {"stdout": stdout}
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
            return self.serve_file(ROOT / "xhs_gui.html", "text/html; charset=utf-8")
        if path == "/xhs_gui.css":
            return self.serve_file(ROOT / "xhs_gui.css", "text/css; charset=utf-8")
        if path == "/xhs_gui.js":
            return self.serve_file(ROOT / "xhs_gui.js", "text/javascript; charset=utf-8")
        if path == "/hype/styles.css":
            return self.serve_file(HYPE_ROOT / "styles.css", "text/css; charset=utf-8")
        if path == "/api/status":
            return json_response(self, 200, {
                "ok": True,
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
                return json_response(self, 200, run_search(payload))
            if self.path == "/api/note":
                return json_response(self, 200, run_note(payload))
            if self.path == "/api/comments":
                return json_response(self, 200, run_comments(payload))
            if self.path == "/api/ai-fill":
                return json_response(self, 200, run_ai_fill(payload))
            if self.path == "/api/amplification-export":
                return json_response(self, 200, run_amplification_export(payload))
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
    port = int(os.environ.get("XHS_GUI_PORT") or find_port())
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print(f"XHS GUI running at {url}")
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
