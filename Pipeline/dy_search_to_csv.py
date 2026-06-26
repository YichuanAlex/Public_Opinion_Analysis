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
from media_enrichment import enrich_flat_row
from pipeline_paths import DY_ORIGIN_CSV, DY_SUMMARY_CSV


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

SORT_OPTIONS = ["综合排序", "最新发布", "最多点赞"]
NOTE_TYPE_OPTIONS = ["不限", "视频", "图文"]
PUBLISH_TIME_OPTIONS = ["不限", "一天内", "一周内", "半年内"]
VIDEO_DURATION_OPTIONS = ["不限", "1分钟以下", "1-5分钟", "5分钟以上"]
SEARCH_SCOPE_OPTIONS = ["不限", "关注的人", "最近看过", "还未看过"]
LOCATION_OPTIONS = ["不限", "同城", "附近"]
PUBLISH_TIME_DAYS = {"一天内": 1, "一周内": 7, "半年内": 183}
SORT_ALIASES = {"综合": "综合排序", "最新": "最新发布", "最多评论": "综合排序", "最多收藏": "综合排序"}
SEARCH_SCOPE_ALIASES = {"已关注": "关注的人", "已看过": "最近看过", "未看过": "还未看过"}
SORT_TYPE = {"综合排序": 0, "最多点赞": 1, "最新发布": 2}
PUBLISH_TIME_CODE = {"不限": 0, "一天内": 1, "一周内": 7, "半年内": 180}
VIDEO_DURATION_CODE = {"不限": 0, "1分钟以下": 1, "1-5分钟": 2, "5分钟以上": 3}
SEARCH_SCOPE_CODE = {"不限": 0, "关注的人": 1, "最近看过": 2, "还未看过": 3}
CONTENT_TYPE_CODE = {"不限": 0, "视频": 1, "图文": 2}


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


def normalize_choice(value: str, allowed: List[str], default: str, aliases: Optional[Dict[str, str]] = None) -> str:
    clean = str(value or "").strip()
    if aliases and clean in aliases:
        clean = aliases[clean]
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


