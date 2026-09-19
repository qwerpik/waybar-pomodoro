"""
Screen lock and inactivity detection (idle-pause and idle-resume) for waybar-pomodoro.
Integrates with hypridle, swayidle, hyprlock, swaylock, and systemd-logind.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Tuple

if TYPE_CHECKING:
    from .timer import PomodoroTimer


def handle_idle_pause(timer: PomodoroTimer) -> Tuple[bool, str]:
    """
    Called when screen locks or inactivity occurs.
    Pauses the timer if currently running and flags 'paused_by_idle: true'.
    Returns (success, message).
    """
    with timer._transaction() as state:
        timer.check_completion(state)
        curr_state = state.get("state")
        if curr_state != "running":
            return False, f"Timer is {curr_state}, nothing to pause on idle."

        now = time.time()
        remaining = max(1, int(round(state["end_time"] - now)))
        state["state"] = "paused"
        state["time_remaining"] = remaining
        state["end_time"] = 0.0
        state["paused_by_idle"] = True
        timer._clear_run_stamps(state)
        timer._apply_dnd(state)

    timer.signal_waybar()
    timer._dispatch_event("pause", state)
    return True, "Active session paused due to screen lock/inactivity."


def handle_idle_resume(timer: PomodoroTimer, auto_resume: bool = True) -> Tuple[bool, str]:
    """
    Called when screen unlocks or user returns.
    If the timer was paused by idle, resumes or notifies the user.
    Preserves manual pauses so user sessions aren't disrupted unexpectedly.
    Returns (success, message).
    """
    resumed = False
    with timer._transaction() as state:
        timer.check_completion(state)
        curr_state = state.get("state")
        paused_by_idle = state.get("paused_by_idle", False)

        if curr_state != "paused" or not paused_by_idle:
            return False, "Timer was not paused by idle lock; preserving current state."

        # Clear the flag regardless
        state["paused_by_idle"] = False

        if auto_resume:
            now = time.time()
            rem = max(1, state.get("time_remaining", timer.config.work_duration * 60))
            state["state"] = "running"
            state["end_time"] = now + rem
            timer._stamp_running(state)
            timer._apply_dnd(state)
            resumed = True

    timer.signal_waybar()
    if resumed:
        timer._dispatch_event("resume", state)

    if resumed and timer.config.idle_resume_notify and timer.config.notification_enabled:
        timer.notifier.send_notification(
            "🍅 Focus Session Resumed",
            "Welcome back! Your pomodoro timer has resumed.",
            urgency="low",
            icon="appointment-soon",
        )

    return True, "Session resumed after unlock."
