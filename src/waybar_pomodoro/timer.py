"""
Core Pomodoro timer engine for waybar-pomodoro.
"""

from __future__ import annotations

import fcntl
import json
import os
import subprocess
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, Optional, Tuple

from .config import PomodoroConfig
from .notifier import Notifier
from .stats import PomodoroStats


class PomodoroTimer:
    def __init__(self, config: PomodoroConfig):
        self.config = config
        self.state_file = Path(os.path.expanduser(config.state_file))
        self.lock_file = self.state_file.with_suffix(".lock")
        self.stats = PomodoroStats(os.path.expanduser(config.stats_file))
        self.notifier = Notifier(
            sound_enabled=config.sound_enabled,
            notification_enabled=config.notification_enabled,
            notification_timeout=config.notification_timeout,
            notification_category=config.notification_category,
        )

    def _default_state(self) -> Dict[str, Any]:
        work_sec = self.config.work_duration * 60
        return {
            "state": "idle",  # "idle", "running", "paused"
            "phase": "work",  # "work", "short_break", "long_break"
            "time_remaining": work_sec,
            "end_time": 0.0,
            "total_time": work_sec,
            "cycle": 1,
        }

    def _sanitize_state(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        work_sec = self.config.work_duration * 60
        state_val = raw.get("state")
        if state_val not in ("idle", "running", "paused"):
            state_val = "idle"

        phase_val = raw.get("phase")
        if phase_val not in ("work", "short_break", "long_break"):
            phase_val = "work"

        try:
            time_rem = max(0, int(raw.get("time_remaining", work_sec)))
        except (ValueError, TypeError):
            time_rem = work_sec

        try:
            end_t = float(raw.get("end_time", 0.0))
        except (ValueError, TypeError):
            end_t = 0.0

        try:
            total_t = max(1, int(raw.get("total_time", work_sec)))
        except (ValueError, TypeError):
            total_t = work_sec

        try:
            cycle_val = max(1, int(raw.get("cycle", 1)))
        except (ValueError, TypeError):
            cycle_val = 1

        return {
            "state": state_val,
            "phase": phase_val,
            "time_remaining": time_rem,
            "end_time": end_t,
            "total_time": total_t,
            "cycle": cycle_val,
        }

    def load_state(self) -> Dict[str, Any]:
        state = self._default_state()
        if self.state_file.is_file():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    content = json.load(f)
                    if isinstance(content, dict):
                        state.update(content)
            except Exception:
                pass
        return self._sanitize_state(state)

    def save_state(self, state: Dict[str, Any]) -> None:
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w",
                dir=self.state_file.parent,
                encoding="utf-8",
                delete=False,
                prefix=f".{self.state_file.name}.",
                suffix=".tmp",
            ) as tmp:
                json.dump(state, tmp, indent=2)
                tmp.flush()
                os.fsync(tmp.fileno())
                temp_path = Path(tmp.name)

            temp_path.replace(self.state_file)
        except Exception:
            pass

    @contextmanager
    def _transaction(self) -> Iterator[Dict[str, Any]]:
        """Advisory file locking transaction context manager for process synchronization."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.lock_file.parent.mkdir(parents=True, exist_ok=True)

        with open(self.lock_file, "w") as lock_f:
            fcntl.flock(lock_f.fileno(), fcntl.LOCK_EX)
            try:
                state = self.load_state()
                yield state
                self.save_state(state)
            finally:
                fcntl.flock(lock_f.fileno(), fcntl.LOCK_UN)

    def signal_waybar(self) -> None:
        sig = self.config.waybar_signal
        if 0 < sig <= 30:
            try:
                # Target only the current user's waybar processes
                subprocess.run(
                    ["pkill", "-u", str(os.getuid()), f"-RTMIN+{sig}", "waybar"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            except Exception:
                pass

    def check_completion(self, state: Dict[str, Any]) -> bool:
        """
        Checks if the active timer has reached zero.
        Handles system sleep/suspend drift to prevent phantom sessions and delayed alarms.
        Returns True if a transition occurred.
        """
        now = time.time()
        if state["state"] != "running":
            return False

        remaining = int(round(state["end_time"] - now))
        if remaining > 0:
            return False

        overdue_seconds = abs(remaining)
        # If expired by more than 30 minutes, machine was likely suspended/asleep
        was_suspended = overdue_seconds > max(1800, state.get("total_time", 1800) * 2)

        max_cycles = max(1, self.config.cycles_before_long_break)

        if state["phase"] == "work":
            # Record completed work session only if not suspended
            if not was_suspended:
                self.stats.record_session(state.get("total_time", self.config.work_duration * 60))

            cycle = state.get("cycle", 1)

            if cycle % max_cycles == 0:
                state["phase"] = "long_break"
                state["total_time"] = self.config.long_break_duration * 60
                state["time_remaining"] = state["total_time"]
                title = f"Pomodoro: {max_cycles} Cycles Completed!"
                msg = f"Fantastic focus! Take a long break ({self.config.long_break_duration} min)."
                urgency = self.config.notification_urgency_work_end
            else:
                state["phase"] = "short_break"
                state["total_time"] = self.config.short_break_duration * 60
                state["time_remaining"] = state["total_time"]
                title = f"Pomodoro Completed! ({cycle}/{max_cycles})"
                msg = f"Good job! Take a short break ({self.config.short_break_duration} min)."
                urgency = self.config.notification_urgency_work_end

            if not was_suspended:
                self.notifier.send_notification(title, msg, urgency=urgency)
                self.notifier.play_sound(self.config.sound_work_end)

            if self.config.auto_start_break and not was_suspended:
                state["state"] = "running"
                state["end_time"] = time.time() + state["time_remaining"]
            else:
                state["state"] = "idle"
                state["end_time"] = 0.0

        else:  # Finished a break
            cycle = state.get("cycle", 1)
            state["cycle"] = (cycle % max_cycles) + 1
            state["phase"] = "work"
            state["total_time"] = self.config.work_duration * 60
            state["time_remaining"] = state["total_time"]

            if not was_suspended:
                title = "Break Finished!"
                msg = f"Ready for focus session {state['cycle']}/{max_cycles}? Let's work!"
                self.notifier.send_notification(
                    title, msg, urgency=self.config.notification_urgency_break_end
                )
                self.notifier.play_sound(self.config.sound_break_end)

            if self.config.auto_start_work and not was_suspended:
                state["state"] = "running"
                state["end_time"] = time.time() + state["time_remaining"]
            else:
                state["state"] = "idle"
                state["end_time"] = 0.0

        return True

    def get_remaining_and_percentage(self, state: Dict[str, Any]) -> Tuple[int, int]:
        now = time.time()
        if state["state"] == "running":
            remaining = max(0, int(round(state["end_time"] - now)))
        else:
            remaining = max(0, state.get("time_remaining", 0))

        total = state.get("total_time", self.config.work_duration * 60)
        percentage = 0
        if total > 0:
            percentage = min(100, max(0, int(((total - remaining) / total) * 100)))

        return remaining, percentage

    def toggle(self) -> None:
        with self._transaction() as state:
            # Check completion first to avoid locking at 00:00
            self.check_completion(state)
            now = time.time()

            if state["state"] == "running":
                state["state"] = "paused"
                state["time_remaining"] = max(0, int(round(state["end_time"] - now)))
                state["end_time"] = 0.0
            elif state["state"] == "paused":
                state["state"] = "running"
                state["end_time"] = now + state["time_remaining"]
            else:  # idle
                state["state"] = "running"
                state["end_time"] = now + state["time_remaining"]

        self.signal_waybar()

    def start(self, duration_seconds: Optional[int] = None) -> None:
        with self._transaction() as state:
            self.check_completion(state)
            now = time.time()

            if duration_seconds is not None and duration_seconds > 0:
                state["time_remaining"] = duration_seconds
                state["total_time"] = duration_seconds
                state["phase"] = "work"

            state["state"] = "running"
            state["end_time"] = now + state["time_remaining"]

        self.signal_waybar()

    def pause(self) -> None:
        with self._transaction() as state:
            self.check_completion(state)
            now = time.time()
            if state["state"] == "running":
                state["state"] = "paused"
                state["time_remaining"] = max(0, int(round(state["end_time"] - now)))
                state["end_time"] = 0.0

        self.signal_waybar()

    def resume(self) -> None:
        with self._transaction() as state:
            self.check_completion(state)
            now = time.time()
            if state["state"] == "paused":
                state["state"] = "running"
                state["end_time"] = now + state["time_remaining"]

        self.signal_waybar()

    def reset(self, duration_seconds: Optional[int] = None) -> None:
        work_sec = (
            duration_seconds
            if (duration_seconds and duration_seconds > 0)
            else (self.config.work_duration * 60)
        )
        with self._transaction() as state:
            state["state"] = "idle"
            state["phase"] = "work"
            state["time_remaining"] = work_sec
            state["end_time"] = 0.0
            state["total_time"] = work_sec
            state["cycle"] = 1

        self.signal_waybar()

    def skip(self) -> None:
        with self._transaction() as state:
            self.check_completion(state)
            now = time.time()
            max_cycles = max(1, self.config.cycles_before_long_break)

            if state["phase"] == "work":
                cycle = state.get("cycle", 1)
                if cycle % max_cycles == 0:
                    state["phase"] = "long_break"
                    state["total_time"] = self.config.long_break_duration * 60
                    state["time_remaining"] = state["total_time"]
                else:
                    state["phase"] = "short_break"
                    state["total_time"] = self.config.short_break_duration * 60
                    state["time_remaining"] = state["total_time"]
            else:
                cycle = state.get("cycle", 1)
                state["cycle"] = (cycle % max_cycles) + 1
                state["phase"] = "work"
                state["total_time"] = self.config.work_duration * 60
                state["time_remaining"] = state["total_time"]

            if state["state"] == "running":
                state["end_time"] = now + state["time_remaining"]

        self.signal_waybar()

    def adjust(self, delta_seconds: int) -> None:
        """
        Adjusts timer duration by delta_seconds (+60, -60, etc.).
        Handles rapid wheel scrolling atomically.
        """
        with self._transaction() as state:
            self.check_completion(state)
            now = time.time()

            if state["state"] == "running":
                current_rem = max(0, int(round(state["end_time"] - now)))
                new_rem = max(1, current_rem + delta_seconds)
                state["end_time"] = now + new_rem
                state["time_remaining"] = new_rem
                state["total_time"] = max(new_rem, state.get("total_time", new_rem))
            else:
                current_rem = state.get("time_remaining", self.config.work_duration * 60)
                new_rem = max(1, current_rem + delta_seconds)
                state["time_remaining"] = new_rem
                # In idle/paused mode before start, new duration becomes the new total time
                state["total_time"] = new_rem

        self.signal_waybar()

    def get_time_left(self, as_seconds: bool = False) -> str | int:
        state = self.load_state()
        self.check_completion(state)
        remaining, _ = self.get_remaining_and_percentage(state)
        if as_seconds:
            return remaining
        mins = remaining // 60
        secs = remaining % 60
        return f"{mins:02d}:{secs:02d}"

    def get_status_payload(self) -> Dict[str, Any]:
        with self._transaction() as state:
            self.check_completion(state)

        remaining, percentage = self.get_remaining_and_percentage(state)
        mins = remaining // 60
        secs = remaining % 60
        time_str = f"{mins:02d}:{secs:02d}"

        curr_state = state["state"]
        curr_phase = state["phase"]
        cycle = state.get("cycle", 1)
        max_cycles = max(1, self.config.cycles_before_long_break)

        # Resolve icon
        if curr_state == "paused":
            icon = self.config.icon_paused
        elif curr_state == "idle" and curr_phase == "work":
            icon = self.config.icon_idle
        elif curr_phase == "short_break":
            icon = self.config.icon_short_break
        elif curr_phase == "long_break":
            icon = self.config.icon_long_break
        else:
            icon = self.config.icon_work

        # Resolve text based on style
        format_vars = {
            "time": time_str,
            "icon": icon,
            "cycle": cycle,
            "phase": curr_phase.replace("_", " ").title(),
        }

        if self.config.style == "minimal":
            if curr_state == "paused":
                text = f"⏸ {time_str}"
            else:
                text = time_str
        elif self.config.style == "icon":
            text = f"{icon} {time_str}"
        else:  # custom
            if curr_state == "paused":
                fmt = self.config.format_paused
            elif curr_state == "idle" and curr_phase == "work":
                fmt = self.config.format_idle
            elif curr_phase == "short_break":
                fmt = self.config.format_short_break
            elif curr_phase == "long_break":
                fmt = self.config.format_long_break
            else:
                fmt = self.config.format_work
            try:
                text = fmt.format(**format_vars)
            except Exception:
                text = f"{icon} {time_str}"

        # CSS classes taxonomy:
        # Crucial fix: do NOT emit "work" when idle, preventing stylesheet cascade clashes
        css_classes = [curr_state]
        if curr_state == "idle":
            css_classes.append("stopped")
            if curr_phase in ("short_break", "long_break"):
                css_classes.extend(["break", curr_phase.replace("_", "-")])
        else:
            if curr_phase in ("short_break", "long_break"):
                css_classes.extend(["break", curr_phase.replace("_", "-")])
            else:
                css_classes.append("work")

        # Waybar standard protocol alt field (for {alt} and format-icons mapping)
        if curr_state == "paused":
            alt_field = "paused"
        elif curr_state == "idle" and curr_phase == "work":
            alt_field = "idle"
        else:
            alt_field = curr_phase

        # Informative tooltip with Pango markup and focus stats
        today_stats = self.stats.get_today_stats()
        today_sessions = today_stats.get("completed_sessions", 0)
        today_mins = today_stats.get("focus_seconds", 0) // 60
        streak = self.stats.get_streak()

        phase_label = {
            "work": f"Focus ({cycle}/{max_cycles})",
            "short_break": f"Short Break ({mins:02d}:{secs:02d})",
            "long_break": f"Long Break ({mins:02d}:{secs:02d})",
        }.get(curr_phase, "Focus")

        state_label = {
            "idle": "Idle",
            "running": "Running",
            "paused": "Paused",
        }.get(curr_state, "Ready")

        tooltip_lines = [
            f"<b>Pomodoro:</b> {phase_label} [{state_label}]",
            f"<b>Time Left:</b> {time_str} ({percentage}%)",
            "─" * 26,
            "• Left-click: Start / Pause",
            "• Right-click: Reset",
            "• Middle-click: Skip phase",
            "• Scroll: +/- 1 min",
            "─" * 26,
            f"<b>Today:</b> {today_sessions} session(s) ({today_mins} min)",
            f"<b>Streak:</b> {streak} day(s)",
        ]

        return {
            "text": text,
            "alt": alt_field,
            "tooltip": "\n".join(tooltip_lines),
            "class": " ".join(css_classes),
            "percentage": percentage,
        }
