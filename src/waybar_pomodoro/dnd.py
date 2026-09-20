"""
Automatic Focus Do Not Disturb control for waybar-pomodoro.

Native, non-blocking controls for swaync, dunst and mako. Every external
call is best-effort (short timeouts, failures swallowed) — DND handling
must never break the timer or block the bar.
"""

from __future__ import annotations

import functools
import shutil
import subprocess
import time
from typing import Dict, List, Optional, Tuple

from .config import PomodoroConfig

_PROVIDERS = ("swaync", "dunst", "mako")

# Daemon process name used to confirm the provider is actually running.
_DAEMON_PROC: Dict[str, str] = {
    "swaync": "swaync",
    "dunst": "dunst",
    "mako": "mako",
}

# CLI binary used to drive each provider.
_CTL_BIN: Dict[str, str] = {
    "swaync": "swaync-client",
    "dunst": "dunstctl",
    "mako": "makoctl",
}

_SYNC_TIMEOUT = 3


@functools.lru_cache(maxsize=8)
def _which(binary: str) -> Optional[str]:
    return shutil.which(binary)


def _process_running(proc_name: str) -> bool:
    """True when a process with this exact name exists (best effort)."""
    pgrep = _which("pgrep")
    if not pgrep:
        return True  # cannot verify; trust the installed binary
    try:
        result = subprocess.run(
            [pgrep, "-x", proc_name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=_SYNC_TIMEOUT,
            check=False,
        )
        return result.returncode == 0
    except Exception:
        return True


def _run(argv: List[str]) -> Tuple[int, str]:
    """Synchronous best-effort call; (returncode, stdout) or (-1, '') on error."""
    try:
        result = subprocess.run(
            argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=_SYNC_TIMEOUT,
            check=False,
            text=True,
        )
        return result.returncode, (result.stdout or "").strip()
    except Exception:
        return -1, ""


def _fire(argv: List[str]) -> bool:
    """Detached async dispatch; True when the process was spawned."""
    try:
        subprocess.Popen(
            argv,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return True
    except Exception:
        return False


def _swaync_status() -> Optional[bool]:
    rc, out = _run(["swaync-client", "-D"])
    if rc != 0:
        return None
    lowered = out.lower()
    if lowered in ("true", "1", "on", "enabled"):
        return True
    if lowered in ("false", "0", "off", "disabled"):
        return False
    return None


def _swaync_set(enabled: bool) -> bool:
    # Absolute flags first (newer swaync); toggle fallback when the
    # current state is readable but the flags are unsupported.
    flag = "--dnd-on" if enabled else "--dnd-off"
    rc, _ = _run(["swaync-client", flag])
    if rc == 0:
        return True
    current = _swaync_status()
    if current is None or current == enabled:
        return current == enabled
    _fire(["swaync-client", "-d"])
    # The toggle is async; poll briefly for the state to settle.
    deadline = time.time() + 2.0
    while time.time() < deadline:
        rechecked = _swaync_status()
        if rechecked == enabled:
            return True
        time.sleep(0.05)
    return False


def _dunst_status() -> Optional[bool]:
    rc, out = _run(["dunstctl", "is-paused"])
    if rc != 0:
        return None
    lowered = out.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    return None


def _dunst_set(enabled: bool) -> bool:
    return _fire(["dunstctl", "set-paused", "true" if enabled else "false"])


def _mako_status() -> Optional[bool]:
    rc, out = _run(["makoctl", "mode"])
    if rc != 0:
        return None
    modes = {line.strip() for line in out.splitlines() if line.strip()}
    return "do-not-disturb" in modes


def _mako_set(enabled: bool) -> bool:
    if enabled:
        return _fire(["makoctl", "mode", "-a", "do-not-disturb"])
    return _fire(["makoctl", "mode", "-r", "do-not-disturb"])


_STATUS_FN = {
    "swaync": _swaync_status,
    "dunst": _dunst_status,
    "mako": _mako_status,
}

_SET_FN = {
    "swaync": _swaync_set,
    "dunst": _dunst_set,
    "mako": _mako_set,
}


class DndManager:
    """Detects the active notification daemon and toggles its DND mode."""

    def __init__(self, config: PomodoroConfig) -> None:
        self.config = config
        self._provider: Optional[str] = None
        self._detected = False

    def detect_provider(self) -> Optional[str]:
        """Provider name, or None when no supported daemon is available."""
        if self._detected:
            return self._provider
        self._detected = True
        wanted = self.config.dnd_provider
        if wanted != "auto":
            if wanted in _PROVIDERS and _which(_CTL_BIN[wanted]):
                self._provider = wanted
            return self._provider
        for name in _PROVIDERS:
            if _which(_CTL_BIN[name]) and _process_running(_DAEMON_PROC[name]):
                self._provider = name
                break
        return self._provider

    def is_dnd_enabled(self) -> Optional[bool]:
        """Current system DND state; None when unknown."""
        provider = self.detect_provider()
        if provider is None:
            return None
        try:
            return _STATUS_FN[provider]()
        except Exception:
            return None

    def set_dnd(self, enabled: bool) -> bool:
        """Enable/disable DND asynchronously; True when dispatched."""
        provider = self.detect_provider()
        if provider is None:
            return False
        try:
            return bool(_SET_FN[provider](enabled))
        except Exception:
            return False


SUPPORTED_DND_PROVIDERS = _PROVIDERS


def set_dnd(enabled: bool, provider: str = "auto") -> bool:
    """Enables or disables Do Not Disturb mode on the active notification daemon."""
    cfg = PomodoroConfig(dnd_provider=provider)
    mgr = DndManager(cfg)
    return mgr.set_dnd(enabled)


def get_dnd_status(provider: str = "auto") -> Optional[bool]:
    """Queries current DND status from the daemon if supported."""
    cfg = PomodoroConfig(dnd_provider=provider)
    mgr = DndManager(cfg)
    return mgr.is_dnd_enabled()


def detect_dnd_provider() -> Optional[str]:
    """Detects which notification daemon is available and supports DND mode."""
    cfg = PomodoroConfig(dnd_provider="auto")
    mgr = DndManager(cfg)
    return mgr.detect_provider()
