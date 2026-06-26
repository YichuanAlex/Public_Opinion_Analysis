#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Optional

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows fallback has no fcntl.
    fcntl = None

from pipeline_paths import PIPELINE_DIR


POOL_CONFIG = PIPELINE_DIR / "browser_profile_pool.json"
POOL_STATE = PIPELINE_DIR / "gui_exports" / "browser_profile_pool_state.json"
POOL_LOCK = PIPELINE_DIR / "gui_exports" / "browser_profile_pool.lock"

MAC_CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
MAC_EDGE = "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"


def _home_path(*parts: str) -> str:
    return str(Path.home().joinpath(*parts))


DEFAULT_CONFIG: dict[str, Any] = {
    "profiles": [
        {
            "id": "chrome_19116411259",
            "label": "Chrome 19116411259",
            "browser": "chrome",
            "chrome_path": MAC_CHROME,
            "profile_source": _home_path("Library", "Application Support", "Google", "Chrome"),
            "profile_directory": "Default",
            "platforms": ["xhs", "dy"],
            "enabled": True,
        },
        {
            "id": "edge_17730297792",
            "label": "Edge 17730297792",
            "browser": "edge",
            "chrome_path": MAC_EDGE,
            "profile_source": _home_path("Library", "Application Support", "Microsoft Edge"),
            "profile_directory": "Default",
            "platforms": ["xhs", "dy"],
            "enabled": True,
        },
    ],
    "min_interval_seconds": 8,
    "blocked_cooldown_seconds": 1800,
}


