import os
import stat
import tempfile
import unittest
from pathlib import Path

from waybar_pomodoro import dnd, idle
from waybar_pomodoro.config import PomodoroConfig
from waybar_pomodoro.timer import PomodoroTimer

NOTIFY_SEND = """#!/bin/sh
# Fake notify-send: answer with $FAKE_NOTIFY_ACTION
echo "$FAKE_NOTIFY_ACTION"
exit 0
"""


def _make_timer(tmpdir: str, **overrides) -> PomodoroTimer:
    kwargs = dict(
        work_duration=25,
        short_break_duration=5,
        long_break_duration=15,
        cycles_before_long_break=4,
        style="minimal",
        sound_enabled=False,
        notification_enabled=False,
        waybar_signal=0,
        state_file=str(Path(tmpdir) / "state.json"),
        stats_file=str(Path(tmpdir) / "stats.json"),
    )
    kwargs.update(overrides)
    return PomodoroTimer(PomodoroConfig(**kwargs))


class IdleTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.timer = _make_timer(self.tmpdir.name)
        self.config = self.timer.config

    def tearDown(self):
        self.tmpdir.cleanup()


class TestIdlePause(IdleTestCase):
    def test_pause_running_marks_idle_flag(self):
        self.timer.start()
        self.assertEqual(idle.handle_idle_pause(self.timer, self.config), 0)
        state = self.timer.load_state()
        self.assertEqual(state["state"], "paused")
        self.assertTrue(state["paused_by_idle"])

    def test_pause_when_idle_is_noop(self):
        self.assertEqual(idle.handle_idle_pause(self.timer, self.config), 0)
        state = self.timer.load_state()
        self.assertEqual(state["state"], "idle")
        self.assertFalse(state["paused_by_idle"])

    def test_pause_when_manually_paused_is_noop(self):
        self.timer.start()
        self.timer.pause()
        self.assertEqual(idle.handle_idle_pause(self.timer, self.config), 0)
        state = self.timer.load_state()
        self.assertFalse(state["paused_by_idle"])


class TestIdleResume(IdleTestCase):
    def _force_idle_pause(self):
        self.timer.start()
        self.assertEqual(idle.handle_idle_pause(self.timer, self.config), 0)

    def test_auto_resume(self):
        self._force_idle_pause()
        self.config.idle_resume_mode = "auto"
        self.assertEqual(idle.handle_idle_resume(self.timer, self.config), 0)
        state = self.timer.load_state()
        self.assertEqual(state["state"], "running")
        self.assertFalse(state["paused_by_idle"])

    def test_manual_pause_is_preserved(self):
        self.timer.start()
        self.timer.pause()
        self.config.idle_resume_mode = "auto"
        self.assertEqual(idle.handle_idle_resume(self.timer, self.config), 0)
        state = self.timer.load_state()
        self.assertEqual(state["state"], "paused")
        self.assertFalse(state["paused_by_idle"])

    def test_keep_mode_stays_paused_without_flag(self):
        self._force_idle_pause()
        self.config.idle_resume_mode = "keep"
        self.assertEqual(idle.handle_idle_resume(self.timer, self.config), 0)
        state = self.timer.load_state()
        self.assertEqual(state["state"], "paused")
        self.assertFalse(state["paused_by_idle"])

    def test_noninteractive_forces_auto(self):
        self._force_idle_pause()
        self.config.idle_resume_mode = "keep"
        self.assertEqual(idle.handle_idle_resume(self.timer, self.config, interactive=False), 0)
        self.assertEqual(self.timer.load_state()["state"], "running")


class NotifySendCase(IdleTestCase):
    def setUp(self):
        super().setUp()
        self.bindir = Path(self.tmpdir.name) / "bin"
        self.bindir.mkdir()
        script = self.bindir / "notify-send"
        script.write_text(NOTIFY_SEND, encoding="utf-8")
        script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        self._old_path = os.environ.get("PATH", "")
        self._old_action = os.environ.get("FAKE_NOTIFY_ACTION")
        os.environ["PATH"] = str(self.bindir) + os.pathsep + self._old_path

    def tearDown(self):
        os.environ["PATH"] = self._old_path
        if self._old_action is None:
            os.environ.pop("FAKE_NOTIFY_ACTION", None)
        else:
            os.environ["FAKE_NOTIFY_ACTION"] = self._old_action
        super().tearDown()

    def _force_idle_pause(self):
        self.timer.start()
        self.assertEqual(idle.handle_idle_pause(self.timer, self.config), 0)


class TestIdlePrompt(NotifySendCase):
    def test_prompt_resume(self):
        os.environ["FAKE_NOTIFY_ACTION"] = "resume"
        self._force_idle_pause()
        self.config.idle_resume_mode = "prompt"
        self.assertEqual(idle.handle_idle_resume(self.timer, self.config), 0)
        state = self.timer.load_state()
        self.assertEqual(state["state"], "running")
        self.assertFalse(state["paused_by_idle"])

    def test_prompt_reset(self):
        os.environ["FAKE_NOTIFY_ACTION"] = "reset"
        self._force_idle_pause()
        self.config.idle_resume_mode = "prompt"
        self.assertEqual(idle.handle_idle_resume(self.timer, self.config), 0)
        state = self.timer.load_state()
        self.assertEqual(state["state"], "idle")
        self.assertEqual(state["phase"], "work")
        self.assertFalse(state["paused_by_idle"])

    def test_prompt_keep_converts_to_manual_pause(self):
        os.environ["FAKE_NOTIFY_ACTION"] = "keep"
        self._force_idle_pause()
        self.config.idle_resume_mode = "prompt"
        self.assertEqual(idle.handle_idle_resume(self.timer, self.config), 0)
        state = self.timer.load_state()
        self.assertEqual(state["state"], "paused")
        self.assertFalse(state["paused_by_idle"])

    def test_prompt_dismiss_is_safe(self):
        os.environ["FAKE_NOTIFY_ACTION"] = "dismissed-by-user"
        self.assertIsNone(idle._prompt_resume_action(self.timer))


class TestIdleDndUntouched(IdleTestCase):
    def test_lock_keeps_dnd_on(self):
        bindir = Path(self.tmpdir.name) / "bin"
        bindir.mkdir()
        makoctl = bindir / "makoctl"
        makoctl.write_text(
            '#!/bin/sh\nif [ "$1" = "mode" ] && [ $# -eq 1 ]; then echo "default"; fi\nexit 0\n',
            encoding="utf-8",
        )
        makoctl.chmod(makoctl.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        old_path = os.environ.get("PATH", "")
        os.environ["PATH"] = str(bindir) + os.pathsep + old_path
        dnd._which.cache_clear()
        try:
            timer = _make_timer(
                self.tmpdir.name, auto_dnd=True, dnd_provider="mako", idle_resume_mode="auto"
            )
            timer.start()
            self.assertTrue(timer.load_state()["dnd_active"])
            self.assertEqual(idle.handle_idle_pause(timer, timer.config), 0)
            # Focus session still owns the screen: DND stays claimed.
            self.assertTrue(timer.load_state()["dnd_active"])
            self.assertEqual(idle.handle_idle_resume(timer, timer.config), 0)
            self.assertEqual(timer.load_state()["state"], "running")
        finally:
            os.environ["PATH"] = old_path
            dnd._which.cache_clear()


if __name__ == "__main__":
    unittest.main()
