"""
Unit tests for screen lock and idle detection (idle-pause and idle-resume).
"""

from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from waybar_pomodoro.config import PomodoroConfig
from waybar_pomodoro.idle import handle_idle_pause, handle_idle_resume
from waybar_pomodoro.timer import PomodoroTimer


class TestIdle(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temp_dir.name)
        self.config = PomodoroConfig(
            work_duration=25,
            state_file=str(self.base_dir / "state.json"),
            stats_file=str(self.base_dir / "stats.json"),
            idle_resume_notify=True,
            notification_enabled=True,
            sound_enabled=False,
            waybar_signal=0,
            auto_dnd=True,
            dnd_provider="dunst",
        )
        self.timer = PomodoroTimer(self.config)
        self.dnd_patcher = patch.object(self.timer, "_apply_dnd")
        self.hook_patcher = patch.object(self.timer, "_dispatch_event")
        self.mock_dnd = self.dnd_patcher.start()
        self.mock_hook = self.hook_patcher.start()

    def tearDown(self) -> None:
        self.dnd_patcher.stop()
        self.hook_patcher.stop()
        self.temp_dir.cleanup()

    def test_idle_pause_when_running(self) -> None:
        self.timer.start()
        state = self.timer.load_state()
        self.assertEqual(state["state"], "running")
        self.assertFalse(state["paused_by_idle"])

        self.mock_dnd.reset_mock()
        self.mock_hook.reset_mock()

        ok, msg = handle_idle_pause(self.timer)
        self.assertTrue(ok)
        self.assertIn("paused", msg.lower())
        self.mock_dnd.assert_called_once()
        self.mock_hook.assert_called_once_with("pause", unittest.mock.ANY)

        paused_state = self.timer.load_state()
        self.assertEqual(paused_state["state"], "paused")
        self.assertTrue(paused_state["paused_by_idle"])
        self.assertEqual(paused_state["start_monotonic"], 0.0)

    def test_idle_pause_when_already_paused_or_idle(self) -> None:
        # Initial is idle
        ok, msg = handle_idle_pause(self.timer)
        self.assertFalse(ok)
        self.assertIn("nothing to pause", msg.lower())

        # Start then manual pause
        self.timer.start()
        self.timer.pause()
        ok2, msg2 = handle_idle_pause(self.timer)
        self.assertFalse(ok2)
        state = self.timer.load_state()
        self.assertEqual(state["state"], "paused")
        self.assertFalse(state["paused_by_idle"])

    def test_idle_resume_after_idle_pause(self) -> None:
        self.timer.start()
        handle_idle_pause(self.timer)

        self.mock_dnd.reset_mock()
        self.mock_hook.reset_mock()

        with patch.object(self.timer.notifier, "send_notification") as mock_notify:
            ok, msg = handle_idle_resume(self.timer, auto_resume=True)
            self.assertTrue(ok)
            self.assertIn("resumed", msg.lower())
            self.mock_dnd.assert_called_once()
            self.mock_hook.assert_called_once_with("resume", unittest.mock.ANY)
            mock_notify.assert_called_once()

        resumed_state = self.timer.load_state()
        self.assertEqual(resumed_state["state"], "running")
        self.assertFalse(resumed_state["paused_by_idle"])
        self.assertGreater(resumed_state["end_time"], time.time())

    def test_idle_resume_preserves_manual_pause(self) -> None:
        self.timer.start()
        self.timer.pause()  # manual pause, paused_by_idle is False

        with patch.object(self.timer.notifier, "send_notification") as mock_notify:
            ok, msg = handle_idle_resume(self.timer, auto_resume=True)
            self.assertFalse(ok)
            self.assertIn("preserving current state", msg.lower())
            mock_notify.assert_not_called()

        state = self.timer.load_state()
        self.assertEqual(state["state"], "paused")
        self.assertFalse(state["paused_by_idle"])


if __name__ == "__main__":
    unittest.main()
