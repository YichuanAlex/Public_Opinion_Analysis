#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import time
from pathlib import Path
from typing import Any, Iterable, Optional

from pipeline_paths import DY_DATA_TABLE_CSV, XHS_DATA_TABLE_CSV


ROOT = Path(__file__).resolve().parent
BACKUP_DIR = ROOT / "gui_exports" / "clean_backups"

TABLES = {
    "xhs": {
        "name": "小红书",
        "path": XHS_DATA_TABLE_CSV,
        "id_patterns": [
            re.compile(r"/(?:discovery/item|explore|search_result)/([0-9a-zA-Z]{24})"),
        ],
    },
    "dy": {
        "name": "抖音",
        "path": DY_DATA_TABLE_CSV,
        "id_patterns": [
            re.compile(r"[?&]modal_id=(\d{10,30})"),
            re.compile(r"/(?:video|note|share/video)/(\d{10,30})"),
        ],
    },
}

DIRTY_WORDS = ["实习", "新橙海", "工号", "入职", "面试", "桔厂", "cpdd", "无匹配内容", "无匹配内容", "无关", "无实质", "无明确关联"]
DIRTY_FIELDS = ["笔记标题", "笔记内容", "概括", "博主昵称", "具体产品/场景", "业务线"]


def read_csv(path: Path) -> tuple[list[str], list[dict[str, Any]]]:
    if not path.exists() or path.stat().st_size == 0:
        return [], []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def clean_text(value: Any) -> str:
    return str(value or "").replace("\u00a0", " ").strip()


def extract_id_from_url(url: str, patterns: list[re.Pattern[str]]) -> str:
    for pattern in patterns:
        match = pattern.search(url or "")
        if match:
            return match.group(1)
    return ""


def row_note_id(row: dict[str, Any], patterns: list[re.Pattern[str]]) -> str:
    note_id = clean_text(row.get("笔记ID"))
    if note_id:
        return note_id
    return extract_id_from_url(clean_text(row.get("笔记链接")), patterns)


def dirty_match(row: dict[str, Any]) -> str:
    text = "\n".join(clean_text(row.get(field)) for field in DIRTY_FIELDS)
    for word in DIRTY_WORDS:
        if word in text:
            return word
    return ""


def make_backup(path: Path, platform: str) -> str:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    backup = BACKUP_DIR / f"{stamp}_{platform}_{path.name}"
    shutil.copy2(path, backup)
    return str(backup)


def clean_table(platform: str, dry_run: bool = False) -> dict[str, Any]:
    config = TABLES[platform]
    path = Path(config["path"])
    fields, rows = read_csv(path)
    if not fields:
        return {
            "platform": platform,
            "platformName": config["name"],
            "table": str(path),
            "beforeRows": 0,
            "afterRows": 0,
            "removedDirtyRows": 0,
            "removedDuplicateRows": 0,
            "filledNoteIds": 0,
            "dirtySamples": [],
            "duplicateSamples": [],
            "backup": "",
            "dryRun": dry_run,
        }
    if "笔记ID" not in fields:
        fields.append("笔记ID")

    patterns = config["id_patterns"]
    kept: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    removed_dirty = 0
    removed_duplicate = 0
    filled_note_ids = 0
    dirty_samples: list[str] = []
    duplicate_samples: list[str] = []

    for row_index, row in enumerate(rows, start=2):
        note_id = row_note_id(row, patterns)
        if note_id and not clean_text(row.get("笔记ID")):
            row["笔记ID"] = note_id
            filled_note_ids += 1

        word = dirty_match(row)
        if word:
            removed_dirty += 1
            if len(dirty_samples) < 8:
                title = clean_text(row.get("笔记标题"))[:60]
                dirty_samples.append(f"第{row_index}行 命中“{word}” {note_id or '无ID'} {title}")
            continue

        if note_id:
            if note_id in seen_ids:
                removed_duplicate += 1
                if len(duplicate_samples) < 8:
                    title = clean_text(row.get("笔记标题"))[:60]
                    duplicate_samples.append(f"第{row_index}行 重复ID {note_id} {title}")
                continue
            seen_ids.add(note_id)

        kept.append(row)

    backup = ""
    if not dry_run and (removed_dirty or removed_duplicate or filled_note_ids):
        backup = make_backup(path, platform)
        write_csv(path, fields, kept)

    return {
        "platform": platform,
        "platformName": config["name"],
        "table": str(path),
        "beforeRows": len(rows),
        "afterRows": len(kept),
        "removedDirtyRows": removed_dirty,
        "removedDuplicateRows": removed_duplicate,
        "filledNoteIds": filled_note_ids,
        "dirtyWords": DIRTY_WORDS,
        "dirtySamples": dirty_samples,
        "duplicateSamples": duplicate_samples,
        "backup": backup,
        "dryRun": dry_run,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    platforms = ["xhs", "dy"] if args.platform == "all" else [args.platform]
    results = [clean_table(platform, dry_run=args.dry_run) for platform in platforms]
    return {
        "ok": True,
        "kind": "clean-data",
        "platform": args.platform,
        "dryRun": args.dry_run,
        "results": results,
        "beforeRows": sum(item["beforeRows"] for item in results),
        "afterRows": sum(item["afterRows"] for item in results),
        "removedDirtyRows": sum(item["removedDirtyRows"] for item in results),
        "removedDuplicateRows": sum(item["removedDuplicateRows"] for item in results),
        "filledNoteIds": sum(item["filledNoteIds"] for item in results),
        "tables": [item["table"] for item in results],
        "backups": [item["backup"] for item in results if item.get("backup")],
    }


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Deduplicate and clean XHS/Douyin monitoring CSV tables.")
    parser.add_argument("--platform", choices=["xhs", "dy", "all"], default="all", help="Which platform table to clean.")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, do not write CSV files.")
    args = parser.parse_args(argv)
    try:
        result = run(args)
    except Exception as exc:
        print(f"ERROR: {exc}", flush=True)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
