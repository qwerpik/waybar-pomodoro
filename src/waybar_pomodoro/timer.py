"""
Core Pomodoro timer engine for waybar-pomodoro.
"""

from __future__ import annotations

import fcntl
import json
import os
import signal
import subprocess
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, Optional, Tuple

from .config import PomodoroConfig
from .dnd import DndManager
from .notifier import Notifier
from .stats import PomodoroStats


def render_progress_bar(percentage: int, accent_color: str, length: int = 12) -> str:
    """
    Renders a 12-step character progress bar with Pango foreground styling.
    Uses filled (▰) and empty (▱) glyphs.
    """
    clamped_pct = max(0, min(100, percentage))
    filled_count = int(round((clamped_pct / 100.0) * length))
    filled = "▰" * filled_count
    empty = "▱" * (length - filled_count)
    if filled_count == 0:
        return f"<span alpha='30%'>{empty}</span>"
    if empty:
        return f"<span foreground='{accent_color}'>{filled}</span><span alpha='30%'>{empty}</span>"
    return f"<span foreground='{accent_color}'>{filled}</span>"


def _monotonic_clock_id() -> int:
    """Best monotonic clock id; falls back when the platform lacks it."""
    return getattr(time, "CLOCK_MONOTONIC", 1)


def _boottime_clock_id() -> int:
    """CLOCK_BOOTTIME keeps ticking across suspend; fallback disables drift math."""
    return getattr(time, "CLOCK_BOOTTIME", _monotonic_clock_id())


