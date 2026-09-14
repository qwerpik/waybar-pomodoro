import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from waybar_pomodoro.cli import main, parse_duration_delta


class TestCLI(unittest.TestCase):
    def test_parse_duration_delta(self):
        self.assertEqual(parse_duration_delta("+1m"), 60)
        self.assertEqual(parse_duration_delta("-2min"), -120)
        self.assertEqual(parse_duration_delta("+30s"), 30)
        self.assertEqual(parse_duration_delta("-45sec"), -45)
        self.assertEqual(parse_duration_delta("5"), 300)  # default minutes
        self.assertEqual(parse_duration_delta("-10"), -600)
        self.assertEqual(parse_duration_delta("25m"), 1500)
        self.assertEqual(parse_duration_delta("120s"), 120)

    def test_cli_execution_lifecycle(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg_file = Path(tmpdir) / "config.json"
            state_file = Path(tmpdir) / "state.json"
            stats_file = Path(tmpdir) / "stats.json"

            # Create test config
            config_content = {
                "work_duration": 20,
                "short_break_duration": 4,
                "state_file": str(state_file),
                "stats_file": str(stats_file),
                "sound_enabled": False,
                "notification_enabled": False,
                "waybar_signal": 0,
            }
            with open(cfg_file, "w") as f:
                json.dump(config_content, f)

            base_args = ["-c", str(cfg_file)]

            # 1. status --plain
            f = io.StringIO()
            with redirect_stdout(f):
                ret = main(base_args + ["status", "--plain"])
            self.assertEqual(ret, 0)
            self.assertEqual(f.getvalue().strip(), "20:00")

            # 2. status (JSON)
            f = io.StringIO()
            with redirect_stdout(f):
                ret = main(base_args + ["status"])
            self.assertEqual(ret, 0)
            data = json.loads(f.getvalue().strip())
            self.assertEqual(data["text"], "20:00")
            self.assertEqual(data["alt"], "idle")
            self.assertIn("class", data)

            # 3. time-left
            f = io.StringIO()
            with redirect_stdout(f):
                ret = main(base_args + ["time-left"])
            self.assertEqual(ret, 0)
            self.assertEqual(f.getvalue().strip(), "20:00")

            f = io.StringIO()
            with redirect_stdout(f):
                ret = main(base_args + ["time-left", "--seconds"])
            self.assertEqual(ret, 0)
            self.assertEqual(f.getvalue().strip(), "1200")

            # 4. adjust +2m
            ret = main(base_args + ["adjust", "+2m"])
            self.assertEqual(ret, 0)

            f = io.StringIO()
            with redirect_stdout(f):
                main(base_args + ["status", "--plain"])
            self.assertEqual(f.getvalue().strip(), "22:00")

            # 5. reset
            ret = main(base_args + ["reset"])
            self.assertEqual(ret, 0)

            f = io.StringIO()
            with redirect_stdout(f):
                main(base_args + ["status", "--plain"])
            self.assertEqual(f.getvalue().strip(), "20:00")

            # 6. start with custom duration
            ret = main(base_args + ["start", "35m"])
            self.assertEqual(ret, 0)

            f = io.StringIO()
            with redirect_stdout(f):
                main(base_args + ["status", "--plain"])
            self.assertEqual(f.getvalue().strip(), "35:00")

            # 7. pause, resume, toggle, skip
            ret = main(base_args + ["pause"])
            self.assertEqual(ret, 0)
            f = io.StringIO()
            with redirect_stdout(f):
                main(base_args + ["status"])
            self.assertEqual(json.loads(f.getvalue().strip())["alt"], "paused")

            ret = main(base_args + ["resume"])
            self.assertEqual(ret, 0)
            f = io.StringIO()
            with redirect_stdout(f):
                main(base_args + ["status"])
            self.assertEqual(json.loads(f.getvalue().strip())["alt"], "work")

            ret = main(base_args + ["toggle"])
            self.assertEqual(ret, 0)
            f = io.StringIO()
            with redirect_stdout(f):
                main(base_args + ["status"])
            self.assertEqual(json.loads(f.getvalue().strip())["alt"], "paused")

            ret = main(base_args + ["skip"])
            self.assertEqual(ret, 0)
            f = io.StringIO()
            with redirect_stdout(f):
                main(base_args + ["status"])
            payload = json.loads(f.getvalue().strip())
            self.assertIn("short-break", payload["class"])

            # Resume running the break
            ret = main(base_args + ["resume"])
            self.assertEqual(ret, 0)
            f = io.StringIO()
            with redirect_stdout(f):
                main(base_args + ["status"])
            self.assertEqual(json.loads(f.getvalue().strip())["alt"], "short_break")

            # 8. stop command
            ret = main(base_args + ["stop"])
            self.assertEqual(ret, 0)

            f = io.StringIO()
            with redirect_stdout(f):
                main(base_args + ["status", "--plain"])
            self.assertEqual(f.getvalue().strip(), "20:00")

            # 9. stats, stats --json, stats --csv, stats --reset
            f = io.StringIO()
            with redirect_stdout(f):
                ret = main(base_args + ["stats"])
            self.assertEqual(ret, 0)
            self.assertIn("Pomodoro Statistics", f.getvalue())

            f = io.StringIO()
            with redirect_stdout(f):
                ret = main(base_args + ["stats", "--json"])
            self.assertEqual(ret, 0)
            stats_json = json.loads(f.getvalue().strip())
            self.assertIn("total_completed", stats_json)

            f = io.StringIO()
            with redirect_stdout(f):
                ret = main(base_args + ["stats", "--csv"])
            self.assertEqual(ret, 0)
            self.assertIn("date,completed_sessions", f.getvalue())

            f = io.StringIO()
            with redirect_stdout(f):
                ret = main(base_args + ["stats", "--reset"])
            self.assertEqual(ret, 0)
            self.assertIn("reset successfully", f.getvalue())

            # 10. test-alert
            f = io.StringIO()
            with redirect_stdout(f):
                ret = main(base_args + ["test-alert"])
            self.assertEqual(ret, 0)
            self.assertIn("Test alert sent", f.getvalue())

            # 12. stats --heatmap
            f = io.StringIO()
            with redirect_stdout(f):
                ret = main(base_args + ["stats", "--heatmap", "--weeks", "10", "--no-color"])
            self.assertEqual(ret, 0)
            self.assertIn("POMODORO STUDY TRACKER", f.getvalue())

            # 13. stats --export-chart
            chart_file = Path(tmpdir) / "exported_chart.svg"
            f = io.StringIO()
            with redirect_stdout(f):
                ret = main(
                    base_args + ["stats", "--export-chart", str(chart_file), "--theme", "nord"]
                )
            self.assertEqual(ret, 0)
            self.assertTrue(chart_file.exists())
            self.assertIn("exported to", f.getvalue())

            # 14. menu subcommand
            from unittest.mock import patch

            with patch("waybar_pomodoro.cli.MenuLauncher.run", return_value=0) as mock_menu:
                ret = main(base_args + ["menu", "--backend", "rofi"])
                self.assertEqual(ret, 0)
                mock_menu.assert_called_once()


if __name__ == "__main__":
    unittest.main()
