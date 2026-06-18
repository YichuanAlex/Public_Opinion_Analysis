#!/usr/bin/env python3
"""
Export Douyin search-result videos/notes to CSV.

Social_Media_Copilot open-source Douyin tasks cover video links, author videos,
and comments. It does not ship a keyword-search task, so this script keeps the
same conservative browser workflow used by the XHS search exporter: open the
real search page, scroll slowly, extract aweme IDs from visible links/page JSON,
then fetch details through the browser session.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import time
import urllib.parse
from collections import OrderedDict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import dy_common as dy


PIPELINE_DIR = Path(__file__).resolve().parent
DEBUG_DIR = PIPELINE_DIR / "gui_exports" / "dy_search_debug"

PRESET_KEYWORDS = [
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
    "滴滴 AI 打车",
    "滴滴 AI 叫车",
    "滴滴IP彩蛋车",
]
DEFAULT_KEYWORD = PRESET_KEYWORDS[0]

SORT_OPTIONS = ["综合", "最新", "最多点赞", "最多评论", "最多收藏"]
NOTE_TYPE_OPTIONS = ["不限", "视频", "图文"]
PUBLISH_TIME_OPTIONS = ["不限", "一天内", "一周内", "半年内"]
SEARCH_SCOPE_OPTIONS = ["不限", "已看过", "未看过", "已关注"]
LOCATION_OPTIONS = ["不限", "同城", "附近"]
PUBLISH_TIME_DAYS = {"一天内": 1, "一周内": 7, "半年内": 183}


def build_search_url(keyword: str) -> str:
    return "https://www.douyin.com/search/" + urllib.parse.quote(keyword) + "?type=general"


def candidate_search_urls(value: str) -> List[str]:
    if value.startswith("http://") or value.startswith("https://"):
        return [value]
    encoded = urllib.parse.quote(value)
    return [
        build_search_url(value),
        f"https://www.douyin.com/search/{encoded}?type=video",
        f"https://www.douyin.com/search/{encoded}?type=general&source=normal_search",
    ]


def normalize_choice(value: str, allowed: List[str], default: str) -> str:
    clean = str(value or "").strip()
    return clean if clean in allowed else default


def extract_search_aweme_items(page: dy.browser.CdpClient) -> List[Dict[str, str]]:
    expression = r"""
