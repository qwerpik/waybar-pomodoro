import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from waybar_pomodoro.stats import PomodoroStats


class TestStats(unittest.TestCase):
    def test_record_session(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            stats_file = Path(tmpdir) / "stats.json"
            stats = PomodoroStats(stats_file)

            self.assertEqual(stats.data["total_completed"], 0)
            self.assertEqual(stats.data["total_focus_seconds"], 0)

            stats.record_session(1800)
            self.assertEqual(stats.data["total_completed"], 1)
            self.assertEqual(stats.data["total_focus_seconds"], 1800)

            # Record another session
            stats.record_session(1800)
            self.assertEqual(stats.data["total_completed"], 2)
            self.assertEqual(stats.data["total_focus_seconds"], 3600)

            today_stats = stats.get_today_stats()
            self.assertEqual(today_stats["completed_sessions"], 2)
            self.assertEqual(today_stats["focus_seconds"], 3600)

    def test_streak_calculation_active_today(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            stats_file = Path(tmpdir) / "stats.json"
            stats = PomodoroStats(stats_file)

            today = date.today()
            # Session today
            stats.record_session(1800, session_date=today)
            self.assertEqual(stats.get_streak(), 1)

            # Session yesterday
            stats.record_session(1800, session_date=today - timedelta(days=1))
            self.assertEqual(stats.get_streak(), 2)

            # Session 2 days ago
            stats.record_session(1800, session_date=today - timedelta(days=2))
            self.assertEqual(stats.get_streak(), 3)

            # Gap at 3 days ago, session at 4 days ago
            stats.record_session(1800, session_date=today - timedelta(days=4))
            # Streak should remain 3 because day 3 is missing
            self.assertEqual(stats.get_streak(), 3)

    def test_streak_preservation_on_new_day_before_first_session(self):
        """
        Verify that on a new day, if today has 0 sessions recorded yet,
        the streak from yesterday is preserved and not reset to 0.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            stats_file = Path(tmpdir) / "stats.json"
            stats = PomodoroStats(stats_file)

            today = date.today()
            yesterday = today - timedelta(days=1)
            two_days_ago = today - timedelta(days=2)

            # User had sessions yesterday and 2 days ago, but NONE today yet
            stats.record_session(1800, session_date=two_days_ago)
            stats.record_session(1800, session_date=yesterday)

            # Streak should be 2, not 0!
            self.assertEqual(stats.get_streak(), 2)

            # If today has an entry with 0 completed sessions (e.g. queried by UI)
            stats.data["days"][today.isoformat()] = {"completed_sessions": 0, "focus_seconds": 0}
            stats._save()
            self.assertEqual(stats.get_streak(), 2)

    def test_format_summary(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            stats_file = Path(tmpdir) / "stats.json"
            stats = PomodoroStats(stats_file)
            stats.record_session(3600)

            summary = stats.format_summary()
            self.assertIn("Completed Sessions : 1", summary)
            self.assertIn("Focus Time         : 60 min", summary)
            self.assertIn("Total Focus Time   : 1.0 hours", summary)

    def test_to_json_and_to_csv(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            stats_file = Path(tmpdir) / "stats.json"
            stats = PomodoroStats(stats_file)
            stats.record_session(1800)

            json_str = stats.to_json()
            data = json.loads(json_str)
            self.assertEqual(data["total_completed"], 1)
            self.assertIn("current_streak", data)
            self.assertIn("today", data)

            csv_str = stats.to_csv()
            self.assertIn("date,completed_sessions,focus_minutes", csv_str)
            self.assertIn(",1,30", csv_str)

    def test_reset(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            stats_file = Path(tmpdir) / "stats.json"
            stats = PomodoroStats(stats_file)
            stats.record_session(1800)
            self.assertEqual(stats.data["total_completed"], 1)

            stats.reset()
            self.assertEqual(stats.data["total_completed"], 0)
            self.assertEqual(stats.data["total_focus_seconds"], 0)
            self.assertEqual(stats.get_streak(), 0)


if __name__ == "__main__":
    unittest.main()
