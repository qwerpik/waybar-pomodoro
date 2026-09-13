"""
Configuration management for waybar-pomodoro.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional


def get_default_config_dir() -> Path:
    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config:
        return Path(xdg_config) / "waybar-pomodoro"
    return Path.home() / ".config" / "waybar-pomodoro"


def get_default_cache_dir() -> Path:
    xdg_cache = os.environ.get("XDG_CACHE_HOME")
    if xdg_cache:
        return Path(xdg_cache) / "waybar-pomodoro"
    return Path.home() / ".cache" / "waybar-pomodoro"


def get_default_data_dir() -> Path:
    xdg_data = os.environ.get("XDG_DATA_HOME")
    if xdg_data:
        return Path(xdg_data) / "waybar-pomodoro"
    return Path.home() / ".local" / "share" / "waybar-pomodoro"


@dataclass
class PomodoroConfig:
    work_duration: int = 30  # minutes
    short_break_duration: int = 5  # minutes
    long_break_duration: int = 15  # minutes
    cycles_before_long_break: int = 4

    # Display style: "minimal" (numbers only), "icon" (icon + time), "custom"
    style: str = "minimal"

    # Custom format strings (supports {time}, {icon}, {cycle}, {phase})
    format_work: str = "{time}"
    format_short_break: str = "{time}"
    format_long_break: str = "{time}"
    format_paused: str = "⏸ {time}"
    format_idle: str = "{time}"

    # Icons for "icon" style or custom format
    icon_work: str = "🍅"
    icon_short_break: str = "☕"
    icon_long_break: str = "🌴"
    icon_paused: str = "⏸"
    icon_idle: str = "⏱"

    # Sound & notifications
    sound_enabled: bool = True
    sound_work_end: str = "/usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga"
    sound_break_end: str = "/usr/share/sounds/freedesktop/stereo/complete.oga"
    notification_enabled: bool = True
    notification_urgency_work_end: str = "critical"
    notification_urgency_break_end: str = "normal"
    notification_timeout: int = 10000  # milliseconds (10s), 0 = default daemon timeout
    notification_category: str = "timer"

    # Auto-start behavior
    auto_start_break: bool = True
    auto_start_work: bool = True

    # Waybar integration
    waybar_signal: int = 8  # SIGRTMIN+8

    # File locations
    state_file: str = field(default_factory=lambda: str(get_default_cache_dir() / "state.json"))
    stats_file: str = field(default_factory=lambda: str(get_default_data_dir() / "stats.json"))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PomodoroConfig:
        instance = cls()
        int_fields = {
            "work_duration": (1, 1440),
            "short_break_duration": (1, 360),
            "long_break_duration": (1, 360),
            "cycles_before_long_break": (1, 100),
            "waybar_signal": (0, 30),
            "notification_timeout": (0, 300000),
        }
        bool_fields = {
            "sound_enabled",
            "notification_enabled",
            "auto_start_break",
            "auto_start_work",
        }
        str_fields = {
            "style",
            "format_work",
            "format_short_break",
            "format_long_break",
            "format_paused",
            "format_idle",
            "icon_work",
            "icon_short_break",
            "icon_long_break",
            "icon_paused",
            "icon_idle",
            "sound_work_end",
            "sound_break_end",
            "notification_urgency_work_end",
            "notification_urgency_break_end",
            "notification_category",
            "state_file",
            "stats_file",
        }

        for k, v in data.items():
            if k in int_fields:
                min_val, max_val = int_fields[k]
                try:
                    val = int(v)
                    setattr(instance, k, max(min_val, min(max_val, val)))
                except (ValueError, TypeError):
                    pass
            elif k in bool_fields:
                if isinstance(v, bool):
                    setattr(instance, k, v)
                elif isinstance(v, str):
                    setattr(instance, k, v.lower() in ("true", "1", "yes"))
            elif k in str_fields and isinstance(v, str):
                setattr(instance, k, v)

        return instance


def load_config(config_path: Optional[Path] = None) -> PomodoroConfig:
    """
    Loads config from the given path or the default ~/.config/waybar-pomodoro/config.json.
    Falls back to default config if file does not exist or has invalid JSON.
    """
    target = config_path or (get_default_config_dir() / "config.json")
    if target.is_file():
        try:
            with open(target, "r", encoding="utf-8") as f:
                content = json.load(f)
                if isinstance(content, dict):
                    return PomodoroConfig.from_dict(content)
        except Exception:
            pass
    return PomodoroConfig()


def save_config(config: PomodoroConfig, config_path: Optional[Path] = None) -> Path:
    """
    Saves configuration atomically to JSON file.
    """
    target = config_path or (get_default_config_dir() / "config.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(target.parent, 0o700)
    except OSError:
        pass

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            dir=target.parent,
            encoding="utf-8",
            delete=False,
            prefix=f".{target.name}.",
            suffix=".tmp",
        ) as tmp:
            temp_path = Path(tmp.name)
            os.chmod(tmp.fileno(), 0o600)
            json.dump(config.to_dict(), tmp, indent=4)
            tmp.flush()
            os.fsync(tmp.fileno())

        temp_path.replace(target)
        return target
    except Exception:
        if temp_path and temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
        raise