def iter_dicts(value: Any) -> Iterable[Dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from iter_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_dicts(child)


def aweme_info_from_node(node: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    for key in ("aweme_info", "aweme_detail", "aweme", "item"):
        child = node.get(key)
        if isinstance(child, dict) and child.get("aweme_id"):
            return child
    if node.get("aweme_id") and any(key in node for key in ("desc", "author", "statistics", "create_time")):
        return node
    return None


def preview_title_from_aweme(info: Dict[str, Any]) -> str:
    text = re.sub(r"\s+", " ", str(info.get("desc") or info.get("caption") or "")).strip()
    if not text:
        return ""
    first = re.split(r"[。！？!?\\n]", text, maxsplit=1)[0].strip()
    return (first or text)[:80]


def search_items_from_api_data(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for node in iter_dicts(data):
        info = aweme_info_from_node(node)
        if not info:
            continue
        aweme_id = str(info.get("aweme_id") or "").strip()
        if not aweme_id or aweme_id in seen:
            continue
        seen.add(aweme_id)
        author = info.get("author") if isinstance(info.get("author"), dict) else {}
        href = str(info.get("share_url") or "") or dy.canonical_aweme_url(aweme_id)
        items.append({
            "id": aweme_id,
            "href": href,
            "preview_title": preview_title_from_aweme(info),
            "preview_author": str(author.get("nickname") or ""),
            "preview_text": str(info.get("desc") or "")[:1200],
            "aweme_info": info,
        })
    return items


def search_api_params(keyword: str, cursor: int, count: int, filters: Dict[str, str]) -> Dict[str, Any]:
    return {
        "keyword": keyword,
        "offset": cursor,
        "count": count,
        "search_channel": "aweme_general",
        "search_source": "normal_search",
        "query_correct_type": 1,
        "is_filter_search": int(any(
            filters.get(key) not in ("", "不限", "综合排序")
            for key in ("sort_by", "note_type", "publish_time", "search_scope", "video_duration")
        )),
        "sort_type": SORT_TYPE.get(filters.get("sort_by", "综合排序"), 0),
        "publish_time": PUBLISH_TIME_CODE.get(filters.get("publish_time", "不限"), 0),
        "filter_duration": VIDEO_DURATION_CODE.get(filters.get("video_duration", "不限"), 0),
        "content_type": CONTENT_TYPE_CODE.get(filters.get("note_type", "不限"), 0),
        "search_range": SEARCH_SCOPE_CODE.get(filters.get("search_scope", "不限"), 0),
        "from_group_id": "",
        "pc_client_type": 1,
    }


def collect_search_items_via_api(
    page: dy.browser.CdpClient,
    keyword: str,
    search_url: str,
    filters: Dict[str, str],
    scroll_rounds: int,
    max_items: int,
    request_interval: float,
    http_timeout: float,
) -> List[Dict[str, Any]]:
    collected: OrderedDict[str, Dict[str, Any]] = OrderedDict()
    cursor = 0
    count = 12
    rounds = max(1, scroll_rounds)
    for round_index in range(rounds):
        data = dy.browser_fetch_json(
            page,
            "/aweme/v1/web/general/search/single/",
            search_api_params(keyword, cursor, count, filters),
            timeout=http_timeout,
        )
        before = len(collected)
        for item in search_items_from_api_data(data):
            aweme_id = item.get("id", "")
            if not aweme_id or aweme_id in collected:
                continue
            item["search_url"] = search_url
            item["search_rank"] = str(len(collected) + 1)
            item["detail_source"] = "search_api"
            collected[str(aweme_id)] = item
            if max_items > 0 and len(collected) >= max_items:
                return list(collected.values())
        cursor_value = data.get("cursor") or data.get("offset") or data.get("next_offset")
        try:
            cursor = int(cursor_value)
        except Exception:
            cursor += count
        has_more = data.get("has_more")
        if len(collected) == before and not has_more:
            break
        if has_more in (0, False, "0", "false", "False") and round_index > 0:
            break
        time.sleep(max(0.5, request_interval))
    return list(collected.values())


def media_type(row: Dict[str, Any]) -> str:
    raw = str(dy.pick(row, "aweme_detail.media_type"))
    if raw == "2" or dy.pick(row, "aweme_detail.images.0.uri", "aweme_detail.images.0.url_list.0"):
        return "图文"
    return "视频"


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


def duration_seconds(row: Dict[str, Any]) -> float:
    value = dy.pick(row, "aweme_detail.duration", "aweme_detail.video.duration")
    try:
        seconds = float(value)
    except Exception:
        return 0.0
    if seconds > 1000:
        seconds = seconds / 1000
    return seconds


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


def matches_video_duration(row: Dict[str, Any], video_duration: str) -> bool:
    if video_duration == "不限":
        return True
    seconds = duration_seconds(row)
    if seconds <= 0:
        return False
    if video_duration == "1分钟以下":
        return seconds < 60
    if video_duration == "1-5分钟":
        return 60 <= seconds <= 300
    if video_duration == "5分钟以上":
        return seconds > 300
    return True


def apply_filters_and_sort(rows: List[OrderedDict], filters: Dict[str, str], max_notes: int) -> List[OrderedDict]:
    filtered = []
    for row in rows:
        if filters["note_type"] != "不限" and media_type(row) != filters["note_type"]:
            continue
        if not matches_publish_time(row, filters["publish_time"]):
            continue
        if not matches_video_duration(row, filters.get("video_duration", "不限")):
            continue
        filtered.append(row)

    sort_by = filters["sort_by"]
    if sort_by == "最新发布":
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
    items: List[Dict[str, Any]],
    filters: Dict[str, str],
    request_interval: float,
    http_timeout: float,
    media_enrich: bool = False,
) -> List[OrderedDict]:
    rows: List[OrderedDict] = []
    for index, item in enumerate(items, start=1):
        if index > 1:
            time.sleep(max(0.0, request_interval))
        aweme_id = item["id"]
        try:
            embedded = item.get("aweme_info")
            if isinstance(embedded, dict):
                detail = {"aweme_detail": embedded}
            else:
                detail = dy.fetch_aweme_detail(page, aweme_id, http_timeout)
            flat = dy.build_flat_row(detail, item.get("href", ""), aweme_id)
            if media_enrich:
                flat = enrich_flat_row("dy", flat)
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
        prefix["filter_video_duration"] = filters.get("video_duration", "不限")
        prefix["detail_source"] = item.get("detail_source", "")
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
    output = Path(args.output) if args.output else DY_ORIGIN_CSV
    summary_output = Path(args.summary_output) if args.summary_output else DY_SUMMARY_CSV
    filters = {
        "sort_by": normalize_choice(args.sort_by, SORT_OPTIONS, "综合排序", SORT_ALIASES),
        "note_type": normalize_choice(args.note_type, NOTE_TYPE_OPTIONS, "不限"),
        "publish_time": normalize_choice(args.publish_time, PUBLISH_TIME_OPTIONS, "不限"),
        "search_scope": normalize_choice(args.search_scope, SEARCH_SCOPE_OPTIONS, "不限", SEARCH_SCOPE_ALIASES),
        "location": normalize_choice(args.location, LOCATION_OPTIONS, "不限"),
        "video_duration": normalize_choice(args.video_duration, VIDEO_DURATION_OPTIONS, "不限"),
    }
    local_filter_active = (
        filters["note_type"] != "不限"
        or filters["publish_time"] != "不限"
        or filters["video_duration"] != "不限"
    )
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
            search_api_error = ""
            items = collect_search_items(
                page,
                candidate_url,
                scroll_rounds=args.scroll_rounds,
                scroll_delay=args.scroll_delay,
                stable_rounds=args.stable_rounds,
                max_items=collect_limit,
                load_timeout=args.search_load_timeout,
            )
            if not items:
                try:
                    items = collect_search_items_via_api(
                        page,
                        keyword,
                        candidate_url,
                        filters,
                        scroll_rounds=args.scroll_rounds,
                        max_items=collect_limit,
                        request_interval=args.request_interval,
                        http_timeout=args.http_timeout,
                    )
                except Exception as exc:
                    search_api_error = str(exc)
            diagnostic = dy.page_diagnostics(page)
            diagnostic["candidate_url"] = candidate_url
            diagnostic["candidate_index"] = index
            diagnostic["extracted_count"] = len(items)
            if search_api_error:
                diagnostic["search_api_error"] = search_api_error
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
                if last.get("search_api_error"):
                    detail += f" 搜索接口兜底失败：{last.get('search_api_error')}。"
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
            media_enrich=args.media_enrich,
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
                "detail_source",
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
    parser.add_argument("--sort-by", choices=SORT_OPTIONS + list(SORT_ALIASES.keys()), default="综合排序")
    parser.add_argument("--note-type", choices=NOTE_TYPE_OPTIONS, default="不限")
    parser.add_argument("--publish-time", choices=PUBLISH_TIME_OPTIONS, default="不限")
    parser.add_argument("--search-scope", choices=SEARCH_SCOPE_OPTIONS + list(SEARCH_SCOPE_ALIASES.keys()), default="不限")
    parser.add_argument("--location", choices=LOCATION_OPTIONS, default="不限")
    parser.add_argument("--video-duration", choices=VIDEO_DURATION_OPTIONS, default="不限")
    parser.add_argument("--scroll-rounds", type=int, default=10)
    parser.add_argument("--stable-rounds", type=int, default=3)
    parser.add_argument("--scroll-delay", type=float, default=2.8)
    parser.add_argument("--search-load-timeout", type=float, default=22.0)
    parser.add_argument("--request-interval", type=float, default=2.0)
    parser.add_argument("--media-enrich", action="store_true", help="Download each exported video's media for local OCR/ASR. Disabled by default for batch safety.")
    dy.add_browser_args(parser)
    args = parser.parse_args(argv)

    try:
        output, summary_output, count = export_search(args)
    except Exception as exc:
        if any(token in str(exc) for token in ("300013", "Too many requests", "安全限制")):
            dy.browser_profile_pool.mark_profile_blocked(getattr(args, "selected_profile_id", ""), str(exc))
        print(f"ERROR: {exc}", file=os.sys.stderr)
        return 1
    print(f"Exported {count} notes")
    print(f"Full CSV exported: {output}")
    print(f"10-field CSV exported: {summary_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