(() => {
  const items = [];
  const seen = new Set();
  const pickId = (value) => {
    value = String(value || '');
    const decoded = decodeURIComponent(value);
    const patterns = [
      /[?&]modal_id=(\d{10,30})/,
      /\/video\/(\d{10,30})/,
      /\/note\/(\d{10,30})/,
      /"aweme_id"\s*:\s*"?(\d{10,30})"?/g,
      /"awemeId"\s*:\s*"?(\d{10,30})"?/g,
      /"group_id"\s*:\s*"?(\d{10,30})"?/g
    ];
    for (const pattern of patterns) {
      pattern.lastIndex = 0;
      const match = pattern.exec(decoded);
      if (match) return match[1];
    }
    return '';
  };
  const push = (id, href, anchor) => {
    if (!id || seen.has(id)) return;
    seen.add(id);
    let absolute = href || `https://www.douyin.com/video/${id}`;
    try { absolute = new URL(absolute, location.href).href; } catch (_) {}
    const card = anchor?.closest?.('[data-e2e*="search"],[data-e2e*="feed"],li,article,section,div') || anchor;
    const text = (card?.innerText || anchor?.innerText || '').trim();
    const lines = text.split(/\n+/).map(s => s.trim()).filter(Boolean);
    items.push({
      id,
      href: absolute,
      preview_title: lines[0] || '',
      preview_author: lines.find(s => /@\S+/.test(s)) || '',
      preview_text: text.slice(0, 1200)
    });
  };

  for (const anchor of Array.from(document.querySelectorAll('a[href]'))) {
    const href = anchor.getAttribute('href') || anchor.href || '';
    const id = pickId(href);
    if (id) push(id, href, anchor);
  }

  const html = document.documentElement.outerHTML || '';
  for (const pattern of [
    /"aweme_id"\s*:\s*"?(\d{10,30})"?/g,
    /"awemeId"\s*:\s*"?(\d{10,30})"?/g,
    /"group_id"\s*:\s*"?(\d{10,30})"?/g,
    /\/video\/(\d{10,30})/g,
    /[?&]modal_id=(\d{10,30})/g
  ]) {
    for (const match of html.matchAll(pattern)) {
      push(match[1], `https://www.douyin.com/video/${match[1]}`, null);
    }
  }
  return items;
})()
"""
    return page.evaluate(expression) or []


def save_debug(page: dy.browser.CdpClient, keyword: str, label: str, diagnostics: Dict[str, Any]) -> Dict[str, str]:
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    slug = re.sub(r"[^\w.\-\u4e00-\u9fff]+", "_", keyword, flags=re.UNICODE).strip("_")[:48] or "dy_search"
    base = DEBUG_DIR / f"{stamp}_{slug}_{label}"
    result = {"debugJson": str(base.with_suffix(".json"))}
    try:
        html = page.evaluate("document.documentElement.outerHTML") or ""
        html_path = base.with_suffix(".html")
        html_path.write_text(html, encoding="utf-8")
        result["debugHtml"] = str(html_path)
    except Exception as exc:
        diagnostics["html_save_error"] = str(exc)
    try:
        screenshot = page.call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True})
        data = screenshot.get("data")
        if data:
            png_path = base.with_suffix(".png")
            png_path.write_bytes(base64.b64decode(data))
            result["debugScreenshot"] = str(png_path)
    except Exception as exc:
        diagnostics["screenshot_save_error"] = str(exc)
    base.with_suffix(".json").write_text(json.dumps(diagnostics, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def collect_search_items(
    page: dy.browser.CdpClient,
    search_url: str,
    scroll_rounds: int,
    scroll_delay: float,
    stable_rounds: int,
    max_items: int,
    load_timeout: float,
) -> List[Dict[str, str]]:
    dy.navigate_and_wait(page, search_url, timeout=load_timeout, minimum_delay=max(2.5, scroll_delay))
    collected: OrderedDict[str, Dict[str, str]] = OrderedDict()
    no_new_rounds = 0
    for round_index in range(max(1, scroll_rounds + 1)):
        before = len(collected)
        for item in extract_search_aweme_items(page):
            aweme_id = item.get("id", "")
            if not aweme_id or aweme_id in collected:
                continue
            item["search_url"] = search_url
            item["search_rank"] = str(len(collected) + 1)
            collected[aweme_id] = item
            if max_items > 0 and len(collected) >= max_items:
                return list(collected.values())
        after = len(collected)
        if round_index >= scroll_rounds:
            break
        if after == before:
            no_new_rounds += 1
            if no_new_rounds >= stable_rounds:
                break
        else:
            no_new_rounds = 0
        page.evaluate(
            """
