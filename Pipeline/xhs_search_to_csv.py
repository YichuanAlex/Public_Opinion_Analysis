#!/usr/bin/env python3
"""
Export Xiaohongshu search-result notes to CSV.

The script uses the same browser-signing and feed-detail flow as
xhs_note_to_csv.py. It loads the search page in Chrome, scrolls conservatively
to collect note links and xsec tokens, then fetches note detail one by one.
"""

from __future__ import annotations

import argparse
import base64
import csv
import json
import os
import re
import shutil
import tempfile
import time
import urllib.parse
from collections import OrderedDict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import xhs_note_to_csv as note_exporter


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
PIPELINE_DIR = Path(__file__).resolve().parent
DEBUG_DIR = PIPELINE_DIR / "gui_exports" / "search_debug"

SORT_OPTIONS = ["综合", "最新", "最多点赞", "最多评论", "最多收藏"]
NOTE_TYPE_OPTIONS = ["不限", "视频", "图文"]
PUBLISH_TIME_OPTIONS = ["不限", "一天内", "一周内", "半年内"]
SEARCH_SCOPE_OPTIONS = ["不限", "已看过", "未看过", "已关注"]
LOCATION_OPTIONS = ["不限", "同城", "附近"]
PUBLISH_TIME_DAYS = {
    "一天内": 1,
    "一周内": 7,
    "半年内": 183,
}


def build_search_url(keyword: str, ai: bool = True, double_encode: bool = False) -> str:
    encoded = urllib.parse.quote(keyword)
    if double_encode:
        encoded = urllib.parse.quote(encoded)
    path = "search_result_ai" if ai else "search_result"
    return (
        f"https://www.xiaohongshu.com/{path}?keyword="
        + encoded
        + "&source=web_explore_feed"
    )


def candidate_search_urls(value: str) -> List[str]:
    if value.startswith("http://") or value.startswith("https://"):
        return [value]
    return [
        build_search_url(value, ai=True, double_encode=False),
        build_search_url(value, ai=False, double_encode=False),
        build_search_url(value, ai=True, double_encode=True),
    ]


def parse_search_note_url(href: str) -> Dict[str, str]:
    parsed = urllib.parse.urlparse(href)
    note_id = parsed.path.rstrip("/").split("/")[-1]
    if len(note_id) != 24 or not note_id.isalnum():
        return {}
    params = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
    token = (params.get("xsec_token") or [""])[0]
    if not token:
        return {}
    source = (params.get("xsec_source") or [""])[0]
    return {
        "id": note_id,
        "href": href,
        "token": token,
        "source": source,
    }


def decode_htmlish_url(value: str) -> str:
    return (
        value.replace("&amp;", "&")
        .replace("\\u002F", "/")
        .replace("\\/", "/")
        .replace("\\u003F", "?")
        .replace("\\u003D", "=")
        .replace("\\u0026", "&")
    )


def extract_search_note_items(page: note_exporter.CdpClient) -> List[Dict[str, str]]:
    expression = r"""
(() => {
  const items = [];
  const seen = new Set();
  const pushItem = (href, anchor) => {
    try {
      href = new URL(href, location.href).href;
    } catch (_) {
      return;
    }
    const match = href.match(/\/(?:search_result|explore|discovery\/item)\/([0-9a-zA-Z]{24})/);
    if (!match || seen.has(match[1])) return;
    seen.add(match[1]);
    const card = anchor?.closest?.('section.note-item,[class*="note-item"],[class*="noteItem"],[class*="feed"],[class*="card"]');
    const title = card?.querySelector?.('.title,[class*="title"]')?.innerText?.trim() || anchor?.innerText?.trim() || '';
    const author = card?.querySelector?.('.author,[class*="author"],[class*="name"],[class*="user"]')?.innerText?.trim() || '';
    const text = card?.innerText?.trim() || anchor?.innerText?.trim() || '';
    items.push({ href, note_id: match[1], title, author, text });
  };

  for (const anchor of Array.from(document.querySelectorAll('a[href]'))) {
    const raw = anchor.getAttribute('href') || '';
    if (!raw.includes('xsec_token=')) continue;
    if (!/\/(?:search_result|explore|discovery\/item)\//.test(raw)) continue;
    pushItem(raw, anchor);
  }

  const html = document.documentElement.outerHTML
    .replaceAll('&amp;', '&')
    .replaceAll('\\u002F', '/')
    .replaceAll('\\/', '/')
    .replaceAll('\\u003F', '?')
    .replaceAll('\\u003D', '=')
    .replaceAll('\\u0026', '&');
  const patterns = [
    /https?:\/\/www\.xiaohongshu\.com\/(?:search_result|explore|discovery\/item)\/[0-9a-zA-Z]{24}\?[^"'<>\\\s]+xsec_token=[^"'<>\\\s]+/g,
    /\/(?:search_result|explore|discovery\/item)\/[0-9a-zA-Z]{24}\?[^"'<>\\\s]+xsec_token=[^"'<>\\\s]+/g
  ];
  for (const pattern of patterns) {
    for (const match of html.matchAll(pattern)) {
      pushItem(match[0], null);
    }
  }
  return items;
})()
"""
    return page.evaluate(expression) or []


