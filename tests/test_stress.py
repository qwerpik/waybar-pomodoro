"""Process-level stress tests: daemon lifecycle and cross-process contention."""

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from waybar_pomodoro.config import PomodoroConfig


def _write_config(tmpdir: str) -> str:
    from waybar_pomodoro.config import save_config

    cfg = PomodoroConfig(
        work_duration=25,
        short_break_duration=5,
        long_break_duration=15,
        sound_enabled=False,
        notification_enabled=False,
        waybar_signal=0,
        state_file=str(Path(tmpdir) / "state.json"),
        stats_file=str(Path(tmpdir) / "stats.json"),
    )
    return str(save_config(cfg, Path(tmpdir) / "cfg.json"))


class TestStreamDaemonLifecycle(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.cfg = _write_config(self.tmpdir.name)
        self.env = dict(os.environ)
        repo_src = str(Path(__file__).resolve().parent.parent / "src")
        self.env["PYTHONPATH"] = repo_src + os.pathsep + self.env.get("PYTHONPATH", "")

    def tearDown(self):
        self.tmpdir.cleanup()

    def _spawn_stream(self, stdout_sink):
        return subprocess.Popen(
            [sys.executable, "-m", "waybar_pomodoro", "--config", self.cfg, "stream"],
            stdout=stdout_sink,
            stderr=subprocess.DEVNULL,
            env=self.env,
        )

    def _cli(self, *args) -> None:
        subprocess.run(
            [sys.executable, "-m", "waybar_pomodoro", "--config", self.cfg, *args],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=self.env,
            check=False,
        )

    def test_daemon_emits_valid_json_and_dies_clean_on_sigterm(self):
        proc = self._spawn_stream(subprocess.PIPE)
        self.addCleanup(lambda: proc.poll() is not None or proc.kill())
        first = proc.stdout.readline().decode()
        payload = json.loads(first)
        self.assertIn("text", payload)
        self.assertIn("percentage", payload)
        self._cli("toggle")
        time.sleep(1.5)
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.fail("stream daemon ignored SIGTERM")
        self.assertEqual(proc.returncode, 0)
        rest = proc.stdout.read().decode()
        for line in (first + rest).strip().split("\n"):
            payload = json.loads(line)
            self.assertEqual(set(("text", "alt", "tooltip", "class", "percentage")), set(payload))

    def test_daemon_exits_quietly_on_broken_pipe(self):
        self._cli("toggle")  # running: daemon writes every second
        proc = self._spawn_stream(subprocess.PIPE)
        proc.stdout.readline()
        proc.stdout.close()  # simulate Waybar going away
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            self.fail("stream daemon hung on broken stdout")
        self.assertEqual(proc.returncode, 0)


class TestCrossProcessToggleStorm(unittest.TestCase):
    def test_concurrent_toggles_keep_valid_state(self):
        tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(tmpdir.cleanup)
        cfg = _write_config(tmpdir.name)
        env = dict(os.environ)
        repo_src = str(Path(__file__).resolve().parent.parent / "src")
        env["PYTHONPATH"] = repo_src + os.pathsep + env.get("PYTHONPATH", "")
        workers = 4
        per_worker = 10
        procs = [
            subprocess.Popen(
                [
                    sys.executable,
                    "-c",
                    "import sys; "
                    "from waybar_pomodoro.cli import main; "
                    f"[main(['--config', {cfg!r}, 'toggle']) for _ in range({per_worker})]",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=env,
            )
            for _ in range(workers)
        ]
        for proc in procs:
            proc.wait(timeout=60)
            self.assertEqual(proc.returncode, 0)
        # 40 toggles from idle must end paused with coherent state.
        final = json.loads(
            subprocess.run(
                [sys.executable, "-m", "waybar_pomodoro", "--config", cfg, "status"],
                capture_output=True,
                text=True,
                env=env,
                check=True,
            ).stdout
        )
        self.assertEqual(final["alt"], "paused")
        self.assertIn("paused", final["class"])


if __name__ == "__main__":
    unittest.main()
