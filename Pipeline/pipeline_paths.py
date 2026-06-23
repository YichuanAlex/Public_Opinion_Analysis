#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


PIPELINE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PIPELINE_DIR.parent
HYPE_ROOT = PROJECT_ROOT / "Hype_Something"
CACHE_DIR = PROJECT_ROOT / "cache"
MODEL_DIR = PROJECT_ROOT / "modelfile"

XHS_ORIGIN_CSV = PIPELINE_DIR / "xhs_origin_data.csv"
XHS_DATA_TABLE_CSV = PIPELINE_DIR / "xhs_Data_Table_on_Channel_Public_Opinion_Monitoring_2026.csv"
XHS_SUMMARY_CSV = PIPELINE_DIR / "xhs_note_10_fields.csv"
XHS_COMMENT_CSV = PIPELINE_DIR / "xhs_comments.csv"
XHS_HYPE_WORKBOOK = HYPE_ROOT / "2026_Didi_Xiaohongshu_Daily_Word-of-Mouth_Amplification.xlsx"

DY_ORIGIN_CSV = PIPELINE_DIR / "dy_origin_data.csv"
DY_DATA_TABLE_CSV = PIPELINE_DIR / "dy_Data_Table_on_Channel_Public_Opinion_Monitoring_2026.csv"
DY_SUMMARY_CSV = PIPELINE_DIR / "dy_note_10_fields.csv"
DY_COMMENT_CSV = PIPELINE_DIR / "dy_comments.csv"
DY_HYPE_WORKBOOK = HYPE_ROOT / "2026_Didi_Douyin_Daily_Word-of-Mouth_Amplification.xlsx"

LEGACY_XHS_ORIGIN_CSV = PIPELINE_DIR / "origin_data.csv"
LEGACY_XHS_DATA_TABLE_CSV = PIPELINE_DIR / "Data_Table_on_Channel_Public_Opinion_Monitoring_2026.csv"


def migrate_legacy_xhs_files() -> list[str]:
    """Move old unprefixed Xiaohongshu output files to canonical xhs_* names."""

    moved: list[str] = []
    pairs = [
        (LEGACY_XHS_ORIGIN_CSV, XHS_ORIGIN_CSV),
        (LEGACY_XHS_DATA_TABLE_CSV, XHS_DATA_TABLE_CSV),
    ]
    for old, new in pairs:
        if old.exists() and not new.exists():
            old.rename(new)
            moved.append(f"{old.name} -> {new.name}")
    return moved