def prepare_search_page(page: note_exporter.CdpClient) -> None:
    page.call("Page.enable")
    page.call("Network.enable")
    page.call("Runtime.enable")
    try:
        user_agent = page.evaluate("navigator.userAgent") or ""
        if "HeadlessChrome" in user_agent:
            page.call("Network.setUserAgentOverride", {
                "userAgent": user_agent.replace("HeadlessChrome", "Chrome"),
                "acceptLanguage": "zh-CN,zh;q=0.9,en;q=0.8",
                "platform": "MacIntel",
            })
    except Exception:
        pass
    try:
        page.call("Emulation.setDeviceMetricsOverride", {
            "width": 1440,
            "height": 1100,
            "deviceScaleFactor": 1,
            "mobile": False,
        })
    except Exception:
        pass


def wait_after_navigation(page: note_exporter.CdpClient, timeout: float, minimum_delay: float) -> None:
    deadline = time.time() + max(1.0, timeout)
    while time.time() < deadline:
        try:
            state = page.evaluate("""
(() => ({
  readyState: document.readyState,
  bodyLength: document.body?.innerText?.length || 0,
  linkCount: document.querySelectorAll('a[href]').length,
  tokenLinkCount: Array.from(document.querySelectorAll('a[href]')).filter(a => a.href.includes('xsec_token=')).length
}))()
""")
            if state and state.get("readyState") in ("interactive", "complete") and (
                state.get("tokenLinkCount", 0) > 0 or state.get("bodyLength", 0) > 200
            ):
                break
        except Exception:
            pass
        time.sleep(0.35)
    time.sleep(max(0.0, minimum_delay))


def page_diagnostics(page: note_exporter.CdpClient) -> Dict[str, Any]:
    try:
        return page.evaluate(r"""
(() => {
  const bodyText = document.body?.innerText || '';
  const links = Array.from(document.querySelectorAll('a[href]')).slice(0, 80).map(a => a.href);
  return {
    href: location.href,
    title: document.title,
    readyState: document.readyState,
    bodyLength: bodyText.length,
    bodySample: bodyText.slice(0, 1200),
    linkCount: document.querySelectorAll('a[href]').length,
    tokenLinkCount: links.filter(href => href.includes('xsec_token=')).length,
    noteItemCount: document.querySelectorAll('section.note-item,[class*="note-item"],[class*="noteItem"]').length,
    hasLoginText: /登录|扫码|验证码|安全验证|验证/.test(bodyText),
    links
  };
})()
""") or {}
    except Exception as exc:
        return {"diagnostic_error": str(exc)}


def save_search_debug(page: note_exporter.CdpClient, keyword: str, label: str, diagnostics: Dict[str, Any]) -> Dict[str, str]:
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    slug = re.sub(r"[^\w.\-\u4e00-\u9fff]+", "_", keyword, flags=re.UNICODE).strip("_")[:48] or "search"
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


