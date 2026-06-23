#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import urllib.parse
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import xhs_note_to_csv as browser
from media_enrichment import append_media_text


API_BASE = "https://www.douyin.com"
DEFAULT_URL = "https://www.douyin.com/"

COMMON_PARAMS = OrderedDict(
    [
        ("aid", 6383),
        ("device_platform", "webapp"),
        ("channel", "channel_pc_web"),
        ("version_code", 170400),
        ("version_name", "17.4.0"),
        ("platform", "PC"),
        ("pc_client_type", 1),
        ("cookie_enabled", "true"),
        ("screen_width", 1440),
        ("screen_height", 1000),
        ("browser_language", "zh-CN"),
        ("browser_platform", "MacIntel"),
        ("browser_name", "Chrome"),
        ("browser_version", "124.0.0.0"),
        ("browser_online", "true"),
        ("engine_name", "Blink"),
        ("engine_version", "124.0.0.0"),
        ("os_name", "Mac OS"),
    ]
)


class DouyinApiError(RuntimeError):
    pass


def parse_aweme_id_from_url(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    decoded = urllib.parse.unquote(text)
    parsed = urllib.parse.urlparse(decoded)
    modal_id = urllib.parse.parse_qs(parsed.query).get("modal_id", [""])[0]
    if re.fullmatch(r"\d{10,30}", modal_id or ""):
        return modal_id
    patterns = [
        r"/video/(\d{10,30})",
        r"/note/(\d{10,30})",
        r"/share/video/(\d{10,30})",
        r"/discover/(\d{10,30})",
        r"/(\d{10,30})(?:[/?#]|$)",
    ]
    for pattern in patterns:
        match = re.search(pattern, decoded)
        if match:
            return match.group(1)
    return ""


def canonical_aweme_url(aweme_id: str) -> str:
    return f"https://www.douyin.com/video/{aweme_id}" if aweme_id else ""


def build_query(params: Dict[str, Any]) -> str:
    merged = OrderedDict(COMMON_PARAMS)
    for key, value in params.items():
        if value not in (None, ""):
            merged[key] = value
    return urllib.parse.urlencode(merged, doseq=False)


def find_chrome(explicit: Optional[str]) -> str:
    return browser.find_chrome(explicit)


def default_browser_user_data_dir(chrome_path: str) -> Path:
    return browser.default_browser_user_data_dir(chrome_path)


def launch_browser_page(args: Any, prefix: str) -> Tuple[subprocess.Popen, browser.CdpClient, Path, bool]:
    chrome_path = find_chrome(getattr(args, "chrome", None))
    if getattr(args, "use_default_profile", False) and getattr(args, "user_data_dir", None):
        raise ValueError("--use-default-profile cannot be combined with --user-data-dir")

    owns_user_dir = getattr(args, "user_data_dir", None) is None
    profile_directory = getattr(args, "profile_directory", "Default")
    if getattr(args, "use_default_profile", False):
        source_root = Path(getattr(args, "profile_source", "") or default_browser_user_data_dir(chrome_path))
        user_dir = Path(tempfile.mkdtemp(prefix=f"{prefix}-profile-"))
        owns_user_dir = True
        browser.clone_browser_profile(source_root, profile_directory, user_dir)
    else:
        user_dir = Path(getattr(args, "user_data_dir", "") or tempfile.mkdtemp(prefix=f"{prefix}-cdp-"))

    proc = browser.launch_chrome(
        chrome_path,
        user_dir,
        headless=not getattr(args, "headed", False),
        profile_directory=profile_directory,
    )
    port, ws_path = browser.wait_for_debug_port(user_dir, getattr(args, "browser_timeout", 45.0))
    page = browser.make_page_client(port, ws_path, getattr(args, "browser_timeout", 45.0))
    prepare_page(page)
    return proc, page, user_dir, owns_user_dir


def close_browser_page(
    proc: subprocess.Popen,
    page: Optional[browser.CdpClient],
    user_dir: Path,
    owns_user_dir: bool,
    keep_browser_open: bool,
) -> None:
    if page is not None:
        page.close()
    if not keep_browser_open:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
    if owns_user_dir and not keep_browser_open:
        shutil.rmtree(user_dir, ignore_errors=True)


def prepare_page(page: browser.CdpClient) -> None:
    page.call("Page.enable")
    page.call("Network.enable")
    page.call("Runtime.enable")
    try:
        user_agent = page.evaluate("navigator.userAgent") or ""
        if "HeadlessChrome" in user_agent:
            page.call(
                "Network.setUserAgentOverride",
                {
                    "userAgent": user_agent.replace("HeadlessChrome", "Chrome"),
                    "acceptLanguage": "zh-CN,zh;q=0.9,en;q=0.8",
                    "platform": "MacIntel",
                },
            )
    except Exception:
        pass
    try:
        page.call(
            "Emulation.setDeviceMetricsOverride",
            {"width": 1440, "height": 1000, "deviceScaleFactor": 1, "mobile": False},
        )
    except Exception:
        pass


def navigate_and_wait(page: browser.CdpClient, url: str, timeout: float = 25.0, minimum_delay: float = 2.0) -> None:
    page.call("Page.navigate", {"url": url})
    deadline = time.time() + max(1.0, timeout)
    while time.time() < deadline:
        try:
            state = page.evaluate(
                """
(() => ({
  readyState: document.readyState,
  href: location.href,
  bodyLength: document.body?.innerText?.length || 0
}))()
"""
            )
            if state and state.get("readyState") in ("interactive", "complete") and state.get("bodyLength", 0) > 80:
                break
        except Exception:
            pass
        time.sleep(0.35)
    time.sleep(max(0.0, minimum_delay))


def page_diagnostics(page: browser.CdpClient) -> Dict[str, Any]:
    try:
        return page.evaluate(
            r"""
(() => {
  const body = document.body?.innerText || '';
  return {
    href: location.href,
    title: document.title,
    readyState: document.readyState,
    bodyLength: body.length,
    bodySample: body.slice(0, 1000),
    linkCount: document.querySelectorAll('a[href]').length,
    hasLoginText: /登录|验证码|安全验证|扫码|验证/.test(body)
  };
})()
"""
        ) or {}
    except Exception as exc:
        return {"diagnostic_error": str(exc)}


def extract_aweme_id_from_page(page: browser.CdpClient) -> str:
    try:
        payload = page.evaluate(
            r"""
(() => {
  const href = location.href;
  const html = document.documentElement.outerHTML || '';
  const body = document.body?.innerText || '';
  const values = [href, html, body];
  const patterns = [
    /[?&]modal_id=(\d{10,30})/,
    /\/video\/(\d{10,30})/,
    /\/note\/(\d{10,30})/,
    /"aweme_id"\s*:\s*"?(\d{10,30})"?/g,
    /"awemeId"\s*:\s*"?(\d{10,30})"?/g,
    /"group_id"\s*:\s*"?(\d{10,30})"?/g
  ];
  for (const value of values) {
    for (const pattern of patterns) {
      pattern.lastIndex = 0;
      const match = pattern.exec(value);
      if (match) return match[1];
    }
  }
  return '';
})()
"""
        )
        return str(payload or "")
    except Exception:
        return ""


def ensure_aweme_id(page: browser.CdpClient, url: str, timeout: float) -> str:
    aweme_id = parse_aweme_id_from_url(url)
    if aweme_id:
        return aweme_id
    navigate_and_wait(page, url, timeout=timeout, minimum_delay=2.4)
    aweme_id = extract_aweme_id_from_page(page)
    if aweme_id:
        return aweme_id
    diagnostics = page_diagnostics(page)
    detail = f"没有从抖音链接中识别到视频ID。页面标题：{diagnostics.get('title', '')}；当前地址：{diagnostics.get('href', '')}"
    if diagnostics.get("hasLoginText"):
        detail += "。页面疑似要求登录或安全验证，请在打开的抖音页面完成后重试。"
    raise ValueError(detail)


def browser_fetch_json(
    page: browser.CdpClient,
    path: str,
    params: Dict[str, Any],
    timeout: float,
) -> Dict[str, Any]:
    payload = {
        "path": path,
        "params": params,
        "common": dict(COMMON_PARAMS),
        "timeoutMs": int(max(5.0, timeout) * 1000),
    }
    expression = f"""
(async () => {{
  const payload = {json.dumps(payload, ensure_ascii=False)};
  const url = new URL(payload.path, 'https://www.douyin.com');
  for (const [key, value] of Object.entries(payload.common)) {{
    if (value !== undefined && value !== null && value !== '') url.searchParams.set(key, String(value));
  }}
  for (const [key, value] of Object.entries(payload.params || {{}})) {{
    if (value !== undefined && value !== null && value !== '') url.searchParams.set(key, String(value));
  }}
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort('timeout'), payload.timeoutMs);
  try {{
    const response = await fetch(url.toString(), {{
      method: 'GET',
      credentials: 'include',
      headers: {{
        'accept': 'application/json, text/plain, */*',
        'x-requested-with': 'XMLHttpRequest'
      }},
      signal: controller.signal
    }});
    const text = await response.text();
    let data = null;
    try {{
      data = JSON.parse(text);
    }} catch (error) {{
      return {{ ok: false, status: response.status, url: url.toString(), text: text.slice(0, 1000), parseError: String(error) }};
    }}
    return {{ ok: response.ok, status: response.status, url: url.toString(), data }};
  }} catch (error) {{
    return {{ ok: false, status: 0, url: url.toString(), error: String(error) }};
  }} finally {{
    clearTimeout(timer);
  }}
}})()
"""
    result = page.evaluate(expression, await_promise=True) or {}
    if not result.get("ok"):
        message = result.get("error") or result.get("text") or result.get("parseError") or "Douyin fetch failed"
        raise DouyinApiError(f"抖音接口请求失败 HTTP {result.get('status')}: {message}")
    data = result.get("data")
    if isinstance(data, dict) and data.get("status_code") not in (None, 0):
        status_msg = data.get("status_msg") or data.get("message") or json.dumps(data, ensure_ascii=False)[:500]
        raise DouyinApiError(f"抖音接口返回异常 status_code={data.get('status_code')}: {status_msg}")
    return data if isinstance(data, dict) else {"data": data}


def fetch_aweme_detail(page: browser.CdpClient, aweme_id: str, timeout: float) -> Dict[str, Any]:
    return browser_fetch_json(page, "/aweme/v1/web/aweme/detail/", {"aweme_id": aweme_id}, timeout)


def fetch_comment_list(page: browser.CdpClient, aweme_id: str, cursor: int, count: int, timeout: float) -> Dict[str, Any]:
    return browser_fetch_json(
        page,
        "/aweme/v1/web/comment/list/",
        {"aweme_id": aweme_id, "cursor": cursor, "count": count, "item_type": 0},
        timeout,
    )


def fetch_comment_reply_list(
    page: browser.CdpClient,
    aweme_id: str,
    comment_id: str,
    cursor: int,
    count: int,
    timeout: float,
) -> Dict[str, Any]:
    return browser_fetch_json(
        page,
        "/aweme/v1/web/comment/list/reply/",
        {"item_id": aweme_id, "comment_id": comment_id, "cursor": cursor, "count": count, "item_type": 0},
        timeout,
    )


def flatten_json(value: Any, prefix: str = "") -> Dict[str, Any]:
    result: Dict[str, Any] = {}

    def visit(current: Any, key: str) -> None:
        if isinstance(current, dict):
            if not current and key:
                result[key] = "{}"
            for child_key, child_value in current.items():
                visit(child_value, f"{key}.{child_key}" if key else str(child_key))
        elif isinstance(current, list):
            if not current and key:
                result[key] = "[]"
            for index, child_value in enumerate(current):
                visit(child_value, f"{key}.{index}" if key else str(index))
        else:
            result[key] = current

    visit(value, prefix)
    return result


def pick(row: Dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = row.get(key, "")
        if value not in (None, ""):
            return value
    return ""


def format_time(value: Any) -> str:
    if value in (None, ""):
        return ""
    try:
        timestamp = int(float(value))
        if timestamp > 10**12:
            timestamp = timestamp / 1000
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(value)


def build_flat_row(data: Dict[str, Any], source_url: str, aweme_id: str) -> OrderedDict:
    flat = OrderedDict()
    detail = data.get("aweme_detail") if isinstance(data, dict) else {}
    detail_id = (detail or {}).get("aweme_id") or aweme_id
    flat["platform"] = "douyin"
    flat["source_url"] = source_url or canonical_aweme_url(detail_id)
    flat["note_id"] = detail_id
    flat["aweme_id"] = detail_id
    for key, value in flatten_json(data).items():
        flat[key] = value
    flat["raw_json"] = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return flat


def title_from_desc(desc: Any) -> str:
    text = re.sub(r"\s+", " ", str(desc or "")).strip()
    if not text:
        return ""
    first = re.split(r"[。！？!?\\n]", text, maxsplit=1)[0].strip()
    return (first or text)[:80]


def summary_row(flat: Dict[str, Any]) -> OrderedDict:
    desc = pick(flat, "aweme_detail.desc", "aweme_detail.caption")
    ocr = pick(flat, "aweme_detail.seo_info.ocr_content")
    body = str(desc or "")
    if ocr and str(ocr).strip() not in body:
        body = (body + "\nOCR：" + str(ocr)).strip()
    body = append_media_text(
        body,
        str(pick(flat, "media_enrichment.image_ocr_text")),
        str(pick(flat, "media_enrichment.video_transcript")),
    )
    aweme_id = pick(flat, "aweme_id", "note_id", "aweme_detail.aweme_id")
    out = OrderedDict()
    out["笔记ID"] = aweme_id
    out["博主昵称"] = pick(flat, "aweme_detail.author.nickname")
    out["笔记链接"] = pick(flat, "source_url", "aweme_detail.share_url") or canonical_aweme_url(str(aweme_id))
    out["笔记标题"] = title_from_desc(desc)
    out["笔记内容"] = body
    out["点赞量"] = pick(flat, "aweme_detail.statistics.digg_count")
    out["收藏量"] = pick(flat, "aweme_detail.statistics.collect_count")
    out["评论量"] = pick(flat, "aweme_detail.statistics.comment_count")
    out["分享量"] = pick(flat, "aweme_detail.statistics.share_count")
    out["发布时间"] = format_time(pick(flat, "aweme_detail.create_time"))
    return out


def write_rows_csv(rows: List[Dict[str, Any]], output_path: Path, preferred: Optional[List[str]] = None) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fields: List[str] = []
    seen = set()
    for key in preferred or []:
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
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_summary_csv(rows: List[Dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["笔记ID", "博主昵称", "笔记链接", "笔记标题", "笔记内容", "点赞量", "收藏量", "评论量", "分享量", "发布时间"]
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(summary_row(row))


def add_browser_args(parser: Any) -> None:
    parser.add_argument("--chrome", help="Chrome/Chromium executable path.")
    parser.add_argument("--user-data-dir", help="Chrome user-data directory.")
    parser.add_argument("--use-default-profile", action="store_true", default=True, help="Clone default Chrome profile.")
    parser.add_argument("--fresh-profile", dest="use_default_profile", action="store_false", help="Do not clone default profile.")
    parser.add_argument("--profile-source", help="Source browser user-data directory to clone.")
    parser.add_argument("--profile-directory", default="Default", help="Chrome profile directory name.")
    parser.add_argument("--headed", action="store_true", help="Show Chrome instead of running headless.")
    parser.add_argument("--keep-browser-open", action="store_true", help="Do not close Chrome when finished.")
    parser.add_argument("--browser-timeout", type=float, default=45.0, help="Seconds to wait for Chrome/CDP.")
    parser.add_argument("--http-timeout", type=float, default=30.0, help="Seconds to wait for API requests.")


def cleanup(proc: subprocess.Popen, page: Optional[browser.CdpClient], user_dir: Path, owns_user_dir: bool, args: Any) -> None:
    close_browser_page(proc, page, user_dir, owns_user_dir, bool(getattr(args, "keep_browser_open", False)))
