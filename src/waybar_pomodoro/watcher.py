"""
Event-driven inotify monitoring of the state file's parent directory.

Pure standard library (ctypes -> libc). Lets the streaming daemon react to
state changes in sub-milliseconds with zero polling.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import os
import struct
from pathlib import Path
from typing import Optional

# inotify masks we care about: our state writes are atomic renames
# (MOVED_FROM tmp + MOVED_TO target) while external editors typically
# produce CLOSE_WRITE / CREATE.
_IN_CLOSE_WRITE = 0x8
_IN_MOVED_FROM = 0x40
_IN_MOVED_TO = 0x80
_IN_CREATE = 0x100
_WATCH_MASK = _IN_CLOSE_WRITE | _IN_MOVED_FROM | _IN_MOVED_TO | _IN_CREATE

# struct inotify_event header: int wd, uint32 mask, uint32 cookie, uint32 len
_EVENT_HEADER = struct.Struct("iIII")


def _load_libc() -> "ctypes.CDLL":
    name = ctypes.util.find_library("c")
    if not name:
        raise OSError("could not locate libc for inotify")
    libc = ctypes.CDLL(name, use_errno=True)
    libc.inotify_init1.argtypes = [ctypes.c_int]
    libc.inotify_init1.restype = ctypes.c_int
    libc.inotify_add_watch.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_uint32]
    libc.inotify_add_watch.restype = ctypes.c_int
    libc.inotify_rm_watch.argtypes = [ctypes.c_int, ctypes.c_int]
    libc.inotify_rm_watch.restype = ctypes.c_int
    return libc


class InotifyWatcher:
    """Watches the parent directory of ``target_path`` for writes to that file.

    Usage:
        watcher = InotifyWatcher(state_file)
        watcher.start()
        r, _, _ = select.select([watcher.fileno()], [], [], timeout)
        if r:
            changed = watcher.consume_events()
        watcher.close()
    """

    def __init__(self, target_path: Path) -> None:
        self.target_path = target_path
        self._fd: Optional[int] = None
        self._wd: Optional[int] = None
        self._libc: Optional["ctypes.CDLL"] = None

    def start(self) -> None:
        """Initialize the inotify descriptor and install the directory watch."""
        if self._fd is not None:
            return
        self.target_path.parent.mkdir(parents=True, exist_ok=True)
        libc = _load_libc()
        fd = libc.inotify_init1(0)
        if fd < 0:
            raise OSError("inotify_init1 failed")
        wd = libc.inotify_add_watch(fd, os.fsencode(str(self.target_path.parent)), _WATCH_MASK)
        if wd < 0:
            try:
                os.close(fd)
            except OSError:
                pass
            raise OSError("inotify_add_watch failed")
        self._libc = libc
        self._fd = fd
        self._wd = wd

    def fileno(self) -> int:
        """File descriptor for multiplexing in a selector / select call."""
        if self._fd is None:
            raise ValueError("watcher not started")
        return self._fd

    def consume_events(self) -> bool:
        """Read pending events; True if the target file was (likely) modified."""
        if self._fd is None:
            return False
        try:
            chunk = os.read(self._fd, 65536)
        except (BlockingIOError, InterruptedError):
            return False
        except OSError:
            return False
        if not chunk:
            return False
        target_name = os.fsencode(self.target_path.name)
        offset = 0
        while offset + _EVENT_HEADER.size <= len(chunk):
            _wd, mask, _cookie, name_len = _EVENT_HEADER.unpack_from(chunk, offset)
            offset += _EVENT_HEADER.size
            name = chunk[offset : offset + name_len].split(b"\x00", 1)[0]
            offset += name_len
            if name == target_name and (mask & _WATCH_MASK):
                return True
        return False

    def close(self) -> None:
        """Remove the watch and close the inotify descriptor."""
        fd, wd = self._fd, self._wd
        self._fd = None
        self._wd = None
        if fd is None:
            return
        try:
            if wd is not None and self._libc is not None:
                self._libc.inotify_rm_watch(fd, wd)
        except Exception:
            pass
        finally:
            self._libc = None
            try:
                os.close(fd)
            except OSError:
                pass

    def __enter__(self) -> "InotifyWatcher":
        self.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