def apply_search_filters(page: note_exporter.CdpClient, filters: Dict[str, str]) -> Dict[str, Any]:
    payload = json.dumps(filters, ensure_ascii=False)
    expression = f"""
(async () => {{
  const filters = {payload};
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const norm = (text) => String(text || '').replace(/\\s+/g, '').trim();
  const visible = (el) => {{
    if (!el) return false;
    const style = getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return style.visibility !== 'hidden' && style.display !== 'none' && rect.width > 0 && rect.height > 0;
  }};
  const clickable = (el) => {{
    if (!el) return null;
    return el.closest('button,[role="button"],a,li,[class*="item"],[class*="option"],[class*="filter"],[class*="select"],div,span') || el;
  }};
  const all = () => Array.from(document.querySelectorAll('button,[role="button"],a,li,span,div'));
  const clickByText = async (label) => {{
    if (!label) return false;
    const wanted = norm(label);
    if (!wanted) return false;
    const exact = all().filter((el) => visible(el) && norm(el.innerText || el.textContent) === wanted);
    const loose = all().filter((el) => {{
      const text = norm(el.innerText || el.textContent);
      return visible(el) && text && text.length <= wanted.length + 8 && text.includes(wanted);
    }});
    for (const el of [...exact, ...loose]) {{
      const target = clickable(el);
      if (!visible(target)) continue;
      target.scrollIntoView({{ block: 'center', inline: 'center' }});
      target.click();
      await sleep(420);
      return true;
    }}
    return false;
  }};

  const selected = [];
  const needsPanel = Object.values(filters).some((value) => value && value !== '不限' && value !== '综合');
  if (needsPanel) {{
    await clickByText('筛选') || await clickByText('综合') || await clickByText('排序');
    await sleep(520);
  }}

  for (const label of [filters.sort_by, filters.note_type, filters.publish_time, filters.search_scope, filters.location]) {{
    if (!label || label === '不限') continue;
    if (await clickByText(label)) selected.push(label);
  }}
  await clickByText('确定') || await clickByText('完成') || await clickByText('确认');
  await sleep(900);
  return {{ selected, href: location.href }};
}})()
"""
    try:
        return page.evaluate(expression, await_promise=True) or {}
    except Exception as exc:
        return {"error": str(exc), "selected": [], "href": ""}


def collect_search_notes(
    page: note_exporter.CdpClient,
    search_url: str,
    scroll_rounds: int,
    scroll_delay: float,
    stable_rounds: int,
    max_notes: int,
    filters: Dict[str, str],
    load_timeout: float,
) -> List[Dict[str, str]]:
    prepare_search_page(page)
    page.call("Page.navigate", {"url": search_url})
    wait_after_navigation(page, load_timeout, max(2.0, scroll_delay))
    filter_result = apply_search_filters(page, filters)
    if filter_result.get("href"):
        search_url = filter_result["href"]
    wait_after_navigation(page, max(3.0, load_timeout / 3), max(1.2, scroll_delay / 2))

    collected: OrderedDict[str, Dict[str, str]] = OrderedDict()
    no_new_rounds = 0

    for round_index in range(max(1, scroll_rounds + 1)):
        before = len(collected)
        raw_items = extract_search_note_items(page)
        for raw in raw_items:
            parsed = parse_search_note_url(raw.get("href", ""))
            if not parsed:
                continue
            parsed["preview_title"] = raw.get("title", "")
            parsed["preview_author"] = raw.get("author", "")
            parsed["preview_text"] = raw.get("text", "")
            parsed["page_filter_url"] = search_url
            parsed["page_filter_selected"] = ",".join(filter_result.get("selected") or [])
            parsed["page_filter_error"] = filter_result.get("error", "")
            if parsed["id"] not in collected:
                collected[parsed["id"]] = parsed
            if max_notes > 0 and len(collected) >= max_notes:
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

        page.evaluate("""
(() => {
  window.scrollBy(0, Math.max(520, Math.floor(window.innerHeight * 0.72)));
  document.dispatchEvent(new Event('scroll', { bubbles: true }));
  window.dispatchEvent(new Event('scroll'));
})()
""")
        time.sleep(max(1.5, scroll_delay))

    return list(collected.values())


