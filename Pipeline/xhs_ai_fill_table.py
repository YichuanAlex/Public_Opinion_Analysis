#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import random
import re
import subprocess
import time
import urllib.error
import urllib.request
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

from pipeline_paths import XHS_DATA_TABLE_CSV, XHS_ORIGIN_CSV


ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
DATA_TABLE = XHS_DATA_TABLE_CSV
ORIGIN_DATA = XHS_ORIGIN_CSV
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


def emit_progress(enabled: bool, event: str, **payload: Any) -> None:
    if not enabled:
        return
    data = {"event": event, **payload}
    print("AI_PROGRESS " + json.dumps(data, ensure_ascii=False, separators=(",", ":")), flush=True)


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


def has_missing_ai_fields(row: dict[str, Any]) -> bool:
    return any(not str(row.get(field, "")).strip() for field in AI_FIELDS)


def missing_ai_count(rows: list[dict[str, Any]]) -> int:
    return sum(1 for row in rows if has_missing_ai_fields(row))


def compact(value: Any, limit: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def compact_result(result: dict[str, str]) -> dict[str, str]:
    return {field: compact(result.get(field, ""), 90) for field in AI_FIELDS}


def progress_row_payload(index: int, row: dict[str, Any], result: dict[str, str], method: str) -> dict[str, Any]:
    return {
        "row": index,
        "method": method,
        "noteId": compact(row.get("笔记ID", ""), 80),
        "title": compact(row.get("笔记标题", ""), 80),
        "link": compact(row.get("笔记链接", ""), 160),
        "fields": compact_result(result),
    }


def contains_any(text: str, words: list[str]) -> bool:
    return any(word and word in text for word in words)


def local_summary(row: dict[str, Any]) -> str:
    title = compact(row.get("笔记标题", ""), 80)
    body = compact(row.get("笔记内容", ""), 120)
    if title and body and body not in title:
        return compact(f"{title}：{body}", 90)
    return title or body or "该内容围绕滴滴相关出行体验或话题展开。"


def local_sentiment(text: str) -> str:
    negative = [
        "投诉", "差评", "避雷", "维权", "危险", "害怕", "恐怖", "绕路", "甩客", "拒载",
        "加价", "乱收费", "态度差", "骂人", "脏", "臭", "异味", "烟味", "客服", "不处理",
        "推诿", "赔偿", "失望", "生气", "无语", "崩溃", "垃圾", "安全问题",
    ]
    positive = [
        "暖心", "舒服", "安心", "安全感", "好评", "感谢", "贴心", "不错", "方便", "省钱",
        "便宜", "快", "准时", "干净", "整洁", "香", "漂亮", "温暖", "给力", "推荐",
    ]
    if contains_any(text, negative):
        return "负向"
    if contains_any(text, positive):
        return "正向"
    return "中性"


def local_business_line(text: str) -> str:
    rules = [
        ("站点巴士/公交/滴滴小巴", ["站点巴士", "滴滴巴士", "公交", "大巴", "小巴"]),
        ("宠物出行", ["宠物", "猫", "狗", "带宠"]),
        ("专车/豪华车", ["专车", "豪华车", "高端车型", "礼橙"]),
        ("六座专车", ["六座", "6座", "大车", "多人座"]),
        ("滴滴特惠", ["特惠"]),
        ("快车", ["快车", "特快"]),
        ("拼车", ["拼车"]),
        ("品牌", ["品牌", "广告", "地广", "站牌", "司机节", "活动"]),
    ]
    for value, words in rules:
        if contains_any(text, words):
            return value
    return "网约车" if "滴滴" in text or "打车" in text or "叫车" in text else "无匹配内容"


def local_scene(text: str) -> str:
    rules = [
        ("危险驾驶", ["超速", "疲劳驾驶", "分神驾驶", "危险驾驶"]),
        ("女性安全事件", ["女性安全", "女乘客", "害怕", "尾随"]),
        ("拒载/甩客", ["拒载", "甩客"]),
        ("态度恶劣", ["态度差", "骂人", "吵架"]),
        ("强行拼客/绕路", ["强行拼客", "绕路"]),
        ("违规收费", ["乱收费", "多收费", "加价"]),
        ("烟味/异味", ["烟味", "异味", "臭"]),
        ("车内脏乱", ["脏乱", "很脏", "脏"]),
        ("投诉无门/推诿", ["投诉无门", "推诿", "客服不处理", "不处理"]),
        ("赔偿不合理", ["赔偿"]),
        ("系统/派单问题", ["派单", "打不到车", "叫不到车", "系统"]),
        ("AI叫车/AI小滴", ["AI叫车", "AI 打车", "AI小滴", "智能叫车", "语音叫车"]),
        ("女性友好计划", ["女性优先", "女性友好", "女司机"]),
        ("宠物出行", ["宠物", "带宠", "猫", "狗"]),
        ("站点巴士", ["站点巴士", "滴滴巴士", "大巴路线"]),
        ("海外打车", ["海外", "韩国", "日本", "济州岛", "国外"]),
        ("六座专车", ["六座", "6座", "大车"]),
        ("专车/豪华车", ["专车", "豪华车"]),
        ("叫车快", ["叫车快", "很快", "秒接", "接单快"]),
        ("价格优惠", ["优惠", "便宜", "券", "省钱", "特惠"]),
        ("清新车", ["清新", "无异味"]),
        ("香卡", ["香卡", "香味"]),
        ("车内整洁", ["干净", "整洁"]),
        ("司乘温暖", ["暖心", "温暖", "感谢"]),
        ("司乘互动", ["聊天", "对话", "互动"]),
        ("司机服务", ["服务好", "贴心"]),
        ("驾驶技术", ["开车稳", "驾驶技术", "很稳"]),
        ("女司机", ["女司机"]),
        ("失物返还", ["失物", "找回", "归还"]),
        ("品牌", ["品牌", "活动"]),
        ("滴滴站牌", ["站牌", "广告牌", "地广"]),
        ("司机节", ["司机节"]),
        ("通勤上下班", ["通勤", "上班", "下班"]),
        ("深夜/晚归出行", ["深夜", "晚上", "夜晚", "晚归"]),
        ("旅游出行", ["旅游", "旅行", "景区"]),
        ("机场/高铁接送", ["机场", "高铁", "火车站"]),
        ("家庭出行/带娃", ["孩子", "宝宝", "带娃"]),
        ("带长辈出行", ["老人", "长辈", "爸妈", "父母"]),
        ("跨城出行", ["跨城", "长途"]),
        ("医院/就医", ["医院", "就医", "看病"]),
        ("马拉松/赛事", ["马拉松", "赛事"]),
    ]
    for value, words in rules:
        if contains_any(text, words):
            return value
    return "无匹配类别"


def local_content_type(text: str, sentiment: str, scene: str) -> str:
    if scene in {"危险驾驶", "女性安全事件"}:
        return "安全问题"
    if scene in {"拒载/甩客", "态度恶劣", "强行拼客/绕路", "违规收费"}:
        return "司机行为投诉"
    if scene in {"烟味/异味", "车内脏乱"}:
        return "车内环境投诉"
    if scene in {"投诉无门/推诿", "赔偿不合理", "系统/派单问题"}:
        return "平台客服投诉"
    if contains_any(text, ["维权", "投诉记录", "后续", "赔偿"]):
        return "维权记录"
    if scene in {"香卡", "车内整洁", "清新车", "司机自发装置", "特殊车型/车衣", "锦旗", "留言本"}:
        return "车内"
    if scene in {"司乘温暖", "司乘互动", "司机服务", "驾驶技术", "女司机", "失物返还", "特殊身份-听障司机", "特殊身份-退伍军人"}:
        return "司机"
    if scene in {"品牌", "滴滴站牌", "司机节"}:
        return "地广/活动"
    if scene in {"AI叫车/AI小滴", "女性友好计划", "拼车", "宠物出行", "站点巴士", "海外打车", "六座专车", "专车/豪华车", "叫车快", "价格优惠", "会员", "无障碍出行", "失物巡回", "轻享"}:
        return "产品力"
    return "场景"


def local_fallback_result(row: dict[str, Any]) -> dict[str, str]:
    text = "\n".join(
        compact(row.get(field, ""), 2000)
        for field in ["笔记标题", "笔记内容", "博主昵称", "笔记链接"]
    )
    sentiment = local_sentiment(text)
    scene = local_scene(text)
    result = {
        "概括": local_summary(row),
        "内容类型": local_content_type(text, sentiment, scene),
        "正负向": sentiment,
        "业务线": local_business_line(text),
        "渠道类型": row.get("渠道类型", "") or "小红书",
        "具体产品/场景": scene,
    }
    return normalize_result(result)


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
                "3",
                "--retry-delay",
                "2",
                "--retry-max-time",
                str(max(30, int(timeout) + 25)),
                "--retry-all-errors",
                "--connect-timeout",
                "30",
                "--max-time",
                str(max(30, int(timeout) + 10)),
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
        return urllib_post_json(endpoint, body, api_key, min(timeout, 20))
    except LlmHttpError:
        raise
    except Exception as first_error:
        try:
            return curl_post_json(endpoint, body, api_key, timeout)
        except Exception as second_error:
            first = re.sub(r"\s+", " ", str(first_error)).strip()
            second = re.sub(r"\s+", " ", str(second_error)).strip()
            raise RuntimeError(f"urllib失败: {first}; curl兜底失败: {second}") from second_error


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
    pre_delay: float = 0.0,
) -> tuple[int, Optional[dict[str, str]], str]:
    if pre_delay > 0:
        time.sleep(pre_delay)
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
    local_fallback: bool,
    progress: bool = False,
    save_callback: Optional[Callable[[], None]] = None,
) -> tuple[int, list[str], int, int, int]:
    models = expand_models(model_choice)
    candidates = [(index, row) for index, row in enumerate(rows, start=1) if needs_ai(row, overwrite)]
    if limit > 0:
        candidates = candidates[:limit]

    updated = 0
    local_fallback_updated = 0
    errors: list[str] = []
    attempted = len(candidates)
    remaining = candidates
    max_workers = max(1, min(max(1, concurrency), max(1, len(remaining))))
    total_rounds = max(1, retry_rounds)
    emit_progress(
        progress,
        "ai_scan",
        attemptedAiRows=attempted,
        concurrency=max_workers,
        retryRounds=total_rounds,
        modelChoice=model_choice,
        missingAiRows=missing_ai_count(rows),
    )

    for round_index in range(1, total_rounds + 1):
        if not remaining:
            break
        if round_index > 1 and retry_failed_delay > 0:
            emit_progress(progress, "round_wait", round=round_index, seconds=retry_failed_delay, remaining=len(remaining))
            time.sleep(retry_failed_delay)

        failures: list[tuple[int, dict[str, Any], str]] = []
        if round_index == total_rounds and round_index > 1:
            round_workers = 1
        elif round_index > 1:
            round_workers = max(1, min(max_workers, concurrency // 2 or 1))
        else:
            round_workers = max_workers
        round_retries = max(1, retries + max(0, round_index - 1))
        emit_progress(
            progress,
            "round_start",
            round=round_index,
            remaining=len(remaining),
            workers=round_workers,
            retries=round_retries,
        )
        with ThreadPoolExecutor(max_workers=round_workers) as executor:
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
                    round_retries,
                    random.uniform(0.0, min(2.0, max(0.0, delay))) if round_workers > 1 else min(2.0, max(0.0, delay)),
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
                        if save_callback:
                            save_callback()
                        emit_progress(
                            progress,
                            "row_filled",
                            **progress_row_payload(result_index, target, result, "AI"),
                            aiUpdated=updated,
                            localFallbackUpdated=local_fallback_updated,
                            missingAiRows=missing_ai_count(rows),
                            saved=True,
                        )
                else:
                    failures.append((index, row, error))
                    emit_progress(
                        progress,
                        "row_failed_round",
                        row=index,
                        title=compact(row.get("笔记标题", ""), 80),
                        round=round_index,
                        error=compact(error, 260),
                    )

        remaining = [(index, row) for index, row, _ in failures if needs_ai(row, overwrite)]
        if round_index == total_rounds:
            if local_fallback and remaining:
                for index, row, _ in failures:
                    if not needs_ai(row, overwrite):
                        continue
                    result = local_fallback_result(row)
                    target = rows[index - 1]
                    changed = False
                    for field, value in result.items():
                        if overwrite or not str(target.get(field, "")).strip():
                            target[field] = value
                            changed = True
                    if changed:
                        local_fallback_updated += 1
                        if save_callback:
                            save_callback()
                        emit_progress(
                            progress,
                            "row_filled",
                            **progress_row_payload(index, target, result, "本地规则兜底"),
                            aiUpdated=updated,
                            localFallbackUpdated=local_fallback_updated,
                            missingAiRows=missing_ai_count(rows),
                            saved=True,
                        )
                remaining = [(index, row) for index, row, _ in failures if has_missing_ai_fields(row)]
                errors = [error for index, row, error in failures if has_missing_ai_fields(row)]
            else:
                errors = [error for index, row, error in failures if needs_ai(row, overwrite)]
            if errors:
                emit_progress(progress, "final_errors", failedAiRows=len(errors), errors=[compact(item, 260) for item in errors[:5]])
        elif delay > 0:
            time.sleep(delay)

    return updated, errors, attempted, len(remaining), local_fallback_updated


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
    if deterministic_changed:
        write_csv(data_path, fields, rows)
    missing_ai_before = missing_ai_count(rows)
    emit_progress(
        args.progress,
        "start",
        table=str(data_path),
        origin=str(origin_path),
        rows=len(rows),
        deterministicChanged=deterministic_changed,
        missingAiBefore=missing_ai_before,
    )

    config = resolve_config(args)
    ai_updated = 0
    local_fallback_updated = 0
    attempted_ai_rows = 0
    failed_ai_rows = 0
    errors: list[str] = []
    if not args.no_ai:
        if not config["api_key"]:
            raise RuntimeError("未配置 LLM API Key")
        def save_current_table() -> None:
            write_csv(data_path, fields, rows)

        ai_updated, errors, attempted_ai_rows, failed_ai_rows, local_fallback_updated = fill_rows(
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
            local_fallback=not args.no_local_fallback,
            progress=args.progress,
            save_callback=save_current_table,
        )
    missing_ai_after = missing_ai_count(rows)
    write_csv(data_path, fields, rows)
    result = {
        "table": str(data_path),
        "origin": str(origin_path),
        "rows": len(rows),
        "scannedRows": len(rows),
        "missingAiBefore": missing_ai_before,
        "missingAiAfter": missing_ai_after,
        "deterministicChanged": deterministic_changed,
        "aiUpdated": ai_updated,
        "localFallbackUpdated": local_fallback_updated,
        "attemptedAiRows": attempted_ai_rows,
        "failedAiRows": failed_ai_rows,
        "concurrency": args.concurrency,
        "retryRounds": args.retry_rounds,
        "errors": errors[:8],
        "model": config["model"],
        "baseUrl": config["base_url"],
    }
    emit_progress(args.progress, "done", **result)
    return result


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Backfill note IDs/interactions and use LLM to fill XHS monitoring table fields.")
    parser.add_argument("--table", default=str(DATA_TABLE), help="Data table CSV path.")
    parser.add_argument("--origin", default=str(ORIGIN_DATA), help="xhs_origin_data.csv path.")
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
    parser.add_argument("--no-local-fallback", action="store_true", help="Do not use local rule fallback after LLM transport failures.")
    parser.add_argument("--progress", action="store_true", help="Print line-by-line progress events and a RESULT_JSON line for the GUI.")
    args = parser.parse_args(argv)

    try:
        result = run(args)
    except Exception as exc:
        print(f"ERROR: {exc}", flush=True)
        return 1
    if args.progress:
        print("RESULT_JSON: " + json.dumps(result, ensure_ascii=False, separators=(",", ":")), flush=True)
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
