import concurrent.futures
import tempfile
import time
import unittest
from pathlib import Path

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

    def test_start_with_custom_duration(self):
        self.timer.start(duration_seconds=45 * 60)
        state = self.timer.load_state()
        self.assertEqual(state["state"], "running")
        self.assertEqual(state["total_time"], 45 * 60)
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
        self.timer.reset(duration_seconds=30 * 60)

        state = self.timer.load_state()
        self.assertEqual(state["state"], "idle")
        self.assertEqual(state["phase"], "work")
        self.assertEqual(state["time_remaining"], 30 * 60)
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

    def test_idle_downward_adjust_percentage(self):
        # When adjusting downwards while idle, total_time should update to new_rem
        # so remaining / total is 100% remaining (0% progress), not artificially pre-filled.
        self.timer.adjust(-10 * 60)  # 25m -> 15m
        state = self.timer.load_state()
        self.assertEqual(state["time_remaining"], 15 * 60)
        self.assertEqual(state["total_time"], 15 * 60)
        _, percentage = self.timer.get_remaining_and_percentage(state)
        self.assertEqual(percentage, 0)

    def test_check_completion_work_to_break(self):
        state = self.timer.load_state()
        state["state"] = "running"
        # Set end_time 5 seconds in the past
        state["end_time"] = time.time() - 5
        self.timer.save_state(state)

        transitioned = self.timer.check_completion(state)
        self.assertTrue(transitioned)
        self.assertEqual(state["phase"], "short_break")
        self.assertEqual(state["total_time"], 5 * 60)

        # Stats should have recorded 1 session
        today = self.timer.stats.get_today_stats()
        self.assertEqual(today["completed_sessions"], 1)

    def test_check_completion_sleep_drift(self):
        # Machine was suspended for 4 hours
        state = self.timer.load_state()
        state["state"] = "running"
        state["end_time"] = time.time() - (4 * 3600)
        self.timer.save_state(state)

        transitioned = self.timer.check_completion(state)
        self.assertTrue(transitioned)
        # Should transition cleanly without recording a phantom session
        today = self.timer.stats.get_today_stats()
        self.assertEqual(today["completed_sessions"], 0)
        self.assertEqual(state["state"], "idle")

    def test_deadlock_prevented_on_00_00_toggle(self):
        # Timer expired 2 seconds ago while running
        state = self.timer.load_state()
        state["state"] = "running"
        state["end_time"] = time.time() - 2
        self.timer.save_state(state)

        # Calling toggle() should complete the session, not lock at 00:00 paused!
        self.timer.toggle()
        new_state = self.timer.load_state()
        self.assertEqual(new_state["phase"], "short_break")
        self.assertGreater(new_state["time_remaining"], 0)

    def test_status_payload_alt_field_and_classes(self):
        # Idle payload
        payload = self.timer.get_status_payload()
        self.assertEqual(payload["text"], "25:00")
        self.assertEqual(payload["alt"], "idle")
        self.assertIn("idle", payload["class"])
        self.assertIn("stopped", payload["class"])
        # Crucial bug fix: "work" class must NOT be present when idle!
        self.assertNotIn("work", payload["class"].split())

        # Running payload
        self.timer.start()
        payload = self.timer.get_status_payload()
        self.assertEqual(payload["alt"], "work")
        self.assertIn("running", payload["class"])
        self.assertIn("work", payload["class"])

        # Paused payload
        self.timer.pause()
        payload = self.timer.get_status_payload()
        self.assertEqual(payload["alt"], "paused")
        self.assertIn("paused", payload["class"])

    def test_auto_start_break_false(self):
        self.config.auto_start_break = False
        timer = PomodoroTimer(self.config)
        state = timer.load_state()
        state["state"] = "running"
        state["end_time"] = time.time() - 1
        timer.check_completion(state)
        self.assertEqual(state["phase"], "short_break")
        self.assertEqual(state["state"], "idle")

    def test_get_time_left(self):
        self.assertEqual(self.timer.get_time_left(), "25:00")
        self.assertEqual(self.timer.get_time_left(as_seconds=True), 25 * 60)

    def test_concurrency_rapid_adjust(self):
        # Simulate 10 rapid scroll wheel adjustments (+1 min each)
        def adjust_once():
            self.timer.adjust(60)

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(adjust_once) for _ in range(10)]
            for f in futures:
                f.result()

        state = self.timer.load_state()
        # Initial 25m + 10 * 1m = 35m
        self.assertEqual(state["time_remaining"], 35 * 60)


if __name__ == "__main__":
    unittest.main()
