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

    def test_get_today_and_streak(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            stats_file = Path(tmpdir) / "stats.json"
            stats = PomodoroStats(stats_file)
            stats.record_session(1800)

            today_stats, streak = stats.get_today_and_streak()
            self.assertEqual(today_stats["completed_sessions"], 1)
            self.assertEqual(today_stats["focus_seconds"], 1800)
            self.assertEqual(streak, 1)

    def test_stats_file_permissions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            stats_file = Path(tmpdir) / "sub" / "stats.json"
            stats = PomodoroStats(stats_file)
            stats.record_session(1800)

            mode = stats_file.stat().st_mode & 0o777
            self.assertEqual(mode, 0o600)
            dir_mode = stats_file.parent.stat().st_mode & 0o777
            self.assertEqual(dir_mode, 0o700)

    def test_longest_streak(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            stats_file = Path(tmpdir) / "stats.json"
            stats = PomodoroStats(stats_file)
            today = date.today()

            self.assertEqual(stats.get_longest_streak(), 0)

            # 3 days run (days -10, -9, -8)
            stats.record_session(1800, session_date=today - timedelta(days=10))
            stats.record_session(1800, session_date=today - timedelta(days=9))
            stats.record_session(1800, session_date=today - timedelta(days=8))
            self.assertEqual(stats.get_longest_streak(), 3)

            # 5 days run (days -5, -4, -3, -2, -1)
            for i in range(1, 6):
                stats.record_session(1800, session_date=today - timedelta(days=i))
            self.assertEqual(stats.get_longest_streak(), 5)

    def test_contribution_grid_structure(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            stats_file = Path(tmpdir) / "stats.json"
            stats = PomodoroStats(stats_file)
            today = date.today()

            # Record sessions with varied intensity
            stats.record_session(1800, session_date=today)
            stats.record_session(1800, session_date=today)
            stats.record_session(1800, session_date=today)  # 3 sessions -> level 2

            grid = stats.get_contribution_grid(weeks=12, end_date=today)
            self.assertEqual(grid["weeks"], 12)
            self.assertEqual(len(grid["matrix"]), 12)
            # Each week must have exactly 7 rows (Mon-Sun)
            for col in grid["matrix"]:
                self.assertEqual(len(col), 7)

            # Check today's cell level
            last_col = grid["matrix"][-1]
            today_row = today.weekday()
            today_cell = last_col[today_row]
            self.assertEqual(today_cell["sessions"], 3)
            self.assertEqual(today_cell["level"], 2)

    def test_render_heatmap(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            stats_file = Path(tmpdir) / "stats.json"
            stats = PomodoroStats(stats_file)
            stats.record_session(1800)

            output = stats.render_heatmap(weeks=20, use_color=False)
            self.assertIn("POMODORO STUDY TRACKER", output)
            self.assertIn("Mon", output)
            self.assertIn("Wed", output)
            self.assertIn("Fri", output)
            self.assertIn("Less", output)
            self.assertIn("More", output)
            self.assertIn("Total Focus:", output)
            self.assertIn("Current Streak:", output)

            # Test with color enabled
            colored_output = stats.render_heatmap(weeks=20, use_color=True)
            self.assertIn("\033[", colored_output)

    def test_render_svg_and_export_chart(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            stats_file = Path(tmpdir) / "stats.json"
            stats = PomodoroStats(stats_file)
            stats.record_session(3600)

            # Test different themes
            for theme in ["github-dark", "catppuccin", "gruvbox", "tokyo-night", "nord"]:
                svg = stats.render_svg(weeks=26, theme=theme)
                self.assertTrue(svg.startswith("<svg"))
                self.assertTrue(svg.endswith("</svg>"))
                self.assertIn("Pomodoro Study Tracker", svg)

            # Test export to file
            export_path = Path(tmpdir) / "custom_chart.svg"
            saved = stats.export_chart(output_path=export_path, open_browser=False)
            self.assertEqual(saved, export_path)
            self.assertTrue(export_path.is_file())
            content = export_path.read_text(encoding="utf-8")
            self.assertIn("<svg", content)


if __name__ == "__main__":
    unittest.main()
