#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
DATA_TABLE = ROOT / "Data_Table_on_Channel_Public_Opinion_Monitoring_2026.csv"
ORIGIN_DATA = ROOT / "origin_data.csv"
HYPE_LLM_CONFIG = PROJECT_ROOT / "Hype_Something" / "llm_config.json"

MODEL_OPTIONS = [
    "All Named Models",
    "All Internal Models",
    "kimi-k2.5-external",
    "minimax-m2.5-external",
    "glm-5.1-external",
    "glm-5-external",
    "glm-5-internal",
    "glm-5.1-internal",
]
MODEL_GROUPS = {
    "All Named Models": ["kimi-k2.5-external", "minimax-m2.5-external", "glm-5.1-external", "glm-5-external"],
    "All Internal Models": ["glm-5-internal", "glm-5.1-internal"],
}

SCRAPED_FIELDS = [
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
]
AI_FIELDS = ["概括", "内容类型", "正负向", "业务线", "渠道类型", "具体产品/场景"]
REQUIRED_FIELDS = SCRAPED_FIELDS + AI_FIELDS + ["笔记ID", "是否剔除", "是否剔除.输出结果"]

CONTENT_TYPES = [
    "场景",
    "产品力",
    "车内",
    "司机",
    "地广/活动",
    "安全问题",
    "司机行为投诉",
    "车内环境投诉",
    "平台客服投诉",
    "维权记录",
]
SENTIMENTS = [
    "正向",
    "负向",
    "中性",
    "无匹配类别",
    "针对这个问题我无法为你提供相应解答。你可以尝试提供其他话题，我会尽力为你提供支持和解答。",
]
BUSINESS_LINES = [
    "快车",
    "滴滴特惠",
    "专车/豪华车",
    "六座专车",
    "拼车",
    "站点巴士/公交/滴滴小巴",
    "宠物出行",
    "网约车",
    "品牌",
    "无匹配内容",
]
SCENES = [
    "通勤上下班",
    "深夜/晚归出行",
    "旅游出行",
    "机场/高铁接送",
    "家庭出行/带娃",
    "带长辈出行",
    "跨城出行",
    "医院/就医",
    "马拉松/赛事",
    "AI叫车/AI小滴",
    "女性友好计划",
    "拼车",
    "宠物出行",
    "站点巴士",
    "海外打车",
    "六座专车",
    "专车/豪华车",
    "叫车快",
    "价格优惠",
    "清新车",
    "会员",
    "无障碍出行",
    "失物巡回",
    "轻享",
    "车内整洁",
    "香卡",
    "司机自发装置",
    "特殊车型/车衣",
    "锦旗",
    "留言本",
    "司乘温暖",
    "司乘互动",
    "司机服务",
    "驾驶技术",
    "女司机",
    "失物返还",
    "特殊身份-听障司机",
    "特殊身份-退伍军人",
    "品牌",
    "滴滴站牌",
    "司机节",
    "危险驾驶",
    "女性安全事件",
    "拒载/甩客",
    "态度恶劣",
    "强行拼客/绕路",
    "违规收费",
    "烟味/异味",
    "车内脏乱",
    "投诉无门/推诿",
    "赔偿不合理",
    "系统/派单问题",
    "无匹配类别",
]


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists() or path.stat().st_size == 0:
        return [], []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def load_json(path: Path) -> dict:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {}


def note_id_from_url(value: str) -> str:
    match = re.search(r"/(?:discovery/item|explore|search_result)/([0-9a-zA-Z]{24})", value or "")
    return match.group(1) if match else ""


def to_number(value: Any) -> int:
    text = str(value or "").strip().replace(",", "")
    if not text:
        return 0
    multipliers = [("万", 10000), ("千", 1000), ("k", 1000), ("K", 1000), ("w", 10000), ("W", 10000)]
    for suffix, factor in multipliers:
        if text.endswith(suffix):
            try:
                return int(float(text[:-len(suffix)]) * factor)
            except Exception:
                return 0
    try:
        return int(float(text))
    except Exception:
        return 0


def interaction_sum(row: dict[str, Any]) -> str:
    value = sum(to_number(row.get(field)) for field in ["点赞量", "收藏量", "评论量", "分享量"])
    return str(value)


