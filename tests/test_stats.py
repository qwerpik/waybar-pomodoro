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

    def test_streak_calculation(self):
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

    def test_format_summary(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            stats_file = Path(tmpdir) / "stats.json"
            stats = PomodoroStats(stats_file)
            stats.record_session(3600)

            summary = stats.format_summary()
            self.assertIn("Completed Sessions : 1", summary)
            self.assertIn("Focus Time         : 60 min", summary)
            self.assertIn("Total Focus Time   : 1.0 hours", summary)


if __name__ == "__main__":
    unittest.main()
