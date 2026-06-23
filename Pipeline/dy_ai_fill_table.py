#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import xhs_ai_fill_table as base
from pipeline_paths import DY_DATA_TABLE_CSV, DY_ORIGIN_CSV


ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
DATA_TABLE = DY_DATA_TABLE_CSV
ORIGIN_DATA = DY_ORIGIN_CSV

base.DATA_TABLE = DATA_TABLE
base.ORIGIN_DATA = ORIGIN_DATA


def note_id_from_url(value: str) -> str:
    text = str(value or "")
    match = re.search(r"[?&]modal_id=(\d{10,30})", text)
    if match:
        return match.group(1)
    match = re.search(r"/(?:video|note|share/video)/(\d{10,30})", text)
    return match.group(1) if match else ""


def origin_maps(origin_rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    by_url: dict[str, str] = {}
    by_title: dict[str, str] = {}
    by_note_id: dict[str, str] = {}
    for row in origin_rows:
        note_id = (
            row.get("note_id")
            or row.get("aweme_id")
            or row.get("aweme_detail.aweme_id")
            or ""
        )
        url = row.get("source_url") or row.get("aweme_detail.share_url") or ""
        title = row.get("aweme_detail.desc") or row.get("preview_title") or ""
        if note_id:
            by_note_id[note_id] = note_id
        if note_id and url:
            by_url[url] = note_id
            by_url[url.split("?")[0]] = note_id
        if note_id and title:
            by_title[title.strip()] = note_id
            by_title[title.strip()[:80]] = note_id
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
            row["互动量"] = base.interaction_sum(row)
        if not row.get("渠道类型"):
            row["渠道类型"] = "抖音"
        after = json.dumps({key: row.get(key, "") for key in tracked_fields}, ensure_ascii=False)
        if before != after:
            changed += 1
    return changed


def build_prompt(row: dict[str, Any]) -> list[dict[str, str]]:
    system = f"""
你是滴滴抖音舆情表格标注助手。请只根据用户提供的一条抖音视频/图文信息填充字段。

输出必须是严格 JSON 对象，且只能包含这些键：
概括, 内容类型, 正负向, 业务线, 渠道类型, 具体产品/场景

字段规则：
1. 概括：一句话总结这条内容在说什么，不做进一步分析。
2. 内容类型：只能从 {base.CONTENT_TYPES} 中选择一个。
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
3. 正负向：只能从 {base.SENTIMENTS} 中选择一个。
4. 业务线：只能从 {base.BUSINESS_LINES} 中选择一个。
   提到快车=快车；特惠=滴滴特惠；专车/豪华车/高端车型=专车/豪华车；
   六座/大车/多人座=六座专车；拼车=拼车；
   站点巴士/公交/大巴路线=站点巴士/公交/滴滴小巴；
   带宠物乘车=宠物出行；没有明确车型=网约车；纯品牌活动/地广=品牌；都不符合=无匹配内容。
5. 渠道类型：固定填“抖音”。
6. 具体产品/场景：只能从 {base.SCENES} 中选择一个。

不要输出 Markdown，不要解释，不要添加多余字段。
""".strip()
    user = {
        "发布时间": row.get("发布时间", ""),
        "标题": base.compact(row.get("笔记标题", ""), 220),
        "链接": row.get("笔记链接", ""),
        "内容": base.compact(row.get("笔记内容", ""), 1600),
        "点赞量": row.get("点赞量", ""),
        "收藏量": row.get("收藏量", ""),
        "评论量": row.get("评论量", ""),
        "分享量": row.get("分享量", ""),
        "互动量": row.get("互动量", ""),
        "作者昵称": row.get("博主昵称", ""),
        "笔记ID": row.get("笔记ID", ""),
    }
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
    ]


def normalize_result(result: dict) -> dict:
    out = {field: str(result.get(field, "") or "").strip() for field in base.AI_FIELDS}
    if out["内容类型"] not in base.CONTENT_TYPES:
        out["内容类型"] = "场景" if out["内容类型"] else "场景"
    if out["正负向"] not in base.SENTIMENTS:
        out["正负向"] = "中性"
    if out["业务线"] not in base.BUSINESS_LINES:
        out["业务线"] = "网约车"
    out["渠道类型"] = "抖音"
    if out["具体产品/场景"] not in base.SCENES:
        out["具体产品/场景"] = "无匹配类别"
    if not out["概括"]:
        out["概括"] = "该内容围绕滴滴相关出行体验或话题展开。"
    return out


base.note_id_from_url = note_id_from_url
base.origin_maps = origin_maps
base.backfill_deterministic = backfill_deterministic
base.build_prompt = build_prompt
base.normalize_result = normalize_result


if __name__ == "__main__":
    raise SystemExit(base.main())
