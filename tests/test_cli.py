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
            self.assertIn("class", data)

            # 3. adjust +2m
            ret = main(base_args + ["adjust", "+2m"])
            self.assertEqual(ret, 0)

            f = io.StringIO()
            with redirect_stdout(f):
                main(base_args + ["status", "--plain"])
            self.assertEqual(f.getvalue().strip(), "22:00")

            # 4. reset
            ret = main(base_args + ["reset"])
            self.assertEqual(ret, 0)

            f = io.StringIO()
            with redirect_stdout(f):
                main(base_args + ["status", "--plain"])
            self.assertEqual(f.getvalue().strip(), "20:00")

            # 5. stats
            f = io.StringIO()
            with redirect_stdout(f):
                ret = main(base_args + ["stats"])
            self.assertEqual(ret, 0)
            self.assertIn("Pomodoro Statistics", f.getvalue())

            # 6. config --show
            f = io.StringIO()
            with redirect_stdout(f):
                ret = main(base_args + ["config", "--show"])
            self.assertEqual(ret, 0)
            cfg_data = json.loads(f.getvalue().strip())
            self.assertEqual(cfg_data["work_duration"], 20)


if __name__ == "__main__":
    unittest.main()
