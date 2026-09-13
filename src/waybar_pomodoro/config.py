"""
Configuration management for waybar-pomodoro.
"""

from __future__ import annotations

import json
import os
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
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)


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
    Saves configuration to JSON file.
    """
    target = config_path or (get_default_config_dir() / "config.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w", encoding="utf-8") as f:
        json.dump(config.to_dict(), f, indent=4)
    return target
