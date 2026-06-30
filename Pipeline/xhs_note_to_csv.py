#!/usr/bin/env python3
"""
Export a Xiaohongshu note feed payload to CSV.

This mirrors the Social_Media_Copilot XHS flow:
  Social_Media_Copilot/src/entrypoints/xhs.content/api/note.ts
  Social_Media_Copilot/src/entrypoints/xhs.content/api/request.ts

No Python packages are required. The script launches Chrome through the Chrome
DevTools Protocol so it can call the page-provided window.mnsv2 signer, then it
posts to https://edith.xiaohongshu.com/api/sns/web/v1/feed.
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import os
import random
import re
import shutil
import socket
import ssl
import struct
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import browser_profile_pool
from media_enrichment import append_media_text, enrich_flat_row
from pipeline_paths import XHS_DATA_TABLE_CSV, XHS_ORIGIN_CSV, XHS_SUMMARY_CSV


DEFAULT_URL = (
    "https://www.xiaohongshu.com/discovery/item/"
    "6a2ea3b0000000001702f2ba?source=webshare&xhsshare=pc_web"
    "&xsec_token=ABCyGjHjOjvsO5Z03mhaZqEKNsrb30SFx940snY3WXPaY="
    "&xsec_source=pc_share"
)

API_BASE = "https://edith.xiaohongshu.com"
API_PATH = "/api/sns/web/v1/feed"
COPILOT_NOTE_CACHE_DIR = Path(__file__).resolve().parent / "gui_exports" / "copilot_note_cache"

CUSTOM_B64_ALPHABET = [
    "Z", "m", "s", "e", "r", "b", "B", "o", "H", "Q", "t", "N", "P", "+", "w", "O",
    "c", "z", "a", "/", "L", "p", "n", "g", "G", "8", "y", "J", "q", "4", "2", "K",
    "W", "Y", "j", "0", "D", "S", "f", "d", "i", "k", "x", "3", "V", "T", "1", "6",
    "I", "l", "U", "A", "F", "M", "9", "7", "h", "E", "C", "v", "u", "R", "X", "5",
]


class CdpError(RuntimeError):
    pass


class WebSocket:
    def __init__(self, url: str, timeout: float = 30.0):
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("ws", "wss"):
            raise ValueError(f"Unsupported websocket scheme: {parsed.scheme}")
        self.host = parsed.hostname or "127.0.0.1"
        self.port = parsed.port or (443 if parsed.scheme == "wss" else 80)
        self.path = parsed.path or "/"
        if parsed.query:
            self.path += "?" + parsed.query

        raw = socket.create_connection((self.host, self.port), timeout=timeout)
        if parsed.scheme == "wss":
            raw = ssl.create_default_context().wrap_socket(raw, server_hostname=self.host)
        self.sock = raw
        self.sock.settimeout(timeout)
        self._handshake()

    def _handshake(self) -> None:
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        request = (
            f"GET {self.path} HTTP/1.1\r\n"
            f"Host: {self.host}:{self.port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        self.sock.sendall(request.encode("ascii"))
        response = b""
        while b"\r\n\r\n" not in response:
            chunk = self.sock.recv(4096)
            if not chunk:
                break
            response += chunk
        if b" 101 " not in response.split(b"\r\n", 1)[0]:
            raise CdpError("Chrome websocket handshake failed")

    def send_json(self, payload: Dict[str, Any]) -> None:
        self._send_frame(json.dumps(payload, separators=(",", ":")).encode("utf-8"))

    def recv_json(self) -> Dict[str, Any]:
        while True:
            opcode, data = self._recv_frame()
            if opcode == 1:
                return json.loads(data.decode("utf-8"))
            if opcode == 8:
                raise CdpError("Chrome websocket closed")
            if opcode == 9:
                self._send_frame(data, opcode=10)

    def close(self) -> None:
        try:
            self._send_frame(b"", opcode=8)
        except OSError:
            pass
        try:
            self.sock.close()
        except OSError:
            pass

    def _send_frame(self, data: bytes, opcode: int = 1) -> None:
        first = 0x80 | opcode
        length = len(data)
        mask_bit = 0x80
        if length < 126:
            header = struct.pack("!BB", first, mask_bit | length)
        elif length < (1 << 16):
            header = struct.pack("!BBH", first, mask_bit | 126, length)
        else:
            header = struct.pack("!BBQ", first, mask_bit | 127, length)
        mask = os.urandom(4)
        masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(data))
        self.sock.sendall(header + mask + masked)

    def _recv_exact(self, size: int) -> bytes:
        chunks = []
        remaining = size
        while remaining:
            chunk = self.sock.recv(remaining)
            if not chunk:
                raise CdpError("Unexpected websocket EOF")
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def _recv_frame(self) -> Tuple[int, bytes]:
        first, second = struct.unpack("!BB", self._recv_exact(2))
        opcode = first & 0x0F
        masked = bool(second & 0x80)
        length = second & 0x7F
        if length == 126:
            length = struct.unpack("!H", self._recv_exact(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", self._recv_exact(8))[0]
        mask = self._recv_exact(4) if masked else b""
        data = self._recv_exact(length)
        if masked:
            data = bytes(byte ^ mask[index % 4] for index, byte in enumerate(data))
        return opcode, data


class CdpClient:
    def __init__(self, ws_url: str, timeout: float = 30.0):
        self.ws = WebSocket(ws_url, timeout=timeout)
        self.next_id = 1

    def close(self) -> None:
        self.ws.close()

    def call(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        message_id = self.next_id
        self.next_id += 1
        self.ws.send_json({"id": message_id, "method": method, "params": params or {}})
        while True:
            message = self.ws.recv_json()
            if message.get("id") != message_id:
                continue
            if "error" in message:
                raise CdpError(f"{method} failed: {message['error']}")
            return message.get("result", {})

    def evaluate(self, expression: str, await_promise: bool = False) -> Any:
        result = self.call(
            "Runtime.evaluate",
            {
                "expression": expression,
                "awaitPromise": await_promise,
                "returnByValue": True,
                "userGesture": True,
            },
        )
        remote = result.get("result", {})
        if "exceptionDetails" in result:
            raise CdpError(json.dumps(result["exceptionDetails"], ensure_ascii=False))
        if remote.get("subtype") == "error":
            raise CdpError(remote.get("description", "Runtime.evaluate error"))
        return remote.get("value")


XHS_NOTE_URL_RE = re.compile(
    r"https?://(?:www\.)?xiaohongshu\.com/(?:discovery/item|explore|search_result)/[^\s，。！？,，）)】\]]+"
)


def extract_redirect_note_url_from_404(url: str) -> str:
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        return ""
    if not parsed.netloc.endswith("xiaohongshu.com") or parsed.path.rstrip("/") != "/404":
        return ""
    params = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
    candidates: List[str] = []
    for key in ("redirectPath", "redirect_path"):
        candidates.extend(params.get(key) or [])
    for source in params.get("source") or []:
        source_text = urllib.parse.unquote(source or "")
        if "redirectPath=" in source_text:
            inner = urllib.parse.urlparse(source_text)
            inner_params = urllib.parse.parse_qs(inner.query, keep_blank_values=True)
            candidates.extend(inner_params.get("redirectPath") or [])
            candidates.extend(inner_params.get("redirect_path") or [])
    for candidate in candidates:
        text = urllib.parse.unquote(candidate or "")
        match = XHS_NOTE_URL_RE.search(text)
        if match:
            return match.group(0).rstrip("。；;，,）)】]")
    return ""


def extract_note_url(value: str) -> str:
    text = (
        str(value or "")
        .replace("&amp;", "&")
        .replace("\\u002F", "/")
        .replace("\\/", "/")
        .replace("\\u003F", "?")
        .replace("\\u003D", "=")
        .replace("\\u0026", "&")
    )
    match = XHS_NOTE_URL_RE.search(text)
    if match:
        return match.group(0).rstrip("。；;，,）)】]")
    for url_match in re.finditer(r"https?://(?:www\.)?xiaohongshu\.com/404[^\s，。！？,，）)】\]]+", text):
        redirected = extract_redirect_note_url_from_404(url_match.group(0))
        if redirected:
            return redirected
    redirected = extract_redirect_note_url_from_404(text.strip())
    if redirected:
        return redirected
    return text.strip().rstrip("。；;，,）)】]")


def parse_note_url(url: str) -> Tuple[str, str, str]:
    url = extract_note_url(url)
    parsed = urllib.parse.urlparse(url)
    note_id = parsed.path.rstrip("/").split("/")[-1]
    if len(note_id) != 24 or not note_id.isalnum():
        raise ValueError(f"Invalid Xiaohongshu note id in URL: {note_id}")
    params = urllib.parse.parse_qs(parsed.query)
    xsec_token = (params.get("xsec_token") or [""])[0]
    xsec_source = (params.get("xsec_source") or [""])[0]
    if not xsec_source:
        xsec_source = "pc_search"
    return note_id, xsec_source, xsec_token


def cached_tokenized_url(note_id: str) -> str:
    if not note_id:
        return ""
    pattern = re.compile(
        rf"https?://(?:www\.)?xiaohongshu\.com/(?:discovery/item|explore|search_result)/{re.escape(note_id)}[^\s\"'<>]*xsec_token=[^\s\"'<>]+",
        re.I,
    )
    for path in (XHS_ORIGIN_CSV, XHS_DATA_TABLE_CSV):
        if not path.exists() or path.stat().st_size == 0:
            continue
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    values = "\n".join(str(value or "") for value in row.values())
                    values = (
                        values.replace("&amp;", "&")
                        .replace("\\u0026", "&")
                        .replace("\\/", "/")
                        .replace("\\u003F", "?")
                        .replace("\\u003D", "=")
                    )
                    match = pattern.search(values)
                    if match:
                        return match.group(0).rstrip("。；;，,）)】]}")
        except Exception:
            continue
    return ""


def with_url_query(url: str, **updates: str) -> str:
    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
    for key, value in updates.items():
        if value:
            params[key] = [value]
    query = urllib.parse.urlencode(params, doseq=True)
    return urllib.parse.urlunparse(parsed._replace(query=query))


def candidate_note_urls(url: str, note_id: str, xsec_source: str, xsec_token: str) -> List[str]:
    parsed = urllib.parse.urlparse(url)
    original_params = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
    original_source = (original_params.get("xsec_source") or [""])[0]
    original_token = (original_params.get("xsec_token") or [""])[0]
    source = xsec_source or original_source or "pc_search"
    token = xsec_token or original_token
    cached_url = cached_tokenized_url(note_id)
    cached_params: Dict[str, List[str]] = {}
    if cached_url:
        cached_params = urllib.parse.parse_qs(urllib.parse.urlparse(cached_url).query, keep_blank_values=True)

    result: List[str] = []
    seen = set()

    def add(candidate: str) -> None:
        if not candidate:
            return
        clean = candidate.replace("&amp;", "&").rstrip("。；;，,）)】]")
        if note_id and note_id not in clean:
            return
        if clean not in seen:
            seen.add(clean)
            result.append(clean)

    def build(path: str, params: Dict[str, str]) -> str:
        query = urllib.parse.urlencode({key: value for key, value in params.items() if value})
        return urllib.parse.urlunparse(("https", "www.xiaohongshu.com", path, "", query, ""))

    pc_search = build(f"/explore/{note_id}", {"xsec_source": "pc_search"})
    if not token:
        # 裸笔记链接在新版小红书更容易从 explore + pc_search 入口进入详情页。
        add(pc_search)
    add(url)
    add(cached_url)

    token_sets: List[Tuple[str, str, Dict[str, str]]] = []
    if token:
        token_sets.append((source, token, {key: values[0] for key, values in original_params.items() if values}))
    cached_token = (cached_params.get("xsec_token") or [""])[0]
    cached_source = (cached_params.get("xsec_source") or [""])[0]
    if cached_token:
        token_sets.append((cached_source or "pc_share", cached_token, {key: values[0] for key, values in cached_params.items() if values}))

    for item_source, item_token, base_params in token_sets:
        params = dict(base_params)
        params["xsec_token"] = item_token
        params["xsec_source"] = item_source or "pc_share"
        if (params["xsec_source"] or "").startswith("pc_"):
            params.setdefault("source", "webshare")
            params.setdefault("xhsshare", "pc_web")
        for path in (f"/explore/{note_id}", f"/discovery/item/{note_id}", f"/search_result/{note_id}"):
            add(build(path, params))
        app_params = {
            "app_platform": "ios",
            "app_version": "9.34.4",
            "type": "normal",
            "xhsshare": "CopyLink",
            "xsec_source": "app_share",
            "xsec_token": item_token,
        }
        add(build(f"/explore/{note_id}", app_params))

    source_candidates = []
    for candidate_source in (source, original_source, "pc_search", "pc_feed", "pc_share"):
        if candidate_source and candidate_source not in source_candidates:
            source_candidates.append(candidate_source)
    for candidate_source in source_candidates:
        add(build(f"/explore/{note_id}", {"xsec_source": candidate_source}))
        add(build(f"/discovery/item/{note_id}", {"xsec_source": candidate_source}))
        add(build(f"/search_result/{note_id}", {"xsec_source": candidate_source}))
    return result


def canonical_pc_search_explore_url(note_id: str) -> str:
    query = urllib.parse.urlencode({"xsec_source": "pc_search"})
    return urllib.parse.urlunparse(("https", "www.xiaohongshu.com", f"/explore/{note_id}", "", query, ""))


def find_chrome(explicit: Optional[str]) -> str:
    candidates = [
        explicit,
        os.environ.get("CHROME_PATH"),
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    raise FileNotFoundError("Chrome/Chromium was not found. Pass --chrome /path/to/chrome.")


def launch_chrome(
    chrome_path: str,
    user_data_dir: Path,
    headless: bool,
    profile_directory: Optional[str] = None,
) -> subprocess.Popen:
    args = [
        chrome_path,
        "--remote-debugging-port=0",
        f"--user-data-dir={user_data_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-background-networking",
        "--disable-sync",
        "--disable-extensions",
    ]
    if profile_directory:
        args.append(f"--profile-directory={profile_directory}")
    if headless:
        args.append("--headless=new")
        args.append("--disable-gpu")
    return subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def default_browser_user_data_dir(chrome_path: str) -> Path:
    home = Path.home()
    if "Microsoft Edge" in chrome_path:
        return home / "Library/Application Support/Microsoft Edge"
    if os.name == "nt":
        local = os.environ.get("LOCALAPPDATA", "")
        return Path(local) / "Google/Chrome/User Data"
    if os.uname().sysname == "Darwin":
        return home / "Library/Application Support/Google/Chrome"
    return home / ".config/google-chrome"


def copy_if_exists(src: Path, dst: Path) -> None:
    if src.is_file():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def copy_tree_if_exists(src: Path, dst: Path, ignore_names: Optional[List[str]] = None) -> None:
    if not src.is_dir():
        return
    ignore = set(ignore_names or [])
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns(*ignore))


def clone_browser_profile(source_root: Path, profile_directory: str, dest_root: Path) -> None:
    source_profile = source_root / profile_directory
    if not source_profile.is_dir():
        raise FileNotFoundError(f"Chrome profile directory not found: {source_profile}")

    dest_root.mkdir(parents=True, exist_ok=True)
    dest_profile = dest_root / profile_directory
    dest_profile.mkdir(parents=True, exist_ok=True)

    for filename in ("Local State", "First Run"):
        copy_if_exists(source_root / filename, dest_root / filename)

    for filename in (
        "Preferences",
        "Secure Preferences",
        "Cookies",
        "Cookies-journal",
        "Login Data",
        "Login Data For Account",
        "History",
        "History-journal",
        "Web Data",
        "Web Data-journal",
        "Favicons",
        "Favicons-journal",
    ):
        copy_if_exists(source_profile / filename, dest_profile / filename)

    for dirname in (
        "Network",
        "Local Storage",
        "Session Storage",
        "IndexedDB",
        "Service Worker",
        "Storage",
        "File System",
        "WebStorage",
        "Shared Dictionary",
        "shared_proto_db",
        "blob_storage",
    ):
        copy_tree_if_exists(
            source_profile / dirname,
            dest_profile / dirname,
            ignore_names=[
                "Cache",
                "Code Cache",
                "GPUCache",
                "DawnCache",
                "GrShaderCache",
                "DawnGraphiteCache",
                "DawnWebGPUCache",
                "ShaderCache",
            ],
        )


def wait_for_debug_port(user_data_dir: Path, timeout: float, since: float = 0.0) -> Tuple[int, str]:
    port_file = user_data_dir / "DevToolsActivePort"
    deadline = time.time() + timeout
    while time.time() < deadline:
        if port_file.exists():
            if since and port_file.stat().st_mtime < since - 1:
                time.sleep(0.1)
                continue
            lines = port_file.read_text(encoding="utf-8").splitlines()
            if len(lines) >= 2:
                return int(lines[0]), lines[1]
        time.sleep(0.1)
    raise TimeoutError("Timed out waiting for Chrome DevToolsActivePort")


def http_json(url: str, timeout: float = 30.0) -> Any:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def make_page_client(port: int, browser_ws_path: str, timeout: float) -> CdpClient:
    deadline = time.time() + timeout
    last_error: Optional[Exception] = None
    target_id = ""
    while time.time() < deadline:
        browser = None
        try:
            browser = CdpClient(f"ws://127.0.0.1:{port}{browser_ws_path}", timeout=timeout)
            target = browser.call("Target.createTarget", {"url": "about:blank"})
            target_id = target["targetId"]
            break
        except Exception as exc:
            last_error = exc
            time.sleep(0.3)
        finally:
            if browser is not None:
                try:
                    browser.close()
                except Exception:
                    pass
    if not target_id:
        detail = f" Last error: {last_error}" if last_error else ""
        raise TimeoutError(f"Timed out connecting to Chrome DevTools websocket.{detail}")

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            targets = http_json(f"http://127.0.0.1:{port}/json/list", timeout=min(timeout, 5.0))
        except Exception as exc:
            last_error = exc
            time.sleep(0.3)
            continue
        for item in targets:
            if item.get("id") == target_id and item.get("webSocketDebuggerUrl"):
                return CdpClient(item["webSocketDebuggerUrl"], timeout=timeout)
        time.sleep(0.1)
    detail = f" Last error: {last_error}" if last_error else ""
    raise TimeoutError(f"Timed out finding Chrome page target.{detail}")


def wait_for_page_signer(page: CdpClient, target_url: str, timeout: float) -> None:
    page.call("Page.enable")
    page.call("Network.enable")
    page.call("Runtime.enable")
    page.call("Page.navigate", {"url": target_url})
    deadline = time.time() + timeout
    last_error = None
    while time.time() < deadline:
        try:
            ready = page.evaluate("document.readyState")
            has_signer = page.evaluate('typeof window.mnsv2 === "function"')
            if ready in ("interactive", "complete") and has_signer:
                return
        except Exception as exc:  # Navigation can briefly destroy the context.
            last_error = exc
        time.sleep(0.5)
    detail = f" Last error: {last_error}" if last_error else ""
    raise TimeoutError(f"Timed out waiting for window.mnsv2 on the page.{detail}")


def page_security_status(page: CdpClient, note_id: str = "") -> Dict[str, Any]:
    note_id_json = json.dumps(note_id or "", ensure_ascii=False)
    expression = r"""
