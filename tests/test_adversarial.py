"""White-box adversarial tests: corrupt inputs, hostile environments, edge values."""

import json
import os
import stat
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from waybar_pomodoro import dnd, hooks, idle
from waybar_pomodoro.config import PomodoroConfig
from waybar_pomodoro.menu import MenuLauncher, parse_menu_duration
from waybar_pomodoro.notifier import Notifier
from waybar_pomodoro.stats import PomodoroStats
from waybar_pomodoro.timer import PomodoroTimer
from waybar_pomodoro.watcher import InotifyWatcher


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


class TestCorruptState(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.timer = _make_timer(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_garbage_file_falls_back_to_defaults(self):
        Path(self.timer.state_file).write_text("{ this is not json", encoding="utf-8")
        state = self.timer.load_state()
        self.assertEqual(state["state"], "idle")
        self.assertEqual(state["time_remaining"], 25 * 60)
        # Timer still fully operable.
        self.timer.toggle()
        self.assertEqual(self.timer.load_state()["state"], "running")

    def test_wrong_types_are_sanitized(self):
        Path(self.timer.state_file).write_text(
            json.dumps(
                {
                    "state": "bogus",
                    "phase": ["work"],
                    "time_remaining": "soon",
                    "end_time": None,
                    "total_time": -50,
                    "cycle": "many",
                    "paused_by_idle": "yes",
                    "start_monotonic": "x",
                    "boot_id": 12345,
                }
            ),
            encoding="utf-8",
        )
        state = self.timer.load_state()
        self.assertEqual(state["state"], "idle")
        self.assertEqual(state["phase"], "work")
        self.assertEqual(state["time_remaining"], 25 * 60)
        self.assertEqual(state["end_time"], 0.0)
        # Out-of-range numerics clamp to minimums, never crash downstream.
        self.assertEqual(state["total_time"], 1)
        self.assertEqual(state["cycle"], 1)
        self.assertIsInstance(state["paused_by_idle"], bool)
        self.assertEqual(state["start_monotonic"], 0.0)
        self.assertEqual(state["boot_id"], "")

    def test_empty_file_is_idle(self):
        Path(self.timer.state_file).write_text("", encoding="utf-8")
        self.assertEqual(self.timer.load_state()["state"], "idle")


class TestSuspendAndClockEdges(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.timer = _make_timer(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def _run_state(self, **extra) -> dict:
        self.timer.start()
        with self.timer._transaction() as state:
            state.update(extra)
        return self.timer.load_state()

    def test_suspend_drift_suppresses_phantom_session(self):
        import time as _time

        mono = _time.clock_gettime(_time.CLOCK_MONOTONIC)
        bt = _time.clock_gettime(_time.CLOCK_BOOTTIME)
        # Expired 5 min ago but clocks prove 1h of suspend covered it.
        self._run_state(
            end_time=time.time() - 300,
            start_monotonic=mono - 100,
            start_boottime=bt - 3700,
        )
        with self.timer._transaction() as state:
            transitioned = self.timer.check_completion(state)
        self.assertTrue(transitioned)
        self.assertEqual(state["state"], "idle")
        # No phantom stats recorded.
        today, _ = self.timer.stats.get_today_and_streak()
        self.assertEqual(today.get("completed_sessions", 0), 0)

    def test_boot_id_mismatch_falls_back_to_wall_clock(self):
        self.timer.start()
        with self.timer._transaction() as state:
            state["boot_id"] = "definitely-not-this-boot"
            state["end_time"] = time.time() - 5
        payload = self.timer.get_status_payload()
        self.assertEqual(payload["alt"], "short_break")
        # Wall-clock fallback: small overdue completes normally AND records.
        today, _ = self.timer.stats.get_today_and_streak()
        self.assertEqual(today.get("completed_sessions", 0), 1)

    def test_backward_clock_jump_resyncs_instead_of_completing(self):
        self.timer.start()
        with self.timer._transaction() as state:
            state["end_time"] = time.time() + state["total_time"] + 3600
        state = self.timer.load_state()
        self.assertFalse(self.timer.is_expired(state))
        remaining, _ = self.timer.get_remaining_and_percentage(state)
        self.assertEqual(remaining, state["total_time"])

    def test_long_overdue_means_suspend_no_stats(self):
        self.timer.start()
        with self.timer._transaction() as state:
            state["end_time"] = time.time() - 4000
        with self.timer._transaction() as state:
            self.assertTrue(self.timer.check_completion(state))
            self.assertEqual(state["state"], "idle")
        today, _ = self.timer.stats.get_today_and_streak()
        self.assertEqual(today.get("completed_sessions", 0), 0)

    def test_completion_on_idle_and_paused_is_noop(self):
        state = self.timer.load_state()
        before = dict(state)
        self.assertFalse(self.timer.check_completion(state))
        self.assertEqual(state, before)
        self.timer.start()
        self.timer.pause()
        with self.timer._transaction() as state:
            before = dict(state)
            self.assertFalse(self.timer.check_completion(state))
            self.assertEqual(state, before)


class TestDurationEdges(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.timer = _make_timer(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_adjust_huge_negative_clamps_to_one_second(self):
        self.timer.adjust(-100000)
        self.assertEqual(self.timer.load_state()["time_remaining"], 1)

    def test_adjust_huge_positive_on_idle(self):
        self.timer.adjust(100000)
        self.assertEqual(self.timer.load_state()["time_remaining"], 25 * 60 + 100000)

    def test_reset_with_zero_duration_uses_default(self):
        self.timer.reset(duration_seconds=0)
        self.assertEqual(self.timer.load_state()["time_remaining"], 25 * 60)

    def test_broken_custom_format_falls_back(self):
        timer = _make_timer(self.tmpdir.name, style="custom")
        timer.config.format_work = "{nonexistent"
        timer.start()
        payload = timer.get_status_payload()
        self.assertIn("25:00", payload["text"])


class TestWatcherEdges(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.target = Path(self.tmpdir.name) / "sub" / "dir" / "state.json"

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_consume_without_start_is_false(self):
        self.assertFalse(InotifyWatcher(self.target).consume_events())

    def test_fileno_without_start_raises(self):
        with self.assertRaises(ValueError):
            InotifyWatcher(self.target).fileno()

    def test_close_without_start_is_safe(self):
        InotifyWatcher(self.target).close()

    def test_double_start_and_double_close_safe(self):
        watcher = InotifyWatcher(self.target)
        watcher.start()
        watcher.start()
        self.assertGreaterEqual(watcher.fileno(), 0)
        watcher.close()
        watcher.close()

    def test_start_creates_missing_parents(self):
        watcher = InotifyWatcher(self.target)
        watcher.start()
        try:
            self.assertTrue(self.target.parent.is_dir())
        finally:
            watcher.close()


class TestDndEdges(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self._old_path = os.environ.get("PATH", "")
        dnd._which.cache_clear()

    def tearDown(self):
        os.environ["PATH"] = self._old_path
        dnd._which.cache_clear()
        self.tmpdir.cleanup()

    def _bindir_with(self, scripts: dict, bare: bool = False) -> Path:
        bindir = Path(self.tmpdir.name) / "bin"
        bindir.mkdir(exist_ok=True)
        for name, body in scripts.items():
            path = bindir / name
            path.write_text(body, encoding="utf-8")
            path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        # Prepend (never replace): fakes shadow real binaries but keep
        # coreutils available to the fake scripts themselves.
        if bare:
            os.environ["PATH"] = str(bindir)
        else:
            os.environ["PATH"] = str(bindir) + os.pathsep + self._old_path
        dnd._which.cache_clear()
        return bindir

    def test_explicit_provider_binary_missing(self):
        self._bindir_with({})
        mgr = dnd.DndManager(PomodoroConfig(dnd_provider="mako"))
        self.assertIsNone(mgr.detect_provider())
        self.assertFalse(mgr.set_dnd(True))
        self.assertIsNone(mgr.is_dnd_enabled())

    def test_unknown_provider_name_in_config(self):
        mgr = dnd.DndManager(PomodoroConfig(dnd_provider="growl"))
        self.assertIsNone(mgr.detect_provider())

    def test_swaync_toggle_fallback_without_absolute_flags(self):
        state_dir = Path(self.tmpdir.name) / "st"
        state_dir.mkdir()
        os.environ["FAKE_STATE_DIR"] = str(state_dir)
        self.addCleanup(os.environ.pop, "FAKE_STATE_DIR")
        self._bindir_with(
            {
                "swaync-client": (
                    "#!/bin/sh\n"
                    'if [ "$1" = "-D" ]; then\n'
                    '  if [ -f "$FAKE_STATE_DIR/d" ]; then echo true; else echo false; fi\n'
                    "elif [ \"$1\" = \"--dnd-on\" ] || [ \"$1\" = \"--dnd-off\" ]; then\n"
                    "  echo unsupported >&2; exit 1\n"
                    'elif [ "$1" = "-d" ]; then\n'
                    '  if [ -f "$FAKE_STATE_DIR/d" ]; then rm -f "$FAKE_STATE_DIR/d";'
                    ' else touch "$FAKE_STATE_DIR/d"; fi\n'
                    "fi\nexit 0\n"
                ),
            }
        )
        mgr = dnd.DndManager(PomodoroConfig(dnd_provider="swaync"))
        self.assertTrue(mgr.set_dnd(True))
        self.assertTrue(mgr.is_dnd_enabled())
        self.assertTrue(mgr.set_dnd(False))
        self.assertFalse(mgr.is_dnd_enabled())

    def test_dunst_garbage_output_is_unknown(self):
        self._bindir_with({"dunstctl": "#!/bin/sh\necho 'maybe?'\nexit 0\n"})
        mgr = dnd.DndManager(PomodoroConfig(dnd_provider="dunst"))
        self.assertIsNone(mgr.is_dnd_enabled())

    def test_failing_ctl_is_unknown(self):
        self._bindir_with({"makoctl": "#!/bin/sh\nexit 1\n"})
        mgr = dnd.DndManager(PomodoroConfig(dnd_provider="mako"))
        self.assertIsNone(mgr.is_dnd_enabled())

    def test_module_wrappers_delegate(self):
        self._bindir_with({}, bare=True)
        self.assertIsNone(dnd.detect_dnd_provider())
        self.assertIsNone(dnd.get_dnd_status("mako"))
        self.assertFalse(dnd.set_dnd(True, "mako"))

    def test_no_pgrep_trusts_installed_binary(self):
        # _process_running returns True when pgrep itself is missing.
        self._bindir_with({"makoctl": "#!/bin/sh\nexit 0\n"}, bare=True)
        self.assertTrue(dnd._process_running("anything-missing"))


class TestIdleEdges(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.timer = _make_timer(self.tmpdir.name)
        self.config = self.timer.config

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_garbage_state_file_never_raises(self):
        Path(self.timer.state_file).write_text("\x00\xff garbage", encoding="utf-8")
        self.assertEqual(idle.handle_idle_pause(self.timer, self.config), 0)
        self.assertEqual(idle.handle_idle_resume(self.timer, self.config), 0)

    def test_failing_notify_send_means_no_action(self):
        bindir = Path(self.tmpdir.name) / "bin"
        bindir.mkdir()
        fake = bindir / "notify-send"
        fake.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        old_path = os.environ.get("PATH", "")
        os.environ["PATH"] = str(bindir) + os.pathsep + old_path
        try:
            self.assertIsNone(idle._prompt_resume_action(self.timer))
        finally:
            os.environ["PATH"] = old_path

    def test_invalid_mode_falls_back(self):
        self.timer.start()
        idle.handle_idle_pause(self.timer, self.config)
        self.config.idle_resume_mode = "telepathy"
        # Isolate from any real notify-send so the prompt path resolves fast.
        bindir = Path(self.tmpdir.name) / "emptybin"
        bindir.mkdir()
        old_path = os.environ.get("PATH", "")
        os.environ["PATH"] = str(bindir)
        try:
            self.assertEqual(idle.handle_idle_resume(self.timer, self.config), 0)
        finally:
            os.environ["PATH"] = old_path
        state = self.timer.load_state()
        # Garbage mode falls back to prompt; with no notifier it keeps paused.
        self.assertEqual(state["state"], "paused")
        self.assertFalse(state["paused_by_idle"])


class TestHooksEdges(unittest.TestCase):
    def test_popen_failure_is_silent(self):
        with patch("subprocess.Popen", side_effect=OSError("noexec")):
            hooks.dispatch_hook(
                "work_start",
                {"phase": "work", "state": "running"},
                True,
                "/nonexistent-hooks-dir",
                {"work_start": "echo hi"},
            )
            hooks.dispatch_hook("pause", {}, True, None, None)

    def test_unknown_event_never_spawns(self):
        with patch("subprocess.Popen") as mock_popen:
            hooks.dispatch_hook("self-destruct", {}, True, "/tmp", {"self-destruct": "x"})
            mock_popen.assert_not_called()


class TestNotifierCommands(unittest.TestCase):
    def test_send_notification_argv(self):
        notifier = Notifier(notification_timeout=5000, notification_category="timer")
        with patch("shutil.which", return_value="/usr/bin/notify-send"):
            with patch("subprocess.Popen") as mock_popen:
                notifier.send_notification("T", "M", urgency="critical", icon="appointment-soon")
                argv = mock_popen.call_args[0][0]
                self.assertIn("-r", argv)
                self.assertIn("4082", argv)
                self.assertIn("critical", argv)
                self.assertIn("timer", argv)
                self.assertIn("Pomodoro", argv)

    def test_disabled_or_missing_is_silent(self):
        notifier = Notifier(notification_enabled=False)
        with patch("subprocess.Popen") as mock_popen:
            notifier.send_notification("T", "M")
            mock_popen.assert_not_called()
        notifier2 = Notifier(notification_enabled=True)
        with patch("shutil.which", return_value=None):
            with patch("subprocess.Popen") as mock_popen:
                notifier2.send_notification("T", "M")
                mock_popen.assert_not_called()

    def test_play_sound_without_player_or_file(self):
        notifier = Notifier(sound_enabled=True)
        with patch("shutil.which", return_value=None):
            with patch.object(
                Notifier, "_resolve_sound_path", return_value=None
            ):
                # Falls back to terminal bell; must not raise.
                with patch("sys.stdout"):
                    notifier.play_sound("/nonexistent/fake.oga")
        disabled = Notifier(sound_enabled=False)
        disabled.play_sound("/nonexistent/fake.oga")


class TestMenuEdges(unittest.TestCase):
    def test_detect_prefers_fake_rofi(self):
        bindir = Path(tempfile.mkdtemp()) / "bin"
        bindir.mkdir(parents=True)
        fake = bindir / "rofi"
        fake.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        old_path = os.environ.get("PATH", "")
        os.environ["PATH"] = str(bindir) + os.pathsep + old_path
        try:
            self.assertEqual(MenuLauncher.detect_backend(), "rofi")
            self.assertEqual(MenuLauncher.detect_backend("rofi"), "rofi")
        finally:
            os.environ["PATH"] = old_path

    def test_parse_menu_duration_rejects_garbage(self):
        for bad in ("", "abc", "-5m", "1h30m", "++25", "m25", "25mm"):
            self.assertIsNone(parse_menu_duration(bad))
        self.assertEqual(parse_menu_duration("25"), 25 * 60)
        self.assertEqual(parse_menu_duration("90s"), 90)


class TestConfigClamps(unittest.TestCase):
    def test_garbage_values_clamped(self):
        cfg = PomodoroConfig.from_dict(
            {
                "work_duration": 99999,
                "short_break_duration": -3,
                "dnd_provider": "growl",
                "idle_resume_mode": "telepathy",
                "sound_enabled": "yes",
                "auto_dnd": "0",
            }
        )
        self.assertEqual(cfg.work_duration, 1440)
        self.assertEqual(cfg.short_break_duration, 1)
        self.assertEqual(cfg.dnd_provider, "auto")
        self.assertEqual(cfg.idle_resume_mode, "prompt")
        self.assertTrue(cfg.sound_enabled)
        self.assertFalse(cfg.auto_dnd)


class TestCorruptStats(unittest.TestCase):
    def test_garbage_stats_file_defaults(self):
        tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(tmpdir.cleanup)
        stats_file = Path(tmpdir.name) / "stats.json"
        stats_file.write_text("{oops", encoding="utf-8")
        stats = PomodoroStats(str(stats_file))
        today, streak = stats.get_today_and_streak()
        self.assertEqual(today.get("completed_sessions", 0), 0)
        self.assertEqual(streak, 0)
        self.assertIn("Pomodoro Statistics", stats.format_summary())

    def test_wrong_typed_stats_file_no_crash(self):
        tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(tmpdir.cleanup)
        stats_file = Path(tmpdir.name) / "stats.json"
        stats_file.write_text(json.dumps({"days": [1, 2, 3], "streak": "lots"}), encoding="utf-8")
        stats = PomodoroStats(str(stats_file))
        # Corrupt shapes degrade to empty stats; nothing raises.
        today, streak = stats.get_today_and_streak()
        self.assertEqual(today.get("completed_sessions", 0), 0)
        self.assertEqual(streak, 0)
        self.assertIn("Pomodoro Statistics", stats.format_summary())
        stats.render_heatmap()

    def test_wrong_typed_day_entries_sanitized(self):
        tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(tmpdir.cleanup)
        stats_file = Path(tmpdir.name) / "stats.json"
        stats_file.write_text(
            json.dumps(
                {
                    "days": {
                        "2026-01-01": {"completed_sessions": "lots", "focus_seconds": -5},
                        "2026-01-02": 42,
                    },
                    "total_completed": "many",
                }
            ),
            encoding="utf-8",
        )
        stats = PomodoroStats(str(stats_file))
        today, streak = stats.get_today_and_streak()
        self.assertIsInstance(today, dict)
        self.assertIsInstance(streak, int)


if __name__ == "__main__":
    unittest.main()
