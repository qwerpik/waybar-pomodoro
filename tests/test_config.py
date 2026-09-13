import argparse
import json
import tempfile
import unittest
from pathlib import Path

from waybar_pomodoro.config import PomodoroConfig, load_config, save_config
from waybar_pomodoro.cli import apply_overrides


class TestConfig(unittest.TestCase):
    def test_default_config(self):
        cfg = PomodoroConfig()
        self.assertEqual(cfg.work_duration, 30)
        self.assertEqual(cfg.short_break_duration, 5)
        self.assertEqual(cfg.long_break_duration, 15)
        self.assertEqual(cfg.cycles_before_long_break, 4)
        self.assertEqual(cfg.style, "minimal")
        self.assertTrue(cfg.sound_enabled)
        self.assertTrue(cfg.notification_enabled)

    def test_to_dict_and_from_dict(self):
        cfg = PomodoroConfig(work_duration=45, style="icon")
        data = cfg.to_dict()
        self.assertEqual(data["work_duration"], 45)
        self.assertEqual(data["style"], "icon")

        # from_dict with extra keys should ignore unexpected fields
        data["unknown_field"] = "ignored"
        restored = PomodoroConfig.from_dict(data)
        self.assertEqual(restored.work_duration, 45)
        self.assertEqual(restored.style, "icon")

    def test_save_and_load_config(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.json"
            cfg = PomodoroConfig(work_duration=25, short_break_duration=10)
            save_config(cfg, config_file)

            self.assertTrue(config_file.is_file())
            loaded = load_config(config_file)
            self.assertEqual(loaded.work_duration, 25)
            self.assertEqual(loaded.short_break_duration, 10)

    def test_load_corrupted_config(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.json"
            with open(config_file, "w") as f:
                f.write("{ invalid json")

            loaded = load_config(config_file)
            # Should fall back to defaults
            self.assertEqual(loaded.work_duration, 30)

    def test_apply_overrides(self):
        cfg = PomodoroConfig()
        args = argparse.Namespace(work=50, short_break=8, long_break=20, style="icon")
        updated = apply_overrides(cfg, args)
        self.assertEqual(updated.work_duration, 50)
        self.assertEqual(updated.short_break_duration, 8)
        self.assertEqual(updated.long_break_duration, 20)
        self.assertEqual(updated.style, "icon")


if __name__ == "__main__":
    unittest.main()