((noteId) => {
  const clean = (value) => String(value || '').replace(/\s+/g, ' ').trim();
  const href = location.href || '';
  const title = document.title || '';
  const body = clean(document.body ? document.body.innerText : '').slice(0, 1000);
  const security = /\/404|\/website-login\/error|error_code=300031|error_code=300017|sec_/i.test(href)
    || /Sorry,\s*This Page Isn't Available Right Now/i.test(title)
    || /Sorry,\s*This Page Isn't Available Right Now/i.test(body);
  const target = !noteId || href.includes(noteId);
  const usable = target && !security && (
    /说点什么|共\s*\d+\s*条评论|下载图片|复制笔记信息|同步飞书|导出评论/.test(body)
    || !!document.querySelector('#noteContainer, .note-container, [class*="note-detail"], [class*="interaction"], [class*="comments"]')
  );
  return { href, title, security, target, usable, body };
})(""" + note_id_json + r""")
"""
    try:
        result = page.evaluate(expression) or {}
        return result if isinstance(result, dict) else {}
    except Exception as exc:
        return {"security": False, "error": str(exc)}


def wait_for_note_page(page: CdpClient, candidates: List[str], timeout: float, note_id: str = "") -> str:
    errors: List[str] = []
    for index, candidate in enumerate(candidates, start=1):
        try:
            wait_for_page_signer(page, candidate, timeout)
        except Exception as exc:
            errors.append(f"{index}/{len(candidates)} {candidate}: {exc}")
            print(
                f"小红书候选链接 {index}/{len(candidates)} 等待页面签名失败，继续尝试下一种入口：{candidate}；{exc}",
                flush=True,
            )
            continue

        status: Dict[str, Any] = {}
        for settle_round in range(3):
            time.sleep(0.8)
            try:
                page.evaluate("window.scrollBy(0, Math.min(360, Math.floor(window.innerHeight / 3 || 240)))")
            except Exception:
                pass
            status = page_security_status(page, note_id)
            if status.get("usable") or (not status.get("security") and status.get("target", True)):
                if index > 1:
                    print(f"小红书访问链接已切换到候选 {index}/{len(candidates)}：{status.get('href') or candidate}", flush=True)
                return str(status.get("href") or candidate)
            if status.get("security") or not status.get("target", True):
                break
        if not status.get("target", True):
            print(
                f"小红书候选链接 {index}/{len(candidates)} 已跳转到非目标页面，继续尝试下一种入口："
                f"{status.get('href') or candidate}",
                flush=True,
            )
            continue
        print(
            f"小红书候选链接 {index}/{len(candidates)} 落到安全页，继续尝试下一种入口："
            f"{status.get('href') or candidate}",
            flush=True,
        )
    detail = " | ".join(errors[-3:])
    raise RuntimeError(
        "所有小红书候选入口都未进入目标详情页，已拒绝继续写入安全页或广告页。"
        f"目标 note_id={note_id}。最后错误：{detail}"
    )


def page_state(page: CdpClient) -> Dict[str, Any]:
    expression = r"""
