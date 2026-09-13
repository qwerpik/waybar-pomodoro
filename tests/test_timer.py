import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from waybar_pomodoro.config import PomodoroConfig
from waybar_pomodoro.timer import PomodoroTimer


class TestTimer(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.state_file = Path(self.tmpdir.name) / "state.json"
        self.stats_file = Path(self.tmpdir.name) / "stats.json"
        self.config = PomodoroConfig(
            work_duration=25,
            short_break_duration=5,
            long_break_duration=15,
            cycles_before_long_break=4,
            style="minimal",
            sound_enabled=False,
            notification_enabled=False,
            waybar_signal=0,
            state_file=str(self.state_file),
            stats_file=str(self.stats_file),
        )
        self.timer = PomodoroTimer(self.config)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_initial_state(self):
        state = self.timer.load_state()
        self.assertEqual(state["state"], "idle")
        self.assertEqual(state["phase"], "work")
        self.assertEqual(state["time_remaining"], 25 * 60)
        self.assertEqual(state["cycle"], 1)

    def test_start_pause_resume(self):
        # Start
        self.timer.start()
        state = self.timer.load_state()
        self.assertEqual(state["state"], "running")
        self.assertGreater(state["end_time"], time.time())

        # Pause
        self.timer.pause()
        state = self.timer.load_state()
        self.assertEqual(state["state"], "paused")
        self.assertLessEqual(state["time_remaining"], 25 * 60)

        # Resume
        self.timer.resume()
        state = self.timer.load_state()
        self.assertEqual(state["state"], "running")
        self.assertGreater(state["end_time"], time.time())

    def test_toggle(self):
        # idle -> running
        self.timer.toggle()
        self.assertEqual(self.timer.load_state()["state"], "running")

        # running -> paused
        self.timer.toggle()
        self.assertEqual(self.timer.load_state()["state"], "paused")

        # paused -> running
        self.timer.toggle()
        self.assertEqual(self.timer.load_state()["state"], "running")

    def test_reset(self):
        self.timer.start()
        self.timer.skip()
        self.timer.reset()

        state = self.timer.load_state()
        self.assertEqual(state["state"], "idle")
        self.assertEqual(state["phase"], "work")
        self.assertEqual(state["time_remaining"], 25 * 60)
        self.assertEqual(state["cycle"], 1)

    def test_skip_transitions(self):
        # Cycle 1: work -> short break
        state = self.timer.load_state()
        self.assertEqual(state["cycle"], 1)
        self.assertEqual(state["phase"], "work")

        self.timer.skip()
        state = self.timer.load_state()
        self.assertEqual(state["phase"], "short_break")
        self.assertEqual(state["time_remaining"], 5 * 60)

        # short break -> work (cycle 2)
        self.timer.skip()
        state = self.timer.load_state()
        self.assertEqual(state["phase"], "work")
        self.assertEqual(state["cycle"], 2)

        # Skip to cycle 4 work
        self.timer.skip()  # break 2
        self.timer.skip()  # work 3
        self.timer.skip()  # break 3
        self.timer.skip()  # work 4
        state = self.timer.load_state()
        self.assertEqual(state["phase"], "work")
        self.assertEqual(state["cycle"], 4)

        # 4th work -> long break
        self.timer.skip()
        state = self.timer.load_state()
        self.assertEqual(state["phase"], "long_break")
        self.assertEqual(state["time_remaining"], 15 * 60)

    def test_adjust_time(self):
        # Adjust when idle
        self.timer.adjust(60)  # +1 min
        state = self.timer.load_state()
        self.assertEqual(state["time_remaining"], 25 * 60 + 60)

        self.timer.adjust(-120)  # -2 min
        state = self.timer.load_state()
        self.assertEqual(state["time_remaining"], 25 * 60 - 60)

        # Adjust when running
        self.timer.start()
        state_before = self.timer.load_state()
        self.timer.adjust(300)  # +5 min
        state_after = self.timer.load_state()
        self.assertAlmostEqual(state_after["end_time"] - state_before["end_time"], 300, delta=2)

    def test_check_completion_work_to_break(self):
        state = self.timer.load_state()
        state["state"] = "running"
        # Set end_time in the past
        state["end_time"] = time.time() - 5
        self.timer.save_state(state)

        transitioned = self.timer.check_completion(state)
        self.assertTrue(transitioned)
        self.assertEqual(state["phase"], "short_break")
        self.assertEqual(state["total_time"], 5 * 60)

        # Stats should have recorded 1 session
        today = self.timer.stats.get_today_stats()
        self.assertEqual(today["completed_sessions"], 1)

    def test_status_payload_minimal_vs_icon(self):
        # Minimal style
        payload = self.timer.get_status_payload()
        self.assertEqual(payload["text"], "25:00")
        self.assertIn("Pomodoro: Focus", payload["tooltip"])
        self.assertIn("work", payload["class"])

        # Icon style (idle)
        self.config.style = "icon"
        payload = self.timer.get_status_payload()
        self.assertIn("25:00", payload["text"])
        self.assertIn(self.config.icon_idle, payload["text"])

        # Icon style (running work)
        self.timer.start()
        payload = self.timer.get_status_payload()
        self.assertIn(self.config.icon_work, payload["text"])


if __name__ == "__main__":
    unittest.main()
