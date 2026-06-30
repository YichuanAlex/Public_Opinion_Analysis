#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable


PROJECT_ROOT = Path(__file__).resolve().parent
PIPELINE_DIR = PROJECT_ROOT / "Pipeline"
if str(PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR))

import pipeline_gui_server as pipeline  # noqa: E402


KEYWORDS = [
    "滴滴打车",
    "滴滴快车",
    "滴滴司机",
    "滴滴宠物",
    "滴滴安全",
    "滴滴女司机",
    "滴滴专车",
    "滴滴特惠",
    "滴滴巴士",
    "滴滴香卡",
    "滴滴豪华车",
    "滴滴拼车",
    "滴滴车站",
    "滴滴海外打车",
    "滴滴轻享",
    "滴滴出租车",
    "滴滴特快",
    "滴滴 AI打车",
    "滴滴 AI 叫车",
    "滴滴IP彩蛋车",
]


def timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(message: str, level: str = "INFO") -> None:
    print(f"[{timestamp()}] [{level}] {message}", flush=True)


def section(title: str) -> None:
    print("\n" + "=" * 96, flush=True)
    log(title)
    print("=" * 96, flush=True)


def month_range_today() -> tuple[str, str]:
    today = date.today()
    return today.replace(day=1).isoformat(), today.isoformat()


def compact_errors(result: dict[str, Any] | None) -> str:
    if not result:
        return ""
    errors = result.get("errors")
    if not isinstance(errors, list) or not errors:
        return ""
    return " | ".join(str(item) for item in errors[:5])


def stdout_tail(result: dict[str, Any] | None, max_lines: int = 10) -> str:
    if not result:
        return ""
    stdout = str(result.get("stdout") or "").strip()
    if not stdout:
        parts = []
        for item in result.get("results") or []:
            if isinstance(item, dict) and item.get("stdout"):
                parts.append(str(item.get("stdout")).strip())
        stdout = "\n".join(parts)
    if not stdout:
        return ""
    lines = stdout.splitlines()
    return "\n".join(lines[-max_lines:])


def log_json_summary(label: str, result: dict[str, Any] | None, verbose_stdout: bool = False) -> None:
    if result is None:
        log(f"{label} 没有返回结果", "WARN")
        return
    summary_keys = [
        "kind",
        "platformName",
        "originRows",
        "dataRows",
        "count",
        "beforeRows",
        "afterRows",
        "removedDuplicateRows",
        "removedDirtyRows",
        "filledNoteIds",
        "scannedRows",
        "attemptedAiRows",
        "aiUpdated",
        "localFallbackUpdated",
        "failedAiRows",
        "missingAiBefore",
        "missingAiAfter",
        "positiveCandidates",
        "skippedNonPositive",
        "judged",
        "selected",
        "appended",
        "skippedExisting",
        "aiFallbackToHype",
        "workbook",
    ]
    summary = {key: result.get(key) for key in summary_keys if key in result}
    if result.get("results"):
        summary["platformResults"] = [
            {
                "platformName": item.get("platformName"),
                "originRows": item.get("originRows"),
                "dataRows": item.get("dataRows"),
                "count": item.get("count"),
                "aiUpdated": item.get("aiUpdated"),
                "failedAiRows": item.get("failedAiRows"),
                "appended": item.get("appended"),
                "selected": item.get("selected"),
                "errorCount": len(item.get("errors") or []),
            }
            for item in result.get("results", [])
            if isinstance(item, dict)
        ]
    log(f"{label} 结果摘要：{json.dumps(summary, ensure_ascii=False)}")
    errors = compact_errors(result)
    if errors:
        log(f"{label} 错误样例：{errors}", "WARN")
    if verbose_stdout:
        tail = stdout_tail(result)
        if tail:
            log(f"{label} stdout 末尾：\n{tail}")


def run_stage(
    label: str,
    func: Callable[[], dict[str, Any]],
    *,
    verbose_stdout: bool = False,
) -> dict[str, Any] | None:
    section(label)
    started = time.time()
    try:
        result = func()
        log_json_summary(label, result, verbose_stdout=verbose_stdout)
        log(f"{label} 完成，用时 {time.time() - started:.1f}s")
        return result
    except KeyboardInterrupt:
        raise
    except Exception as exc:
        log(f"{label} 失败：{exc}", "ERROR")
        log(traceback.format_exc().strip(), "DEBUG")
        return None


def keyword_payload(keyword: str, args: argparse.Namespace) -> dict[str, Any]:
    return {
        "platform": "all",
        "keyword": keyword,
        "maxNotes": args.max_notes,
        "scrollRounds": args.scroll_rounds,
        "filtersByPlatform": {
            "xhs": {
                "sortBy": "最新",
                "noteType": "不限",
                "publishTime": args.publish_time,
                "searchScope": "不限",
                "location": "不限",
            },
            "dy": {
                "sortBy": "最新发布",
                "noteType": "不限",
                "publishTime": args.publish_time,
                "searchScope": "不限",
                "location": "不限",
                "videoDuration": "不限",
            },
        },
    }


def run_keyword_searches(args: argparse.Namespace) -> None:
    section(f"xhs/dy 双平台关键词爬取：{len(KEYWORDS)} 个关键词，发布时间={args.publish_time}")
    for index, keyword in enumerate(KEYWORDS, start=1):
        label = f"关键词 {index}/{len(KEYWORDS)}：{keyword}"
        log(f"开始 {label}")
        started = time.time()
        try:
            result = pipeline.run_parallel_platforms(
                keyword_payload(keyword, args),
                pipeline.run_search,
                "双平台关键词查询",
            )
            log_json_summary(label, result, verbose_stdout=args.verbose_stdout)
            log(f"完成 {label}，用时 {time.time() - started:.1f}s")
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            log(f"{label} 失败：{exc}", "ERROR")
            log(traceback.format_exc().strip(), "DEBUG")
        if index < len(KEYWORDS) and args.keyword_sleep > 0:
            log(f"关键词间隔休眠 {args.keyword_sleep:.1f}s")
            time.sleep(args.keyword_sleep)


