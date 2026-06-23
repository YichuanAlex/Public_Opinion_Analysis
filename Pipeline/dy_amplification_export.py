#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import xhs_amplification_export as base
from pipeline_paths import DY_DATA_TABLE_CSV, DY_HYPE_WORKBOOK


ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
HYPE_ROOT = PROJECT_ROOT / "Hype_Something"
DATA_TABLE = DY_DATA_TABLE_CSV
HYPE_WORKBOOK = DY_HYPE_WORKBOOK

DY_MONTH_NAMES = {
    1: ["1月", "一月"],
    2: ["2月", "二月"],
    3: ["3月", "三月"],
    4: ["4月", "四月"],
    5: ["5月", "五月"],
    6: ["6月", "六月"],
    7: ["7月", "七月"],
    8: ["8月", "八月"],
    9: ["9月", "九月"],
    10: ["10月", "十月"],
    11: ["11月", "十一月"],
    12: ["12月", "十二月"],
}

DY_HEADER_ROW = [
    "发布日期",
    "投放截止",
    "状态",
    "作者昵称",
    "链接",
    "笔记ID",
    "投放记录\nxx日投放xx元",
    "标题",
    "投前互动量",
    "投后笔记总互动量",
    "投放后点赞量",
    "投放后收藏量",
    "投放后评论量",
    "投放带来的互动量",
    "总投放金额",
    "投放CPE",
    "综合cpe\n*投入/笔记外层互动数据",
    "一级分类",
    "二级分类",
    "备注",
    "爆款定级",
]

base.DATA_TABLE = DATA_TABLE
base.HYPE_WORKBOOK = HYPE_WORKBOOK
_ORIGINAL_RUN = base.run


def note_id_from_url(value: str) -> str:
    text = str(value or "")
    match = re.search(r"[?&]modal_id=(\d{10,30})", text)
    if match:
        return match.group(1)
    match = re.search(r"/(?:video|note|share/video)/(\d{10,30})", text)
    return match.group(1) if match else ""


def ensure_sheet_headers(ws: Any) -> None:
    try:
        for merged_range in list(ws.merged_cells.ranges):
            ws.unmerge_cells(str(merged_range))
    except Exception:
        pass
    for col, header in enumerate(DY_HEADER_ROW, start=1):
        ws.cell(1, col).value = header
    try:
        for col in range(1, len(DY_HEADER_ROW) + 1):
            ws.cell(1, col).font = ws.cell(1, 1).font.copy(bold=True) if hasattr(ws.cell(1, 1).font, "copy") else ws.cell(1, 1).font
            ws.column_dimensions[base.col_letter(col)].width = max(ws.column_dimensions[base.col_letter(col)].width or 10, 14)
        ws.freeze_panes = "A2"
    except Exception:
        pass


def sheet_for_month(wb: Any, month: int) -> Any:
    names = DY_MONTH_NAMES.get(month, [f"{month}月"])
    for ws in wb.worksheets:
        title = ws.title
        if any(name in title for name in names) and ("加热" in title or "汇总" in title) and "废" not in title:
            ensure_sheet_headers(ws)
            return ws
    template = None
    for candidate in (f"{month}月加热汇总", "6月加热汇总", "5月加热汇总"):
        if candidate in wb.sheetnames:
            template = wb[candidate]
            break
    template = template or wb.worksheets[0]
    ws = wb.copy_worksheet(template)
    ws.title = f"{month}月加热汇总"
    for row in range(1, ws.max_row + 1):
        for col in range(1, max(ws.max_column, len(DY_HEADER_ROW)) + 1):
            ws.cell(row, col).value = None
    ensure_sheet_headers(ws)
    return ws


def first_empty_row(ws: Any, mapping: dict[str, int]) -> int:
    key_cols = [mapping.get("note_id"), mapping.get("link"), mapping.get("title")]
    key_cols = [col for col in key_cols if col]
    if not key_cols:
        return max(2, ws.max_row + 1)
    for row in range(2, max(ws.max_row, 2) + 1):
        if all(not base.clean(ws.cell(row, col).value) for col in key_cols):
            return row
    return max(2, ws.max_row + 1)


def build_ai_prompt(candidate: base.Candidate, local_decision: base.Decision) -> list[dict[str, str]]:
    system = "你是抖音口碑加热投放判断助手。必须以历史CPE、相似样本和当前互动为主要依据，且只允许正向内容进入候选，输出严格JSON。"
    user = f"""
请判断这条抖音内容是否值得进入加热投放候选池。

决策只能三选一：
- 值得加热：预期CPE好、相似历史表现较好，适合进入Excel候选表
- 建议小额测试：有潜力但不稳定，可以小预算测试
- 暂不建议加热：风险较高或与历史高CPE样本相似

只返回JSON，不要Markdown：
{{
  "decision": "值得加热 | 建议小额测试 | 暂不建议加热",
  "score": 0,
  "confidence": 0,
  "predicted_cpe_range": "",
  "suggested_budget": "",
  "summary": "",
  "reasons": []
}}

内容信息：
{json.dumps({
    "发布时间": candidate.publish_date.isoformat(),
    "标题": candidate.title,
    "正文": candidate.body[:1600],
    "作者昵称": candidate.author,
    "笔记ID": candidate.note_id,
    "正负向": candidate.sentiment,
    "投前互动量": candidate.interactions,
    "点赞量": candidate.likes,
    "收藏量": candidate.collects,
    "评论量": candidate.comments,
    "分享量": candidate.shares,
    "一级分类": candidate.category1,
    "二级分类": candidate.category2,
    "Hype本地判断": local_decision.decision,
    "Hype值得分": local_decision.score,
    "Hype预测CPE": local_decision.predicted_cpe,
    "Hype理由": local_decision.reasons,
}, ensure_ascii=False, indent=2)}
""".strip()
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


base.note_id_from_url = note_id_from_url
base.sheet_for_month = sheet_for_month
base.first_empty_row = first_empty_row
base.build_ai_prompt = build_ai_prompt


def run(args: Any) -> dict[str, Any]:
    start = base.parse_date_value(args.start_date)
    end = base.parse_date_value(args.end_date)
    if not start or not end:
        raise RuntimeError("请选择有效的开始日期和结束日期")
    if end < start:
        raise RuntimeError("结束日期不能早于开始日期")
    _, table_rows = base.read_csv(Path(args.source))
    if not table_rows:
        return {
            "source": str(Path(args.source)),
            "history": str(Path(args.history)),
            "workbook": str(Path(args.workbook)),
            "method": args.method,
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
            "totalInRange": 0,
            "positiveCandidates": 0,
            "skippedNonPositive": 0,
            "judged": 0,
            "selected": 0,
            "dryRun": args.dry_run,
            "appended": 0,
            "wouldAppend": 0,
            "skippedExisting": 0,
            "sheets": {},
            "errors": [],
            "preview": [],
        }
    return _ORIGINAL_RUN(args)


base.run = run


if __name__ == "__main__":
    raise SystemExit(base.main())