def ensure_fields(fields: list[str]) -> list[str]:
    output = list(fields)
    for field in REQUIRED_FIELDS:
        if field not in output:
            output.append(field)
    return output


def origin_maps(origin_rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    by_url: dict[str, str] = {}
    by_title: dict[str, str] = {}
    by_note_id: dict[str, str] = {}
    for row in origin_rows:
        note_id = row.get("note_id") or row.get("items.0.note_card.note_id") or row.get("items.0.id") or ""
        url = row.get("source_url") or ""
        title = row.get("items.0.note_card.title") or row.get("preview_title") or ""
        if note_id:
            by_note_id[note_id] = note_id
        if note_id and url:
            by_url[url] = note_id
            by_url[url.split("?")[0]] = note_id
        if note_id and title:
            by_title[title.strip()] = note_id
    return {"by_url": by_url, "by_title": by_title, "by_note_id": by_note_id}


def backfill_deterministic(rows: list[dict[str, Any]], maps: dict[str, dict[str, str]]) -> int:
    changed = 0
    for row in rows:
        tracked_fields = ["笔记ID", "互动量", "渠道类型"]
        before = json.dumps({key: row.get(key, "") for key in tracked_fields}, ensure_ascii=False)
        if not row.get("笔记ID"):
            url = row.get("笔记链接", "")
            title = str(row.get("笔记标题", "")).strip()
            row["笔记ID"] = (
                note_id_from_url(url)
                or maps["by_url"].get(url, "")
                or maps["by_url"].get(url.split("?")[0], "")
                or maps["by_title"].get(title, "")
            )
        if not row.get("互动量"):
            row["互动量"] = interaction_sum(row)
        if not row.get("渠道类型"):
            row["渠道类型"] = "小红书"
        after = json.dumps({key: row.get(key, "") for key in tracked_fields}, ensure_ascii=False)
        if before != after:
            changed += 1
    return changed


def needs_ai(row: dict[str, Any], overwrite: bool) -> bool:
    if overwrite:
        return bool(row.get("笔记标题") or row.get("笔记内容"))
    return any(not str(row.get(field, "")).strip() for field in AI_FIELDS)


def missing_ai_count(rows: list[dict[str, Any]]) -> int:
    return sum(1 for row in rows if any(not str(row.get(field, "")).strip() for field in AI_FIELDS))


def compact(value: Any, limit: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def build_prompt(row: dict[str, Any]) -> list[dict[str, str]]:
    system = f"""
你是滴滴小红书舆情表格标注助手。请只根据用户提供的一条小红书笔记信息填充字段。

输出必须是严格 JSON 对象，且只能包含这些键：
概括, 内容类型, 正负向, 业务线, 渠道类型, 具体产品/场景

字段规则：
1. 概括：一句话总结这篇内容在说什么，不做进一步分析。
2. 内容类型：只能从 {CONTENT_TYPES} 中选择一个。
   场景=核心是某个出行场景，产品只是背景工具；
   产品力=核心是在讲滴滴具体功能或产品；
   车内=车内硬件环境、装置、装饰；
   司机=司机本人、服务、互动、温暖故事；
   地广/活动=线下广告牌、品牌活动、司机节；
   安全问题=投诉涉及人身安全风险；
   司机行为投诉=投诉司机具体行为；
   车内环境投诉=投诉烟味、异味、脏乱；
   平台客服投诉=投诉滴滴平台机制、客服处理、派单加价；
   维权记录=记录维权过程。
3. 正负向：只能从 {SENTIMENTS} 中选择一个。
4. 业务线：只能从 {BUSINESS_LINES} 中选择一个。
   提到快车=快车；特惠=滴滴特惠；专车/豪华车/高端车型=专车/豪华车；
   六座/大车/多人座=六座专车；拼车=拼车；
   站点巴士/公交/大巴路线=站点巴士/公交/滴滴小巴；
   带宠物乘车=宠物出行；没有明确车型=网约车；纯品牌活动/地广=品牌；都不符合=无匹配内容。
5. 渠道类型：固定填“小红书”。
6. 具体产品/场景：只能从 {SCENES} 中选择一个。

不要输出 Markdown，不要解释，不要添加多余字段。
""".strip()
    user = {
        "发布时间": row.get("发布时间", ""),
        "笔记标题": compact(row.get("笔记标题", ""), 220),
        "笔记链接": row.get("笔记链接", ""),
        "笔记内容": compact(row.get("笔记内容", ""), 1600),
        "点赞量": row.get("点赞量", ""),
        "收藏量": row.get("收藏量", ""),
        "评论量": row.get("评论量", ""),
        "分享量": row.get("分享量", ""),
        "互动量": row.get("互动量", ""),
        "博主昵称": row.get("博主昵称", ""),
        "笔记ID": row.get("笔记ID", ""),
    }
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
    ]


def extract_json(text: str) -> dict:
    clean = text.strip()
    clean = re.sub(r"^```(?:json)?\s*", "", clean)
    clean = re.sub(r"\s*```$", "", clean)
    try:
        return json.loads(clean)
    except Exception:
        match = re.search(r"\{.*\}", clean, flags=re.S)
        if match:
            return json.loads(match.group(0))
        raise


def normalize_result(result: dict) -> dict:
    out = {field: str(result.get(field, "") or "").strip() for field in AI_FIELDS}
    if out["内容类型"] not in CONTENT_TYPES:
        out["内容类型"] = "场景" if out["内容类型"] else "场景"
    if out["正负向"] not in SENTIMENTS:
        out["正负向"] = "中性"
    if out["业务线"] not in BUSINESS_LINES:
        out["业务线"] = "网约车"
    out["渠道类型"] = "小红书"
    if out["具体产品/场景"] not in SCENES:
        out["具体产品/场景"] = "无匹配类别"
    if not out["概括"]:
        out["概括"] = "该笔记围绕滴滴相关出行体验或话题展开。"
    return out


def endpoint_candidates(base_url: str) -> list[str]:
    base = base_url.rstrip("/")
    urls = [f"{base}/chat/completions"]
    if not base.endswith("/v1"):
        urls.append(f"{base}/v1/chat/completions")
    return urls


class LlmHttpError(RuntimeError):
    def __init__(self, status_code: int, body: str):
        super().__init__(f"HTTP {status_code}: {body[:500]}")
        self.status_code = status_code


def curl_config_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def curl_post_json(endpoint: str, body: bytes, api_key: str, timeout: float) -> dict:
    temp_path = ""
    try:
        with tempfile.NamedTemporaryFile("wb", delete=False) as handle:
            handle.write(body)
            temp_path = handle.name
        config = "\n".join(
            [
                f"url = {curl_config_quote(endpoint)}",
                'request = "POST"',
                'header = "Content-Type: application/json"',
                f"header = {curl_config_quote('Authorization: Bearer ' + api_key)}",
                f"data-binary = @{temp_path}",
            ]
        )
        result = subprocess.run(
            [
                "curl",
                "-sS",
                "--http1.1",
                "--tlsv1.2",
                "--no-keepalive",
                "--retry",
                "1",
                "--retry-delay",
                "2",
                "--retry-all-errors",
                "--connect-timeout",
                "20",
                "--max-time",
                str(max(20, int(timeout))),
                "-w",
                "\n%{http_code}",
                "--config",
                "-",
            ],
            input=config,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout or f"curl exit {result.returncode}").strip())
        response_text, _, status_text = result.stdout.rpartition("\n")
        status = int(status_text) if status_text.isdigit() else 0
        if status < 200 or status >= 300:
            raise LlmHttpError(status, response_text)
        return json.loads(response_text)
    finally:
        if temp_path:
            try:
                os.unlink(temp_path)
            except OSError:
                pass


