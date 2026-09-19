"""
Unit tests for Focus Do Not Disturb (DND) integration.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from waybar_pomodoro.config import PomodoroConfig
from waybar_pomodoro.dnd import (
    DndManager,
    detect_dnd_provider,
    get_dnd_status,
    set_dnd,
)


class TestDndManager(unittest.TestCase):
    def test_detect_provider_explicit(self) -> None:
        config = PomodoroConfig(dnd_provider="dunst")
        mgr = DndManager(config)
        with patch("waybar_pomodoro.dnd._which", return_value="/usr/bin/dunstctl"):
            self.assertEqual(mgr.detect_provider(), "dunst")

    def test_detect_provider_auto(self) -> None:
        config = PomodoroConfig(dnd_provider="auto")
        mgr = DndManager(config)

        def mock_which(bin_name: str) -> str | None:
            if bin_name == "dunstctl":
                return "/usr/bin/dunstctl"
            return None

        def mock_proc(proc_name: str) -> bool:
            return proc_name == "dunst"

        with (
            patch("waybar_pomodoro.dnd._which", side_effect=mock_which),
            patch("waybar_pomodoro.dnd._process_running", side_effect=mock_proc),
        ):
            self.assertEqual(mgr.detect_provider(), "dunst")

    def test_detect_provider_none(self) -> None:
        config = PomodoroConfig(dnd_provider="auto")
        mgr = DndManager(config)
        with (
            patch("waybar_pomodoro.dnd._which", return_value=None),
            patch("waybar_pomodoro.dnd._process_running", return_value=False),
        ):
            self.assertIsNone(mgr.detect_provider())

    def test_set_dnd_swaync(self) -> None:
        config = PomodoroConfig(dnd_provider="swaync")
        mgr = DndManager(config)
        with (
            patch.object(mgr, "detect_provider", return_value="swaync"),
            patch("waybar_pomodoro.dnd._run", return_value=(0, "")),
        ):
            self.assertTrue(mgr.set_dnd(True))
            self.assertTrue(mgr.set_dnd(False))

    def test_set_dnd_dunst(self) -> None:
        config = PomodoroConfig(dnd_provider="dunst")
        mgr = DndManager(config)
        with (
            patch.object(mgr, "detect_provider", return_value="dunst"),
            patch("waybar_pomodoro.dnd._fire", return_value=True) as mock_fire,
        ):
            self.assertTrue(mgr.set_dnd(True))
            mock_fire.assert_called_with(["dunstctl", "set-paused", "true"])
            self.assertTrue(mgr.set_dnd(False))
            mock_fire.assert_called_with(["dunstctl", "set-paused", "false"])

    def test_set_dnd_mako(self) -> None:
        config = PomodoroConfig(dnd_provider="mako")
        mgr = DndManager(config)
        with (
            patch.object(mgr, "detect_provider", return_value="mako"),
            patch("waybar_pomodoro.dnd._fire", return_value=True) as mock_fire,
        ):
            self.assertTrue(mgr.set_dnd(True))
            mock_fire.assert_called_with(["makoctl", "mode", "-a", "do-not-disturb"])
            self.assertTrue(mgr.set_dnd(False))
            mock_fire.assert_called_with(["makoctl", "mode", "-r", "do-not-disturb"])

    def test_is_dnd_enabled_swaync(self) -> None:
        config = PomodoroConfig(dnd_provider="swaync")
        mgr = DndManager(config)
        with (
            patch.object(mgr, "detect_provider", return_value="swaync"),
            patch("waybar_pomodoro.dnd._run", return_value=(0, "true")),
        ):
            self.assertTrue(mgr.is_dnd_enabled())

        with (
            patch.object(mgr, "detect_provider", return_value="swaync"),
            patch("waybar_pomodoro.dnd._run", return_value=(0, "false")),
        ):
            self.assertFalse(mgr.is_dnd_enabled())

    def test_is_dnd_enabled_dunst(self) -> None:
        config = PomodoroConfig(dnd_provider="dunst")
        mgr = DndManager(config)
        with (
            patch.object(mgr, "detect_provider", return_value="dunst"),
            patch("waybar_pomodoro.dnd._run", return_value=(0, "true")),
        ):
            self.assertTrue(mgr.is_dnd_enabled())

    def test_is_dnd_enabled_mako(self) -> None:
        config = PomodoroConfig(dnd_provider="mako")
        mgr = DndManager(config)
        with (
            patch.object(mgr, "detect_provider", return_value="mako"),
            patch("waybar_pomodoro.dnd._run", return_value=(0, "default\ndo-not-disturb")),
        ):
            self.assertTrue(mgr.is_dnd_enabled())

        with (
            patch.object(mgr, "detect_provider", return_value="mako"),
            patch("waybar_pomodoro.dnd._run", return_value=(0, "default")),
        ):
            self.assertFalse(mgr.is_dnd_enabled())

    def test_top_level_helpers(self) -> None:
        with patch.object(DndManager, "set_dnd", return_value=True) as mock_set:
            self.assertTrue(set_dnd(True, "dunst"))
            mock_set.assert_called_once_with(True)

        with patch.object(DndManager, "is_dnd_enabled", return_value=False) as mock_status:
            self.assertFalse(get_dnd_status("dunst"))
            mock_status.assert_called_once()

        with patch.object(DndManager, "detect_provider", return_value="mako") as mock_det:
            self.assertEqual(detect_dnd_provider(), "mako")
            mock_det.assert_called_once()


if __name__ == "__main__":
    unittest.main()