(() => {
  const getCookie = (name) => {
    const cookies = document.cookie.split(';');
    for (const item of cookies) {
      const cookie = item.trim();
      if (cookie.startsWith(name + '=')) return cookie.slice(name.length + 1);
    }
    return null;
  };
  const b1 = localStorage["b1"];
  return {
    href: location.href,
    userAgent: navigator.userAgent,
    cookie: document.cookie,
    a1: getCookie("a1"),
    b1: b1 === undefined ? null : b1,
    b1Missing: b1 === undefined,
    b1b1: localStorage["b1b1"] || "1",
    xsecplatform: window["xsecplatform"] || "PC"
  };
})()
"""
    return page.evaluate(expression)


def resolve_note_access_from_page(
    page: CdpClient,
    note_id: str,
    fallback_source: str,
    fallback_token: str,
    timeout: float,
) -> Dict[str, str]:
    if fallback_token:
        return {"xsec_source": fallback_source or "pc_search", "xsec_token": fallback_token, "href": ""}

    note_id_json = json.dumps(note_id)
    expression = r"""
((noteId) => {
  const decode = (value) => String(value || '')
    .replaceAll('&amp;', '&')
    .replaceAll('\\u002F', '/')
    .replaceAll('\\/', '/')
    .replaceAll('\\u003F', '?')
    .replaceAll('\\u003D', '=')
    .replaceAll('\\u0026', '&');
  const candidates = [];
  const push = (value) => {
    const text = decode(value);
    if (text && text.includes(noteId) && text.includes('xsec_token=')) candidates.push(text);
  };
  push(location.href);
  for (const anchor of Array.from(document.querySelectorAll('a[href]'))) {
    push(anchor.href || anchor.getAttribute('href'));
  }
  push(document.documentElement.outerHTML);
  for (const text of candidates) {
    const patterns = [
      new RegExp(`https?:\\/\\/www\\.xiaohongshu\\.com\\/(?:search_result|explore|discovery\\/item)\\/${noteId}[^"'<>\\s]*xsec_token=[^"'<>\\s&]+[^"'<>\\s]*`, 'g'),
      new RegExp(`\\/(?:search_result|explore|discovery\\/item)\\/${noteId}[^"'<>\\s]*xsec_token=[^"'<>\\s&]+[^"'<>\\s]*`, 'g')
    ];
    for (const pattern of patterns) {
      const matches = text.match(pattern) || [];
      for (const raw of matches) {
        try {
          const href = new URL(raw, location.origin).href;
          const url = new URL(href);
          const token = url.searchParams.get('xsec_token') || '';
          const source = url.searchParams.get('xsec_source') || 'pc_search';
          if (token) return { href, xsec_token: token, xsec_source: source };
        } catch (_) {}
      }
    }
  }
  return { href: location.href, xsec_token: '', xsec_source: '' };
})(""" + note_id_json + r""")
"""
    deadline = time.time() + max(1.0, min(timeout, 20.0))
    last_result: Dict[str, str] = {}
    while time.time() < deadline:
        try:
            result = page.evaluate(expression) or {}
            if isinstance(result, dict):
                last_result = {str(key): str(value or "") for key, value in result.items()}
                if last_result.get("xsec_token"):
                    print(
                        f"已从小红书页面补齐 xsec_token，xsec_source={last_result.get('xsec_source') or 'pc_search'}",
                        flush=True,
                    )
                    return last_result
        except Exception:
            pass
        time.sleep(0.8)

    if fallback_token:
        return {"xsec_source": fallback_source or "pc_search", "xsec_token": fallback_token, "href": ""}
    href = last_result.get("href", "")
    print(
        "当前小红书链接缺少 xsec_token，页面中也未解析到 token；"
        "将继续用 note_id 直接请求接口，如平台拒绝会在下一步返回错误。"
        f" 当前页面：{href}",
        flush=True,
    )
    return {"href": href, "xsec_token": "", "xsec_source": fallback_source or "pc_search"}


def browser_cookie_header(page: CdpClient) -> str:
    urls = ["https://www.xiaohongshu.com/", API_BASE + "/"]
    try:
        result = page.call("Network.getCookies", {"urls": urls})
        cookies = result.get("cookies", [])
    except CdpError:
        result = page.call("Network.getAllCookies")
        cookies = [
            item for item in result.get("cookies", [])
            if str(item.get("domain", "")).lstrip(".").endswith("xiaohongshu.com")
        ]

    deduped = OrderedDict()
    for cookie in cookies:
        name = cookie.get("name")
        value = cookie.get("value")
        if name is not None and value is not None:
            deduped[name] = value
    return "; ".join(f"{name}={value}" for name, value in deduped.items())


def page_mnsv2(page: CdpClient, path: str, body_json: str) -> str:
    sign_input = path + body_json
    md5_input = hashlib.md5(sign_input.encode("utf-8")).hexdigest()
    md5_path = hashlib.md5(path.encode("utf-8")).hexdigest()
    args_json = json.dumps([sign_input, md5_input, md5_path], ensure_ascii=False)
    expression = f"window.mnsv2(...{args_json})"
    return page.evaluate(expression, await_promise=True)


def custom_b64(data: bytes) -> str:
    out = []
    full = len(data) - (len(data) % 3)
    for i in range(0, full, 3):
        triplet = (data[i] << 16) + (data[i + 1] << 8) + data[i + 2]
        out.append(CUSTOM_B64_ALPHABET[(triplet >> 18) & 63])
        out.append(CUSTOM_B64_ALPHABET[(triplet >> 12) & 63])
        out.append(CUSTOM_B64_ALPHABET[(triplet >> 6) & 63])
        out.append(CUSTOM_B64_ALPHABET[triplet & 63])

    remainder = len(data) % 3
    if remainder == 1:
        value = data[-1]
        out.append(CUSTOM_B64_ALPHABET[value >> 2])
        out.append(CUSTOM_B64_ALPHABET[(value << 4) & 63])
        out.append("==")
    elif remainder == 2:
        value = (data[-2] << 8) + data[-1]
        out.append(CUSTOM_B64_ALPHABET[value >> 10])
        out.append(CUSTOM_B64_ALPHABET[(value >> 4) & 63])
        out.append(CUSTOM_B64_ALPHABET[(value << 2) & 63])
        out.append("=")
    return "".join(out)


def custom_b64_json(data: OrderedDict) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return custom_b64(payload.encode("utf-8"))


def js_crc_for_xs_common(value: str) -> int:
    table = [0] * 256
    poly = 0xEDB88320
    for d in range(255, -1, -1):
        r = d
        for _ in range(8):
            r = ((r >> 1) ^ poly) if (r & 1) else (r >> 1)
        table[d] = r & 0xFFFFFFFF

    c = 0xFFFFFFFF
    for char in value:
        c = (table[((c & 0xFF) ^ ord(char)) & 0xFF] ^ (c >> 8)) & 0xFFFFFFFF
    return ((0xFFFFFFFF ^ c) ^ poly) & 0xFFFFFFFF


def os_get_os_like_plugin(user_agent: str) -> str:
    ua = (user_agent or "").lower()
    if "android" in ua:
        return "Android"
    if "iphone" in ua or "ipad" in ua or "ipod" in ua:
        return "iOS"
    if ua.find("macintosh") != 0:
        return "Mac OS"
    if ua.find("windows") != 0:
        return "Windows"
    if ua.find("linux") != 0:
        return "Linux"
    return "PC"


def platform_code(os_name: str) -> int:
    return {
        "Windows": 0,
        "iOS": 1,
        "Android": 2,
        "Mac OS": 3,
        "Linux": 4,
    }.get(os_name, 5)


def build_xs_common(state: Dict[str, Any]) -> str:
    os_name = os_get_os_like_plugin(state.get("userAgent", ""))
    b1_missing = bool(state.get("b1Missing"))
    b1 = state.get("b1")
    b1_text = "undefined" if b1_missing else str(b1)
    data = OrderedDict()
    data["s0"] = platform_code(os_name)
    data["s1"] = ""
    data["x0"] = state.get("b1b1") or "1"
    data["x1"] = "4.2.6"
    data["x2"] = os_name
    data["x3"] = "xhs-pc-web"
    data["x4"] = "4.83.1"
    data["x5"] = state.get("a1")
    data["x6"] = ""
    data["x7"] = ""
    if not b1_missing:
        data["x8"] = b1
    data["x9"] = js_crc_for_xs_common(b1_text)
    data["x10"] = 0
    data["x11"] = "normal"
    return custom_b64_json(data)


def build_xs(page: CdpClient, state: Dict[str, Any], body_json: str) -> str:
    mnsv2 = page_mnsv2(page, API_PATH, body_json)
    data = OrderedDict()
    data["x0"] = "4.2.6"
    data["x1"] = "xhs-pc-web"
    data["x2"] = state.get("xsecplatform") or "PC"
    data["x3"] = mnsv2
    data["x4"] = "object"
    return "XYS_" + custom_b64_json(data)


def trace_id() -> str:
    now_ms = int(time.time() * 1000)
    part1 = (now_ms << 23) | random.randrange(1 << 23)
    part2 = (random.randrange(1 << 32) << 32) | random.randrange(1 << 32)
    return f"{part1:016x}{part2:016x}"


def b3_trace_id() -> str:
    return "".join(random.choice("abcdef0123456789") for _ in range(16))


def build_body(note_id: str, xsec_source: str, xsec_token: str) -> OrderedDict:
    body = OrderedDict()
    body["source_note_id"] = note_id
    body["image_formats"] = ["jpg", "webp", "avif"]
    body["extra"] = OrderedDict([("need_body_topic", "1")])
    body["xsec_source"] = xsec_source
    body["xsec_token"] = xsec_token
    return body


def post_feed(page: CdpClient, state: Dict[str, Any], body: OrderedDict, timeout: float) -> Dict[str, Any]:
    body_json = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json;charset=UTF-8",
        "Origin": "https://www.xiaohongshu.com",
        "Referer": state.get("href") or "https://www.xiaohongshu.com/",
        "User-Agent": state.get("userAgent") or "",
        "Cookie": state.get("cookie_header") or state.get("cookie") or "",
        "x-s": build_xs(page, state, body_json),
        "x-t": str(int(time.time() * 1000)),
        "x-s-common": build_xs_common(state),
        "x-xray-traceid": trace_id(),
        "x-b3-traceid": b3_trace_id(),
    }
    request = urllib.request.Request(
        API_BASE + API_PATH,
        data=body_json.encode("utf-8"),
        headers=headers,
        method="POST",
    )
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
            message += (
                "。请确认浏览器已登录小红书；可尝试加 --use-default-profile，"
                "或加 --headed --login-timeout 180 后在打开的浏览器里登录。"
            )
        raise RuntimeError(message)
    if isinstance(payload, dict) and "data" in payload:
        return payload["data"]
    return payload


def should_use_page_fallback(exc: Exception) -> bool:
    text = str(exc)
    return any(token in text for token in ("HTTP 461", "300031", "当前笔记暂时无法浏览"))


def feed_data_has_note(data: Dict[str, Any]) -> bool:
    if not isinstance(data, dict) or not data:
        return False
    if data.get("items") or data.get("note_card") or data.get("noteCard"):
        return True
    return any(key in data for key in ("title", "desc", "display_title", "content"))


def page_fallback_payload(page: CdpClient, note_id: str, source_url: str) -> Dict[str, Any]:
    note_id_json = json.dumps(note_id, ensure_ascii=False)
    source_url_json = json.dumps(source_url, ensure_ascii=False)
    expression = r"""