def build_multi_origin_rows(
    page: note_exporter.CdpClient,
    state: Dict[str, Any],
    keyword: str,
    search_url: str,
    notes: List[Dict[str, str]],
    filters: Dict[str, str],
    request_interval: float,
    http_timeout: float,
) -> List[OrderedDict]:
    rows: List[OrderedDict] = []

    for index, item in enumerate(notes, start=1):
        if index > 1:
            time.sleep(max(0.0, request_interval))

        flat = OrderedDict()
        flat["search_keyword"] = keyword
        flat["search_url"] = search_url
        flat["search_rank"] = index
        flat["filter_sort_by"] = filters["sort_by"]
        flat["filter_note_type"] = filters["note_type"]
        flat["filter_publish_time"] = filters["publish_time"]
        flat["filter_search_scope"] = filters["search_scope"]
        flat["filter_location"] = filters["location"]
        flat["page_filter_url"] = item.get("page_filter_url", "")
        flat["page_filter_selected"] = item.get("page_filter_selected", "")
        flat["page_filter_error"] = item.get("page_filter_error", "")
        flat["source_url"] = item["href"]
        flat["note_id"] = item["id"]
        flat["xsec_source"] = item.get("source", "")
        flat["preview_title"] = item.get("preview_title", "")
        flat["preview_author"] = item.get("preview_author", "")

        try:
            body = note_exporter.build_body(item["id"], item.get("source", ""), item["token"])
            data = note_exporter.post_feed(page, state, body, timeout=http_timeout)
            detail = note_exporter.build_flat_row(data, item["href"], item["id"], item.get("source", ""))
            for key, value in detail.items():
                flat[key] = value
        except Exception as exc:
            flat["fetch_error"] = str(exc)
            flat["raw_json"] = ""

        rows.append(flat)

    return rows


def normalize_choice(value: str, allowed: List[str], default: str) -> str:
    clean = str(value or "").strip()
    return clean if clean in allowed else default


def note_time_value(row: Dict[str, Any]) -> float:
    value = note_exporter.pick(row, "items.0.note_card.time")
    try:
        timestamp = float(value)
        if timestamp > 10**12:
            timestamp = timestamp / 1000
        return timestamp
    except Exception:
        return 0.0


def numeric_value(row: Dict[str, Any], key: str) -> int:
    value = note_exporter.pick(row, key)
    try:
        return int(float(value))
    except Exception:
        return 0


def matches_note_type(row: Dict[str, Any], note_type: str) -> bool:
    if note_type == "不限":
        return True
    raw_type = str(note_exporter.pick(row, "items.0.note_card.type")).lower()
    is_video = raw_type == "video"
    return is_video if note_type == "视频" else not is_video


def matches_publish_time(row: Dict[str, Any], publish_time: str) -> bool:
    if publish_time == "不限":
        return True
    days = PUBLISH_TIME_DAYS.get(publish_time)
    if not days:
        return True
    timestamp = note_time_value(row)
    if not timestamp:
        return False
    return datetime.fromtimestamp(timestamp) >= datetime.now() - timedelta(days=days)


def apply_row_filters_and_sort(rows: List[OrderedDict], filters: Dict[str, str], max_notes: int) -> List[OrderedDict]:
    filtered = [
        row for row in rows
        if matches_note_type(row, filters["note_type"])
        and matches_publish_time(row, filters["publish_time"])
    ]

    sort_by = filters["sort_by"]
    if sort_by == "最新":
        filtered.sort(key=note_time_value, reverse=True)
    elif sort_by == "最多点赞":
        filtered.sort(key=lambda row: numeric_value(row, "items.0.note_card.interact_info.liked_count"), reverse=True)
    elif sort_by == "最多评论":
        filtered.sort(key=lambda row: numeric_value(row, "items.0.note_card.interact_info.comment_count"), reverse=True)
    elif sort_by == "最多收藏":
        filtered.sort(key=lambda row: numeric_value(row, "items.0.note_card.interact_info.collected_count"), reverse=True)

    if max_notes > 0:
        filtered = filtered[:max_notes]
    for output_rank, row in enumerate(filtered, start=1):
        row["output_rank"] = output_rank
    return filtered


def union_fieldnames(rows: List[Dict[str, Any]]) -> List[str]:
    fields: List[str] = []
    seen = set()
    preferred = [
        "search_keyword",
        "search_url",
        "search_rank",
        "output_rank",
        "filter_sort_by",
        "filter_note_type",
        "filter_publish_time",
        "filter_search_scope",
        "filter_location",
        "page_filter_url",
        "page_filter_selected",
        "page_filter_error",
        "source_url",
        "note_id",
        "xsec_source",
        "preview_title",
        "preview_author",
        "fetch_error",
    ]
    for key in preferred:
        for row in rows:
            if key in row and key not in seen:
                fields.append(key)
                seen.add(key)
                break
    for row in rows:
        for key in row.keys():
            if key not in seen:
                fields.append(key)
                seen.add(key)
    return fields