def urllib_post_json(endpoint: str, body: bytes, api_key: str, timeout: float) -> dict:
    req = urllib.request.Request(
        endpoint,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "Connection": "close",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise LlmHttpError(exc.code, exc.read().decode("utf-8", errors="replace")) from exc


def post_json_with_fallback(endpoint: str, body: bytes, api_key: str, timeout: float) -> dict:
    try:
        return urllib_post_json(endpoint, body, min(timeout, 20))
    except LlmHttpError:
        raise
    except Exception as first_error:
        try:
            return curl_post_json(endpoint, body, api_key, timeout)
        except Exception as second_error:
            raise RuntimeError(f"urllib失败: {first_error}; curl兜底失败: {second_error}") from second_error


def call_llm(
    messages: list[dict[str, str]],
    model: str,
    api_key: str,
    base_url: str,
    temperature: float,
    timeout: float,
    retries: int = 3,
) -> dict:
    request = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "response_format": {"type": "json_object"},
    }
    body = json.dumps(request, ensure_ascii=False).encode("utf-8")
    last_error: Optional[Exception] = None
    for endpoint in endpoint_candidates(base_url):
        for attempt in range(1, max(1, retries) + 1):
            try:
                payload = post_json_with_fallback(endpoint, body, api_key, timeout)
                content = payload["choices"][0]["message"]["content"]
                return normalize_result(extract_json(content))
            except LlmHttpError as exc:
                last_error = exc
                if exc.status_code == 404:
                    break
                if exc.status_code in (408, 409, 425, 429, 500, 502, 503, 504) and attempt < retries:
                    time.sleep(min(8, 1.5 * attempt))
                    continue
                break
            except Exception as exc:
                last_error = exc
                if attempt < retries:
                    time.sleep(min(8, 1.5 * attempt))
                    continue
                break
    raise RuntimeError(str(last_error) if last_error else "LLM request failed")


