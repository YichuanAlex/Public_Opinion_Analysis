#!/usr/bin/env python3
"""
Export all Xiaohongshu comments for one note to CSV.

This mirrors Social_Media_Copilot's XHS comment flow:
  Social_Media_Copilot/src/entrypoints/xhs.content/api/comment.ts
  Social_Media_Copilot/src/entrypoints/xhs.content/tasks/post-comment/processor.ts

It reuses xhs_note_to_csv.py for Chrome/CDP profile handling, login cookies,
and the page-provided window.mnsv2 signer.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import xhs_note_to_csv as note_exporter


COMMENT_PAGE_PATH = "/api/sns/web/v2/comment/page"
COMMENT_SUB_PAGE_PATH = "/api/sns/web/v2/comment/sub/page"
DEFAULT_IMAGE_FORMATS = "jpg,webp,avif"
OUTPUT_FIELDS = [
    "评论ID",
    "笔记ID",
    "笔记链接",
    "评论层级",
    "用户ID",
    "用户链接",
    "用户名称",
    "评论内容",
    "评论时间",
    "点赞数",
    "子评论数",
    "IP地址",
    "一级评论ID",
    "回复目标评论ID",
    "回复目标用户ID",
    "回复目标用户名称",
]


def build_query(params: OrderedDict) -> str:
    return urllib.parse.urlencode(params, doseq=False, safe=",")


def build_get_path(path: str, params: OrderedDict) -> str:
    return path + "?" + build_query(params)


def build_xs_for_path(
    page: note_exporter.CdpClient,
    state: Dict[str, Any],
    path: str,
    body_json: str = "",
) -> str:
    mnsv2 = note_exporter.page_mnsv2(page, path, body_json)
    data = OrderedDict()
    data["x0"] = "4.2.6"
    data["x1"] = "xhs-pc-web"
    data["x2"] = state.get("xsecplatform") or "PC"
    data["x3"] = mnsv2
    data["x4"] = "object" if body_json else ""
    return "XYS_" + note_exporter.custom_b64_json(data)


def get_api(page: note_exporter.CdpClient, state: Dict[str, Any], path: str, timeout: float) -> Dict[str, Any]:
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.xiaohongshu.com",
        "Referer": state.get("href") or "https://www.xiaohongshu.com/",
        "User-Agent": state.get("userAgent") or "",
        "Cookie": state.get("cookie_header") or state.get("cookie") or "",
        "x-s": build_xs_for_path(page, state, path),
        "x-t": str(int(time.time() * 1000)),
        "x-s-common": note_exporter.build_xs_common(state),
        "x-xray-traceid": note_exporter.trace_id(),
        "x-b3-traceid": note_exporter.b3_trace_id(),
    }
    request = urllib.request.Request(note_exporter.API_BASE + path, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from Xiaohongshu API: {detail}") from exc

    payload = json.loads(raw)
    if isinstance(payload, dict) and payload.get("success") is False:
        message = payload.get("msg") or "Xiaohongshu API returned success=false"
        if "登录" in message:
            message += "。请确认浏览器已登录小红书后重试。"
        raise RuntimeError(message)
    if isinstance(payload, dict) and "data" in payload:
        return payload["data"]
    return payload


def get_comment_page(
    page: note_exporter.CdpClient,
    state: Dict[str, Any],
    note_id: str,
    xsec_token: str,
    cursor: str,
    timeout: float,
) -> Dict[str, Any]:
    params = OrderedDict()
    params["note_id"] = note_id
    params["xsec_token"] = xsec_token
    params["cursor"] = cursor
    params["top_comment_id"] = ""
    params["image_formats"] = DEFAULT_IMAGE_FORMATS
    return get_api(page, state, build_get_path(COMMENT_PAGE_PATH, params), timeout)


def get_comment_sub_page(
    page: note_exporter.CdpClient,
    state: Dict[str, Any],
    note_id: str,
    xsec_token: str,
    root_comment_id: str,
    cursor: str,
    timeout: float,
) -> Dict[str, Any]:
    params = OrderedDict()
    params["note_id"] = note_id
    params["xsec_token"] = xsec_token
    params["root_comment_id"] = root_comment_id
    params["num"] = 10
    params["cursor"] = cursor
    params["image_formats"] = DEFAULT_IMAGE_FORMATS
    params["top_comment_id"] = ""
    return get_api(page, state, build_get_path(COMMENT_SUB_PAGE_PATH, params), timeout)


def format_comment_time(value: Any) -> str:
    return note_exporter.format_time(value)


def user_link(user_id: str) -> str:
    return f"https://www.xiaohongshu.com/user/profile/{user_id}" if user_id else ""


def comment_to_row(
    comment: Dict[str, Any],
    note_id: str,
    note_url: str,
    level: str,
    root_comment_id: str = "",
) -> OrderedDict:
    user = comment.get("user_info") or {}
    target = comment.get("target_comment") or {}
    target_user = target.get("user_info") or {}

    row = OrderedDict()
    row["评论ID"] = comment.get("id", "")
    row["笔记ID"] = note_id
    row["笔记链接"] = note_url
    row["评论层级"] = level
    row["用户ID"] = user.get("user_id", "")
    row["用户链接"] = user_link(user.get("user_id", ""))
    row["用户名称"] = user.get("nickname", "")
    row["评论内容"] = comment.get("content", "")
    row["评论时间"] = format_comment_time(comment.get("create_time", ""))
    row["点赞数"] = comment.get("like_count", "")
    row["子评论数"] = comment.get("sub_comment_count", "") if level == "一级评论" else ""
    row["IP地址"] = comment.get("ip_location", "")
    row["一级评论ID"] = root_comment_id
    row["回复目标评论ID"] = target.get("id", "")
    row["回复目标用户ID"] = target_user.get("user_id", "")
    row["回复目标用户名称"] = target_user.get("nickname", "")

    for key, value in note_exporter.flatten_json(comment).items():
        row[f"comment.{key}"] = value
    row["raw_json"] = json.dumps(comment, ensure_ascii=False, separators=(",", ":"))
    return row


def append_comment_row(
    rows: List[OrderedDict],
    seen_ids: set,
    comment: Dict[str, Any],
    note_id: str,
    note_url: str,
    level: str,
    root_comment_id: str = "",
) -> bool:
    comment_id = str(comment.get("id") or "")
    if not comment_id or comment_id in seen_ids:
        return False
    seen_ids.add(comment_id)
    rows.append(comment_to_row(comment, note_id, note_url, level, root_comment_id))
    return True


def collect_comments(
    page: note_exporter.CdpClient,
    state: Dict[str, Any],
    note_id: str,
    xsec_token: str,
    note_url: str,
    limit: int,
    request_interval: float,
    http_timeout: float,
    include_sub_comments: bool,
) -> List[OrderedDict]:
    rows: List[OrderedDict] = []
    top_comments: List[Dict[str, Any]] = []
    seen_ids: set = set()
    cursor = ""

    while True:
        payload = get_comment_page(page, state, note_id, xsec_token, cursor, http_timeout)
        comments = payload.get("comments") or []
        if not comments:
            break

        for comment in comments:
            top_comments.append(comment)
            append_comment_row(rows, seen_ids, comment, note_id, note_url, "一级评论")
            if include_sub_comments:
                for sub_comment in comment.get("sub_comments") or []:
                    append_comment_row(rows, seen_ids, sub_comment, note_id, note_url, "子评论", comment.get("id", ""))
            if limit > 0 and len(rows) >= limit:
                return rows[:limit]

        if not payload.get("has_more"):
            break
        cursor = payload.get("cursor") or ""
        if not cursor:
            break
        time.sleep(max(0.0, request_interval))

    if not include_sub_comments:
        return rows[:limit] if limit > 0 else rows

    for comment in top_comments:
        if limit > 0 and len(rows) >= limit:
            return rows[:limit]
        if not comment.get("sub_comment_has_more"):
            continue
        root_comment_id = comment.get("id") or ""
        cursor = comment.get("sub_comment_cursor") or ""
        while root_comment_id:
            time.sleep(max(0.0, request_interval))
            payload = get_comment_sub_page(
                page,
                state,
                note_id,
                xsec_token,
                root_comment_id,
                cursor,
                http_timeout,
            )
            comments = payload.get("comments") or []
            if not comments:
                break
            for sub_comment in comments:
                append_comment_row(rows, seen_ids, sub_comment, note_id, note_url, "子评论", root_comment_id)
                if limit > 0 and len(rows) >= limit:
                    return rows[:limit]
            if not payload.get("has_more"):
                break
            cursor = payload.get("cursor") or ""
            if not cursor:
                break

    return rows[:limit] if limit > 0 else rows


def union_fieldnames(rows: List[Dict[str, Any]]) -> List[str]:
    fields: List[str] = []
    seen = set()
    for key in OUTPUT_FIELDS:
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


def write_comments_csv(rows: List[OrderedDict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fields = union_fieldnames(rows) if rows else list(OUTPUT_FIELDS)
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def run(args: argparse.Namespace) -> Tuple[Path, int]:
    note_url = note_exporter.extract_note_url(args.url)
    note_id, xsec_source, xsec_token = note_exporter.parse_note_url(note_url)
    if not xsec_token:
        cached_url = note_exporter.cached_tokenized_url(note_id)
        if cached_url:
            cached_id, cached_source, cached_token = note_exporter.parse_note_url(cached_url)
            if cached_id == note_id and cached_token:
                note_url = cached_url
                xsec_source = cached_source or xsec_source
                xsec_token = cached_token
                print(
                    f"已从本地历史数据为小红书评论爬取补齐 xsec_token，note_id={note_id}",
                    flush=True,
                )
    output = Path(args.output) if args.output else Path(__file__).with_name("xhs_comments.csv")

    chrome_path = note_exporter.find_chrome(args.chrome)
    if args.use_default_profile and args.user_data_dir:
        raise ValueError("--use-default-profile cannot be combined with --user-data-dir")

    owns_user_dir = args.user_data_dir is None
    profile_directory = args.profile_directory
    if args.use_default_profile:
        source_root = Path(args.profile_source) if args.profile_source else note_exporter.default_browser_user_data_dir(chrome_path)
        user_dir = Path(tempfile.mkdtemp(prefix="xhs-comment-profile-"))
        owns_user_dir = True
        note_exporter.clone_browser_profile(source_root, profile_directory, user_dir)
    else:
        user_dir = Path(args.user_data_dir) if args.user_data_dir else Path(tempfile.mkdtemp(prefix="xhs-comment-cdp-"))

    proc = note_exporter.launch_chrome(chrome_path, user_dir, headless=not args.headed, profile_directory=profile_directory)
    page: Optional[note_exporter.CdpClient] = None
    try:
        port, ws_path = note_exporter.wait_for_debug_port(user_dir, args.browser_timeout)
        page = note_exporter.make_page_client(port, ws_path, args.browser_timeout)
        note_exporter.wait_for_page_signer(page, note_url, args.browser_timeout)
        state = note_exporter.wait_for_login_cookie(page, note_exporter.page_state(page), args.login_timeout)
        state["cookie_header"] = note_exporter.browser_cookie_header(page)
        if not state.get("a1") or not state.get("cookie_header"):
            raise RuntimeError("未检测到完整小红书登录 Cookie，请先登录小红书后重试。")
        access = note_exporter.resolve_note_access_from_page(
            page,
            note_id,
            xsec_source,
            xsec_token,
            args.browser_timeout,
        )
        xsec_token = access.get("xsec_token") or xsec_token
        note_url = access.get("href") or note_url

        rows = collect_comments(
            page,
            state,
            note_id,
            xsec_token,
            note_url,
            limit=args.limit,
            request_interval=args.request_interval,
            http_timeout=args.http_timeout,
            include_sub_comments=not args.no_sub_comments,
        )
        write_comments_csv(rows, output)
        return output, len(rows)
    finally:
        if page is not None:
            page.close()
        if not args.keep_browser_open:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        if owns_user_dir and not args.keep_browser_open:
            shutil.rmtree(user_dir, ignore_errors=True)


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Export all comments for one Xiaohongshu note to CSV.")
    parser.add_argument("url", help="Xiaohongshu note URL with xsec_token.")
    parser.add_argument("-o", "--output", help="Comment CSV path. Defaults to Pipeline/xhs_comments.csv.")
    parser.add_argument("--limit", type=int, default=0, help="Maximum comments to export. 0 means all comments.")
    parser.add_argument("--no-sub-comments", action="store_true", help="Only export top-level comments.")
    parser.add_argument("--request-interval", type=float, default=0.5, help="Seconds to wait between comment page requests.")
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
    parser.add_argument("--http-timeout", type=float, default=30.0, help="Seconds to wait for comment requests.")
    args = parser.parse_args(argv)

    try:
        output, count = run(args)
    except Exception as exc:
        print(f"ERROR: {exc}", file=os.sys.stderr)
        return 1
    print(f"Exported {count} comments")
    print(f"Comment CSV exported: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
