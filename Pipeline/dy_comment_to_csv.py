#!/usr/bin/env python3
"""
Export Douyin comments for one video/note to CSV.

This mirrors Social_Media_Copilot's Douyin comment exporter:
  Social_Media_Copilot/src/entrypoints/dy.content/tasks/post-comment/processor.ts
  Social_Media_Copilot/src/entrypoints/dy.content/api/comment.ts
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import dy_common as dy


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


def user_link(sec_uid: str) -> str:
    return f"https://www.douyin.com/user/{sec_uid}" if sec_uid else ""


def comment_to_row(comment: Dict[str, Any], aweme_id: str, level: str, root_comment_id: str = "") -> OrderedDict:
    user = comment.get("user") or {}
    row = OrderedDict()
    row["评论ID"] = comment.get("cid", "")
    row["笔记ID"] = comment.get("aweme_id") or aweme_id
    row["笔记链接"] = dy.canonical_aweme_url(aweme_id)
    row["评论层级"] = level
    row["用户ID"] = user.get("uid", "")
    row["用户链接"] = user_link(user.get("sec_uid", ""))
    row["用户名称"] = user.get("nickname", "")
    row["评论内容"] = comment.get("text", "")
    row["评论时间"] = dy.format_time(comment.get("create_time", ""))
    row["点赞数"] = comment.get("digg_count", "")
    row["子评论数"] = comment.get("reply_comment_total", "") if level == "一级评论" else ""
    row["IP地址"] = comment.get("ip_label", "")
    row["一级评论ID"] = root_comment_id
    row["回复目标评论ID"] = comment.get("reply_to_reply_id", "") or comment.get("reply_id", "")
    row["回复目标用户ID"] = comment.get("reply_to_userid", "")
    row["回复目标用户名称"] = comment.get("reply_to_username", "")
    for key, value in dy.flatten_json(comment).items():
        row[f"comment.{key}"] = value
    row["raw_json"] = json.dumps(comment, ensure_ascii=False, separators=(",", ":"))
    return row


def append_comment_row(
    rows: List[OrderedDict],
    seen: set,
    comment: Dict[str, Any],
    aweme_id: str,
    level: str,
    root_comment_id: str = "",
) -> bool:
    cid = str(comment.get("cid") or "")
    if not cid or cid in seen:
        return False
    seen.add(cid)
    rows.append(comment_to_row(comment, aweme_id, level, root_comment_id))
    return True


def collect_comments(
    page: dy.browser.CdpClient,
    aweme_id: str,
    limit: int,
    request_interval: float,
    http_timeout: float,
    include_replies: bool,
) -> List[OrderedDict]:
    rows: List[OrderedDict] = []
    top_comments: List[Dict[str, Any]] = []
    seen: set = set()
    cursor = 0

    while True:
        payload = dy.fetch_comment_list(page, aweme_id, cursor=cursor, count=20, timeout=http_timeout)
        comments = payload.get("comments") or []
        if not comments:
            break
        for comment in comments:
            top_comments.append(comment)
            append_comment_row(rows, seen, comment, aweme_id, "一级评论")
            if include_replies:
                for reply in comment.get("reply_comment") or []:
                    append_comment_row(rows, seen, reply, aweme_id, "子评论", comment.get("cid", ""))
            if limit > 0 and len(rows) >= limit:
                return rows[:limit]
        if not payload.get("has_more"):
            break
        cursor = int(payload.get("cursor") or 0)
        if cursor <= 0:
            break
        time.sleep(max(0.0, request_interval))

    if not include_replies:
        return rows[:limit] if limit > 0 else rows

    for comment in top_comments:
        if limit > 0 and len(rows) >= limit:
            return rows[:limit]
        if int(comment.get("reply_comment_total") or 0) <= len(comment.get("reply_comment") or []):
            continue
        root_comment_id = comment.get("cid") or ""
        cursor = 0
        while root_comment_id:
            time.sleep(max(0.0, request_interval))
            payload = dy.fetch_comment_reply_list(
                page,
                aweme_id,
                comment_id=root_comment_id,
                cursor=cursor,
                count=20,
                timeout=http_timeout,
            )
            replies = payload.get("comments") or []
            if not replies:
                break
            for reply in replies:
                append_comment_row(rows, seen, reply, aweme_id, "子评论", root_comment_id)
                if limit > 0 and len(rows) >= limit:
                    return rows[:limit]
            if not payload.get("has_more"):
                break
            cursor = int(payload.get("cursor") or 0)
            if cursor <= 0:
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
    output = Path(args.output) if args.output else Path(__file__).with_name("dy_comments.csv")
    proc, page, user_dir, owns_user_dir = dy.launch_browser_page(args, "dy-comment")
    try:
        aweme_id = dy.parse_aweme_id_from_url(args.url)
        landing_url = dy.canonical_aweme_url(aweme_id) if aweme_id else args.url
        dy.navigate_and_wait(page, landing_url, timeout=args.browser_timeout, minimum_delay=2.0)
        aweme_id = aweme_id or dy.extract_aweme_id_from_page(page)
        if not aweme_id:
            aweme_id = dy.ensure_aweme_id(page, args.url, args.browser_timeout)
        rows = collect_comments(
            page,
            aweme_id,
            limit=args.limit,
            request_interval=args.request_interval,
            http_timeout=args.http_timeout,
            include_replies=not args.no_sub_comments,
        )
        write_comments_csv(rows, output)
        return output, len(rows)
    finally:
        dy.cleanup(proc, page, user_dir, owns_user_dir, args)


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Export all comments for one Douyin video/note to CSV.")
    parser.add_argument("url", help="Douyin video/share URL.")
    parser.add_argument("-o", "--output", help="Comment CSV path. Defaults to Pipeline/dy_comments.csv.")
    parser.add_argument("--limit", type=int, default=0, help="Maximum comments to export. 0 means all comments.")
    parser.add_argument("--no-sub-comments", action="store_true", help="Only export top-level comments.")
    parser.add_argument("--request-interval", type=float, default=0.7, help="Seconds to wait between comment page requests.")
    dy.add_browser_args(parser)
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