def expand_models(model_choice: str) -> list[str]:
    return MODEL_GROUPS.get(model_choice, [model_choice if model_choice in MODEL_OPTIONS else "kimi-k2.5-external"])


def fill_one_row(
    index: int,
    row: dict[str, Any],
    models: list[str],
    api_key: str,
    base_url: str,
    temperature: float,
    timeout: float,
    retries: int,
) -> tuple[int, Optional[dict[str, str]], str]:
    messages = build_prompt(row)
    failures: list[str] = []
    for model in models:
        try:
            return index, call_llm(messages, model, api_key, base_url, temperature, timeout, retries), ""
        except Exception as exc:
            failures.append(f"model {model}: {exc}")
    return index, None, f"row {index}: " + " | ".join(failures)


def fill_rows(
    rows: list[dict[str, Any]],
    model_choice: str,
    api_key: str,
    base_url: str,
    limit: int,
    overwrite: bool,
    delay: float,
    temperature: float,
    timeout: float,
    retries: int,
    concurrency: int,
    retry_rounds: int,
    retry_failed_delay: float,
) -> tuple[int, list[str], int, int]:
    models = expand_models(model_choice)
    candidates = [(index, row) for index, row in enumerate(rows, start=1) if needs_ai(row, overwrite)]
    if limit > 0:
        candidates = candidates[:limit]

    updated = 0
    errors: list[str] = []
    attempted = len(candidates)
    remaining = candidates
    max_workers = max(1, min(max(1, concurrency), max(1, len(remaining))))
    total_rounds = max(1, retry_rounds)

    for round_index in range(1, total_rounds + 1):
        if not remaining:
            break
        if round_index > 1 and retry_failed_delay > 0:
            time.sleep(retry_failed_delay)

        failures: list[tuple[int, dict[str, Any], str]] = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    fill_one_row,
                    index,
                    row,
                    models,
                    api_key,
                    base_url,
                    temperature,
                    timeout,
                    retries,
                ): (index, row)
                for index, row in remaining
            }
            for future in as_completed(futures):
                index, row = futures[future]
                try:
                    result_index, result, error = future.result()
                except Exception as exc:
                    failures.append((index, row, f"row {index}: {exc}"))
                    continue
                if result:
                    target = rows[result_index - 1]
                    changed = False
                    for field, value in result.items():
                        if overwrite or not str(target.get(field, "")).strip():
                            target[field] = value
                            changed = True
                    if changed:
                        updated += 1
                else:
                    failures.append((index, row, error))

        remaining = [(index, row) for index, row, _ in failures if needs_ai(row, overwrite)]
        if round_index == total_rounds:
            errors = [error for index, row, error in failures if needs_ai(row, overwrite)]
        elif delay > 0:
            time.sleep(delay)

    return updated, errors, attempted, len(remaining)


