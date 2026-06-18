#!/usr/bin/env python3
"""
Always-on-top Xiaohongshu CSV exporter.

Two workflows are available:
1. Keyword search export: open the Xiaohongshu search page, collect visible note
   cards with conservative scrolling, then export all fetched details.
2. Single note export: paste a Xiaohongshu share text or note URL and export it.
"""

from __future__ import annotations

import queue
import re
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
from tkinter import (
    BOTH,
    END,
    LEFT,
    RIGHT,
    TOP,
    Button,
    Entry,
    Frame,
    Label,
    Scrollbar,
    StringVar,
    TclError,
    Text,
    Tk,
    W,
    Y,
)


PIPELINE_DIR = Path(__file__).resolve().parent
NOTE_SCRIPT = PIPELINE_DIR / "xhs_note_to_csv.py"
SEARCH_SCRIPT = PIPELINE_DIR / "xhs_search_to_csv.py"
EXPORT_DIR = PIPELINE_DIR / "gui_exports"
SEARCH_ORIGIN_CSV = PIPELINE_DIR / "origin_data.csv"
SEARCH_TEN_CSV = PIPELINE_DIR / "xhs_note_10_fields.csv"

URL_RE = re.compile(r"https?://(?:www\.)?xiaohongshu\.com/[^\s，。！？,，）)】]+")
NOTE_ID_RE = re.compile(r"/(?:discovery/item|explore|search_result)/([0-9a-zA-Z]{24})")

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

INK = "#1f2933"
MUTED = "#687684"
LINE = "#dbe3ea"
PAPER = "#f5f7f8"
PANEL = "#ffffff"
TEAL = "#0f766e"
TEAL_SOFT = "#d7f2ee"
ROSE = "#be3455"
ROSE_SOFT = "#ffe5ec"
AMBER = "#a45d10"
AMBER_SOFT = "#fff0d6"
BLUE = "#2457b8"
BLUE_SOFT = "#e7eefc"
GREEN = "#1f7a4c"
GREEN_SOFT = "#ddf4e7"
FONT = ("Arial", 13)
FONT_BOLD = ("Arial", 13, "bold")