def write_origin_csv(rows: List[OrderedDict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fields = union_fieldnames(rows)
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_ten_fields_csv(rows: List[Dict[str, Any]], output_path: Path) -> None:
    out_fields = [
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
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=out_fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                "笔记ID": note_exporter.pick(row, "note_id", "items.0.note_card.note_id", "items.0.id"),
                "博主昵称": note_exporter.pick(row, "items.0.note_card.user.nickname", "preview_author"),
                "笔记链接": note_exporter.pick(row, "source_url"),
                "笔记标题": note_exporter.pick(row, "items.0.note_card.title", "preview_title"),
                "笔记内容": note_exporter.pick(row, "items.0.note_card.desc"),
                "点赞量": note_exporter.pick(row, "items.0.note_card.interact_info.liked_count"),
                "收藏量": note_exporter.pick(row, "items.0.note_card.interact_info.collected_count"),
                "评论量": note_exporter.pick(row, "items.0.note_card.interact_info.comment_count"),
                "分享量": note_exporter.pick(row, "items.0.note_card.interact_info.share_count"),
                "发布时间": note_exporter.format_time(note_exporter.pick(row, "items.0.note_card.time")),
            })


def export_search(args: argparse.Namespace) -> Tuple[Path, Path, int]:
    keyword_or_url = args.search_url or args.keyword
    search_urls = candidate_search_urls(keyword_or_url)
    search_url = search_urls[0]
    keyword = args.keyword
    output = Path(args.output) if args.output else PIPELINE_DIR / "origin_data.csv"
    summary_output = Path(args.summary_output) if args.summary_output else PIPELINE_DIR / "xhs_note_10_fields.csv"
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

    chrome_path = note_exporter.find_chrome(args.chrome)
    if args.use_default_profile and args.user_data_dir:
        raise ValueError("--use-default-profile cannot be combined with --user-data-dir")

    owns_user_dir = args.user_data_dir is None
    if args.use_default_profile:
        source_root = Path(args.profile_source) if args.profile_source else note_exporter.default_browser_user_data_dir(chrome_path)
        user_dir = Path(tempfile.mkdtemp(prefix="xhs-search-profile-"))
        owns_user_dir = True
        note_exporter.clone_browser_profile(source_root, args.profile_directory, user_dir)
    else:
        user_dir = Path(args.user_data_dir) if args.user_data_dir else Path(tempfile.mkdtemp(prefix="xhs-search-cdp-"))

    proc = note_exporter.launch_chrome(
        chrome_path,
        user_dir,
        headless=not args.headed,
        profile_directory=args.profile_directory,
    )
    page: Optional[note_exporter.CdpClient] = None
    try:
        port, ws_path = note_exporter.wait_for_debug_port(user_dir, args.browser_timeout)
        page = note_exporter.make_page_client(port, ws_path, args.browser_timeout)
        notes: List[Dict[str, str]] = []
        diagnostics: List[Dict[str, Any]] = []
        debug_files: Dict[str, str] = {}
        for index, candidate_url in enumerate(search_urls, start=1):
            search_url = candidate_url
            notes = collect_search_notes(
                page,
                search_url,
                scroll_rounds=args.scroll_rounds,
                scroll_delay=args.scroll_delay,
                stable_rounds=args.stable_rounds,
                max_notes=collect_limit,
                filters=filters,
                load_timeout=args.search_load_timeout,
            )
            diagnostic = page_diagnostics(page)
            diagnostic["candidate_url"] = candidate_url
            diagnostic["candidate_index"] = index
            diagnostic["extracted_count"] = len(notes)
            diagnostics.append(diagnostic)
            if notes:
                break
            debug_files = save_search_debug(page, keyword, f"try{index}", diagnostic)
        if not notes:
            detail = "没有从搜索页识别到带 xsec_token 的笔记卡片。"
            if diagnostics:
                last = diagnostics[-1]
                if last.get("hasLoginText"):
                    detail += " 页面疑似出现登录/验证/安全提示，请在打开的小红书页面完成登录或验证后重试。"
                detail += (
                    f" 最后页面标题：{last.get('title', '')}；"
                    f"链接数：{last.get('linkCount', 0)}；token链接数：{last.get('tokenLinkCount', 0)}。"
                )
            if debug_files:
                detail += " 已保存诊断文件：" + "，".join(debug_files.values())
            raise RuntimeError(detail)

        state = note_exporter.wait_for_login_cookie(page, note_exporter.page_state(page), args.login_timeout)
        state["cookie_header"] = note_exporter.browser_cookie_header(page)
        if not state.get("a1") or not state.get("cookie_header"):
            raise RuntimeError("未检测到完整小红书登录 Cookie，请先登录小红书后重试。")

        rows = build_multi_origin_rows(
            page,
            state,
            keyword,
            search_url,
            notes,
            filters,
            request_interval=args.request_interval,
            http_timeout=args.http_timeout,
        )
        rows = apply_row_filters_and_sort(rows, filters, args.max_notes)
        if not rows:
            raise RuntimeError("搜索结果已加载，但筛选条件下没有可导出的笔记。")
        write_origin_csv(rows, output)
        write_ten_fields_csv(rows, summary_output)
        return output, summary_output, len(rows)
    finally:
        if page is not None:
            page.close()
        if not args.keep_browser_open:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except Exception:
                proc.kill()
        if owns_user_dir and not args.keep_browser_open:
            shutil.rmtree(user_dir, ignore_errors=True)


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Export Xiaohongshu search-result notes to CSV.")
    parser.add_argument("keyword", nargs="?", default=DEFAULT_KEYWORD, help="Search keyword. Defaults to 滴滴出行.")
    parser.add_argument("--search-url", help="Full Xiaohongshu search-result URL. Overrides keyword URL building.")
    parser.add_argument("-o", "--output", help="Full-field CSV path. Defaults to Pipeline/origin_data.csv.")
    parser.add_argument("--summary-output", help="10-field CSV path. Defaults to Pipeline/xhs_note_10_fields.csv.")
    parser.add_argument("--max-notes", type=int, default=0, help="Maximum notes to fetch. 0 means no note cap.")
    parser.add_argument("--sort-by", choices=SORT_OPTIONS, default="综合", help="搜索排序：综合/最新/最多点赞/最多评论/最多收藏。")
    parser.add_argument("--note-type", choices=NOTE_TYPE_OPTIONS, default="不限", help="笔记类型：不限/视频/图文。")
    parser.add_argument("--publish-time", choices=PUBLISH_TIME_OPTIONS, default="不限", help="发布时间：不限/一天内/一周内/半年内。")
    parser.add_argument("--search-scope", choices=SEARCH_SCOPE_OPTIONS, default="不限", help="搜索范围：不限/已看过/未看过/已关注。")
    parser.add_argument("--location", choices=LOCATION_OPTIONS, default="不限", help="位置距离：不限/同城/附近。")
    parser.add_argument("--scroll-rounds", type=int, default=10, help="Maximum conservative scroll rounds.")
    parser.add_argument("--stable-rounds", type=int, default=3, help="Stop after this many scrolls add no new notes.")
    parser.add_argument("--scroll-delay", type=float, default=2.5, help="Seconds to wait between scrolls.")
    parser.add_argument("--search-load-timeout", type=float, default=18.0, help="Seconds to wait for the search page to render cards.")
    parser.add_argument("--request-interval", type=float, default=2.0, help="Seconds to wait between detail requests.")
    parser.add_argument("--chrome", help="Chrome/Chromium executable path.")
    parser.add_argument("--user-data-dir", help="Chrome user-data directory.")
    parser.add_argument("--use-default-profile", action="store_true", default=True, help="Clone default Chrome profile.")
    parser.add_argument("--fresh-profile", dest="use_default_profile", action="store_false", help="Do not clone default profile.")
    parser.add_argument("--profile-source", help="Source browser user-data directory to clone.")
    parser.add_argument("--profile-directory", default="Default", help="Chrome profile directory name.")
    parser.add_argument("--headed", action="store_true", help="Show Chrome instead of running headless.")
    parser.add_argument("--keep-browser-open", action="store_true", help="Do not close Chrome when finished.")
    parser.add_argument("--login-timeout", type=float, default=0.0, help="Seconds to wait for manual login.")
    parser.add_argument("--browser-timeout", type=float, default=45.0, help="Seconds to wait for Chrome/CDP.")
    parser.add_argument("--http-timeout", type=float, default=30.0, help="Seconds to wait for detail requests.")
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
