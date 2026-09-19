"""
Visual and lifecycle event hooks for waybar-pomodoro.
Executes non-blocking user scripts on timer transitions.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

SUPPORTED_EVENTS = (
    "work_start",
    "break_start",
    "pause",
    "resume",
    "reset",
    "complete",
)


def find_hook_scripts(hooks_dir: Path, event: str) -> List[Path]:
    """
    Finds matching executable hook scripts in the hooks directory for an event.
    Accepts: 'on_<event>.sh', 'on_<event>', '<event>.sh', '<event>'.
    """
    if not hooks_dir.is_dir():
        return []

    candidates = [
        f"on_{event}.sh",
        f"on_{event}",
        f"{event}.sh",
        event,
    ]

    found: List[Path] = []
    for cand in candidates:
        path = hooks_dir / cand
        if path.is_file() and os.access(path, os.X_OK):
            found.append(path)
    return found


def dispatch_hook(
    event: str,
    state: Dict[str, Any],
    hooks_enabled: bool = True,
    hooks_dir: Optional[str] = None,
    custom_hooks: Optional[Dict[str, str]] = None,
) -> None:
    """
    Asynchronously executes hook scripts and configured commands for an event.
    Passes POMODORO_* environment variables. Never blocks.
    """
    if not hooks_enabled or event not in SUPPORTED_EVENTS:
        return

    env = os.environ.copy()
    env["POMODORO_EVENT"] = event
    env["POMODORO_PHASE"] = str(state.get("phase", "work"))
    env["POMODORO_STATE"] = str(state.get("state", "idle"))
    env["POMODORO_TIME_REMAINING"] = str(state.get("time_remaining", 0))
    env["POMODORO_TOTAL_TIME"] = str(state.get("total_time", 0))
    env["POMODORO_CYCLE"] = str(state.get("cycle", 1))

    # 1. Custom command defined in config.json
    if custom_hooks and event in custom_hooks:
        cmd_str = custom_hooks[event]
        if cmd_str and cmd_str.strip():
            try:
                subprocess.Popen(
                    cmd_str,
                    shell=True,
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
            except Exception:
                pass

    # 2. Executable scripts in hooks_dir
    if hooks_dir:
        dir_path = Path(os.path.expanduser(hooks_dir))
        for script in find_hook_scripts(dir_path, event):
            try:
                subprocess.Popen(
                    [str(script)],
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
            except Exception:
                pass
