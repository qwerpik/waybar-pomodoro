import os
import stat
import tempfile
import time
import unittest
from pathlib import Path

from waybar_pomodoro import dnd
from waybar_pomodoro.config import PomodoroConfig
from waybar_pomodoro.timer import PomodoroTimer

MAKOCTL = """#!/bin/sh
# Fake makoctl: DND state in $FAKE_STATE_DIR/mako_dnd
if [ "$1" = "mode" ] && [ $# -eq 1 ]; then
    if [ -f "$FAKE_STATE_DIR/mako_dnd" ]; then echo "do-not-disturb"; else echo "default"; fi
elif [ "$1" = "mode" ] && [ "$2" = "-a" ]; then
    touch "$FAKE_STATE_DIR/mako_dnd"
elif [ "$1" = "mode" ] && [ "$2" = "-r" ]; then
    rm -f "$FAKE_STATE_DIR/mako_dnd"
fi
exit 0
"""

DUNSTCTL = """#!/bin/sh
# Fake dunstctl: paused state in $FAKE_STATE_DIR/dunst_paused
if [ "$1" = "is-paused" ]; then
    if [ -f "$FAKE_STATE_DIR/dunst_paused" ]; then echo "true"; else echo "false"; fi
elif [ "$1" = "set-paused" ] && [ "$2" = "true" ]; then
    touch "$FAKE_STATE_DIR/dunst_paused"
elif [ "$1" = "set-paused" ]; then
    rm -f "$FAKE_STATE_DIR/dunst_paused"
fi
exit 0
"""

SWAYNC_CLIENT = """#!/bin/sh
# Fake swaync-client: DND state in $FAKE_STATE_DIR/swaync_dnd
if [ "$1" = "-D" ]; then
    if [ -f "$FAKE_STATE_DIR/swaync_dnd" ]; then echo "true"; else echo "false"; fi
elif [ "$1" = "--dnd-on" ]; then
    touch "$FAKE_STATE_DIR/swaync_dnd"
elif [ "$1" = "--dnd-off" ]; then
    rm -f "$FAKE_STATE_DIR/swaync_dnd"
elif [ "$1" = "-d" ]; then
    if [ -f "$FAKE_STATE_DIR/swaync_dnd" ]; then
        rm -f "$FAKE_STATE_DIR/swaync_dnd"
    else
        touch "$FAKE_STATE_DIR/swaync_dnd"
    fi
fi
exit 0
"""

PGREP = """#!/bin/sh
# Fake pgrep: pretend every queried daemon is running
exit 0
"""


def _make_timer(tmpdir: str, **overrides) -> PomodoroTimer:
    kwargs = dict(
        work_duration=25,
        short_break_duration=5,
        long_break_duration=15,
        cycles_before_long_break=4,
        style="minimal",
        sound_enabled=False,
        notification_enabled=False,
        waybar_signal=0,
        state_file=str(Path(tmpdir) / "state.json"),
        stats_file=str(Path(tmpdir) / "stats.json"),
    )
    kwargs.update(overrides)
    return PomodoroTimer(PomodoroConfig(**kwargs))