((noteId, sourceUrl) => {
  const clean = (value) => String(value || '').replace(/\s+/g, ' ').trim();
  const meta = (name) => {
    const selectors = [
      `meta[property="${name}"]`,
      `meta[name="${name}"]`,
      `meta[itemprop="${name}"]`
    ];
    for (const selector of selectors) {
      const node = document.querySelector(selector);
      const value = node && (node.getAttribute('content') || node.content);
      if (clean(value)) return clean(value);
    }
    return '';
  };
  const decodeJsonString = (value) => {
    const text = String(value || '');
    if (!text) return '';
    try {
      return clean(JSON.parse('"' + text.replace(/"/g, '\\"') + '"'));
    } catch (_error) {
      return clean(text.replace(/\\n/g, '\n').replace(/\\"/g, '"').replace(/\\u002F/g, '/').replace(/\\u0026/g, '&'));
    }
  };
  const scriptText = Array.from(document.scripts || [])
    .map((node) => node.textContent || '')
    .filter((text) => !noteId || text.includes(noteId))
    .join('\n')
    .slice(0, 800000);
  const scriptValue = (names, maxLen = 10000) => {
    for (const name of names) {
      const patterns = [
        new RegExp('"' + name + '"\\s*:\\s*"((?:\\\\.|[^"\\\\])*)"', 'i'),
        new RegExp("'" + name + "'\\s*:\\s*'((?:\\\\.|[^'\\\\])*)'", 'i')
      ];
      for (const pattern of patterns) {
        const match = scriptText.match(pattern);
        const value = match ? decodeJsonString(match[1]) : '';
        if (value && value.length <= maxLen && value !== '[]' && value !== '{}') return value;
      }
    }
    return '';
  };
  const scriptNumber = (names) => {
    for (const name of names) {
      const match = scriptText.match(new RegExp('"' + name + '"\\s*:\\s*"?([0-9]+(?:\\.[0-9]+)?\\s*(?:万|千|w|W|k|K)?)"?', 'i'));
      if (match) return clean(match[1]);
    }
    return '';
  };
  const firstText = (selectors, minLen = 1, maxLen = 5000) => {
    for (const selector of selectors) {
      for (const node of Array.from(document.querySelectorAll(selector))) {
        const text = clean(node.innerText || node.textContent || node.getAttribute('title') || '');
        if (text.length >= minLen && text.length <= maxLen) return text;
      }
    }
    return '';
  };
  const escapeRe = (value) => String(value || '').replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const allText = clean(document.body ? document.body.innerText : '');
  const titleCandidates = [
    scriptValue(['title', 'display_title', 'displayTitle'], 220),
    firstText(['h1', '.title', '[class*="title"]'], 2, 180),
    meta('og:title'),
    meta('twitter:title'),
    document.title
  ].filter(Boolean).map(clean);
  let title = titleCandidates.find((item) => !/小红书|你的生活兴趣社区|登录/.test(item)) || titleCandidates[0] || '';
  title = title.replace(/\s*[-|_]\s*小红书.*$/, '').replace(/\s*小红书.*$/, '').trim();
  const pageTitle = clean(document.title || '');
  const href = location.href || sourceUrl;
  const isSecurityPage = /\/404|\/website-login\/error|error_code=300031|error_code=300017|sec_/i.test(href)
    || /Sorry,\s*This Page Isn't Available Right Now/i.test(pageTitle)
    || /Sorry,\s*This Page Isn't Available Right Now/i.test(allText.slice(0, 800));
  const targetNotePresent = !noteId || href.includes(noteId);

  const descCandidates = [
    scriptValue(['desc', 'desc_v2', 'content', 'description'], 12000),
    firstText(['#detail-desc', '.note-content', '.desc', '[class*="desc"]', '[class*="content"]'], 3, 8000),
    meta('description'),
    meta('og:description'),
    meta('twitter:description')
  ].filter(Boolean).map(clean);
  let desc = descCandidates.find((item) => item && item !== title && !/^小红书/.test(item)) || '';
  desc = desc.replace(/展开全部$/, '').trim();

  const authorCandidates = [
    scriptValue(['nickname', 'nick_name', 'user_nickname'], 100),
    firstText(['#noteContainer [class*="author"] [class*="name"]', '#noteContainer [class*="user"] [class*="name"]', '#noteContainer [class*="nickname"]'], 1, 80),
    firstText(['[class*="author"] [class*="name"]', '[class*="user"] [class*="name"]', '[class*="nickname"]'], 1, 80),
    meta('author')
  ].filter(Boolean).map(clean);
  let author = authorCandidates[0] || '';
  if (title) {
    const titleIndex = allText.indexOf(title);
    if (titleIndex > 0) {
      const beforeTitle = allText.slice(Math.max(0, titleIndex - 100), titleIndex);
      const beforeMatch = beforeTitle.match(/(?:^|\s)(?:\d+\s*\/\s*\d+\s+)?(.{1,36}?)\s+关注\s*$/);
      if (beforeMatch && clean(beforeMatch[1]) && !/^我$/.test(clean(beforeMatch[1]))) {
        author = clean(beforeMatch[1]);
      }
    }
  }
  if ((!author || /^我$/.test(author)) && title) {
    const aroundMatch = allText.match(new RegExp('(?:\\d+\\s*\\/\\s*\\d+\\s+)?(.{1,36}?)\\s+关注\\s+' + escapeRe(title)));
    if (aroundMatch && clean(aroundMatch[1]) && !/^我$/.test(clean(aroundMatch[1]))) {
      author = clean(aroundMatch[1]);
    }
  }
  const normalizeAuthor = (value) => {
    let out = clean(value)
      .replace(/\s*关注$/, '')
      .replace(/\s*\/\s*(刚刚|\d+\s*(秒|分钟|小时|天|周|月|年)前).*$/, '')
      .trim();
    const slideMatch = out.match(/(?:^|\s)\d+\s*\/\s*\d+\s+(.+)$/);
    if (slideMatch && clean(slideMatch[1])) out = clean(slideMatch[1]);
    out = out.replace(/^.*电话[:：]\s*\S+\s+/, '').trim();
    return out.length <= 36 ? out : out.slice(-36).trim();
  };
  author = normalizeAuthor(author);

  const parseCountText = (text, labels) => {
    const normalized = clean(text).replace(/,/g, '');
    for (const label of labels) {
      const patterns = [
        new RegExp('([0-9]+(?:\\.[0-9]+)?\\s*(?:万|千|w|W|k|K)?)\\s*' + label),
        new RegExp(label + '\\s*([0-9]+(?:\\.[0-9]+)?\\s*(?:万|千|w|W|k|K)?)')
      ];
      for (const pattern of patterns) {
        const match = normalized.match(pattern);
        if (match) return match[1].replace(/\s+/g, '');
      }
    }
    return '';
  };
  const texts = Array.from(document.querySelectorAll('button, span, div, a'))
    .map((node) => clean(node.innerText || node.textContent || ''))
    .filter((text) => text && text.length <= 120);
  const joined = texts.join(' | ') + ' | ' + allText.slice(0, 12000);
  let likedCount = scriptNumber(['liked_count', 'likedCount', 'like_count', 'likeCount']) || parseCountText(joined, ['点赞', '赞']);
  let collectedCount = scriptNumber(['collected_count', 'collectedCount', 'collect_count', 'collectCount']) || parseCountText(joined, ['收藏']);
  let commentCount = scriptNumber(['comment_count', 'commentCount', 'comments_count', 'commentsCount']) || parseCountText(joined, ['评论']);
  let shareCount = scriptNumber(['share_count', 'shareCount', 'shares_count', 'sharesCount']) || parseCountText(joined, ['分享']);
  const bottomCounts = allText.match(/说点什么[.。…·\s]*([0-9]+(?:\.[0-9]+)?\s*(?:万|千|w|W|k|K)?)\s+([0-9]+(?:\.[0-9]+)?\s*(?:万|千|w|W|k|K)?)\s+([0-9]+(?:\.[0-9]+)?\s*(?:万|千|w|W|k|K)?)(?:\s+([0-9]+(?:\.[0-9]+)?\s*(?:万|千|w|W|k|K)?))?/);
  if (bottomCounts) {
    likedCount = likedCount || bottomCounts[1];
    collectedCount = collectedCount || bottomCounts[2];
    commentCount = commentCount || bottomCounts[3];
    shareCount = shareCount || (bottomCounts[4] || '');
  }

  const scriptTime = scriptNumber(['time', 'create_time', 'createTime', 'publish_time', 'publishTime']);
  const timeMatch = allText.match(/(20\d{2}[-/.年]\s*\d{1,2}[-/.月]\s*\d{1,2}(?:[日号]?\s+\d{1,2}:\d{2}(?::\d{2})?)?|(?:昨天|前天|今天)\s*\d{1,2}:\d{2}|刚刚|\d+\s*(?:秒|分钟|小时|天)前)/);
  const publishTime = scriptTime || (timeMatch ? clean(timeMatch[1].replace(/年|月/g, '-').replace(/日|号/g, '')) : '');

  const images = Array.from(document.images || [])
    .map((img) => img.currentSrc || img.src || img.getAttribute('src') || '')
    .filter((src) => /^https?:\/\//.test(src))
    .filter((src) => !/avatar|qrcode|icon|logo/i.test(src))
    .filter((src) => !/fe-platform\.xhscdn\.com\/platform|\/platform\//i.test(src))
    .slice(0, 20);
  const videos = Array.from(document.querySelectorAll('video, source'))
    .map((node) => node.currentSrc || node.src || node.getAttribute('src') || '')
    .filter((src) => /^https?:\/\//.test(src))
    .slice(0, 8);

  const scriptImageUrls = Array.from(scriptText.matchAll(/https?:\\?\/\\?\/[^"'\\\s]+(?:sns-webpic|sns-img|notes_pre_post|xhscdn)[^"'\\\s]*/ig))
    .map((match) => match[0].replace(/\\\//g, '/').replace(/\\u002F/g, '/').replace(/\\u0026/g, '&'))
    .filter((src) => /^https?:\/\//.test(src));
  const uniqueImages = Array.from(new Set(images.concat(scriptImageUrls)));
  const preferredImages = uniqueImages.filter((url) => /notes_pre_post|sns-webpic|sns-img/i.test(url));
  const imageList = (preferredImages.length ? preferredImages : uniqueImages).map((url) => ({ url_default: url, url }));
  const videoList = Array.from(new Set(videos)).map((url) => ({ url }));
  return {
    href,
    is_security_page: isSecurityPage,
    target_note_present: targetNotePresent,
    title,
    desc,
    author,
    liked_count: likedCount,
    collected_count: collectedCount,
    comment_count: commentCount,
    share_count: shareCount,
    publish_time: publishTime,
    image_list: imageList,
    video_list: videoList,
    text_sample: allText.slice(0, 2000),
    extraction_method: 'page_dom_fallback'
  };
})(""" + note_id_json + ", " + source_url_json + r""")
"""
    payload = page.evaluate(expression) or {}
    if not isinstance(payload, dict):
        payload = {}
    title = str(payload.get("title") or "").strip()
    desc = str(payload.get("desc") or "").strip()
    author = str(payload.get("author") or "").strip()
    if str(payload.get("is_security_page", "")).lower() == "true":
        raise RuntimeError(
            "小红书页面仍停留在 404/300031 安全页，拒绝把安全页或广告页内容写入 CSV。"
            "请在打开的浏览器窗口中确认该链接能进入详情页后重试。"
        )
    if str(payload.get("target_note_present", "")).lower() == "false":
        raise RuntimeError(
            "小红书页面已跳转到非目标笔记页，拒绝把推荐流、广告页或首页内容写入 CSV。"
            f"目标 note_id={note_id}，当前页面={payload.get('href') or source_url}"
        )
    if not any((title, desc, author)):
        raise RuntimeError("小红书 API 拒绝后，页面 DOM 中也没有提取到可用的标题/正文/作者。")
    card = OrderedDict()
    card["note_id"] = note_id
    card["title"] = title
    card["display_title"] = title
    card["desc"] = desc or title
    card["time"] = payload.get("publish_time", "")
    card["user"] = OrderedDict([("nickname", author)])
    card["interact_info"] = OrderedDict([
        ("liked_count", str(payload.get("liked_count", "") or "").strip()),
        ("collected_count", str(payload.get("collected_count", "") or "").strip()),
        ("comment_count", str(payload.get("comment_count", "") or "").strip()),
        ("share_count", str(payload.get("share_count", "") or "").strip()),
    ])
    card["image_list"] = payload.get("image_list") or []
    if payload.get("video_list"):
        card["video"] = OrderedDict([("url_list", payload.get("video_list") or [])])
    return {
        "items": [
            {
                "id": note_id,
                "note_card": card,
            }
        ],
        "page_fallback": payload,
    }


LIVE_BROWSER_JS = r"""
(() => {
  const clean = (value) => String(value || '').replace(/\s+/g, ' ').trim();
  const firstText = (selectors, minLen = 1, maxLen = 5000) => {
    for (const selector of selectors) {
      for (const node of Array.from(document.querySelectorAll(selector))) {
        const text = clean(node.innerText || node.textContent || node.getAttribute('title') || '');
        if (text.length >= minLen && text.length <= maxLen) return text;
      }
    }
    return '';
  };
  const meta = (name) => {
    for (const selector of [`meta[property="${name}"]`, `meta[name="${name}"]`, `meta[itemprop="${name}"]`]) {
      const node = document.querySelector(selector);
      const value = node && (node.getAttribute('content') || node.content);
      if (clean(value)) return clean(value);
    }
    return '';
  };
  const decodeJsonString = (value) => {
    const text = String(value || '');
    if (!text) return '';
    try {
      return clean(JSON.parse('"' + text.replace(/"/g, '\\"') + '"'));
    } catch (_error) {
      return clean(text.replace(/\\n/g, '\n').replace(/\\"/g, '"').replace(/\\u002F/g, '/').replace(/\\u0026/g, '&'));
    }
  };
  const href = location.href || '';
  const noteIdMatch = href.match(/(?:explore|discovery\/item|search_result)\/([0-9a-zA-Z]{24})/);
  const noteId = noteIdMatch ? noteIdMatch[1] : '';
  const scriptText = Array.from(document.scripts || [])
    .map((node) => node.textContent || '')
    .filter((text) => !noteId || text.includes(noteId))
    .join('\n')
    .slice(0, 800000);
  const scriptValue = (names, maxLen = 10000) => {
    for (const name of names) {
      const patterns = [
        new RegExp('"' + name + '"\\s*:\\s*"((?:\\\\.|[^"\\\\])*)"', 'i'),
        new RegExp("'" + name + "'\\s*:\\s*'((?:\\\\.|[^'\\\\])*)'", 'i')
      ];
      for (const pattern of patterns) {
        const match = scriptText.match(pattern);
        const value = match ? decodeJsonString(match[1]) : '';
        if (value && value.length <= maxLen && value !== '[]' && value !== '{}') return value;
      }
    }
    return '';
  };
  const scriptNumber = (names) => {
    for (const name of names) {
      const match = scriptText.match(new RegExp('"' + name + '"\\s*:\\s*"?([0-9]+(?:\\.[0-9]+)?\\s*(?:万|千|w|W|k|K)?)"?', 'i'));
      if (match) return clean(match[1]);
    }
    return '';
  };
  const allText = clean(document.body ? document.body.innerText : '');
  const pageTitle = clean(document.title || '');
  const isSecurityPage = /\/404|\/website-login\/error|error_code=300031|error_code=300017|sec_/i.test(href)
    || /Sorry,\s*This Page Isn't Available Right Now/i.test(pageTitle)
    || /Sorry,\s*This Page Isn't Available Right Now/i.test(allText.slice(0, 800));
  const titleCandidates = [
    scriptValue(['title', 'display_title', 'displayTitle'], 220),
    firstText(['h1', '.title', '[class*="title"]'], 2, 180),
    meta('og:title'),
    meta('twitter:title'),
    pageTitle
  ].filter(Boolean).map(clean);
  let title = titleCandidates.find((item) => !/小红书|你的生活兴趣社区|登录/.test(item)) || titleCandidates[0] || '';
  title = title.replace(/\s*[-|_]\s*小红书.*$/, '').replace(/\s*小红书.*$/, '').trim();
  const descCandidates = [
    scriptValue(['desc', 'desc_v2', 'content', 'description'], 12000),
    firstText(['#detail-desc', '.note-content', '.desc', '[class*="desc"]', '[class*="content"]'], 3, 8000),
    meta('description'),
    meta('og:description'),
    meta('twitter:description')
  ].filter(Boolean).map(clean);
  let desc = descCandidates.find((item) => item && item !== title && !/^小红书/.test(item)) || '';
  desc = desc.replace(/展开全部$/, '').trim();
  let author = scriptValue(['nickname', 'nick_name', 'user_nickname'], 100)
    || firstText(['#noteContainer [class*="author"] [class*="name"]', '#noteContainer [class*="user"] [class*="name"]', '#noteContainer [class*="nickname"]'], 1, 80)
    || firstText(['[class*="author"] [class*="name"]', '[class*="user"] [class*="name"]', '[class*="nickname"]'], 1, 80)
    || meta('author');
  if (title) {
    const titleIndex = allText.indexOf(title);
    if (titleIndex > 0) {
      const beforeTitle = allText.slice(Math.max(0, titleIndex - 120), titleIndex);
      const beforeMatch = beforeTitle.match(/(?:^|\s)(?:\d+\s*\/\s*\d+\s+)?(.{1,36}?)\s+关注\s*$/);
      if (beforeMatch && clean(beforeMatch[1]) && !/^我$/.test(clean(beforeMatch[1]))) {
        author = clean(beforeMatch[1]);
      }
    }
  }
  author = clean(author)
    .replace(/\s*关注$/, '')
    .replace(/^.*电话[:：]\s*\S+\s+/, '')
    .replace(/(?:^|\s)\d+\s*\/\s*\d+\s+/, '')
    .trim();
  const parseCountText = (text, labels) => {
    const normalized = clean(text).replace(/,/g, '');
    for (const label of labels) {
      for (const pattern of [
        new RegExp('([0-9]+(?:\\.[0-9]+)?\\s*(?:万|千|w|W|k|K)?)\\s*' + label),
        new RegExp(label + '\\s*([0-9]+(?:\\.[0-9]+)?\\s*(?:万|千|w|W|k|K)?)')
      ]) {
        const match = normalized.match(pattern);
        if (match) return match[1].replace(/\s+/g, '');
      }
    }
    return '';
  };
  let likedCount = scriptNumber(['liked_count', 'likedCount', 'like_count', 'likeCount']) || parseCountText(allText, ['点赞', '赞']);
  let collectedCount = scriptNumber(['collected_count', 'collectedCount', 'collect_count', 'collectCount']) || parseCountText(allText, ['收藏']);
  let commentCount = scriptNumber(['comment_count', 'commentCount', 'comments_count', 'commentsCount']) || parseCountText(allText, ['评论']);
  let shareCount = scriptNumber(['share_count', 'shareCount', 'shares_count', 'sharesCount']) || parseCountText(allText, ['分享']);
  const bottomCounts = allText.match(/说点什么[.。…·\s]*([0-9]+(?:\.[0-9]+)?\s*(?:万|千|w|W|k|K)?)\s+([0-9]+(?:\.[0-9]+)?\s*(?:万|千|w|W|k|K)?)\s+([0-9]+(?:\.[0-9]+)?\s*(?:万|千|w|W|k|K)?)(?:\s+([0-9]+(?:\.[0-9]+)?\s*(?:万|千|w|W|k|K)?))?/);
  if (bottomCounts) {
    likedCount = likedCount || bottomCounts[1];
    collectedCount = collectedCount || bottomCounts[2];
    commentCount = commentCount || bottomCounts[3];
    shareCount = shareCount || (bottomCounts[4] || '');
  }
  const scriptTime = scriptNumber(['time', 'create_time', 'createTime', 'publish_time', 'publishTime']);
  const timeMatch = allText.match(/(20\d{2}[-/.年]\s*\d{1,2}[-/.月]\s*\d{1,2}(?:[日号]?\s+\d{1,2}:\d{2}(?::\d{2})?)?|(?:昨天|前天|今天)\s*\d{1,2}:\d{2}|刚刚|\d+\s*(?:秒|分钟|小时|天)前)/);
  const publishTime = scriptTime || (timeMatch ? clean(timeMatch[1].replace(/年|月/g, '-').replace(/日|号/g, '')) : '');
  const images = Array.from(document.images || [])
    .map((img) => img.currentSrc || img.src || img.getAttribute('src') || '')
    .filter((src) => /^https?:\/\//.test(src))
    .filter((src) => !/avatar|qrcode|icon|logo|fe-platform\.xhscdn\.com\/platform|\/platform\//i.test(src));
  const scriptImageUrls = Array.from(scriptText.matchAll(/https?:\\?\/\\?\/[^"'\\\s]+(?:sns-webpic|sns-img|notes_pre_post|xhscdn)[^"'\\\s]*/ig))
    .map((match) => match[0].replace(/\\\//g, '/').replace(/\\u002F/g, '/').replace(/\\u0026/g, '&'))
    .filter((src) => /^https?:\/\//.test(src));
  const uniqueImages = Array.from(new Set(images.concat(scriptImageUrls)));
  const preferredImages = uniqueImages.filter((url) => /notes_pre_post|sns-webpic|sns-img/i.test(url));
  const imageList = (preferredImages.length ? preferredImages : uniqueImages).slice(0, 20).map((url) => ({ url_default: url, url }));
  return JSON.stringify({
    href,
    is_security_page: isSecurityPage,
    title,
    desc,
    author,
    liked_count: likedCount,
    collected_count: collectedCount,
    comment_count: commentCount,
    share_count: shareCount,
    publish_time: publishTime,
    image_list: imageList,
    text_sample: allText.slice(0, 2000),
    extraction_method: 'mac_live_browser_fallback'
  });
})()
"""


def payload_to_feed_data(payload: Dict[str, Any], note_id: str) -> Dict[str, Any]:
    title = str(payload.get("title") or "").strip()
    desc = str(payload.get("desc") or "").strip()
    author = str(payload.get("author") or "").strip()
    href = str(payload.get("href") or "").strip()
    if str(payload.get("is_security_page", "")).lower() == "true":
        raise RuntimeError(
            "真实浏览器页面仍停留在 404/300031 安全页，拒绝把安全页或广告页内容写入 CSV。"
        )
    if note_id and href and note_id not in href:
        raise RuntimeError(
            "真实浏览器页面已跳转到非目标笔记页，拒绝把推荐流、广告页或首页内容写入 CSV。"
            f"目标 note_id={note_id}，当前页面={href}"
        )
    if not any((title, desc, author)):
        raise RuntimeError("真实浏览器 DOM 中没有提取到可用的标题/正文/作者。")
    card = OrderedDict()
    card["note_id"] = note_id
    card["title"] = title
    card["display_title"] = title
    card["desc"] = desc or title
    card["time"] = payload.get("publish_time", "")
    card["user"] = OrderedDict([("nickname", author)])
    card["interact_info"] = OrderedDict([
        ("liked_count", str(payload.get("liked_count", "") or "").strip()),
        ("collected_count", str(payload.get("collected_count", "") or "").strip()),
        ("comment_count", str(payload.get("comment_count", "") or "").strip()),
        ("share_count", str(payload.get("share_count", "") or "").strip()),
    ])
    card["image_list"] = payload.get("image_list") or []
    return {
        "items": [
            {
                "id": note_id,
                "note_card": card,
            }
        ],
        "page_fallback": payload,
    }


COPILOT_LABEL_ALIASES = OrderedDict([
    ("note_id", ["笔记ID", "笔记id", "帖子ID", "帖子id"]),
    ("source_url", ["笔记链接", "帖子链接", "链接"]),
    ("author", ["博主昵称", "作者昵称", "作者", "博主"]),
    ("title", ["笔记标题", "帖子标题", "标题"]),
    ("desc", ["笔记内容", "帖子内容", "正文", "内容"]),
    ("liked_count", ["点赞数", "点赞量"]),
    ("collected_count", ["收藏数", "收藏量"]),
    ("comment_count", ["评论数", "评论量"]),
    ("share_count", ["分享数", "分享量"]),
    ("time", ["发布时间", "发布日期"]),
    ("note_type", ["笔记类型", "帖子类型"]),
    ("ip_location", ["IP地址", "IP属地"]),
])


def parse_copilot_label_text(text: str) -> Dict[str, str]:
    raw = str(text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not raw:
        return {}
    labels = [label for names in COPILOT_LABEL_ALIASES.values() for label in names]
    label_re = re.compile(r"(?m)^(" + "|".join(re.escape(label) for label in labels) + r")\s*[:：]\s*")
    matches = list(label_re.finditer(raw))
    parsed: Dict[str, str] = {}
    for index, match in enumerate(matches):
        label = match.group(1)
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(raw)
        value = raw[start:end].strip()
        for key, aliases in COPILOT_LABEL_ALIASES.items():
            if label in aliases:
                parsed[key] = value
                break
    return parsed


def parse_copilot_payload_text(text: str) -> Dict[str, str]:
    raw = str(text or "").strip()
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except Exception:
        payload = None
    if isinstance(payload, dict):
        flat = flatten_json(payload)
        return {
            "note_id": str(pick(flat, "note_id", "note_card.note_id", "items.0.note_card.note_id", "id") or ""),
            "source_url": str(pick(flat, "source_url", "url", "href") or ""),
            "author": str(pick(flat, "user.nickname", "note_card.user.nickname", "items.0.note_card.user.nickname") or ""),
            "title": str(pick(flat, "title", "note_card.title", "items.0.note_card.title") or ""),
            "desc": str(pick(flat, "desc", "content", "note_card.desc", "items.0.note_card.desc") or ""),
            "liked_count": str(pick(flat, "interact_info.liked_count", "note_card.interact_info.liked_count", "items.0.note_card.interact_info.liked_count") or ""),
            "collected_count": str(pick(flat, "interact_info.collected_count", "note_card.interact_info.collected_count", "items.0.note_card.interact_info.collected_count") or ""),
            "comment_count": str(pick(flat, "interact_info.comment_count", "note_card.interact_info.comment_count", "items.0.note_card.interact_info.comment_count") or ""),
            "share_count": str(pick(flat, "interact_info.share_count", "note_card.interact_info.share_count", "items.0.note_card.interact_info.share_count") or ""),
            "time": str(pick(flat, "time", "note_card.time", "items.0.note_card.time") or ""),
            "note_type": str(pick(flat, "type", "note_card.type", "items.0.note_card.type") or ""),
            "ip_location": str(pick(flat, "ip_location", "note_card.ip_location", "items.0.note_card.ip_location") or ""),
        }
    return parse_copilot_label_text(raw)


def read_macos_clipboard_text() -> str:
    try:
        result = subprocess.run(["pbpaste"], text=True, capture_output=True, timeout=3, check=False)
    except Exception:
        return ""
    return result.stdout or ""


def copilot_text_to_feed_data(
    text: str,
    note_url: str,
    note_id: str,
    source_label: str = "剪贴板",
) -> Tuple[Dict[str, Any], str]:
    parsed = parse_copilot_payload_text(text)
    copied_note_id = str(parsed.get("note_id") or "").strip()
    if copied_note_id and note_id and copied_note_id != note_id:
        raise RuntimeError(
            f"{source_label}里的 Social_Media_Copilot 笔记ID是 {copied_note_id}，不是当前目标 {note_id}。"
            "请在目标帖子页确认插件已拿到当前笔记信息后重试。"
        )
    final_note_id = copied_note_id or note_id
    title = str(parsed.get("title") or "").strip()
    desc = str(parsed.get("desc") or "").strip()
    author = str(parsed.get("author") or "").strip()
    if not final_note_id or not any((title, desc, author)):
        raise RuntimeError(
            f"{source_label}中没有可识别的 Social_Media_Copilot 笔记结果。"
            "请在真实 Chrome 打开的目标帖子页确认插件已出现，必要时点击“复制笔记信息”后重试。"
        )
    source_url = str(parsed.get("source_url") or note_url or "").strip()
    card = OrderedDict()
    card["note_id"] = final_note_id
    card["title"] = title
    card["display_title"] = title
    card["desc"] = desc or title
    card["type"] = str(parsed.get("note_type") or "")
    card["time"] = str(parsed.get("time") or "")
    card["ip_location"] = str(parsed.get("ip_location") or "")
    card["user"] = OrderedDict([("nickname", author)])
    card["interact_info"] = OrderedDict([
        ("liked_count", str(parsed.get("liked_count") or "").strip()),
        ("collected_count", str(parsed.get("collected_count") or "").strip()),
        ("comment_count", str(parsed.get("comment_count") or "").strip()),
        ("share_count", str(parsed.get("share_count") or "").strip()),
    ])
    data = {
        "items": [
            {
                "id": final_note_id,
                "note_card": card,
            }
        ],
        "social_media_copilot_clipboard": parsed,
    }
    return data, source_url


def run_with_copilot_clipboard_fallback(
    args: argparse.Namespace,
    note_url: str,
    note_id: str,
    output: Path,
    summary_output: Optional[Path],
) -> Tuple[Path, Optional[Path]]:
    text = str(getattr(args, "copilot_clipboard_text", "") or "") or read_macos_clipboard_text()
    data, source_url = copilot_text_to_feed_data(text, note_url, note_id, "剪贴板")
    flat = build_flat_row(data, source_url, note_id, "social_media_copilot_clipboard")
    if not args.no_media_enrich:
        flat = enrich_flat_row("xhs", flat)
    export_csv(flat, output)
    if summary_output is not None:
        export_ten_fields_csv(flat, summary_output)
    print("XHS_SOCIAL_MEDIA_COPILOT_CLIPBOARD: 已使用插件复制结果写入 CSV。", flush=True)
    return output, summary_output


def run_with_copilot_cache_fallback(
    args: argparse.Namespace,
    note_url: str,
    note_id: str,
    output: Path,
    summary_output: Optional[Path],
) -> Tuple[Path, Optional[Path]]:
    cache_path = COPILOT_NOTE_CACHE_DIR / f"xhs_{note_id}.json"
    if not cache_path.exists():
        raise RuntimeError(
            f"没有找到 Social_Media_Copilot 本地缓存：{cache_path}。"
            "请先用真实 Chrome 打开目标帖子页，等待插件自动缓存，或点击“复制笔记信息”。"
        )
    text = cache_path.read_text(encoding="utf-8")
    data, source_url = copilot_text_to_feed_data(text, note_url, note_id, "插件本地缓存")
    flat = build_flat_row(data, source_url, note_id, "social_media_copilot_cache")
    if not args.no_media_enrich:
        flat = enrich_flat_row("xhs", flat)
    export_csv(flat, output)
    if summary_output is not None:
        export_ten_fields_csv(flat, summary_output)
    print(f"XHS_SOCIAL_MEDIA_COPILOT_CACHE: 已使用插件本地缓存写入 CSV：{cache_path}", flush=True)
    return output, summary_output


def osascript_live_browser_payload(app_name: str, url: str, timeout: float) -> Dict[str, Any]:
    app_literal = app_name.replace("\\", "\\\\").replace('"', '\\"')
    script = f"""
on run argv
  set targetUrl to item 1 of argv
  set jsPath to item 2 of argv
  set jsCode to read (POSIX file jsPath) as text
  tell application "{app_literal}"
    activate
    if (count of windows) = 0 then make new window
    set URL of active tab of front window to targetUrl
    delay 8
    set resultText to execute active tab of front window javascript jsCode
  end tell
  return resultText
end run
"""
    script_path = None
    js_path = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".applescript", delete=False) as handle:
            script_path = handle.name
            handle.write(script)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".js", delete=False) as handle:
            js_path = handle.name
            handle.write(LIVE_BROWSER_JS)
        result = subprocess.run(
            ["osascript", script_path, url, js_path],
            text=True,
            capture_output=True,
            timeout=max(timeout + 15, 30),
            check=False,
        )
    finally:
        for path in (script_path, js_path):
            if path:
                try:
                    Path(path).unlink(missing_ok=True)
                except Exception:
                    pass
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        if "AppleScript 执行 JavaScript 的功能已关闭" in detail or "Allow JavaScript from Apple Events" in detail:
            detail += "。请在浏览器菜单“查看 > 开发者”中开启“允许 Apple 事件中的 JavaScript”后重试。"
        raise RuntimeError(f"{app_name} 真实浏览器 DOM 兜底失败: {detail}")
    text = (result.stdout or "").strip()
    try:
        payload = json.loads(text)
    except Exception as exc:
        raise RuntimeError(f"{app_name} 真实浏览器 DOM 返回内容不是 JSON: {text[:300]}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"{app_name} 真实浏览器 DOM 返回结构异常。")
    return payload


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


def build_flat_row(
    data: Dict[str, Any],
    source_url: str,
    note_id: str,
    xsec_source: str,
) -> OrderedDict:
    flat = OrderedDict()
    flat["source_url"] = source_url
    flat["note_id"] = note_id
    flat["xsec_source"] = xsec_source
    for key, value in flatten_json(data).items():
        flat[key] = value
    flat["raw_json"] = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return flat


def export_csv(flat: OrderedDict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(flat.keys()))
        writer.writeheader()
        writer.writerow(flat)


def pick(row: Dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = row.get(key, "")
        if value not in (None, ""):
            return value
    return ""


def pick_by_suffix(row: Dict[str, Any], *suffixes: str, min_length: int = 1) -> Any:
    for suffix in suffixes:
        for key, value in row.items():
            if not key.endswith(suffix):
                continue
            text = str(value or "").strip()
            if len(text) >= min_length and text not in ("[]", "{}"):
                return value
    return ""


def pick_first_text(row: Dict[str, Any], exact_keys: Iterable[str], suffixes: Iterable[str] = ()) -> str:
    value = pick(row, *exact_keys)
    if value not in (None, ""):
        text = str(value).strip()
        if text and text not in ("[]", "{}"):
            return text
    value = pick_by_suffix(row, *suffixes, min_length=1)
    return str(value or "").strip()


def xhs_note_title(flat: Dict[str, Any]) -> str:
    return pick_first_text(
        flat,
        [
            "items.0.note_card.title",
            "items.0.note_card.display_title",
            "note_card.title",
            "note_card.display_title",
            "title",
            "display_title",
            "preview_title",
        ],
        [".note_card.title", ".note_card.display_title", ".title", ".display_title"],
    )


def xhs_note_body(flat: Dict[str, Any]) -> str:
    body = pick_first_text(
        flat,
        [
            "items.0.note_card.desc",
            "items.0.note_card.desc_v2",
            "items.0.note_card.content",
            "note_card.desc",
            "note_card.desc_v2",
            "note_card.content",
            "desc",
            "desc_v2",
            "content",
            "preview_text",
        ],
        [".note_card.desc", ".note_card.desc_v2", ".note_card.content", ".desc", ".desc_v2", ".content"],
    )
    if not body:
        body = xhs_note_title(flat)
    return append_media_text(
        body,
        str(pick(flat, "media_enrichment.image_ocr_text")),
        str(pick(flat, "media_enrichment.video_transcript")),
    )


def xhs_author_nickname(flat: Dict[str, Any]) -> str:
    value = pick_first_text(
        flat,
        [
            "items.0.note_card.user.nickname",
            "note_card.user.nickname",
            "user.nickname",
            "author.nickname",
            "preview_author",
        ],
        [".note_card.user.nickname", ".user.nickname", ".author.nickname"],
    )
    lines = [line.strip() for line in str(value or "").splitlines() if line.strip()]
    if not lines:
        return ""
    author = lines[0]
    author = re.sub(
        r"\s*/\s*(刚刚|\d+\s*(秒|分钟|小时|天|周|月|年)前|昨天|前天|今天.*)$",
        "",
        author,
    ).strip()
    return author


def xhs_note_id(flat: Dict[str, Any]) -> str:
    return pick_first_text(
        flat,
        ["note_id", "items.0.note_card.note_id", "items.0.id", "note_card.note_id", "id"],
        [".note_card.note_id"],
    )


def xhs_count(flat: Dict[str, Any], name: str) -> Any:
    exact = [
        f"items.0.note_card.interact_info.{name}",
        f"note_card.interact_info.{name}",
        f"interact_info.{name}",
        name,
    ]
    value = pick(flat, *exact)
    if value not in (None, ""):
        return value
    return pick_by_suffix(flat, f".interact_info.{name}", f".{name}")


def xhs_summary_row(flat: Dict[str, Any]) -> OrderedDict:
    out = OrderedDict()
    out["笔记ID"] = xhs_note_id(flat)
    out["博主昵称"] = xhs_author_nickname(flat)
    out["笔记链接"] = pick(flat, "source_url")
    out["笔记标题"] = xhs_note_title(flat)
    out["笔记内容"] = xhs_note_body(flat)
    out["点赞量"] = xhs_count(flat, "liked_count")
    out["收藏量"] = xhs_count(flat, "collected_count")
    out["评论量"] = xhs_count(flat, "comment_count")
    out["分享量"] = xhs_count(flat, "share_count")
    out["发布时间"] = format_time(pick(flat, "items.0.note_card.time", "note_card.time") or pick_by_suffix(flat, ".note_card.time", ".time"))
    return out


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


def export_ten_fields_csv(flat: Dict[str, Any], output_path: Path) -> None:
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
        writer.writerow(xhs_summary_row(flat))


def wait_for_login_cookie(page: CdpClient, initial_state: Dict[str, Any], timeout: float) -> Dict[str, Any]:
    state = initial_state
    if state.get("a1") or timeout <= 0:
        return state

    print(
        "未检测到小红书登录 Cookie。请在打开的浏览器中登录小红书，脚本会继续等待...",
        file=os.sys.stderr,
    )
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(1.0)
        state = page_state(page)
        if state.get("a1"):
            return state
    return state


def should_try_next_profile(exc: Exception) -> bool:
    text = str(exc)
    return any(
        token in text
        for token in (
            "Connection refused",
            "Errno 61",
            "Errno 611",
            "DevToolsActivePort",
            "Chrome DevTools websocket",
            "Chrome websocket handshake failed",
            "小红书页面仍停留",
            "候选入口都未进入",
            "未进入目标详情页",
            "404/300031",
            "300031",
            "300017",
            "website-login/error",
            "未检测到小红书 a1 登录 Cookie",
            "未能从浏览器读取小红书 Cookie",
            "Timed out waiting",
            "当前笔记暂时无法浏览",
        )
    )


def xhs_profile_attempt_args(args: argparse.Namespace) -> List[argparse.Namespace]:
    if args.use_default_profile and args.user_data_dir:
        raise ValueError("--use-default-profile cannot be combined with --user-data-dir")
    if args.user_data_dir or args.chrome or args.profile_source or not args.use_default_profile:
        return [argparse.Namespace(**vars(args))]
    if getattr(args, "profile_pool", "auto") == "off":
        return [argparse.Namespace(**vars(args))]

    first = browser_profile_pool.choose_profile(
        "xhs",
        purpose="note",
        profile_id=str(getattr(args, "profile_id", "") or ""),
        enabled=True,
    )
    if not first:
        return [argparse.Namespace(**vars(args))]

    profiles = [first]
    if not getattr(args, "profile_id", ""):
        for item in browser_profile_pool.available_profiles("xhs"):
            if item.get("id") != first.get("id"):
                profiles.append(item)

    attempts: List[argparse.Namespace] = []
    for item in profiles:
        attempt = argparse.Namespace(**vars(args))
        attempt.chrome = str(item.get("chrome_path") or "")
        attempt.profile_source = str(item.get("profile_source") or "")
        attempt.profile_directory = str(item.get("profile_directory") or "Default")
        attempt.selected_profile_id = str(item.get("id") or "")
        attempt.selected_profile_label = browser_profile_pool._mask_label(str(item.get("label") or item.get("id") or ""))
        attempts.append(attempt)
    return attempts


def xhs_direct_profile_attempt_args(args: argparse.Namespace) -> List[argparse.Namespace]:
    if args.user_data_dir or args.chrome or args.profile_source or not args.use_default_profile:
        return []
    if getattr(args, "profile_pool", "auto") == "off":
        return []
    profiles = browser_profile_pool.available_profiles("xhs")
    # The user's Chrome can currently open xhs /explore detail pages, so prefer Chrome for direct profile fallback.
    profiles.sort(key=lambda item: 0 if str(item.get("browser") or "").lower() == "chrome" else 1)
    attempts: List[argparse.Namespace] = []
    for item in profiles:
        attempt = argparse.Namespace(**vars(args))
        attempt.chrome = str(item.get("chrome_path") or "")
        attempt.profile_source = str(item.get("profile_source") or "")
        attempt.profile_directory = str(item.get("profile_directory") or "Default")
        attempt.selected_profile_id = str(item.get("id") or "")
        attempt.selected_profile_label = browser_profile_pool._mask_label(str(item.get("label") or item.get("id") or ""))
        attempt.direct_default_profile = True
        attempts.append(attempt)
    return attempts


def run_with_browser_profile(
    args: argparse.Namespace,
    note_url: str,
    note_id: str,
    xsec_source: str,
    xsec_token: str,
    output: Path,
    summary_output: Optional[Path],
) -> Tuple[Path, Optional[Path]]:
    chrome_path = find_chrome(args.chrome)
    direct_default_profile = bool(getattr(args, "direct_default_profile", False))
    if getattr(args, "selected_profile_id", ""):
        mode = "direct" if direct_default_profile else "clone"
        print(
            f"BROWSER_PROFILE: platform=xhs purpose=note "
            f"profile={getattr(args, 'selected_profile_label', args.selected_profile_id)} "
            f"profile_directory={args.profile_directory} mode={mode}",
            flush=True,
        )

    owns_user_dir = args.user_data_dir is None
    profile_directory = args.profile_directory
    if args.use_default_profile:
        source_root = Path(args.profile_source) if args.profile_source else default_browser_user_data_dir(chrome_path)
        if direct_default_profile:
            user_dir = source_root
            owns_user_dir = False
        else:
            user_dir = Path(tempfile.mkdtemp(prefix="xhs-profile-clone-"))
            owns_user_dir = True
            clone_browser_profile(source_root, profile_directory, user_dir)
    else:
        user_dir = Path(args.user_data_dir) if args.user_data_dir else Path(tempfile.mkdtemp(prefix="xhs-cdp-"))

    launch_started = time.time()
    proc = launch_chrome(chrome_path, user_dir, headless=not args.headed, profile_directory=profile_directory)
    page: Optional[CdpClient] = None
    try:
        port, ws_path = wait_for_debug_port(user_dir, args.browser_timeout, since=launch_started)
        page = make_page_client(port, ws_path, args.browser_timeout)
        current_note_url = note_url
        current_xsec_source = xsec_source
        current_xsec_token = xsec_token
        access_candidates = candidate_note_urls(current_note_url, note_id, current_xsec_source, current_xsec_token)
        current_note_url = wait_for_note_page(page, access_candidates, args.browser_timeout, note_id)
        state = wait_for_login_cookie(page, page_state(page), args.login_timeout)
        state["cookie_header"] = browser_cookie_header(page)
        if not state.get("a1"):
            raise RuntimeError(
                "未检测到小红书 a1 登录 Cookie，接口通常会拒绝请求。"
                "请先登录小红书后重试，或使用 --use-default-profile 复用本机 Chrome 登录态，"
                "也可以使用 --headed --login-timeout 180 手动登录。"
            )
        if not state.get("cookie_header"):
            raise RuntimeError("未能从浏览器读取小红书 Cookie，请登录后重试。")
        access = resolve_note_access_from_page(page, note_id, current_xsec_source, current_xsec_token, args.browser_timeout)
        current_xsec_source = access.get("xsec_source") or current_xsec_source or "pc_search"
        current_xsec_token = access.get("xsec_token") or current_xsec_token
        source_url = access.get("href") or current_note_url
        if current_xsec_token and "xsec_token=" not in source_url:
            source_url = with_url_query(source_url, xsec_token=current_xsec_token, xsec_source=current_xsec_source)
        body = build_body(note_id, current_xsec_source, current_xsec_token)
        try:
            data = post_feed(page, state, body, timeout=args.http_timeout)
        except Exception as exc:
            if not should_use_page_fallback(exc):
                raise
            print(
                "小红书 API 返回当前笔记暂时无法浏览，改用已打开页面 DOM 兜底提取。"
                f" 原始错误：{exc}",
                flush=True,
            )
            data = page_fallback_payload(page, note_id, source_url)
        if not feed_data_has_note(data):
            print("小红书 API 返回空笔记数据，改用已打开页面 DOM 兜底提取。", flush=True)
            data = page_fallback_payload(page, note_id, source_url)
        flat = build_flat_row(data, source_url, note_id, current_xsec_source)
        if not args.no_media_enrich:
            flat = enrich_flat_row("xhs", flat)
        export_csv(flat, output)
        if summary_output is not None:
            export_ten_fields_csv(flat, summary_output)
        return output, summary_output
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


def run_with_live_browser_fallback(
    args: argparse.Namespace,
    note_url: str,
    note_id: str,
    xsec_source: str,
    xsec_token: str,
    output: Path,
    summary_output: Optional[Path],
) -> Tuple[Path, Optional[Path]]:
    if os.name != "posix" or not os.uname().sysname == "Darwin":
        raise RuntimeError("真实浏览器 DOM 兜底目前仅支持 macOS。")
    apps = ["Google Chrome", "Microsoft Edge"]
    live_urls = candidate_note_urls(note_url, note_id, xsec_source, xsec_token)
    if not xsec_token:
        explore_url = f"https://www.xiaohongshu.com/explore/{note_id}?xsec_source={urllib.parse.quote(xsec_source or 'pc_search')}"
        live_urls = [explore_url] + [item for item in live_urls if item != explore_url]
    errors: List[str] = []
    for app_name in apps:
        for url_index, live_url in enumerate(live_urls, start=1):
            try:
                print(
                    f"XHS_LIVE_BROWSER_FALLBACK: 尝试使用真实浏览器 {app_name} "
                    f"抽取 DOM，候选 {url_index}/{len(live_urls)}：{live_url}",
                    flush=True,
                )
                payload = osascript_live_browser_payload(app_name, live_url, args.browser_timeout)
                data = payload_to_feed_data(payload, note_id)
                source_url = str(payload.get("href") or live_url)
                flat = build_flat_row(data, source_url, note_id, str(payload.get("xsec_source") or "live_browser"))
                if not args.no_media_enrich:
                    flat = enrich_flat_row("xhs", flat)
                export_csv(flat, output)
                if summary_output is not None:
                    export_ten_fields_csv(flat, summary_output)
                return output, summary_output
            except Exception as exc:
                message = str(exc)
                errors.append(f"{app_name} {live_url}: {message}")
                print(f"XHS_LIVE_BROWSER_FALLBACK_FAILED: {app_name}: {message}", flush=True)
                if "允许 Apple 事件中的 JavaScript" in message or "AppleScript is turned off" in message:
                    print(
                        f"XHS_LIVE_BROWSER_FALLBACK_STOP: {app_name} 未开启 AppleScript JavaScript 权限，"
                        "跳过该浏览器剩余候选入口。",
                        flush=True,
                    )
                    break
    raise RuntimeError("所有小红书真实浏览器 DOM 兜底都失败：" + " | ".join(errors))


def run(args: argparse.Namespace) -> Tuple[Path, Optional[Path]]:
    note_url = extract_note_url(args.url)
    note_id, xsec_source, xsec_token = parse_note_url(note_url)
    parsed_note_url = urllib.parse.urlparse(note_url)
    if not xsec_token:
        if parsed_note_url.netloc.endswith("xiaohongshu.com"):
            note_url = canonical_pc_search_explore_url(note_id)
            xsec_source = "pc_search"
            print(
                f"小红书裸链接已规范化为可访问优先入口：{note_url}",
                flush=True,
            )
    output = Path(args.output) if args.output else XHS_ORIGIN_CSV
    summary_output = None if args.no_summary else (
        Path(args.summary_output) if args.summary_output else XHS_SUMMARY_CSV
    )
    if getattr(args, "from_copilot_clipboard", False):
        return run_with_copilot_clipboard_fallback(args, note_url, note_id, output, summary_output)
    if getattr(args, "from_copilot_cache", False):
        return run_with_copilot_cache_fallback(args, note_url, note_id, output, summary_output)

    attempts = xhs_profile_attempt_args(args)
    errors: List[str] = []
    last_profile_error: Optional[Exception] = None
    for index, attempt in enumerate(attempts, start=1):
        try:
            if len(attempts) > 1:
                print(f"XHS_PROFILE_ATTEMPT: {index}/{len(attempts)}", flush=True)
            return run_with_browser_profile(attempt, note_url, note_id, xsec_source, xsec_token, output, summary_output)
        except Exception as exc:
            last_profile_error = exc
            message = str(exc)
            errors.append(f"{getattr(attempt, 'selected_profile_label', getattr(attempt, 'selected_profile_id', 'default'))}: {message}")
            if any(token in message for token in ("300013", "Too many requests", "安全限制")):
                browser_profile_pool.mark_profile_blocked(getattr(attempt, "selected_profile_id", ""), message)
            if index >= len(attempts):
                break
            if not should_try_next_profile(exc):
                raise
            print(
                f"XHS_PROFILE_FALLBACK: 当前浏览器登录态失败，自动切换下一个账号。原因：{message}",
                flush=True,
            )

    if last_profile_error and should_try_next_profile(last_profile_error) and getattr(args, "direct_profile_fallback", True):
        direct_attempts = xhs_direct_profile_attempt_args(args)
        for index, attempt in enumerate(direct_attempts, start=1):
            try:
                print(
                    f"XHS_DIRECT_PROFILE_FALLBACK: 尝试真实浏览器 Profile {index}/{len(direct_attempts)}。"
                    "如果 Chrome/Edge 已经打开，请先退出浏览器后重试。",
                    flush=True,
                )
                return run_with_browser_profile(attempt, note_url, note_id, xsec_source, xsec_token, output, summary_output)
            except Exception as exc:
                message = str(exc)
                errors.append(
                    f"direct:{getattr(attempt, 'selected_profile_label', getattr(attempt, 'selected_profile_id', 'default'))}: {message}"
                )
                if any(token in message for token in ("300013", "Too many requests", "安全限制")):
                    browser_profile_pool.mark_profile_blocked(getattr(attempt, "selected_profile_id", ""), message)
                print(
                    f"XHS_DIRECT_PROFILE_FALLBACK_FAILED: {getattr(attempt, 'selected_profile_label', 'direct')}：{message}",
                    flush=True,
                )
                if not should_try_next_profile(exc):
                    raise

    can_try_live = bool(getattr(args, "live_browser_fallback", True))
    if can_try_live and last_profile_error and should_try_next_profile(last_profile_error):
        print("XHS_PROFILE_FALLBACK: CDP 登录态均失败，转入真实浏览器 DOM 兜底。", flush=True)
        try:
            return run_with_live_browser_fallback(args, note_url, note_id, xsec_source, xsec_token, output, summary_output)
        except Exception as exc:
            errors.append(f"live_browser: {exc}")
            if getattr(args, "copilot_cache_fallback", True):
                print(
                    "XHS_SOCIAL_MEDIA_COPILOT_CACHE: 自动化浏览器读取失败，尝试读取插件自动缓存。",
                    flush=True,
                )
                try:
                    return run_with_copilot_cache_fallback(args, note_url, note_id, output, summary_output)
                except Exception as cache_exc:
                    errors.append(f"copilot_cache: {cache_exc}")
            if getattr(args, "copilot_clipboard_fallback", True):
                print(
                    "XHS_SOCIAL_MEDIA_COPILOT_CLIPBOARD: 自动化浏览器读取失败，尝试读取剪贴板中的插件复制结果。",
                    flush=True,
                )
                return run_with_copilot_clipboard_fallback(args, note_url, note_id, output, summary_output)
            raise
    if getattr(args, "copilot_cache_fallback", True):
        print(
            "XHS_SOCIAL_MEDIA_COPILOT_CACHE: 浏览器/API 读取失败，尝试读取插件自动缓存。",
            flush=True,
        )
        try:
            return run_with_copilot_cache_fallback(args, note_url, note_id, output, summary_output)
        except Exception as cache_exc:
            errors.append(f"copilot_cache: {cache_exc}")
    if getattr(args, "copilot_clipboard_fallback", True):
        print(
            "XHS_SOCIAL_MEDIA_COPILOT_CLIPBOARD: 浏览器/API 读取失败，尝试读取剪贴板中的插件复制结果。",
            flush=True,
        )
        return run_with_copilot_clipboard_fallback(args, note_url, note_id, output, summary_output)
    if last_profile_error:
        raise last_profile_error
    raise RuntimeError("所有小红书浏览器登录态都失败：" + " | ".join(errors))


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Export Xiaohongshu note API fields to CSV.")
    parser.add_argument("url", nargs="?", default=DEFAULT_URL, help="Xiaohongshu note/share URL.")
    parser.add_argument("-o", "--output", help="Full-field CSV output path. Defaults to Pipeline/xhs_origin_data.csv.")
    parser.add_argument(
        "--summary-output",
        help="10-field CSV output path. Defaults to Pipeline/xhs_note_10_fields.csv.",
    )
    parser.add_argument("--no-summary", action="store_true", help="Do not write the 10-field summary CSV.")
    parser.add_argument("--no-media-enrich", action="store_true", help="Skip local image OCR and video speech transcription.")
    parser.add_argument("--chrome", help="Chrome/Chromium executable path.")
    parser.add_argument("--user-data-dir", help="Chrome user-data directory, useful if the API requires login cookies.")
    parser.add_argument(
        "--use-default-profile",
        action="store_true",
        help="Clone the default Chrome/Edge profile into a temporary profile to reuse Xiaohongshu login cookies.",
    )
    parser.add_argument(
        "--profile-source",
        help="Source browser user-data directory to clone when --use-default-profile is set.",
    )
    parser.add_argument(
        "--profile-directory",
        default="Default",
        help="Chrome profile directory name, for example Default or 'Profile 1'.",
    )
    parser.add_argument("--headed", action="store_true", help="Show Chrome instead of running headless.")
    parser.add_argument("--keep-browser-open", action="store_true", help="Do not close Chrome when finished.")
    parser.add_argument(
        "--login-timeout",
        type=float,
        default=0.0,
        help="Seconds to wait for manual Xiaohongshu login in the opened browser.",
    )
    parser.add_argument("--browser-timeout", type=float, default=45.0, help="Seconds to wait for Chrome/page signer.")
    parser.add_argument("--http-timeout", type=float, default=30.0, help="Seconds to wait for the API request.")
    parser.add_argument(
        "--no-live-browser-fallback",
        dest="live_browser_fallback",
        action="store_false",
        default=True,
        help="Disable macOS real Chrome/Edge DOM fallback after cloned profiles fail.",
    )
    parser.add_argument(
        "--no-direct-profile-fallback",
        dest="direct_profile_fallback",
        action="store_false",
        default=True,
        help="Disable direct CDP fallback that launches the real Chrome/Edge profile after cloned profiles fail.",
    )
    parser.add_argument(
        "--from-copilot-clipboard",
        action="store_true",
        help="Read Social_Media_Copilot copied note info from the clipboard and export it directly.",
    )
    parser.add_argument(
        "--from-copilot-cache",
        action="store_true",
        help="Read Social_Media_Copilot note cache saved by the local Pipeline GUI and export it directly.",
    )
    parser.add_argument(
        "--no-copilot-cache-fallback",
        dest="copilot_cache_fallback",
        action="store_false",
        default=True,
        help="Disable fallback that reads Social_Media_Copilot note cache saved by the local Pipeline GUI.",
    )
    parser.add_argument(
        "--no-copilot-clipboard-fallback",
        dest="copilot_clipboard_fallback",
        action="store_false",
        default=True,
        help="Disable final fallback that reads Social_Media_Copilot copied note info from the clipboard.",
    )
    parser.add_argument(
        "--copilot-clipboard-text",
        default="",
        help=argparse.SUPPRESS,
    )
    browser_profile_pool.add_profile_pool_args(parser)
    args = parser.parse_args(argv)

    try:
        output, summary_output = run(args)
    except Exception as exc:
        if any(token in str(exc) for token in ("300013", "Too many requests", "安全限制")):
            browser_profile_pool.mark_profile_blocked(getattr(args, "selected_profile_id", ""), str(exc))
        print(f"ERROR: {exc}", file=os.sys.stderr)
        return 1
    print(f"Full CSV exported: {output}")
    if summary_output is not None:
        print(f"10-field CSV exported: {summary_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
