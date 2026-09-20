"""
Screen lock and inactivity detection for waybar-pomodoro.

Turnkey targets: hypridle (`on-timeout`/`on-resume`), swayidle
(`timeout`/`resume`/`before-sleep`), screen lockers. Never raises, never
blocks the session: every handler returns an exit code.
"""

from __future__ import annotations

import shutil
import subprocess
import time
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .config import PomodoroConfig
    from .timer import PomodoroTimer

_PROMPT_TIMEOUT = 60


def handle_idle_pause(timer: "PomodoroTimer", config: "PomodoroConfig") -> int:
    """Pause a running timer on screen lock / inactivity.

    Marks `paused_by_idle` so resume can tell forced pauses apart from
    manual ones. DND is intentionally untouched: the focus session still
    owns the screen. Always returns 0 unless something unexpected fails.
    """
    try:
        with timer._transaction() as state:
            timer.check_completion(state)
            if state.get("state") != "running":
                return 0
            now = time.time()
            state["state"] = "paused"
            state["time_remaining"] = max(0, int(round(state["end_time"] - now)))
            state["end_time"] = 0.0
            state["paused_by_idle"] = True
            timer._clear_run_stamps(state)
        timer.signal_waybar()
        timer._dispatch_event("pause", state)
        timer.notifier.send_notification(
            "⏸ Paused — screen locked",
            "Timer paused. Unlock to resume your focus session.",
            urgency="low",
            icon="appointment-soon",
        )
        return 0
    except Exception:
        return 1


def _prompt_resume_action(timer: "PomodoroTimer", timeout: int = _PROMPT_TIMEOUT) -> Optional[str]:
    """Ask via notify-send action buttons; 'resume', 'reset', 'keep' or None.

    None means dismissed, timed out, or notify-send unavailable — the safe
    answer, treated as keep-paused.
    """
    if not shutil.which("notify-send"):
        return None
    try:
        result = subprocess.run(
            [
                "notify-send",
                "-a",
                "Pomodoro",
                "-u",
                "normal",
                "-c",
                "timer",
                "-t",
                "60000",
                "-i",
                "appointment-soon",
                "-w",
                "-A",
                "resume,Resume",
                "-A",
                "reset,Reset",
                "-A",
                "keep,Keep paused",
                "🔓 Welcome back",
                "Resume your focus session?",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
            check=False,
            text=True,
        )
        action = (result.stdout or "").strip().lower()
        return action if action in ("resume", "reset", "keep") else None
    except Exception:
        return None


def handle_idle_resume(
    timer: "PomodoroTimer", config: "PomodoroConfig", interactive: bool = True
) -> int:
    """Resume a lock-paused timer on unlock / return.

    Manual pauses (`paused_by_idle` unset) are always preserved. Mode comes
    from `idle_resume_mode` ('prompt' | 'auto' | 'keep'); a non-interactive
    call forces 'auto'. Anything but an explicit resume converts the pause
    to a manual one so later unlocks stay quiet.
    """
    try:
        mode = config.idle_resume_mode if interactive else "auto"
        if mode not in ("prompt", "auto", "keep"):
            mode = "prompt" if interactive else "auto"

        snap = timer.load_state()
        if snap.get("state") != "paused" or not snap.get("paused_by_idle"):
            return 0

        if mode == "keep":
            with timer._transaction() as state:
                state["paused_by_idle"] = False
            timer.signal_waybar()
            return 0

        if mode == "prompt":
            action = _prompt_resume_action(timer)
            if action == "reset":
                timer.reset()
                return 0
            if action != "resume":
                with timer._transaction() as state:
                    state["paused_by_idle"] = False
                timer.signal_waybar()
                return 0

        with timer._transaction() as state:
            timer.check_completion(state)
            if state.get("state") != "paused" or not state.get("paused_by_idle"):
                return 0
            state["paused_by_idle"] = False
            state["state"] = "running"
            remaining = max(0, int(state.get("time_remaining", 0)))
            state["time_remaining"] = remaining
            state["end_time"] = time.time() + remaining
            timer._stamp_running(state)
            timer._apply_dnd(state)
        timer.signal_waybar()
        timer._dispatch_event("resume", state)
        if config.idle_resume_notify:
            timer.notifier.send_notification(
                "🍅 Focus Session Resumed",
                "Welcome back! Your pomodoro timer has resumed.",
                urgency="low",
                icon="appointment-soon",
            )
        return 0
    except Exception:
        return 1