class XhsExporterGui:
    def __init__(self) -> None:
        self.root = Tk()
        self.root.title("Rednote Heat Search Exporter")
        self.root.geometry("1120x720+70+60")
        self.root.configure(bg=PAPER)
        self.root.attributes("-topmost", True)
        self.root.minsize(980, 640)
        self.root.option_add("*Entry.background", "#ffffff")
        self.root.option_add("*Entry.foreground", INK)
        self.root.option_add("*Entry.insertBackground", INK)
        self.root.option_add("*Text.background", "#ffffff")
        self.root.option_add("*Text.foreground", INK)
        self.root.option_add("*Text.insertBackground", INK)

        self.status = StringVar(value="READY · 选择一个预设关键词，或粘贴单条笔记链接。")
        self.keyword = StringVar(value=PRESET_KEYWORDS[0])
        self.max_notes = StringVar(value="0")
        self.scroll_rounds = StringVar(value="10")
        self.last_submitted_url = ""
        self.jobs: queue.Queue[dict | None] = queue.Queue()

        self._build_ui()
        self.worker = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker.start()

        self.root.protocol("WM_DELETE_WINDOW", self._close)
        self.root.after(250, self._focus_keyword)

    def _build_ui(self) -> None:
        shell = Frame(self.root, bg=PAPER, padx=20, pady=20)
        shell.pack(fill=BOTH, expand=True)

        self.side_panel = Frame(shell, bg=PANEL, padx=18, pady=18, highlightthickness=1, highlightbackground=LINE)
        self.side_panel.pack(side=LEFT, fill=Y)

        self.workspace = Frame(shell, bg=PANEL, highlightthickness=1, highlightbackground=LINE)
        self.workspace.pack(side=RIGHT, fill=BOTH, expand=True, padx=(20, 0))

        self._build_side_panel()
        self._build_workspace()

    def _build_side_panel(self) -> None:
        brand = Frame(self.side_panel, bg=PANEL)
        brand.pack(side=TOP, fill="x")

        Label(
            brand,
            text="R",
            width=3,
            height=2,
            bg=TEAL,
            fg="#ffffff",
            font=("Arial", 18, "bold"),
        ).pack(side=LEFT)
        brand_text = Frame(brand, bg=PANEL)
        brand_text.pack(side=LEFT, padx=(12, 0))
        Label(brand_text, text="Rednote Export", bg=PANEL, fg=INK, font=("Arial", 19, "bold")).pack(anchor="w")
        Label(brand_text, text="Public Opinion Pipeline", bg=PANEL, fg=MUTED, font=("Arial", 11)).pack(anchor="w")

        self._build_keyword_chips()
        self._build_settings_panel()
        self._build_footer()

    def _build_keyword_chips(self) -> None:
        panel = self._card(self.side_panel)
        panel.pack(side=TOP, fill="x", pady=(18, 0))
        Label(panel, text="SEARCH PRESETS", bg=PANEL, fg=MUTED, font=("Arial", 11, "bold")).pack(anchor="w")
        Label(panel, text="点击一个关键词填入搜索框", bg=PANEL, fg=INK, font=FONT_BOLD).pack(anchor="w", pady=(6, 10))

        chips = Frame(panel, bg=PANEL)
        chips.pack(fill="x")
        for index, keyword in enumerate(PRESET_KEYWORDS):
            button = self._button(
                chips,
                keyword,
                command=lambda value=keyword: self._select_keyword(value),
                variant="chip",
                width=11,
            )
            button.grid(row=index // 2, column=index % 2, sticky="ew", padx=(0 if index % 2 == 0 else 8, 0), pady=(0, 8))
        chips.grid_columnconfigure(0, weight=1)
        chips.grid_columnconfigure(1, weight=1)

    def _build_settings_panel(self) -> None:
        panel = self._card(self.side_panel)
        panel.pack(side=TOP, fill="x", pady=(16, 0))
        Label(panel, text="CRAWL SETTINGS", bg=PANEL, fg=MUTED, font=("Arial", 11, "bold")).pack(anchor="w")

        self._control_row(panel, "最多笔记", self.max_notes, "0=不限制")
        self._control_row(panel, "滚动轮次", self.scroll_rounds, "建议 6-12")
        self._button(panel, "打开导出目录", command=self._open_pipeline_dir, variant="secondary").pack(fill="x", pady=(12, 0))

    def _build_workspace(self) -> None:
        top_bar = Frame(self.workspace, bg=PANEL, padx=24, pady=20, highlightthickness=1, highlightbackground=LINE)
        top_bar.pack(side=TOP, fill="x")
        title_box = Frame(top_bar, bg=PANEL)
        title_box.pack(side=LEFT)
        Label(title_box, text="关键词搜索批量导出", bg=PANEL, fg=INK, font=("Arial", 22, "bold")).pack(anchor="w")
        Label(
            title_box,
            text="搜索页保守滚动收集笔记卡片，再逐条限速导出详情 CSV。",
            bg=PANEL,
            fg=MUTED,
            font=("Arial", 12),
        ).pack(anchor="w", pady=(4, 0))
        self.status_pill = Label(
            top_bar,
            text="READY",
            bg=AMBER_SOFT,
            fg=AMBER,
            font=("Arial", 11, "bold"),
            padx=12,
            pady=7,
        )
        self.status_pill.pack(side=RIGHT)

        self._build_search_panel()
        self._build_note_panel()

    def _build_search_panel(self) -> None:
        panel = self._card(self.workspace)
        panel.pack(side=TOP, fill="x", padx=24, pady=(20, 0))

        head = Frame(panel, bg=PANEL)
        head.pack(side=TOP, fill="x")
        Label(head, text="SEARCH INPUT", bg=PANEL, fg=MUTED, font=("Arial", 11, "bold")).pack(side=LEFT)
        Label(head, text="输出到 Pipeline/origin_data.csv 与 xhs_note_10_fields.csv", bg=PANEL, fg=MUTED, font=("Arial", 11)).pack(side=RIGHT)

        row = Frame(panel, bg=PANEL)
        row.pack(side=TOP, fill="x", pady=(14, 0))
        Label(row, text="关键词输入框", bg=PANEL, fg=INK, font=FONT_BOLD).pack(side=LEFT)
        keyword_frame = Frame(row, bg=LINE, padx=1, pady=1)
        keyword_frame.pack(side=LEFT, fill="x", expand=True, padx=(10, 12))
        self.keyword_entry = Text(
            keyword_frame,
            height=1,
            wrap="none",
            font=("Arial", 15),
            bg="#ffffff",
            fg=INK,
            insertbackground=INK,
            selectbackground="#bfdbfe",
            highlightthickness=0,
            relief="flat",
            padx=10,
            pady=7,
        )
        self.keyword_entry.insert("1.0", self.keyword.get())
        self.keyword_entry.pack(fill="x", expand=True)
        self.keyword_entry.bind("<Return>", lambda _event: self._submit_search_from_key())
        self._button(row, "导出当前关键词", command=self._submit_search, variant="primary", width=18).pack(side=RIGHT)

        Label(
            panel,
            text="反扒策略：复用本机登录态临时克隆、单线程串行、滚动间隔 2.5s、详情请求间隔 2s。",
            bg=PANEL,
            fg=MUTED,
            font=("Arial", 11),
        ).pack(side=TOP, anchor="w", pady=(10, 0))

    def _build_note_panel(self) -> None:
        panel = self._card(self.workspace)
        panel.pack(side=TOP, fill=BOTH, expand=True, padx=24, pady=(18, 20))
        Label(panel, text="SINGLE NOTE", bg=PANEL, fg=MUTED, font=("Arial", 11, "bold")).pack(anchor="w")
        Label(
            panel,
            text="粘贴单条小红书分享文案或详情链接",
            bg=PANEL,
            fg=INK,
            font=("Arial", 16, "bold"),
        ).pack(anchor="w", pady=(6, 10))

        action_row = Frame(panel, bg=PANEL)
        action_row.pack(side=TOP, fill="x", pady=(0, 12))
        self._button(action_row, "从剪贴板粘贴并导出", command=self._paste_note_from_clipboard, variant="secondary", width=22).pack(side=LEFT)
        self._button(action_row, "导出链接框内容", command=self._submit_note, variant="primary", width=18).pack(side=LEFT, padx=(10, 0))

        Label(
            panel,
            text="链接框内容（可键盘输入，也可直接粘贴整段分享文案）",
            bg=PANEL,
            fg=INK,
            font=FONT_BOLD,
        ).pack(anchor="w", pady=(0, 8))

        text_frame = Frame(panel, bg=LINE, padx=1, pady=1)
        text_frame.pack(fill=BOTH, expand=True)

        scrollbar = Scrollbar(text_frame)
        scrollbar.pack(side=RIGHT, fill=Y)

        self.text = Text(
            text_frame,
            height=10,
            wrap="word",
            font=("Arial", 13),
            padx=12,
            pady=12,
            bg="#ffffff",
            fg=INK,
            insertbackground=INK,
            selectbackground="#bfdbfe",
            relief="flat",
            undo=True,
            yscrollcommand=scrollbar.set,
        )
        self.text.pack(fill=BOTH, expand=True)
        scrollbar.config(command=self.text.yview)
        self.text.bind("<Command-Return>", lambda _event: self._submit_note())
        self.text.bind("<Control-Return>", lambda _event: self._submit_note())

    def _build_footer(self) -> None:
        footer = self._card(self.side_panel)
        footer.pack(side=TOP, fill="x", pady=(16, 0))
        Label(footer, text="STATUS", bg=PANEL, fg=MUTED, font=("Arial", 11, "bold")).pack(anchor="w")
        Label(
            footer,
            textvariable=self.status,
            anchor="w",
            justify=LEFT,
            bg=PANEL,
            fg=INK,
            font=("Arial", 12),
            wraplength=310,
        ).pack(fill="x", pady=(8, 0))

    def _card(self, parent: Frame) -> Frame:
        return Frame(parent, bg=PANEL, padx=16, pady=16, highlightthickness=1, highlightbackground=LINE)

    def _button(self, parent: Frame, text: str, command, variant: str = "secondary", width: int = 14) -> Button:
        palette = {
            "primary": (TEAL, "#ffffff", TEAL),
            "secondary": ("#ffffff", INK, LINE),
            "ghost": (PAPER, INK, LINE),
            "chip": (TEAL_SOFT, TEAL, TEAL_SOFT),
        }
        bg, fg, border = palette.get(variant, palette["secondary"])
        return Button(
            parent,
            text=text,
            command=command,
            width=width,
            bg=bg,
            fg=fg,
            activebackground=bg,
            activeforeground=fg,
            relief="flat",
            borderwidth=0,
            highlightthickness=1,
            highlightbackground=border,
            padx=8,
            pady=8,
            font=FONT_BOLD,
            cursor="hand2",
        )

    def _control_row(self, parent: Frame, label: str, variable: StringVar, hint: str) -> None:
        row = Frame(parent, bg=PANEL)
        row.pack(side=TOP, fill="x", pady=(12, 0))
        left = Frame(row, bg=PANEL)
        left.pack(side=LEFT, anchor=W)
        Label(left, text=label, bg=PANEL, fg=INK, font=FONT_BOLD).pack(anchor="w")
        Label(left, text=hint, bg=PANEL, fg=MUTED, font=("Arial", 10)).pack(anchor="w")
        Entry(
            row,
            textvariable=variable,
            font=FONT,
            width=8,
            bg="#ffffff",
            fg=INK,
            insertbackground=INK,
            selectbackground="#bfdbfe",
            highlightthickness=1,
            highlightbackground=LINE,
            highlightcolor=TEAL,
            relief="flat",
        ).pack(side=RIGHT, ipady=5)

    def _focus_keyword(self) -> None:
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.keyword_entry.focus_force()

    def _select_keyword(self, keyword: str) -> None:
        self._set_keyword(keyword)
        self.status.set(f"已选择关键词：{keyword}。点击“导出当前关键词”开始。")

    def _submit_search(self) -> None:
        keyword = self._get_keyword()
        if not keyword:
            self.status.set("请输入搜索关键词。")
            return
        max_notes = parse_int(self.max_notes.get(), 0)
        scroll_rounds = parse_int(self.scroll_rounds.get(), 10)
        self.jobs.put({
            "type": "search",
            "keyword": keyword,
            "max_notes": max_notes,
            "scroll_rounds": max(1, scroll_rounds),
        })
        cap = "不限制" if max_notes <= 0 else str(max_notes)
        self.status.set(f"已加入关键词搜索队列：{keyword}；最多笔记：{cap}")
        self.status_pill.config(text="RUNNING", bg=BLUE_SOFT, fg=BLUE)

    def _submit_search_from_key(self) -> str:
        self._submit_search()
        return "break"

    def _get_keyword(self) -> str:
        return self.keyword_entry.get("1.0", END).strip()

    def _set_keyword(self, keyword: str) -> None:
        self.keyword.set(keyword)
        self.keyword_entry.delete("1.0", END)
        self.keyword_entry.insert("1.0", keyword)

    def _paste_note_from_clipboard(self) -> None:
        try:
            content = self.root.clipboard_get()
        except TclError:
            self.status.set("剪贴板没有可读取的文本。")
            return
        self.text.delete("1.0", END)
        self.text.insert("1.0", content)
        self._submit_note()

    def _submit_note(self) -> None:
        content = self.text.get("1.0", END)
        url = extract_xhs_url(content)
        if not url:
            self.status.set("链接框里还没有识别到小红书链接。")
            return
        if url == self.last_submitted_url:
            return
        self.last_submitted_url = url
        self.jobs.put({"type": "note", "url": url})
        self.status.set(f"已加入单条链接队列：{shorten(url)}")

    def _worker_loop(self) -> None:
        while True:
            job = self.jobs.get()
            if job is None:
                return
            try:
                if job["type"] == "search":
                    origin_csv, ten_csv, count = run_search_export(
                        job["keyword"],
                        job["max_notes"],
                        job["scroll_rounds"],
                    )
                    self._set_status(
                        f"关键词搜索导出完成，共 {count} 条：\n"
                        f"全量字段：{origin_csv}\n"
                        f"10字段：{ten_csv}"
                    )
                    self._set_pill("READY", GREEN_SOFT, GREEN)
                else:
                    full_csv, ten_csv = run_note_export(job["url"])
                    self._set_status(
                        "单条链接导出完成：\n"
                        f"全量字段：{full_csv}\n"
                        f"10字段：{ten_csv}"
                    )
                    self._set_pill("READY", GREEN_SOFT, GREEN)
            except Exception as exc:
                self._set_status(f"导出失败：{exc}")
                self._set_pill("ERROR", ROSE_SOFT, ROSE)
            finally:
                self.jobs.task_done()

    def _set_status(self, value: str) -> None:
        self.root.after(0, lambda: self.status.set(value))

    def _set_pill(self, text: str, bg: str, fg: str) -> None:
        self.root.after(0, lambda: self.status_pill.config(text=text, bg=bg, fg=fg))

    def _open_pipeline_dir(self) -> None:
        subprocess.run(["open", str(PIPELINE_DIR)], check=False)

    def _close(self) -> None:
        self.jobs.put(None)
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def extract_xhs_url(text: str) -> str:
    match = URL_RE.search(text)
    if not match:
        return ""
    return match.group(0).rstrip("。；;，,）)】]")


def note_id_from_url(url: str) -> str:
    match = NOTE_ID_RE.search(url)
    if match:
        return match.group(1)
    return datetime.now().strftime("%Y%m%d%H%M%S")


def shorten(value: str, max_len: int = 90) -> str:
    return value if len(value) <= max_len else value[:max_len - 3] + "..."


def parse_int(value: str, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def run_note_export(url: str) -> tuple[Path, Path]:
    if not NOTE_SCRIPT.exists():
        raise FileNotFoundError(f"找不到抓取脚本：{NOTE_SCRIPT}")

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    note_id = note_id_from_url(url)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    full_csv = EXPORT_DIR / f"{stamp}_{note_id}_origin_data.csv"
    ten_csv = EXPORT_DIR / f"{stamp}_{note_id}_10_fields.csv"

    cmd = [
        sys.executable,
        str(NOTE_SCRIPT),
        "--use-default-profile",
        "--output",
        str(full_csv),
        "--summary-output",
        str(ten_csv),
        url,
    ]
    run_checked(cmd)
    return full_csv, ten_csv


def run_search_export(keyword: str, max_notes: int, scroll_rounds: int) -> tuple[Path, Path, int]:
    if not SEARCH_SCRIPT.exists():
        raise FileNotFoundError(f"找不到搜索抓取脚本：{SEARCH_SCRIPT}")

    cmd = [
        sys.executable,
        str(SEARCH_SCRIPT),
        keyword,
        "--output",
        str(SEARCH_ORIGIN_CSV),
        "--summary-output",
        str(SEARCH_TEN_CSV),
        "--max-notes",
        str(max_notes),
        "--scroll-rounds",
        str(scroll_rounds),
    ]
    stdout = run_checked(cmd)
    count = 0
    for line in stdout.splitlines():
        if line.startswith("Exported ") and " notes" in line:
            count = parse_int(line.split()[1], 0)
    return SEARCH_ORIGIN_CSV, SEARCH_TEN_CSV, count


def run_checked(cmd: list[str]) -> str:
    result = subprocess.run(
        cmd,
        cwd=str(PIPELINE_DIR.parent),
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(detail or f"{Path(cmd[1]).name} exited with code {result.returncode}")
    return result.stdout or ""


def main() -> int:
    XhsExporterGui().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