def _read_boot_id() -> str:
    """Kernel boot id; changes on every reboot. Empty string when unreadable."""
    try:
        with open("/proc/sys/kernel/random/boot_id", "r", encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


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
            "paused_by_idle": False,
            "dnd_active": False,
            "start_monotonic": 0.0,
            "start_boottime": 0.0,
            "boot_id": "",
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

        try:
            start_mono = float(raw.get("start_monotonic", 0.0))
        except (ValueError, TypeError):
            start_mono = 0.0

        try:
            start_bt = float(raw.get("start_boottime", 0.0))
        except (ValueError, TypeError):
            start_bt = 0.0

        boot_id_val = raw.get("boot_id", "")
        if not isinstance(boot_id_val, str):
            boot_id_val = ""

        return {
            "state": state_val,
            "phase": phase_val,
            "time_remaining": time_rem,
            "end_time": end_t,
            "total_time": total_t,
            "cycle": cycle_val,
            "paused_by_idle": bool(raw.get("paused_by_idle", False)),
            "dnd_active": bool(raw.get("dnd_active", False)),
            "start_monotonic": start_mono,
            "start_boottime": start_bt,
            "boot_id": boot_id_val,
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
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.state_file.parent, 0o700)
        except OSError:
            pass

        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                dir=self.state_file.parent,
                encoding="utf-8",
                delete=False,
                prefix=f".{self.state_file.name}.",
                suffix=".tmp",
            ) as tmp:
                temp_path = Path(tmp.name)
                os.chmod(tmp.fileno(), 0o600)
                json.dump(state, tmp, indent=2)
                tmp.flush()
                os.fsync(tmp.fileno())

            temp_path.replace(self.state_file)
        except Exception:
            if temp_path and temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass

    @contextmanager
    def _transaction(self) -> Iterator[Dict[str, Any]]:
        """Advisory file locking transaction context manager for process synchronization."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.lock_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.state_file.parent, 0o700)
        except OSError:
            pass

        with open(self.lock_file, "a") as lock_f:
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
                try:
                    # Ignore the RT signal in the current process so it can never signal itself
                    signal.signal(signal.SIGRTMIN + sig, signal.SIG_IGN)
                except Exception:
                    pass

                # Target only exact waybar process owned by the current user
                subprocess.run(
                    ["pkill", "-x", "-u", str(os.getuid()), f"-RTMIN+{sig}", "waybar"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            except Exception:
                pass

    def _dispatch_event(self, event: str, state: Dict[str, Any]) -> None:
        """Asynchronously triggers hook scripts and config commands."""
        from .hooks import dispatch_hook

        dispatch_hook(
            event=event,
            state=state,
            hooks_enabled=self.config.hooks_enabled,
            hooks_dir=self.config.hooks_dir,
            custom_hooks=self.config.hooks,
        )

    def _apply_dnd(self, state: Dict[str, Any]) -> None:
        """Enables or disables Do Not Disturb mode based on current state."""
        if not self.config.auto_dnd:
            return
        from .dnd import set_dnd

        curr_state = state.get("state")
        curr_phase = state.get("phase")
        should_dnd = curr_state == "running" and curr_phase == "work"
        is_dnd = state.get("dnd_active", False)

        if should_dnd and not is_dnd:
            if set_dnd(True, self.config.dnd_provider):
                state["dnd_active"] = True
        elif not should_dnd and is_dnd:
            set_dnd(False, self.config.dnd_provider)
            state["dnd_active"] = False

    @staticmethod
    def _stamp_running(state: Dict[str, Any]) -> None:
        """Record monotonic/boot clocks at the moment a run (re)starts."""
        try:
            state["start_monotonic"] = time.clock_gettime(_monotonic_clock_id())
            state["start_boottime"] = time.clock_gettime(_boottime_clock_id())
        except (OSError, ValueError):
            state["start_monotonic"] = 0.0
            state["start_boottime"] = 0.0
        state["boot_id"] = _read_boot_id()

    @staticmethod
    def _clear_run_stamps(state: Dict[str, Any]) -> None:
        """Invalidate run clocks when the timer stops running."""
        state["start_monotonic"] = 0.0
        state["start_boottime"] = 0.0

    @staticmethod
    def _suspend_drift_seconds(state: Dict[str, Any]) -> float:
        """Seconds the machine spent suspended since this run started.

        CLOCK_BOOTTIME advances across suspend, CLOCK_MONOTONIC does not,
        so their difference is the suspend time. Returns 0.0 when the
        clocks are unavailable or no run was stamped.
        """
        mono_id = _monotonic_clock_id()
        bt_id = _boottime_clock_id()
        if mono_id == bt_id:
            return 0.0
        start_mono_raw = state.get("start_monotonic", 0.0)
        start_bt_raw = state.get("start_boottime", 0.0)
        try:
            start_mono = float(start_mono_raw)
            start_bt = float(start_bt_raw)
        except (ValueError, TypeError):
            return 0.0
        if not start_mono or not start_bt:
            return 0.0
        try:
            mono_now = time.clock_gettime(mono_id)
            bt_now = time.clock_gettime(bt_id)
        except (OSError, ValueError):
            return 0.0
        return max(0.0, (bt_now - start_bt) - (mono_now - start_mono))

    def is_expired(self, state: Dict[str, Any], now: Optional[float] = None) -> bool:
        """Pure expiry check with no side effects (no notify, no stats, no write)."""
        if state.get("state") != "running":
            return False
        moment = time.time() if now is None else now
        total = state.get("total_time", self.config.work_duration * 60)
        end_time = state.get("end_time", 0.0)
        try:
            end_time = float(end_time)
        except (ValueError, TypeError):
            return False
        # Backward clock jump guard (mirrors check_completion): not expired.
        if end_time - moment > total + 60:
            return False
        return int(round(end_time - moment)) <= 0

    def refresh(self) -> Dict[str, Any]:
        """Run completion inside a locked transaction and return the fresh state."""
        with self._transaction() as state:
            self.check_completion(state)
            return state

    def _sync_dnd(self, state: Dict[str, Any]) -> None:
        """Align system DND with the timer phase (no-op unless auto_dnd).

        Claims DND only when the system doesn't already have it on, so a
        user-muted desktop is never un-muted on break. Paused sessions keep
        whatever DND state they have.
        """
        if not self.config.auto_dnd:
            return
        curr_state = state.get("state")
        curr_phase = state.get("phase")
        try:
            manager = DndManager(self.config)
        except Exception:
            return
        if curr_state == "running" and curr_phase == "work":
            if state.get("dnd_active"):
                return
            try:
                already_on = manager.is_dnd_enabled()
            except Exception:
                already_on = None
            if already_on is True:
                return
            try:
                if manager.set_dnd(True):
                    state["dnd_active"] = True
            except Exception:
                pass
        elif curr_state == "idle" or (
            curr_state == "running" and curr_phase in ("short_break", "long_break")
        ):
            if not state.get("dnd_active"):
                return
            try:
                manager.set_dnd(False)
            except Exception:
                pass
            finally:
                state["dnd_active"] = False

    def check_completion(self, state: Dict[str, Any]) -> bool:
        """
        Checks if the active timer has reached zero.
        Handles system sleep/suspend drift to prevent phantom sessions and delayed alarms.
        Returns True if a transition occurred.
        """
        now = time.time()
        if state["state"] != "running":
            return False

        # A reboot invalidates the monotonic/boot clocks stamped at run start;
        # fall back to the wall-clock overdue heuristic below.
        recorded_boot = state.get("boot_id", "")
        if recorded_boot and recorded_boot != _read_boot_id():
            self._clear_run_stamps(state)

        total_time = state.get("total_time", self.config.work_duration * 60)
        # Guard against backward system clock jump (e.g. NTP backwards step or DST adjustments)
        if state["end_time"] - now > total_time + 60:
            resync_rem = min(total_time, max(0, state.get("time_remaining", total_time)))
            state["end_time"] = now + resync_rem

        remaining = int(round(state["end_time"] - now))
        if remaining > 0:
            return False

        overdue_seconds = abs(remaining)
        # If expired by more than 30 minutes, machine was likely suspended/asleep
        was_suspended = overdue_seconds > max(1800, state.get("total_time", 1800) * 2)
        # Microsecond-accurate cross-check: BOOTTIME kept ticking while suspended.
        # Any suspend longer than 2 minutes that covers the expiry means the
        # session did not really complete in front of the user.
        if not was_suspended and self._suspend_drift_seconds(state) > 120:
            was_suspended = True

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
                title = f"🏆 {max_cycles} Cycles Completed! Time for a Long Break"
                msg = (
                    f"Outstanding focus! You've crushed <b>{max_cycles} sessions</b>.\n"
                    f"Take a well-deserved <b>{self.config.long_break_duration} min</b> "
                    "break to recharge."
                )
                urgency = self.config.notification_urgency_work_end
                icon = "appointment-soon"
            else:
                state["phase"] = "short_break"
                state["total_time"] = self.config.short_break_duration * 60
                state["time_remaining"] = state["total_time"]
                title = f"🍅 Focus Session Complete! ({cycle}/{max_cycles})"
                msg = (
                    f"Great progress on session {cycle} of {max_cycles}!\n"
                    f"Take a quick <b>{self.config.short_break_duration} min</b> break."
                )
                urgency = self.config.notification_urgency_work_end
                icon = "appointment-soon"

            if not was_suspended:
                self.notifier.send_notification(title, msg, urgency=urgency, icon=icon)
                self.notifier.play_sound(self.config.sound_work_end)

            self._dispatch_event("complete", state)

            if self.config.auto_start_break and not was_suspended:
                state["state"] = "running"
                state["end_time"] = time.time() + state["time_remaining"]
                self._stamp_running(state)
                self._apply_dnd(state)
                self._dispatch_event("break_start", state)
            else:
                state["state"] = "idle"
                state["end_time"] = 0.0
                self._clear_run_stamps(state)
                self._apply_dnd(state)

        else:  # Finished a break
            cycle = state.get("cycle", 1)
            state["cycle"] = (cycle % max_cycles) + 1
            state["phase"] = "work"
            state["total_time"] = self.config.work_duration * 60
            state["time_remaining"] = state["total_time"]

            if not was_suspended:
                title = "⚡ Break Finished! Ready to Focus?"
                msg = (
                    f"Starting focus session <b>{state['cycle']}/{max_cycles}</b> "
                    f"({self.config.work_duration} min).\nLet's get back in the flow!"
                )
                self.notifier.send_notification(
                    title,
                    msg,
                    urgency=self.config.notification_urgency_break_end,
                    icon="preferences-system-time",
                )
                self.notifier.play_sound(self.config.sound_break_end)

            self._dispatch_event("complete", state)

            if self.config.auto_start_work and not was_suspended:
                state["state"] = "running"
                state["end_time"] = time.time() + state["time_remaining"]
                self._stamp_running(state)
                self._apply_dnd(state)
                self._dispatch_event("work_start", state)
            else:
                state["state"] = "idle"
                state["end_time"] = 0.0
                self._clear_run_stamps(state)
                self._apply_dnd(state)

        return True

    def get_remaining_and_percentage(self, state: Dict[str, Any]) -> Tuple[int, int]:
        now = time.time()
        total = state.get("total_time", self.config.work_duration * 60)
        if state["state"] == "running":
            if state["end_time"] - now > total + 60:
                remaining = min(total, max(0, state.get("time_remaining", total)))
            else:
                remaining = max(0, int(round(state["end_time"] - now)))
        else:
            remaining = max(0, state.get("time_remaining", 0))

        percentage = 0
        if total > 0:
            percentage = min(100, max(0, int(((total - remaining) / total) * 100)))

        return remaining, percentage

    def toggle(self) -> None:
        event = "work_start"
        with self._transaction() as state:
            # Check completion first to avoid locking at 00:00
            self.check_completion(state)
            now = time.time()

            if state["state"] == "running":
                state["state"] = "paused"
                state["time_remaining"] = max(0, int(round(state["end_time"] - now)))
                state["end_time"] = 0.0
                state["paused_by_idle"] = False
                self._clear_run_stamps(state)
                event = "pause"
            elif state["state"] == "paused":
                state["state"] = "running"
                state["end_time"] = now + state["time_remaining"]
                state["paused_by_idle"] = False
                self._stamp_running(state)
                event = "resume"
            else:  # idle
                state["state"] = "running"
                state["end_time"] = now + state["time_remaining"]
                state["paused_by_idle"] = False
                self._stamp_running(state)
                event = "work_start" if state.get("phase") == "work" else "break_start"

            self._apply_dnd(state)

        self.signal_waybar()
        self._dispatch_event(event, state)

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
            state["paused_by_idle"] = False
            self._stamp_running(state)
            self._apply_dnd(state)

        self.signal_waybar()
        self._dispatch_event("work_start" if state.get("phase") == "work" else "break_start", state)

    def pause(self) -> None:
        with self._transaction() as state:
            self.check_completion(state)
            now = time.time()
            if state["state"] == "running":
                state["state"] = "paused"
                state["time_remaining"] = max(0, int(round(state["end_time"] - now)))
                state["end_time"] = 0.0
                state["paused_by_idle"] = False
                self._clear_run_stamps(state)
                self._apply_dnd(state)

        self.signal_waybar()
        self._dispatch_event("pause", state)

    def resume(self) -> None:
        with self._transaction() as state:
            self.check_completion(state)
            now = time.time()
            if state["state"] == "paused":
                state["state"] = "running"
                state["end_time"] = now + state["time_remaining"]
                state["paused_by_idle"] = False
                self._stamp_running(state)
                self._apply_dnd(state)

        self.signal_waybar()
        self._dispatch_event("resume", state)

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
            state["paused_by_idle"] = False
            self._clear_run_stamps(state)
            self._apply_dnd(state)

        self.signal_waybar()
        self._dispatch_event("reset", state)

    def skip(self) -> None:
        event = "work_start"
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
                event = "break_start"
            else:
                cycle = state.get("cycle", 1)
                state["cycle"] = (cycle % max_cycles) + 1
                state["phase"] = "work"
                state["total_time"] = self.config.work_duration * 60
                state["time_remaining"] = state["total_time"]
                event = "work_start"

            if state["state"] == "running":
                state["end_time"] = now + state["time_remaining"]
                self._stamp_running(state)

            self._apply_dnd(state)

        self.signal_waybar()
        self._dispatch_event(event, state)

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
                self._stamp_running(state)
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
        # Read-only fast path: every state write is an atomic rename, so an
        # unlocked read never observes a torn file. Only an actual expiry
        # takes the locked, side-effecting transaction path.
        state = self.load_state()
        if self.is_expired(state):
            state = self.refresh()
        return self.render_payload(state)

    def render_payload(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Build the Waybar JSON payload from an in-memory state (no I/O)."""
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

        # Determine theme accent color and state label for Pango markup
        if curr_state == "paused":
            accent_color = "#f9e2af"
            state_markup = "<span foreground='#f9e2af'><b>Paused ⏸</b></span>"
        elif curr_state == "running":
            accent_color = "#a6e3a1" if "break" in curr_phase else "#f38ba8"
            state_markup = "<span foreground='#a6e3a1'>Running</span>"
        else:
            accent_color = "#89b4fa"
            state_markup = "<span alpha='60%'>Idle ⏱</span>"

        bar = render_progress_bar(percentage, accent_color, length=12)

        # Phase label with session counter
        if curr_phase == "work":
            header_title = (
                f"<b>🍅 Focus Session</b> <span alpha='70%'>[{cycle}/{max_cycles}]</span>"
            )
        elif curr_phase == "short_break":
            header_title = f"<b>☕ Short Break</b> <span alpha='70%'>[{cycle}/{max_cycles}]</span>"
        else:
            header_title = "<b>🌴 Long Break</b> <span alpha='70%'>[Reward]</span>"

        # Focus statistics for tooltip (single disk read)
        today_stats, streak = self.stats.get_today_and_streak()
        today_sessions = today_stats.get("completed_sessions", 0)
        today_mins = today_stats.get("focus_seconds", 0) // 60
        streak_display = (
            f"<b>{streak}</b> day(s) 🔥" if streak > 0 else "<span alpha='60%'>0 days</span>"
        )

        tooltip_lines = [
            f"{header_title}  {state_markup}",
            f"<tt>{bar}</tt>  <b>{time_str}</b> <span alpha='60%'>({percentage}%)</span>",
            "<span alpha='25%'>─────────────────────────────</span>",
            "<span alpha='60%'>• Left-click:</span>   <b>Toggle / Pause</b>",
            "<span alpha='60%'>• Right-click:</span>  <b>Menu / Reset</b>",
            "<span alpha='60%'>• Middle-click:</span> <b>Skip Phase</b>",
            "<span alpha='60%'>• Scroll:</span>       <b>±1 min</b>",
            "<span alpha='25%'>─────────────────────────────</span>",
            (
                f"<span alpha='60%'>Today:</span>  <b>{today_sessions}</b> session(s) "
                f"<span alpha='50%'>•</span> <b>{today_mins}m</b> focus"
            ),
            f"<span alpha='60%'>Streak:</span> {streak_display}",
        ]

        return {
            "text": text,
            "alt": alt_field,
            "tooltip": "\n".join(tooltip_lines),
            "class": " ".join(css_classes),
            "percentage": percentage,
        }
