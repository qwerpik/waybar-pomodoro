"""
Unit tests for visual and lifecycle event hooks.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from waybar_pomodoro.hooks import dispatch_hook, find_hook_scripts


class TestHooks(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.hooks_dir = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_find_hook_scripts_empty_or_nonexistent(self) -> None:
        non_existent = self.hooks_dir / "does_not_exist"
        self.assertEqual(find_hook_scripts(non_existent, "work_start"), [])
        self.assertEqual(find_hook_scripts(self.hooks_dir, "work_start"), [])

    def test_find_hook_scripts_executable_check(self) -> None:
        script = self.hooks_dir / "on_work_start.sh"
        script.write_text("#!/bin/sh\necho hello\n")
        # Not executable yet
        self.assertEqual(find_hook_scripts(self.hooks_dir, "work_start"), [])

        # Make executable
        os.chmod(script, 0o755)
        found = find_hook_scripts(self.hooks_dir, "work_start")
        self.assertEqual(found, [script])

    def test_find_hook_scripts_precedence(self) -> None:
        s1 = self.hooks_dir / "on_pause.sh"
        s2 = self.hooks_dir / "pause.sh"
        s1.write_text("#!/bin/sh\n")
        s2.write_text("#!/bin/sh\n")
        os.chmod(s1, 0o755)
        os.chmod(s2, 0o755)

        found = find_hook_scripts(self.hooks_dir, "pause")
        self.assertEqual(found, [s1, s2])

    def test_dispatch_hook_disabled_or_unsupported(self) -> None:
        with patch("subprocess.Popen") as mock_popen:
            dispatch_hook(
                "work_start",
                {"state": "running"},
                hooks_enabled=False,
                hooks_dir=str(self.hooks_dir),
            )
            mock_popen.assert_not_called()

            dispatch_hook(
                "unsupported_event",
                {"state": "running"},
                hooks_enabled=True,
                hooks_dir=str(self.hooks_dir),
            )
            mock_popen.assert_not_called()

    def test_dispatch_hook_custom_command(self) -> None:
        custom_hooks = {
            "work_start": "hyprctl dispatch notify 'Focus Started'",
        }
        state = {
            "phase": "work",
            "state": "running",
            "time_remaining": 1500,
            "total_time": 1500,
            "cycle": 2,
        }

        with patch("subprocess.Popen") as mock_popen:
            dispatch_hook(
                "work_start",
                state,
                hooks_enabled=True,
                hooks_dir=str(self.hooks_dir),
                custom_hooks=custom_hooks,
            )
            mock_popen.assert_called_once()
            args, kwargs = mock_popen.call_args
            self.assertEqual(args[0], "hyprctl dispatch notify 'Focus Started'")
            self.assertTrue(kwargs.get("shell"))
            self.assertTrue(kwargs.get("start_new_session"))
            env = kwargs.get("env", {})
            self.assertEqual(env.get("POMODORO_EVENT"), "work_start")
            self.assertEqual(env.get("POMODORO_PHASE"), "work")
            self.assertEqual(env.get("POMODORO_STATE"), "running")
            self.assertEqual(env.get("POMODORO_TIME_REMAINING"), "1500")
            self.assertEqual(env.get("POMODORO_TOTAL_TIME"), "1500")
            self.assertEqual(env.get("POMODORO_CYCLE"), "2")

    def test_dispatch_hook_executable_dir_script(self) -> None:
        script = self.hooks_dir / "on_break_start.sh"
        script.write_text("#!/bin/sh\nnotify-send 'Break'\n")
        os.chmod(script, 0o755)

        state = {
            "phase": "short_break",
            "state": "running",
            "time_remaining": 300,
            "total_time": 300,
            "cycle": 1,
        }

        with patch("subprocess.Popen") as mock_popen:
            dispatch_hook(
                "break_start",
                state,
                hooks_enabled=True,
                hooks_dir=str(self.hooks_dir),
            )
            mock_popen.assert_called_once()
            args, kwargs = mock_popen.call_args
            self.assertEqual(args[0], [str(script)])
            self.assertTrue(kwargs.get("start_new_session"))
            env = kwargs.get("env", {})
            self.assertEqual(env.get("POMODORO_EVENT"), "break_start")
            self.assertEqual(env.get("POMODORO_PHASE"), "short_break")


if __name__ == "__main__":
    unittest.main()