def resolve_config(args: argparse.Namespace) -> dict:
    config = load_json(HYPE_LLM_CONFIG)
    return {
        "api_key": args.api_key or os.environ.get("OPENAI_API_KEY") or config.get("apiKey") or "",
        "base_url": args.base_url or os.environ.get("OPENAI_BASE_URL") or config.get("baseUrl") or "https://llm-proxy.intra.xiaojukeji.com",
        "model": args.model or config.get("model") or "kimi-k2.5-external",
    }


def run(args: argparse.Namespace) -> dict:
    data_path = Path(args.table)
    origin_path = Path(args.origin)
    fields, rows = read_csv(data_path)
    if not fields:
        raise RuntimeError(f"表格不存在或为空: {data_path}")
    fields = ensure_fields(fields)
    origin_fields, origin_rows = read_csv(origin_path)
    maps = origin_maps(origin_rows) if origin_fields else {"by_url": {}, "by_title": {}, "by_note_id": {}}
    deterministic_changed = backfill_deterministic(rows, maps)
    missing_ai_before = missing_ai_count(rows)

    config = resolve_config(args)
    ai_updated = 0
    attempted_ai_rows = 0
    failed_ai_rows = 0
    errors: list[str] = []
    if not args.no_ai:
        if not config["api_key"]:
            raise RuntimeError("未配置 LLM API Key")
        ai_updated, errors, attempted_ai_rows, failed_ai_rows = fill_rows(
            rows,
            model_choice=config["model"],
            api_key=config["api_key"],
            base_url=config["base_url"],
            limit=args.limit,
            overwrite=args.overwrite,
            delay=args.delay,
            temperature=args.temperature,
            timeout=args.timeout,
            retries=args.retries,
            concurrency=args.concurrency,
            retry_rounds=args.retry_rounds,
            retry_failed_delay=args.retry_failed_delay,
        )
    missing_ai_after = missing_ai_count(rows)
    write_csv(data_path, fields, rows)
    return {
        "table": str(data_path),
        "origin": str(origin_path),
        "rows": len(rows),
        "scannedRows": len(rows),
        "missingAiBefore": missing_ai_before,
        "missingAiAfter": missing_ai_after,
        "deterministicChanged": deterministic_changed,
        "aiUpdated": ai_updated,
        "attemptedAiRows": attempted_ai_rows,
        "failedAiRows": failed_ai_rows,
        "concurrency": args.concurrency,
        "retryRounds": args.retry_rounds,
        "errors": errors[:8],
        "model": config["model"],
        "baseUrl": config["base_url"],
    }


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Backfill note IDs/interactions and use LLM to fill XHS monitoring table fields.")
    parser.add_argument("--table", default=str(DATA_TABLE), help="Data table CSV path.")
    parser.add_argument("--origin", default=str(ORIGIN_DATA), help="origin_data.csv path.")
    parser.add_argument("--model", choices=MODEL_OPTIONS, default="", help="LLM model option.")
    parser.add_argument("--api-key", default="", help="LLM API key. Defaults to env/config.")
    parser.add_argument("--base-url", default="", help="LLM base URL. Defaults to env/config.")
    parser.add_argument("--limit", type=int, default=0, help="Maximum rows to fill with AI. 0 means all currently blank rows.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing AI fields.")
    parser.add_argument("--no-ai", action="store_true", help="Only backfill note IDs, interaction count, and channel.")
    parser.add_argument("--delay", type=float, default=0.8, help="Seconds to wait between LLM calls.")
    parser.add_argument("--temperature", type=float, default=0.1)
    parser.add_argument("--timeout", type=float, default=35.0)
    parser.add_argument("--retries", type=int, default=2, help="Retry count per row/model for transient LLM transport errors.")
    parser.add_argument("--concurrency", type=int, default=3, help="Concurrent LLM workers for filling rows.")
    parser.add_argument("--retry-rounds", type=int, default=2, help="How many rounds to retry rows that still failed.")
    parser.add_argument("--retry-failed-delay", type=float, default=3.0, help="Seconds to wait before each failed-row retry round.")
    args = parser.parse_args(argv)

    try:
        result = run(args)
    except Exception as exc:
        print(f"ERROR: {exc}", flush=True)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
