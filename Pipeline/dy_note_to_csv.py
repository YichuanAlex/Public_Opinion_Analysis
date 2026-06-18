#!/usr/bin/env python3
"""
Export one Douyin video/note detail to CSV.

The field mapping follows Social_Media_Copilot's Douyin video exporter:
  Social_Media_Copilot/src/entrypoints/dy.content/tasks/post/processor.ts
  Social_Media_Copilot/src/entrypoints/dy.content/api/aweme.ts
"""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path
from typing import Iterable, Optional, Tuple

import dy_common as dy


PIPELINE_DIR = Path(__file__).resolve().parent
DEFAULT_URL = "https://www.douyin.com/"


def run(args: argparse.Namespace) -> Tuple[Path, Optional[Path]]:
    output = Path(args.output) if args.output else PIPELINE_DIR / "dy_origin_data.csv"
    summary_output = None if args.no_summary else (
        Path(args.summary_output) if args.summary_output else PIPELINE_DIR / "dy_note_10_fields.csv"
    )

    proc, page, user_dir, owns_user_dir = dy.launch_browser_page(args, "dy-note")
    try:
        aweme_id = dy.parse_aweme_id_from_url(args.url)
        landing_url = args.url
        if aweme_id:
            landing_url = dy.canonical_aweme_url(aweme_id)
        dy.navigate_and_wait(page, landing_url, timeout=args.browser_timeout, minimum_delay=2.0)
        aweme_id = aweme_id or dy.extract_aweme_id_from_page(page)
        if not aweme_id:
            aweme_id = dy.ensure_aweme_id(page, args.url, args.browser_timeout)

        detail = dy.fetch_aweme_detail(page, aweme_id, timeout=args.http_timeout)
        flat = dy.build_flat_row(detail, args.url, aweme_id)
        dy.write_rows_csv(
            [flat],
            output,
            preferred=[
                "platform",
                "source_url",
                "note_id",
                "aweme_id",
                "aweme_detail.aweme_id",
                "aweme_detail.share_url",
                "aweme_detail.author.nickname",
                "aweme_detail.desc",
                "aweme_detail.statistics.digg_count",
                "aweme_detail.statistics.collect_count",
                "aweme_detail.statistics.comment_count",
                "aweme_detail.statistics.share_count",
                "aweme_detail.create_time",
            ],
        )
        if summary_output is not None:
            dy.write_summary_csv([flat], summary_output)
        return output, summary_output
    finally:
        dy.cleanup(proc, page, user_dir, owns_user_dir, args)


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Export Douyin video/note API fields to CSV.")
    parser.add_argument("url", nargs="?", default=DEFAULT_URL, help="Douyin video/share URL.")
    parser.add_argument("-o", "--output", help="Full-field CSV output path. Defaults to Pipeline/dy_origin_data.csv.")
    parser.add_argument("--summary-output", help="10-field CSV output path. Defaults to Pipeline/dy_note_10_fields.csv.")
    parser.add_argument("--no-summary", action="store_true", help="Do not write the 10-field summary CSV.")
    dy.add_browser_args(parser)
    args = parser.parse_args(argv)

    try:
        output, summary_output = run(args)
    except Exception as exc:
        print(f"ERROR: {exc}", file=os.sys.stderr)
        return 1
    print(f"Full CSV exported: {output}")
    if summary_output is not None:
        print(f"10-field CSV exported: {summary_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