def run_clean_all(args: argparse.Namespace, label: str) -> dict[str, Any] | None:
    return run_stage(
        label,
        lambda: pipeline.run_clean_data({"scope": "all", "platform": "all"}),
        verbose_stdout=args.verbose_stdout,
    )


def run_ai_fill_all(args: argparse.Namespace) -> dict[str, Any] | None:
    payload = {
        "platform": "all",
        "model": args.model,
        "limit": args.ai_limit,
        "concurrency": args.ai_concurrency,
    }
    return run_stage(
        "双平台并行AI填写",
        lambda: pipeline.run_parallel_platforms(payload, pipeline.run_ai_fill, "双平台AI填写"),
        verbose_stdout=args.verbose_stdout,
    )


def run_amplification_all(args: argparse.Namespace, method: str, label: str) -> dict[str, Any] | None:
    start_date = args.start_date
    end_date = args.end_date
    if not start_date or not end_date:
        start_date, end_date = month_range_today()
    payload = {
        "platform": "all",
        "method": method,
        "model": args.model,
        "startDate": start_date,
        "endDate": end_date,
        "limit": args.hype_limit,
        "minDecision": args.min_decision,
        "dryRun": args.dry_run,
    }
    return run_stage(
        f"{label}（{start_date} 至 {end_date}）",
        lambda: pipeline.run_parallel_platforms(payload, pipeline.run_amplification_export, label),
        verbose_stdout=args.verbose_stdout,
    )


def run_cycle(args: argparse.Namespace, cycle_index: int) -> None:
    section(f"第 {cycle_index} 轮 daily work 开始")
    log(f"项目目录：{PROJECT_ROOT}")
    log(f"脚本 Python：{pipeline.SCRIPT_PYTHON}")
    log(f"关键词：{', '.join(KEYWORDS)}")
    log(f"发布时间筛选：{args.publish_time}；maxNotes={args.max_notes}；scrollRounds={args.scroll_rounds}")

    run_keyword_searches(args)
    run_clean_all(args, "清洗双平台总表（关键词爬取后）")
    run_ai_fill_all(args)
    run_clean_all(args, "清洗双平台总表（AI填写后）")
    run_amplification_all(args, "hype", "Hype模型写入Excel")
    run_amplification_all(args, "ai", "AI判断写入Excel")
    section(f"第 {cycle_index} 轮 daily work 完成")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run public opinion daily workflow forever: search, clean, AI fill, clean, and amplification export.",
    )
    parser.add_argument("--once", action="store_true", help="只执行一轮后退出，便于测试。")
    parser.add_argument("--publish-time", default="一周内", choices=["不限", "一天内", "一周内", "半年内"])
    parser.add_argument("--max-notes", type=int, default=0, help="每个平台每个关键词最大导出数；0 表示不设上限。")
    parser.add_argument("--scroll-rounds", type=int, default=10, help="每次关键词搜索的滚动轮数。")
    parser.add_argument("--keyword-sleep", type=float, default=20.0, help="关键词之间休眠秒数。")
    parser.add_argument("--cycle-sleep", type=float, default=1800.0, help="每轮结束后的休眠秒数；0 表示立即下一轮。")
    parser.add_argument("--error-sleep", type=float, default=300.0, help="整轮出现未捕获错误后的休眠秒数。")
    parser.add_argument("--model", default="kimi-k2.5-external", help="AI填写和AI判断使用的模型。")
    parser.add_argument("--ai-concurrency", type=int, default=3, help="单平台 AI 填写并发数。")
    parser.add_argument("--ai-limit", type=int, default=0, help="AI填写最多处理行数；0 表示不设上限。")
    parser.add_argument("--hype-limit", type=int, default=0, help="加热候选最多判断行数；0 表示不设上限。")
    parser.add_argument("--min-decision", default="worth", choices=["worth", "test"], help="加热入选门槛。")
    parser.add_argument("--start-date", default="", help="加热写入开始日期，默认本月1日。")
    parser.add_argument("--end-date", default="", help="加热写入结束日期，默认今天。")
    parser.add_argument("--dry-run", action="store_true", help="只预览加热写入，不写 Excel。")
    parser.add_argument("--verbose-stdout", action="store_true", help="打印各脚本 stdout 末尾，便于排错。")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cycle_index = 1
    log("daily_work.py 已启动。按 Ctrl+C 可停止。")
    while True:
        try:
            run_cycle(args, cycle_index)
        except KeyboardInterrupt:
            log("收到 Ctrl+C，daily_work.py 停止。")
            return 130
        except Exception as exc:
            log(f"第 {cycle_index} 轮出现未捕获错误：{exc}", "ERROR")
            log(traceback.format_exc().strip(), "DEBUG")
            if args.error_sleep > 0:
                log(f"错误后休眠 {args.error_sleep:.1f}s 再继续。")
                time.sleep(args.error_sleep)
        if args.once:
            log("--once 已启用，执行一轮后退出。")
            return 0
        cycle_index += 1
        if args.cycle_sleep > 0:
            log(f"整轮结束，休眠 {args.cycle_sleep:.1f}s 后继续下一轮。")
            time.sleep(args.cycle_sleep)


if __name__ == "__main__":
    raise SystemExit(main())
