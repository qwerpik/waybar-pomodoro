from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from waybar_pomodoro.config import PomodoroConfig
from waybar_pomodoro.menu import MenuLauncher, parse_menu_duration
from waybar_pomodoro.timer import PomodoroTimer


class TestMenuLauncher(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.config = PomodoroConfig(
            state_file=str(Path(self.tmpdir.name) / "state.json"),
            stats_file=str(Path(self.tmpdir.name) / "stats.json"),
        )
        self.timer = PomodoroTimer(self.config)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_parse_menu_duration(self):
        self.assertEqual(parse_menu_duration("25m"), 1500)
        self.assertEqual(parse_menu_duration("25min"), 1500)
        self.assertEqual(parse_menu_duration("10"), 600)
        self.assertEqual(parse_menu_duration("30s"), 30)
        self.assertEqual(parse_menu_duration("120sec"), 120)
        self.assertIsNone(parse_menu_duration("invalid"))
        self.assertIsNone(parse_menu_duration(""))

    def test_detect_backend_preferred(self):
        with patch("shutil.which", return_value="/usr/bin/wofi"):
            backend = MenuLauncher.detect_backend(preferred="wofi")
            self.assertEqual(backend, "wofi")

    def test_detect_backend_auto(self):
        def fake_which(cmd):
            if cmd == "fuzzel":
                return "/usr/bin/fuzzel"
            return None

        with patch("shutil.which", side_effect=fake_which):
            backend = MenuLauncher.detect_backend()
            self.assertEqual(backend, "fuzzel")

    def test_build_menu_items_idle(self):
        items = MenuLauncher.build_menu_items(self.timer)
        actions = [item[1] for item in items]

        self.assertIn("start", actions)
        self.assertIn("skip", actions)
        self.assertIn("reset", actions)
        self.assertIn("preset:15", actions)
        self.assertIn("preset:25", actions)
        self.assertIn("preset:45", actions)
        self.assertIn("preset:60", actions)
        self.assertIn("adjust:+5m", actions)
        self.assertIn("adjust:-5m", actions)
        self.assertIn("study_tracker_terminal", actions)
        self.assertIn("study_tracker_chart", actions)

    def test_build_menu_items_running(self):
        self.timer.start()
        items = MenuLauncher.build_menu_items(self.timer)
        actions = [item[1] for item in items]

        self.assertIn("pause", actions)
        self.assertIn("stop", actions)
        self.assertNotIn("start", actions)

    def test_build_menu_items_paused(self):
        self.timer.start()
        self.timer.pause()
        items = MenuLauncher.build_menu_items(self.timer)
        actions = [item[1] for item in items]

        self.assertIn("resume", actions)
        self.assertIn("stop", actions)

    def test_execute_action_presets(self):
        with patch.object(self.timer, "start") as mock_start:
            MenuLauncher.execute_action(self.timer, "preset:45")
            mock_start.assert_called_once_with(duration_seconds=2700)

    def test_execute_action_adjust(self):
        with patch.object(self.timer, "adjust") as mock_adjust:
            MenuLauncher.execute_action(self.timer, "adjust:+5m")
            mock_adjust.assert_called_once_with(300)

        with patch.object(self.timer, "adjust") as mock_adjust:
            MenuLauncher.execute_action(self.timer, "adjust:-5m")
            mock_adjust.assert_called_once_with(-300)

    def test_execute_action_custom_duration(self):
        with patch.object(MenuLauncher, "prompt_input", return_value="50m"):
            with patch.object(self.timer, "start") as mock_start:
                MenuLauncher.execute_action(self.timer, "custom_duration")
                mock_start.assert_called_once_with(duration_seconds=3000)

    def test_run_launcher_not_found(self):
        with patch.object(MenuLauncher, "detect_backend", return_value=None):
            with patch.object(self.timer.notifier, "send_notification"):
                ret = MenuLauncher.run(self.timer)
                self.assertEqual(ret, 1)

    def test_run_launcher_selection(self):
        with patch.object(MenuLauncher, "detect_backend", return_value="rofi"):
            with patch.object(MenuLauncher, "show_menu", return_value="⚡ 15m Sprint"):
                with patch.object(self.timer, "start") as mock_start:
                    ret = MenuLauncher.run(self.timer)
                    self.assertEqual(ret, 0)
                    mock_start.assert_called_once_with(duration_seconds=900)


if __name__ == "__main__":
    unittest.main()
