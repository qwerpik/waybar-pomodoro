"""
Persistent Waybar streaming daemon (`waybar-pomodoro stream`).

Emits newline-delimited JSON payloads on stdout instead of being re-executed
every second by Waybar. Integer-second alignment keeps the display crisp;
when idle or paused the process blocks in the kernel with ~0% CPU and wakes
only on state changes (inotify) or realtime signals.
"""

from __future__ import annotations

import fcntl
import json
import math
import os
import select
import signal
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, TextIO

from .timer import PomodoroTimer
from .watcher import InotifyWatcher


class StreamAlreadyRunning(RuntimeError):
    """Raised when another `stream` daemon already holds the instance lock."""


class _InstanceLock:
    """Exclusive non-blocking lock file, acquired eagerly on construction.

    Use as a context manager (`with single_instance(path): ...`).
    """

    def __init__(self, lock_path: Path) -> None:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            handle = open(lock_path, "w", encoding="utf-8")
        except OSError as exc:
            raise StreamAlreadyRunning(f"cannot open stream lock: {exc}") from exc
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (BlockingIOError, OSError) as exc:
            handle.close()
            holder = ""
            try:
                holder = lock_path.read_text(encoding="utf-8").strip()
            except OSError:
                pass
            detail = f" (held by pid {holder})" if holder else ""
            raise StreamAlreadyRunning(f"another stream daemon is running{detail}") from exc
        handle.write(str(os.getpid()))
        handle.flush()
        self._handle: Optional[TextIO] = handle

    def release(self) -> None:
        handle, self._handle = self._handle, None
        if handle is None:
            return
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        handle.close()

    def __enter__(self) -> "_InstanceLock":
        return self

    def __exit__(self, *exc: object) -> None:
        self.release()


def single_instance(lock_path: Path) -> _InstanceLock:
    """Acquire the stream instance lock; raises StreamAlreadyRunning if held."""
    return _InstanceLock(lock_path)


def next_tick_delay(now: float) -> float:
    """Seconds until just past the next integer second boundary.

    Waking at floor(t) + 1.005 keeps <10us scheduling jitter from showing a
    stale second while never skipping a boundary.
    """
    return max(0.0, (math.floor(now) + 1.005) - now)


def _emit(payload: Dict[str, Any]) -> bool:
    """Write one payload line; False when stdout went away (Waybar restarted)."""
    try:
        sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
        sys.stdout.flush()
        return True
    except BrokenPipeError:
        return False


def run_stream(timer: PomodoroTimer) -> int:
    """Main loop. Returns 0 on clean shutdown, 1 if already running."""
    lock_path = timer.state_file.parent / "stream.lock"
    try:
        instance = single_instance(lock_path)
    except StreamAlreadyRunning as exc:
        print(f"waybar-pomodoro stream: {exc}", file=sys.stderr)
        return 1

    with instance:
        try:
            watcher = InotifyWatcher(timer.state_file)
            watcher.start()
        except OSError as exc:
            print(f"waybar-pomodoro stream: inotify unavailable: {exc}", file=sys.stderr)
            return 1

        pipe_r, pipe_w = os.pipe()
        os.set_blocking(pipe_r, False)
        os.set_blocking(pipe_w, False)
        stopped = False

        def _wake(signum: int, frame: Any) -> None:
            try:
                os.write(pipe_w, b"\x00")
            except OSError:
                pass

        def _stop(signum: int, frame: Any) -> None:
            nonlocal stopped
            stopped = True
            try:
                os.write(pipe_w, b"\x00")
            except OSError:
                pass

        signals: List[int] = [signal.SIGUSR1]
        sig_rt = timer.config.waybar_signal
        if 0 < sig_rt <= 30:
            try:
                signals.append(signal.SIGRTMIN + sig_rt)
            except (ValueError, OSError, AttributeError):
                pass
        old_handlers = {}
        for sig in signals:
            try:
                old_handlers[sig] = signal.signal(sig, _wake)
            except (ValueError, OSError):
                pass
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                old_handlers[sig] = signal.signal(sig, _stop)
            except (ValueError, OSError):
                pass

        def _drain() -> None:
            try:
                while os.read(pipe_r, 1024):
                    pass
            except (BlockingIOError, InterruptedError, OSError):
                pass

        def _refresh_and_emit() -> bool:
            # Same contract as get_status_payload: read-only unless expired.
            state = timer.load_state()
            if timer.is_expired(state):
                state = timer.refresh()
            return _emit(timer.render_payload(state))

        exit_code = 0
        try:
            if not _refresh_and_emit():
                return 0
            while not stopped:
                state = timer.load_state()
                remaining, _ = timer.get_remaining_and_percentage(state)
                ticking = state.get("state") == "running" and remaining > 0
                timeout = next_tick_delay(time.time()) if ticking else None
                try:
                    ready, _, _ = select.select([watcher.fileno(), pipe_r], [], [], timeout)
                except (ValueError, OSError):
                    break
                if stopped:
                    break
                _drain()
                if watcher.fileno() in ready:
                    watcher.consume_events()
                if not _refresh_and_emit():
                    break
        finally:
            for sig, handler in old_handlers.items():
                try:
                    signal.signal(sig, handler)
                except (ValueError, OSError):
                    pass
            watcher.close()
            try:
                os.close(pipe_r)
            except OSError:
                pass
            try:
                os.close(pipe_w)
            except OSError:
                pass
        return exit_code
