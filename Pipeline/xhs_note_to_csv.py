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


DEFAULT_URL = (
    "https://www.xiaohongshu.com/discovery/item/"
    "6a2ea3b0000000001702f2ba?source=webshare&xhsshare=pc_web"
    "&xsec_token=ABCyGjHjOjvsO5Z03mhaZqEKNsrb30SFx940snY3WXPaY="
    "&xsec_source=pc_share"
)

API_BASE = "https://edith.xiaohongshu.com"
API_PATH = "/api/sns/web/v1/feed"

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


def parse_note_url(url: str) -> Tuple[str, str, str]:
    parsed = urllib.parse.urlparse(url)
    note_id = parsed.path.rstrip("/").split("/")[-1]
    if len(note_id) != 24 or not note_id.isalnum():
        raise ValueError(f"Invalid Xiaohongshu note id in URL: {note_id}")
    params = urllib.parse.parse_qs(parsed.query)
    xsec_token = (params.get("xsec_token") or [""])[0]
    xsec_source = (params.get("xsec_source") or [""])[0]
    if not xsec_token:
        raise ValueError("URL is missing xsec_token")
    if not xsec_source:
        raise ValueError("URL is missing xsec_source")
    return note_id, xsec_source, xsec_token


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
    ):
        copy_if_exists(source_profile / filename, dest_profile / filename)

    for dirname in ("Network", "Local Storage", "Session Storage"):
        copy_tree_if_exists(
            source_profile / dirname,
            dest_profile / dirname,
            ignore_names=["Cache", "Code Cache", "GPUCache", "DawnCache", "GrShaderCache"],
        )


def wait_for_debug_port(user_data_dir: Path, timeout: float) -> Tuple[int, str]:
    port_file = user_data_dir / "DevToolsActivePort"
    deadline = time.time() + timeout
    while time.time() < deadline:
        if port_file.exists():
            lines = port_file.read_text(encoding="utf-8").splitlines()
            if len(lines) >= 2:
                return int(lines[0]), lines[1]
        time.sleep(0.1)
    raise TimeoutError("Timed out waiting for Chrome DevToolsActivePort")


def http_json(url: str, timeout: float = 30.0) -> Any:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def make_page_client(port: int, browser_ws_path: str, timeout: float) -> CdpClient:
    browser = CdpClient(f"ws://127.0.0.1:{port}{browser_ws_path}", timeout=timeout)
    try:
        target = browser.call("Target.createTarget", {"url": "about:blank"})
        target_id = target["targetId"]
    finally:
        browser.close()

    deadline = time.time() + timeout
    while time.time() < deadline:
        targets = http_json(f"http://127.0.0.1:{port}/json/list", timeout=timeout)
        for item in targets:
            if item.get("id") == target_id and item.get("webSocketDebuggerUrl"):
                return CdpClient(item["webSocketDebuggerUrl"], timeout=timeout)
        time.sleep(0.1)
    raise TimeoutError("Timed out finding Chrome page target")


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
        writer.writerow({
            "笔记ID": pick(flat, "note_id", "items.0.note_card.note_id", "items.0.id"),
            "博主昵称": pick(flat, "items.0.note_card.user.nickname"),
            "笔记链接": pick(flat, "source_url"),
            "笔记标题": pick(flat, "items.0.note_card.title"),
            "笔记内容": pick(flat, "items.0.note_card.desc"),
            "点赞量": pick(flat, "items.0.note_card.interact_info.liked_count"),
            "收藏量": pick(flat, "items.0.note_card.interact_info.collected_count"),
            "评论量": pick(flat, "items.0.note_card.interact_info.comment_count"),
            "分享量": pick(flat, "items.0.note_card.interact_info.share_count"),
            "发布时间": format_time(pick(flat, "items.0.note_card.time")),
        })


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


def run(args: argparse.Namespace) -> Tuple[Path, Optional[Path]]:
    note_id, xsec_source, xsec_token = parse_note_url(args.url)
    output = Path(args.output) if args.output else Path(__file__).with_name("origin_data.csv")
    summary_output = None if args.no_summary else (
        Path(args.summary_output) if args.summary_output else Path(__file__).with_name("xhs_note_10_fields.csv")
    )

    chrome_path = find_chrome(args.chrome)
    if args.use_default_profile and args.user_data_dir:
        raise ValueError("--use-default-profile cannot be combined with --user-data-dir")

    owns_user_dir = args.user_data_dir is None
    profile_directory = args.profile_directory
    if args.use_default_profile:
        source_root = Path(args.profile_source) if args.profile_source else default_browser_user_data_dir(chrome_path)
        user_dir = Path(tempfile.mkdtemp(prefix="xhs-profile-clone-"))
        owns_user_dir = True
        clone_browser_profile(source_root, profile_directory, user_dir)
    else:
        user_dir = Path(args.user_data_dir) if args.user_data_dir else Path(tempfile.mkdtemp(prefix="xhs-cdp-"))

    proc = launch_chrome(chrome_path, user_dir, headless=not args.headed, profile_directory=profile_directory)
    page: Optional[CdpClient] = None
    try:
        port, ws_path = wait_for_debug_port(user_dir, args.browser_timeout)
        page = make_page_client(port, ws_path, args.browser_timeout)
        wait_for_page_signer(page, args.url, args.browser_timeout)
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
        body = build_body(note_id, xsec_source, xsec_token)
        data = post_feed(page, state, body, timeout=args.http_timeout)
        flat = build_flat_row(data, args.url, note_id, xsec_source)
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


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Export Xiaohongshu note API fields to CSV.")
    parser.add_argument("url", nargs="?", default=DEFAULT_URL, help="Xiaohongshu note/share URL.")
    parser.add_argument("-o", "--output", help="Full-field CSV output path. Defaults to Pipeline/origin_data.csv.")
    parser.add_argument(
        "--summary-output",
        help="10-field CSV output path. Defaults to Pipeline/xhs_note_10_fields.csv.",
    )
    parser.add_argument("--no-summary", action="store_true", help="Do not write the 10-field summary CSV.")
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
