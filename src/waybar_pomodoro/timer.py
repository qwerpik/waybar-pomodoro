"""
Core Pomodoro timer engine for waybar-pomodoro.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from .config import PomodoroConfig
from .notifier import Notifier
from .stats import PomodoroStats


class PomodoroTimer:
    def __init__(self, config: PomodoroConfig):
        self.config = config
        self.state_file = Path(os.path.expanduser(config.state_file))
        self.stats = PomodoroStats(os.path.expanduser(config.stats_file))
        self.notifier = Notifier(
            sound_enabled=config.sound_enabled,
            notification_enabled=config.notification_enabled,
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
        return state

    def save_state(self, state: Dict[str, Any]) -> None:
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            temp_file = self.state_file.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
            temp_file.replace(self.state_file)
        except Exception:
            pass

    def signal_waybar(self) -> None:
        sig = self.config.waybar_signal
        if sig > 0:
            try:
                subprocess.run(
                    ["pkill", f"-RTMIN+{sig}", "waybar"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            except Exception:
                pass

    def check_completion(self, state: Dict[str, Any]) -> bool:
        """
        Checks if the active timer has reached zero.
        Returns True if a transition occurred.
        """
        now = time.time()
        if state["state"] != "running":
            return False

        remaining = int(round(state["end_time"] - now))
        if remaining > 0:
            return False

        # Phase completed!
        if state["phase"] == "work":
            # Record completed work session
            self.stats.record_session(state.get("total_time", self.config.work_duration * 60))
            cycle = state.get("cycle", 1)

            if cycle % self.config.cycles_before_long_break == 0:
                state["phase"] = "long_break"
                state["total_time"] = self.config.long_break_duration * 60
                state["time_remaining"] = state["total_time"]
                title = "Pomodoro: 4 Cycles Completed!"
                msg = f"Fantastic focus! Take a long break ({self.config.long_break_duration} min)."
                urgency = self.config.notification_urgency_work_end
            else:
                state["phase"] = "short_break"
                state["total_time"] = self.config.short_break_duration * 60
                state["time_remaining"] = state["total_time"]
                title = f"Pomodoro Completed! ({cycle}/{self.config.cycles_before_long_break})"
                msg = f"Good job! Take a short break ({self.config.short_break_duration} min)."
                urgency = self.config.notification_urgency_work_end

            self.notifier.send_notification(title, msg, urgency=urgency)
            self.notifier.play_sound(self.config.sound_work_end)

            if self.config.auto_start_break:
                state["state"] = "running"
                state["end_time"] = time.time() + state["time_remaining"]
            else:
                state["state"] = "idle"

        else:  # Finished a break
            cycle = state.get("cycle", 1)
            state["cycle"] = (cycle % self.config.cycles_before_long_break) + 1
            state["phase"] = "work"
            state["total_time"] = self.config.work_duration * 60
            state["time_remaining"] = state["total_time"]

            title = "Break Finished!"
            msg = f"Ready for focus session {state['cycle']}/{self.config.cycles_before_long_break}? Let's work!"
            self.notifier.send_notification(
                title, msg, urgency=self.config.notification_urgency_break_end
            )
            self.notifier.play_sound(self.config.sound_break_end)

            if self.config.auto_start_work:
                state["state"] = "running"
                state["end_time"] = time.time() + state["time_remaining"]
            else:
                state["state"] = "idle"

        self.save_state(state)
        return True

    def get_remaining_and_percentage(
        self, state: Dict[str, Any]
    ) -> Tuple[int, int]:
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
        state = self.load_state()
        now = time.time()

        if state["state"] == "running":
            state["state"] = "paused"
            state["time_remaining"] = max(0, int(round(state["end_time"] - now)))
        elif state["state"] == "paused":
            state["state"] = "running"
            state["end_time"] = now + state["time_remaining"]
        else:  # idle
            state["state"] = "running"
            state["end_time"] = now + state["time_remaining"]

        self.save_state(state)
        self.signal_waybar()

    def start(self) -> None:
        state = self.load_state()
        now = time.time()
        if state["state"] != "running":
            state["state"] = "running"
            state["end_time"] = now + state["time_remaining"]
            self.save_state(state)
            self.signal_waybar()

    def pause(self) -> None:
        state = self.load_state()
        now = time.time()
        if state["state"] == "running":
            state["state"] = "paused"
            state["time_remaining"] = max(0, int(round(state["end_time"] - now)))
            self.save_state(state)
            self.signal_waybar()

    def resume(self) -> None:
        state = self.load_state()
        now = time.time()
        if state["state"] == "paused":
            state["state"] = "running"
            state["end_time"] = now + state["time_remaining"]
            self.save_state(state)
            self.signal_waybar()

    def reset(self) -> None:
        work_sec = self.config.work_duration * 60
        state = {
            "state": "idle",
            "phase": "work",
            "time_remaining": work_sec,
            "end_time": 0.0,
            "total_time": work_sec,
            "cycle": 1,
        }
        self.save_state(state)
        self.signal_waybar()

    def skip(self) -> None:
        state = self.load_state()
        now = time.time()

        if state["phase"] == "work":
            cycle = state.get("cycle", 1)
            if cycle % self.config.cycles_before_long_break == 0:
                state["phase"] = "long_break"
                state["total_time"] = self.config.long_break_duration * 60
                state["time_remaining"] = state["total_time"]
            else:
                state["phase"] = "short_break"
                state["total_time"] = self.config.short_break_duration * 60
                state["time_remaining"] = state["total_time"]
        else:
            cycle = state.get("cycle", 1)
            state["cycle"] = (cycle % self.config.cycles_before_long_break) + 1
            state["phase"] = "work"
            state["total_time"] = self.config.work_duration * 60
            state["time_remaining"] = state["total_time"]

        if state["state"] == "running":
            state["end_time"] = now + state["time_remaining"]

        self.save_state(state)
        self.signal_waybar()

    def adjust(self, delta_seconds: int) -> None:
        """
        Adjusts the time by delta_seconds (+60 or -60, etc.).
        """
        state = self.load_state()
        now = time.time()

        if state["state"] == "running":
            current_rem = max(0, int(round(state["end_time"] - now)))
            new_rem = max(1, current_rem + delta_seconds)
            state["end_time"] = now + new_rem
            state["total_time"] = max(new_rem, state.get("total_time", new_rem))
        else:
            current_rem = state.get("time_remaining", self.config.work_duration * 60)
            new_rem = max(1, current_rem + delta_seconds)
            state["time_remaining"] = new_rem
            state["total_time"] = max(new_rem, state.get("total_time", new_rem))

        self.save_state(state)
        self.signal_waybar()

    def get_status_payload(self) -> Dict[str, Any]:
        state = self.load_state()
        self.check_completion(state)

        remaining, percentage = self.get_remaining_and_percentage(state)
        mins = remaining // 60
        secs = remaining % 60
        time_str = f"{mins:02d}:{secs:02d}"

        curr_state = state["state"]
        curr_phase = state["phase"]
        cycle = state.get("cycle", 1)
        max_cycles = self.config.cycles_before_long_break

        # Resolve icon
        if curr_state == "paused":
            icon = self.config.icon_paused
        elif curr_state == "idle":
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
            # Numbers only, except paused indicator if paused
            if curr_state == "paused":
                text = f"⏸ {time_str}"
            else:
                text = time_str
        elif self.config.style == "icon":
            text = f"{icon} {time_str}"
        else:  # custom
            if curr_state == "paused":
                fmt = self.config.format_paused
            elif curr_state == "idle":
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

        # CSS classes: support both new and legacy classes
        # (e.g. "work", "break", "paused", "stopped", "idle")
        css_classes = [curr_state]
        if curr_state == "idle":
            css_classes.append("stopped")
        if curr_phase in ("short_break", "long_break"):
            css_classes.extend(["break", curr_phase.replace("_", "-")])
        else:
            css_classes.append("work")

        # Construct informative tooltip with stats
        today_stats = self.stats.get_today_stats()
        today_sessions = today_stats.get("completed_sessions", 0)

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
            f"Pomodoro: {phase_label} [{state_label}]",
            "• Left-click: Start / Pause",
            "• Right-click: Reset",
            "• Middle-click: Skip phase",
            "• Scroll: +/- 1 min",
            "─" * 24,
            f"Today's completed: {today_sessions} session(s)",
        ]

        return {
            "text": text,
            "tooltip": "\n".join(tooltip_lines),
            "class": " ".join(css_classes),
            "percentage": percentage,
        }