class FakeBinEnv(unittest.TestCase):
    bins = ("makoctl", "dunstctl", "swaync-client", "pgrep")

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.bindir = Path(self.tmpdir.name) / "bin"
        self.statedir = Path(self.tmpdir.name) / "daemons"
        self.bindir.mkdir()
        self.statedir.mkdir()
        scripts = {
            "makoctl": MAKOCTL,
            "dunstctl": DUNSTCTL,
            "swaync-client": SWAYNC_CLIENT,
            "pgrep": PGREP,
        }
        for name in self.bins:
            path = self.bindir / name
            path.write_text(scripts[name], encoding="utf-8")
            path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        self._old_path = os.environ.get("PATH", "")
        self._old_fake_state = os.environ.get("FAKE_STATE_DIR")
        os.environ["PATH"] = str(self.bindir) + os.pathsep + self._old_path
        os.environ["FAKE_STATE_DIR"] = str(self.statedir)
        dnd._which.cache_clear()

    def tearDown(self):
        os.environ["PATH"] = self._old_path
        if self._old_fake_state is None:
            os.environ.pop("FAKE_STATE_DIR", None)
        else:
            os.environ["FAKE_STATE_DIR"] = self._old_fake_state
        dnd._which.cache_clear()
        self.tmpdir.cleanup()

    def marker(self, name: str) -> Path:
        return self.statedir / name

    def wait_for(self, cond, timeout: float = 5.0) -> bool:
        """Poll a condition; async Popen dispatch needs a grace period."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if cond():
                return True
            time.sleep(0.05)
        return bool(cond())


class TestDetectProvider(FakeBinEnv):
    bins = ("makoctl", "dunstctl", "swaync-client", "pgrep")

    def test_auto_prefers_swaync(self):
        mgr = dnd.DndManager(PomodoroConfig())
        self.assertEqual(mgr.detect_provider(), "swaync")

    def test_explicit_provider(self):
        mgr = dnd.DndManager(PomodoroConfig(dnd_provider="mako"))
        self.assertEqual(mgr.detect_provider(), "mako")

    def test_no_daemons_returns_none(self):
        os.environ["PATH"] = str(self.bindir)
        for name in ("makoctl", "dunstctl", "swaync-client", "pgrep"):
            (self.bindir / name).unlink()
        dnd._which.cache_clear()
        mgr = dnd.DndManager(PomodoroConfig())
        self.assertIsNone(mgr.detect_provider())
        self.assertIsNone(mgr.is_dnd_enabled())
        self.assertFalse(mgr.set_dnd(True))


class TestMakoProvider(FakeBinEnv):
    bins = ("makoctl", "pgrep")

    def test_status_roundtrip(self):
        mgr = dnd.DndManager(PomodoroConfig(dnd_provider="mako"))
        self.assertFalse(mgr.is_dnd_enabled())
        self.assertTrue(mgr.set_dnd(True))
        self.assertTrue(self.wait_for(lambda: self.marker("mako_dnd").exists()))
        self.assertTrue(mgr.is_dnd_enabled())
        self.assertTrue(mgr.set_dnd(False))
        self.assertTrue(self.wait_for(lambda: not self.marker("mako_dnd").exists()))
        self.assertFalse(mgr.is_dnd_enabled())


class TestDunstProvider(FakeBinEnv):
    bins = ("dunstctl", "pgrep")

    def test_status_roundtrip(self):
        mgr = dnd.DndManager(PomodoroConfig(dnd_provider="dunst"))
        self.assertEqual(mgr.detect_provider(), "dunst")
        self.assertFalse(mgr.is_dnd_enabled())
        mgr.set_dnd(True)
        self.assertTrue(self.wait_for(lambda: mgr.is_dnd_enabled()))
        mgr.set_dnd(False)
        self.assertTrue(self.wait_for(lambda: mgr.is_dnd_enabled() is False))


class TestSwayncProvider(FakeBinEnv):
    bins = ("swaync-client", "pgrep")

    def test_status_roundtrip(self):
        mgr = dnd.DndManager(PomodoroConfig(dnd_provider="swaync"))
        self.assertFalse(mgr.is_dnd_enabled())
        self.assertTrue(mgr.set_dnd(True))
        self.assertTrue(self.wait_for(lambda: mgr.is_dnd_enabled()))
        self.assertTrue(mgr.set_dnd(False))
        self.assertTrue(self.wait_for(lambda: mgr.is_dnd_enabled() is False))


class TestTimerDndIntegration(FakeBinEnv):
    bins = ("makoctl", "pgrep")

    def test_work_claims_dnd_break_releases(self):
        timer = _make_timer(self.tmpdir.name, auto_dnd=True, dnd_provider="mako")
        timer.start()
        state = timer.load_state()
        self.assertTrue(state["dnd_active"])
        self.assertTrue(self.wait_for(lambda: self.marker("mako_dnd").exists()))
        timer.reset()
        state = timer.load_state()
        self.assertFalse(state["dnd_active"])
        self.assertTrue(self.wait_for(lambda: not self.marker("mako_dnd").exists()))

    def test_users_own_dnd_is_never_claimed_nor_released(self):
        self.marker("mako_dnd").touch()
        timer = _make_timer(self.tmpdir.name, auto_dnd=True, dnd_provider="mako")
        timer.start()
        state = timer.load_state()
        self.assertFalse(state["dnd_active"])
        timer.reset()
        # Still on: it was never ours to turn off.
        self.assertTrue(self.marker("mako_dnd").exists())

    def test_pause_keeps_dnd(self):
        timer = _make_timer(self.tmpdir.name, auto_dnd=True, dnd_provider="mako")
        timer.start()
        self.assertTrue(self.wait_for(lambda: self.marker("mako_dnd").exists()))
        timer.pause()
        state = timer.load_state()
        self.assertTrue(state["dnd_active"])
        self.assertTrue(self.marker("mako_dnd").exists())

    def test_auto_dnd_off_is_total_noop(self):
        timer = _make_timer(self.tmpdir.name)
        timer.start()
        self.assertFalse(timer.load_state()["dnd_active"])
        self.assertFalse(self.marker("mako_dnd").exists())


if __name__ == "__main__":
    unittest.main()
