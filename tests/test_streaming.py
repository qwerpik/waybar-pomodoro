import fcntl
import io
import json
import os
import select
import signal
import tempfile
import threading
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from waybar_pomodoro.config import PomodoroConfig
from waybar_pomodoro.streaming import (
    StreamAlreadyRunning,
    _neutralize_stdout,
    next_tick_delay,
    run_stream,
    single_instance,
)
from waybar_pomodoro.timer import PomodoroTimer
from waybar_pomodoro.watcher import InotifyWatcher


def _make_timer(tmpdir: str) -> PomodoroTimer:
    config = PomodoroConfig(
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
    return PomodoroTimer(config)


class TestInotifyWatcher(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.state_file = Path(self.tmpdir.name) / "state.json"
        self.watcher = InotifyWatcher(self.state_file)
        self.watcher.start()

    def tearDown(self):
        self.watcher.close()
        self.tmpdir.cleanup()

    def test_detects_atomic_rename_write(self):
        timer = _make_timer(self.tmpdir.name)
        timer.save_state(timer._default_state())
        self.assertTrue(self.watcher.consume_events())

    def test_ignores_unrelated_files(self):
        (Path(self.tmpdir.name) / "other.json").write_text("{}", encoding="utf-8")
        self.assertFalse(self.watcher.consume_events())

    def test_fileno_usable_before_close(self):
        self.assertGreaterEqual(self.watcher.fileno(), 0)

    def test_context_manager(self):
        with InotifyWatcher(self.state_file) as watcher:
            self.assertGreaterEqual(watcher.fileno(), 0)


class TestSingleInstance(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.lock = Path(self.tmpdir.name) / "stream.lock"

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_second_acquire_raises(self):
        with single_instance(self.lock):
            with self.assertRaises(StreamAlreadyRunning):
                with single_instance(self.lock):
                    pass

    def test_lock_released_after_exit(self):
        with single_instance(self.lock):
            pass
        with single_instance(self.lock):
            pass

    def test_run_stream_refuses_second_instance(self):
        timer = _make_timer(self.tmpdir.name)
        with open(timer.state_file.parent / "stream.lock", "w", encoding="utf-8") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertEqual(run_stream(timer), 1)


class TestTickAlignment(unittest.TestCase):
    def test_delay_within_one_second(self):
        for now in (10.0, 10.5, 10.999, 1234567890.123):
            delay = next_tick_delay(now)
            self.assertGreater(delay, 0.0)
            self.assertLessEqual(delay, 1.01)

    def test_delay_lands_past_boundary(self):
        delay = next_tick_delay(10.0)
        self.assertAlmostEqual(delay, 1.005, places=3)
        self.assertAlmostEqual(10.999 + next_tick_delay(10.999), 11.005, places=3)


class TestReadOnlyPayload(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.timer = _make_timer(self.tmpdir.name)
        self.timer.start()

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_status_does_not_rewrite_unchanged_state(self):
        first = self.timer.get_status_payload()
        mtime = Path(self.timer.state_file).stat().st_mtime_ns
        second = self.timer.get_status_payload()
        self.assertEqual(first["text"], second["text"])
        self.assertEqual(Path(self.timer.state_file).stat().st_mtime_ns, mtime)

    def test_expired_state_still_transitions(self):
        with self.timer._transaction() as state:
            state["end_time"] = time.time() - 1
        payload = self.timer.get_status_payload()
        self.assertEqual(payload["alt"], "short_break")
        fresh = self.timer.load_state()
        self.assertEqual(fresh["phase"], "short_break")

    def test_is_expired_has_no_side_effects(self):
        with self.timer._transaction() as state:
            before = dict(state)
            state["end_time"] = time.time() - 5
            self.assertTrue(self.timer.is_expired(state))
            state["end_time"] = time.time() + 600
            self.assertFalse(self.timer.is_expired(state))
            state["state"] = "idle"
            self.assertFalse(self.timer.is_expired(state))
            state.update(before)


class TestDriftDetection(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.timer = _make_timer(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_no_stamps_means_no_drift(self):
        state = self.timer._default_state()
        self.assertEqual(self.timer._suspend_drift_seconds(state), 0.0)

    def test_fresh_run_has_negligible_drift(self):
        self.timer.start()
        state = self.timer.load_state()
        self.assertGreater(state["start_monotonic"], 0.0)
        self.assertGreater(state["start_boottime"], 0.0)
        self.assertLess(self.timer._suspend_drift_seconds(state), 5.0)

    def test_pause_clears_run_stamps(self):
        self.timer.start()
        self.timer.pause()
        state = self.timer.load_state()
        self.assertEqual(state["start_monotonic"], 0.0)
        self.assertEqual(state["start_boottime"], 0.0)


class TestStreamLoopInProcess(unittest.TestCase):
    """Drive the real daemon loop in-process: toggle wakes it, SIGTERM stops it."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.timer = _make_timer(self.tmpdir.name)
        self.timer.reset()

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_loop_reacts_and_shuts_down(self):
        stopper = threading.Timer(
            2.5, lambda: os.kill(os.getpid(), signal.SIGTERM)
        )
        toggler = threading.Timer(0.5, self.timer.toggle)
        buf = io.StringIO()
        stopper.start()
        toggler.start()
        try:
            with redirect_stdout(buf):
                code = run_stream(self.timer)
        finally:
            stopper.cancel()
            toggler.cancel()
        self.assertEqual(code, 0)
        lines = [line for line in buf.getvalue().split("\n") if line.strip()]
        self.assertGreaterEqual(len(lines), 2)
        payloads = [json.loads(line) for line in lines]
        for payload in payloads:
            self.assertEqual(
                set(("text", "alt", "tooltip", "class", "percentage")), set(payload)
            )
        self.assertTrue(any(p["alt"] == "work" for p in payloads))

    def test_broken_stdout_exits_zero(self):
        class BrokenOut(io.StringIO):
            def write(self, _s):
                raise BrokenPipeError(32, "Broken pipe")

            def flush(self):
                raise BrokenPipeError(32, "Broken pipe")

        self.timer.start()
        with redirect_stdout(BrokenOut()):
            code = run_stream(self.timer)
        self.assertEqual(code, 0)


class TestStreamFailureBranches(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.timer = _make_timer(self.tmpdir.name)
        self.timer.reset()

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_lock_open_failure_returns_one(self):
        with patch("builtins.open", side_effect=OSError("denied")):
            self.assertEqual(run_stream(self.timer), 1)

    def test_inotify_unavailable_returns_one(self):
        with patch.object(InotifyWatcher, "start", side_effect=OSError("no inotify")):
            with redirect_stdout(io.StringIO()):
                self.assertEqual(run_stream(self.timer), 1)

    def test_select_error_breaks_loop_cleanly(self):
        with patch.object(select, "select", side_effect=OSError("bad fd")):
            with redirect_stdout(io.StringIO()):
                self.assertEqual(run_stream(self.timer), 0)

    def test_neutralize_stdout_variants(self):
        with redirect_stdout(io.StringIO()):
            _neutralize_stdout()  # healthy path: no-op
        with redirect_stdout(io.StringIO()):
            with patch.object(os, "open", side_effect=OSError("no devnull")):
                _neutralize_stdout()
        with redirect_stdout(io.StringIO()):
            with patch.object(os, "dup2", side_effect=OSError("bad fd")):
                with patch.object(os, "close", side_effect=OSError("bad close")):
                    _neutralize_stdout()


if __name__ == "__main__":
    unittest.main()