(() => {
  window.scrollBy(0, Math.max(620, Math.floor(window.innerHeight * 0.8)));
  document.dispatchEvent(new Event('scroll', { bubbles: true }));
  window.dispatchEvent(new Event('scroll'));
})()
"""
        )
        time.sleep(max(1.8, scroll_delay))
    return list(collected.values())


def media_type(row: Dict[str, Any]) -> str:
    raw = str(dy.pick(row, "aweme_detail.media_type"))
    return "图文" if raw == "2" else "视频"


def publish_timestamp(row: Dict[str, Any]) -> float:
    try:
        return float(dy.pick(row, "aweme_detail.create_time"))
    except Exception:
        return 0.0


def numeric(row: Dict[str, Any], key: str) -> int:
    try:
        return int(float(dy.pick(row, key)))
    except Exception:
        return 0


def matches_publish_time(row: Dict[str, Any], publish_time: str) -> bool:
    if publish_time == "不限":
        return True
    days = PUBLISH_TIME_DAYS.get(publish_time)
    if not days:
        return True
    timestamp = publish_timestamp(row)
    if not timestamp:
        return False
    return datetime.fromtimestamp(timestamp) >= datetime.now() - timedelta(days=days)


def apply_filters_and_sort(rows: List[OrderedDict], filters: Dict[str, str], max_notes: int) -> List[OrderedDict]:
    filtered = []
    for row in rows:
        if filters["note_type"] != "不限" and media_type(row) != filters["note_type"]:
            continue
        if not matches_publish_time(row, filters["publish_time"]):
            continue
        filtered.append(row)

    sort_by = filters["sort_by"]
    if sort_by == "最新":
        filtered.sort(key=publish_timestamp, reverse=True)
    elif sort_by == "最多点赞":
        filtered.sort(key=lambda row: numeric(row, "aweme_detail.statistics.digg_count"), reverse=True)
    elif sort_by == "最多评论":
        filtered.sort(key=lambda row: numeric(row, "aweme_detail.statistics.comment_count"), reverse=True)
    elif sort_by == "最多收藏":
        filtered.sort(key=lambda row: numeric(row, "aweme_detail.statistics.collect_count"), reverse=True)

    if max_notes > 0:
        filtered = filtered[:max_notes]
    for rank, row in enumerate(filtered, start=1):
        row["output_rank"] = rank
    return filtered


def build_origin_rows(
    page: dy.browser.CdpClient,
    keyword: str,
    search_url: str,
    items: List[Dict[str, str]],
    filters: Dict[str, str],
    request_interval: float,
    http_timeout: float,
) -> List[OrderedDict]:
    rows: List[OrderedDict] = []
    for index, item in enumerate(items, start=1):
        if index > 1:
            time.sleep(max(0.0, request_interval))
        aweme_id = item["id"]
        try:
            detail = dy.fetch_aweme_detail(page, aweme_id, http_timeout)
            flat = dy.build_flat_row(detail, item.get("href", ""), aweme_id)
        except Exception as exc:
            flat = OrderedDict()
            flat["platform"] = "douyin"
            flat["source_url"] = item.get("href", "") or dy.canonical_aweme_url(aweme_id)
            flat["note_id"] = aweme_id
            flat["aweme_id"] = aweme_id
            flat["fetch_error"] = str(exc)
            flat["raw_json"] = ""
        prefix = OrderedDict()
        prefix["search_keyword"] = keyword
        prefix["search_url"] = search_url
        prefix["search_rank"] = item.get("search_rank", index)
        prefix["filter_sort_by"] = filters["sort_by"]
        prefix["filter_note_type"] = filters["note_type"]
        prefix["filter_publish_time"] = filters["publish_time"]
        prefix["filter_search_scope"] = filters["search_scope"]
        prefix["filter_location"] = filters["location"]
        prefix["preview_title"] = item.get("preview_title", "")
        prefix["preview_author"] = item.get("preview_author", "")
        prefix["preview_text"] = item.get("preview_text", "")
        for key, value in flat.items():
            prefix[key] = value
        rows.append(prefix)
    return rows


def export_search(args: argparse.Namespace) -> Tuple[Path, Path, int]:
    keyword_or_url = args.search_url or args.keyword
    search_urls = candidate_search_urls(keyword_or_url)
    keyword = args.keyword
    output = Path(args.output) if args.output else PIPELINE_DIR / "dy_origin_data.csv"
    summary_output = Path(args.summary_output) if args.summary_output else PIPELINE_DIR / "dy_note_10_fields.csv"
    filters = {
        "sort_by": normalize_choice(args.sort_by, SORT_OPTIONS, "综合"),
        "note_type": normalize_choice(args.note_type, NOTE_TYPE_OPTIONS, "不限"),
        "publish_time": normalize_choice(args.publish_time, PUBLISH_TIME_OPTIONS, "不限"),
        "search_scope": normalize_choice(args.search_scope, SEARCH_SCOPE_OPTIONS, "不限"),
        "location": normalize_choice(args.location, LOCATION_OPTIONS, "不限"),
    }
    local_filter_active = filters["note_type"] != "不限" or filters["publish_time"] != "不限"
    collect_limit = args.max_notes
    if args.max_notes > 0 and local_filter_active:
        collect_limit = max(args.max_notes * 4, args.max_notes + 20)

    proc, page, user_dir, owns_user_dir = dy.launch_browser_page(args, "dy-search")
    try:
        items: List[Dict[str, str]] = []
        diagnostics: List[Dict[str, Any]] = []
        debug_files: Dict[str, str] = {}
        search_url = search_urls[0]
        for index, candidate_url in enumerate(search_urls, start=1):
            search_url = candidate_url
            items = collect_search_items(
                page,
                candidate_url,
                scroll_rounds=args.scroll_rounds,
                scroll_delay=args.scroll_delay,
                stable_rounds=args.stable_rounds,
                max_items=collect_limit,
                load_timeout=args.search_load_timeout,
            )
            diagnostic = dy.page_diagnostics(page)
            diagnostic["candidate_url"] = candidate_url
            diagnostic["candidate_index"] = index
            diagnostic["extracted_count"] = len(items)
            diagnostics.append(diagnostic)
            if items:
                break
            debug_files = save_debug(page, keyword, f"try{index}", diagnostic)
        if not items:
            detail = "没有从抖音搜索页识别到视频卡片。"
            if diagnostics:
                last = diagnostics[-1]
                if last.get("hasLoginText"):
                    detail += " 页面疑似出现登录/验证/安全提示，请在打开的抖音页面完成登录或验证后重试。"
                detail += f" 最后页面标题：{last.get('title', '')}；链接数：{last.get('linkCount', 0)}。"
            if debug_files:
                detail += " 已保存诊断文件：" + "，".join(debug_files.values())
            raise RuntimeError(detail)

        rows = build_origin_rows(
            page,
            keyword,
            search_url,
            items,
            filters,
            request_interval=args.request_interval,
            http_timeout=args.http_timeout,
        )
        rows = apply_filters_and_sort(rows, filters, args.max_notes)
        if not rows:
            raise RuntimeError("抖音搜索结果已加载，但筛选条件下没有可导出的内容。")
        dy.write_rows_csv(
            rows,
            output,
            preferred=[
                "search_keyword",
                "search_url",
                "search_rank",
                "output_rank",
                "platform",
                "source_url",
                "note_id",
                "aweme_id",
                "preview_title",
                "preview_author",
                "fetch_error",
            ],
        )
        dy.write_summary_csv(rows, summary_output)
        return output, summary_output, len(rows)
    finally:
        dy.cleanup(proc, page, user_dir, owns_user_dir, args)


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Export Douyin search-result videos/notes to CSV.")
    parser.add_argument("keyword", nargs="?", default=DEFAULT_KEYWORD, help="Search keyword.")
    parser.add_argument("--search-url", help="Full Douyin search URL. Overrides keyword URL building.")
    parser.add_argument("-o", "--output", help="Full-field CSV path. Defaults to Pipeline/dy_origin_data.csv.")
    parser.add_argument("--summary-output", help="10-field CSV path. Defaults to Pipeline/dy_note_10_fields.csv.")
    parser.add_argument("--max-notes", type=int, default=0, help="Maximum videos/notes to fetch. 0 means no cap.")
    parser.add_argument("--sort-by", choices=SORT_OPTIONS, default="综合")
    parser.add_argument("--note-type", choices=NOTE_TYPE_OPTIONS, default="不限")
    parser.add_argument("--publish-time", choices=PUBLISH_TIME_OPTIONS, default="不限")
    parser.add_argument("--search-scope", choices=SEARCH_SCOPE_OPTIONS, default="不限")
    parser.add_argument("--location", choices=LOCATION_OPTIONS, default="不限")
    parser.add_argument("--scroll-rounds", type=int, default=10)
    parser.add_argument("--stable-rounds", type=int, default=3)
    parser.add_argument("--scroll-delay", type=float, default=2.8)
    parser.add_argument("--search-load-timeout", type=float, default=22.0)
    parser.add_argument("--request-interval", type=float, default=2.0)
    dy.add_browser_args(parser)
    args = parser.parse_args(argv)

    try:
        output, summary_output, count = export_search(args)
    except Exception as exc:
        print(f"ERROR: {exc}", file=os.sys.stderr)
        return 1
    print(f"Exported {count} notes")
    print(f"Full CSV exported: {output}")
    print(f"10-field CSV exported: {summary_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