@contextmanager
def file_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as handle:
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def ensure_config() -> None:
    if POOL_CONFIG.exists():
        return
    POOL_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    POOL_CONFIG.write_text(json.dumps(DEFAULT_CONFIG, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_json(path: Path, default: Any) -> Any:
    if not path.exists() or path.stat().st_size == 0:
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def load_config() -> dict[str, Any]:
    ensure_config()
    payload = load_json(POOL_CONFIG, DEFAULT_CONFIG)
    if not isinstance(payload, dict):
        payload = DEFAULT_CONFIG
    payload.setdefault("profiles", [])
    payload.setdefault("min_interval_seconds", DEFAULT_CONFIG["min_interval_seconds"])
    payload.setdefault("blocked_cooldown_seconds", DEFAULT_CONFIG["blocked_cooldown_seconds"])
    return payload


def available_profiles(platform: str, config: Optional[dict[str, Any]] = None) -> list[dict[str, Any]]:
    config = config or load_config()
    profiles = []
    for item in config.get("profiles") or []:
        if not item.get("enabled", True):
            continue
        if platform and platform not in (item.get("platforms") or []):
            continue
        chrome_path = str(item.get("chrome_path") or "")
        profile_source = str(item.get("profile_source") or "")
        profile_directory = str(item.get("profile_directory") or "Default")
        if not chrome_path or not Path(chrome_path).exists():
            continue
        if not profile_source or not (Path(profile_source) / profile_directory).is_dir():
            continue
        profiles.append(dict(item))
    return profiles


def _mask_label(value: str) -> str:
    text = str(value or "")
    return text.replace("19116411259", "191****1259").replace("17730297792", "177****7792")


def choose_profile(
    platform: str,
    purpose: str = "crawler",
    profile_id: str = "",
    enabled: bool = True,
) -> Optional[dict[str, Any]]:
    if not enabled:
        return None
    config = load_config()
    profiles = available_profiles(platform, config)
    if not profiles:
        return None

    now = time.time()
    min_interval = float(config.get("min_interval_seconds") or 0)
    blocked_cooldown = float(config.get("blocked_cooldown_seconds") or 0)
    with file_lock(POOL_LOCK):
        state = load_json(POOL_STATE, {})
        if not isinstance(state, dict):
            state = {}
        platform_state = state.setdefault(platform, {})
        profile_state = state.setdefault("profiles", {})

        if profile_id:
            selected = next((item for item in profiles if item.get("id") == profile_id), None)
            if selected is None:
                raise ValueError(f"浏览器账号池里没有可用 profile: {profile_id}")
        else:
            last_index = int(platform_state.get("last_index", -1))
            selected = None
            best_wait = None
            for offset in range(1, len(profiles) + 1):
                index = (last_index + offset) % len(profiles)
                candidate = profiles[index]
                item_state = profile_state.get(candidate["id"], {})
                blocked_until = float(item_state.get("blocked_until") or 0)
                last_used = float(item_state.get("last_used") or 0)
                wait_seconds = max(blocked_until - now, last_used + min_interval - now, 0)
                if wait_seconds <= 0:
                    selected = candidate
                    platform_state["last_index"] = index
                    break
                if best_wait is None or wait_seconds < best_wait[0]:
                    best_wait = (wait_seconds, index, candidate)
            if selected is None and best_wait is not None:
                wait_seconds, index, selected = best_wait
                if wait_seconds > 0:
                    # This is a safety brake, not a throughput booster.
                    time.sleep(min(wait_seconds, 60))
                platform_state["last_index"] = index

        item_state = profile_state.setdefault(selected["id"], {})
        item_state["last_used"] = time.time()
        item_state["last_platform"] = platform
        item_state["last_purpose"] = purpose
        item_state.setdefault("blocked_until", 0)
        item_state["use_count"] = int(item_state.get("use_count") or 0) + 1
        state["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        write_json(POOL_STATE, state)

    selected["profile_label_masked"] = _mask_label(str(selected.get("label") or selected.get("id") or ""))
    selected["min_interval_seconds"] = min_interval
    selected["blocked_cooldown_seconds"] = blocked_cooldown
    return selected


def mark_profile_blocked(profile_id: str, reason: str = "") -> None:
    if not profile_id:
        return
    config = load_config()
    cooldown = float(config.get("blocked_cooldown_seconds") or DEFAULT_CONFIG["blocked_cooldown_seconds"])
    with file_lock(POOL_LOCK):
        state = load_json(POOL_STATE, {})
        if not isinstance(state, dict):
            state = {}
        profile_state = state.setdefault("profiles", {})
        item_state = profile_state.setdefault(profile_id, {})
        item_state["blocked_until"] = time.time() + cooldown
        item_state["blocked_reason"] = str(reason or "")[:500]
        item_state["blocked_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        write_json(POOL_STATE, state)


def apply_profile_to_args(args: Any, platform: str, purpose: str = "crawler") -> Optional[dict[str, Any]]:
    if getattr(args, "user_data_dir", None):
        return None
    if getattr(args, "chrome", None) or getattr(args, "profile_source", None):
        return None
    if not getattr(args, "use_default_profile", False):
        return None
    pool_mode = str(getattr(args, "profile_pool", os.environ.get("PIPELINE_PROFILE_POOL", "auto")) or "auto")
    if pool_mode == "off":
        return None
    profile_id = str(getattr(args, "profile_id", "") or "")
    selected = choose_profile(platform, purpose=purpose, profile_id=profile_id, enabled=True)
    if not selected:
        return None
    args.chrome = str(selected.get("chrome_path") or "")
    args.profile_source = str(selected.get("profile_source") or "")
    args.profile_directory = str(selected.get("profile_directory") or "Default")
    setattr(args, "selected_profile_id", selected.get("id") or "")
    print(
        f"BROWSER_PROFILE: platform={platform} purpose={purpose} "
        f"profile={selected.get('profile_label_masked')} browser={selected.get('browser')} "
        f"profile_directory={args.profile_directory}",
        flush=True,
    )
    return selected


def add_profile_pool_args(parser: Any) -> None:
    parser.add_argument(
        "--profile-pool",
        choices=["auto", "off"],
        default=os.environ.get("PIPELINE_PROFILE_POOL", "auto"),
        help="Use Pipeline/browser_profile_pool.json to rotate logged-in Chrome/Edge profiles.",
    )
    parser.add_argument("--profile-id", default="", help="Force one browser profile id from browser_profile_pool.json.")
