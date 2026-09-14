"""
Universal cross-distro popup menu engine for waybar-pomodoro.
Supports rofi, wofi, fuzzel, tofi, zenity, and PyGObject GTK3.
"""

from __future__ import annotations

import re
import shlex
import shutil
import subprocess
from typing import Any, Dict, List, Optional, Tuple

from .timer import PomodoroTimer


def parse_menu_duration(value: str) -> Optional[int]:
    """
    Parses a string like "25m", "45", "1500s" into seconds.
    Default unit is minutes.
    """
    cleaned = value.strip().lower()
    match = re.match(r"^(\d+)\s*(s|sec|seconds|m|min|minutes)?$", cleaned)
    if not match:
        return None
    num = int(match.group(1))
    unit = match.group(2)
    if unit in ("s", "sec", "seconds"):
        return num
    return num * 60


class MenuLauncher:
    """
    Dispatches and displays an interactive popup menu across all Linux distributions.
    """

    SUPPORTED_BACKENDS = ["rofi", "wofi", "fuzzel", "tofi", "zenity", "gtk"]

    @classmethod
    def detect_backend(cls, preferred: Optional[str] = None) -> Optional[str]:
        """
        Determines the best available menu launcher.
        """
        if preferred and preferred.strip().lower() != "auto":
            pref = preferred.strip().lower()
            if pref == "gtk":
                try:
                    import gi  # type: ignore

                    gi.require_version("Gtk", "3.0")
                    from gi.repository import Gtk  # type: ignore # noqa: F401

                    return "gtk"
                except Exception:
                    pass
            elif shutil.which(pref):
                return pref

        # Auto-detection hierarchy: rofi -> wofi -> fuzzel -> tofi -> zenity -> gtk
        for candidate in ["rofi", "wofi", "fuzzel", "tofi", "zenity"]:
            if shutil.which(candidate):
                return candidate

        try:
            import gi  # type: ignore

            gi.require_version("Gtk", "3.0")
            from gi.repository import Gtk  # type: ignore # noqa: F401

            return "gtk"
        except Exception:
            pass

        return None

    @classmethod
    def show_gtk_menu(cls, items: List[str], prompt: str) -> Optional[str]:
        """
        Lightweight fallback using PyGObject GTK3 when available.
        """
        try:
            import gi  # type: ignore

            gi.require_version("Gtk", "3.0")
            from gi.repository import Gtk  # type: ignore
        except Exception:
            return None

        chosen: List[Optional[str]] = [None]

        menu = Gtk.Menu()
        title_item = Gtk.MenuItem(label=f"── {prompt} ──")
        title_item.set_sensitive(False)
        menu.append(title_item)

        def make_callback(text: str) -> Any:
            def _cb(_widget: Any) -> None:
                chosen[0] = text
                Gtk.main_quit()

            return _cb

        for item in items:
            if not item.strip():
                sep = Gtk.SeparatorMenuItem()
                menu.append(sep)
                continue
            menu_item = Gtk.MenuItem(label=item)
            menu_item.connect("activate", make_callback(item))
            menu.append(menu_item)

        menu.connect("selection-done", lambda _w: Gtk.main_quit())
        menu.show_all()

        # Popup at pointer
        try:
            menu.popup_at_pointer(None)
        except AttributeError:
            menu.popup(None, None, None, None, 0, Gtk.get_current_event_time())

        Gtk.main()
        return chosen[0]

    @classmethod
    def prompt_input(
        cls,
        title: str,
        prompt: str,
        backend: Optional[str] = None,
        custom_cmd: Optional[str] = None,
    ) -> Optional[str]:
        """
        Prompts the user to enter text (e.g. ad-hoc duration like "45m").
        """
        active_backend = backend or cls.detect_backend()
        if not active_backend:
            return None

        if active_backend == "zenity":
            cmd = ["zenity", "--entry", f"--title={title}", f"--text={prompt}"]
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
                if proc.returncode == 0 and proc.stdout.strip():
                    return proc.stdout.strip()
            except Exception:
                return None
            return None

        if active_backend == "rofi":
            cmd = ["rofi", "-dmenu", "-p", prompt, "-lines", "0"]
            try:
                proc = subprocess.run(cmd, input="", capture_output=True, text=True, check=False)
                if proc.returncode == 0 and proc.stdout.strip():
                    return proc.stdout.strip()
            except Exception:
                return None
            return None

        if active_backend == "wofi":
            cmd = ["wofi", "--dmenu", "--prompt", prompt, "--lines", "1"]
            try:
                proc = subprocess.run(cmd, input="", capture_output=True, text=True, check=False)
                if proc.returncode == 0 and proc.stdout.strip():
                    return proc.stdout.strip()
            except Exception:
                return None
            return None

        if active_backend in ("fuzzel", "tofi"):
            cmd = [active_backend, "--dmenu", "--prompt", f"{prompt}: "]
            try:
                proc = subprocess.run(cmd, input="", capture_output=True, text=True, check=False)
                if proc.returncode == 0 and proc.stdout.strip():
                    return proc.stdout.strip()
            except Exception:
                return None
            return None

        return None

    @classmethod
    def show_menu(
        cls,
        items: List[str],
        prompt: str = "Pomodoro",
        backend: Optional[str] = None,
        custom_cmd: Optional[str] = None,
    ) -> Optional[str]:
        """
        Displays menu choices and returns the selected item string or None if cancelled.
        """
        if custom_cmd and custom_cmd.strip():
            cmd = shlex.split(custom_cmd.strip())
            try:
                proc = subprocess.run(
                    cmd,
                    input="\n".join(items) + "\n",
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if proc.returncode == 0 and proc.stdout.strip():
                    return proc.stdout.strip()
                return None
            except Exception:
                return None

        active_backend = backend or cls.detect_backend()
        if not active_backend:
            return None

        if active_backend == "gtk":
            return cls.show_gtk_menu(items, prompt)

        if active_backend == "rofi":
            cmd = ["rofi", "-dmenu", "-i", "-p", prompt, "-no-custom"]
        elif active_backend == "wofi":
            cmd = ["wofi", "--dmenu", "--prompt", prompt, "--insensitive"]
        elif active_backend == "fuzzel":
            cmd = ["fuzzel", "--dmenu", "--prompt", f"{prompt}: "]
        elif active_backend == "tofi":
            cmd = ["tofi", "--prompt-text", f"{prompt}: "]
        elif active_backend == "zenity":
            cmd = [
                "zenity",
                "--list",
                f"--title={prompt}",
                "--column=Actions",
                "--hide-header",
                "--width=420",
                "--height=380",
            ]
        else:
            cmd = [active_backend]

        try:
            proc = subprocess.run(
                cmd,
                input="\n".join(items) + "\n",
                capture_output=True,
                text=True,
                check=False,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                return proc.stdout.strip()
        except Exception:
            return None

        return None

    @classmethod
    def build_menu_items(cls, timer: PomodoroTimer) -> List[Tuple[str, str]]:
        """
        Constructs user-facing menu items and corresponding internal action codes.
        """
        with timer._transaction() as st:
            timer.check_completion(st)
        rem_sec, _ = timer.get_remaining_and_percentage(st)
        state_val = st.get("state", "idle")
        phase_val = st.get("phase", "work")
        rem_fmt = f"{rem_sec // 60:02d}:{rem_sec % 60:02d}"
        cycle_val = st.get("cycle", 1)
        max_cycles = timer.config.cycles_before_long_break

        today_stats, streak = timer.stats.get_today_and_streak()
        today_count = today_stats["completed_sessions"]
        today_mins = today_stats["focus_seconds"] // 60

        if phase_val == "work":
            phase_name = "Work Session"
            icon = "🍅"
        elif phase_val == "short_break":
            phase_name = "Short Break"
            icon = "☕"
        else:
            phase_name = "Long Break"
            icon = "🌴"

        # 1. Header with dynamic session state & statistics
        if state_val == "running":
            status_text = (
                f"{icon} {phase_name.upper()} · {rem_fmt} remaining [{cycle_val}/{max_cycles}]"
            )
        elif state_val == "paused":
            status_text = f"⏸️ PAUSED · {rem_fmt} remaining [{cycle_val}/{max_cycles}]"
        else:
            status_text = (
                f"⏱️ IDLE · {timer.config.work_duration}m default [{cycle_val}/{max_cycles}]"
            )

        items: List[Tuple[str, str]] = []
        items.append((f"📌 {status_text}", "noop"))
        today_stat_label = f"🔥 Streak: {streak}d | Today: {today_count} ({today_mins}m)"
        items.append((today_stat_label, "show_stats"))

        # 2. Primary Playback Controls
        if state_val == "running":
            items.append(("⏸️  Pause Session", "pause"))
        elif state_val == "paused":
            items.append(("▶️  Resume Session", "resume"))
        else:
            items.append(("▶️  Start Session", "start"))

        items.append(("⏭️  Skip Current Phase", "skip"))
        items.append((f"🔄  Reset ({timer.config.work_duration}m work)", "reset"))
        if state_val != "idle":
            items.append(("⏹️  Stop & Reset to Idle", "stop"))

        # 3. Quick Duration Presets
        presets = getattr(timer.config, "menu_presets", [15, 25, 45, 60])
        preset_labels: Dict[int, str] = {
            15: "⚡ 15m Sprint",
            25: "🍅 25m Classic Pomodoro",
            45: "🎯 45m Deep Work Sprint",
            60: "🏆 60m Marathon Session",
        }
        for mins in presets:
            label = preset_labels.get(mins, f"⏱️  {mins}m Session")
            items.append((label, f"preset:{mins}"))

        # 4. Quick Adjustments
        items.append(("➕  Add 5 Minutes (+5m)", "adjust:+5m"))
        items.append(("➖  Subtract 5 Minutes (-5m)", "adjust:-5m"))
        items.append(("⏱️  Custom Duration...", "custom_duration"))

        # 5. Study Tracker & Analytics
        items.append(("📊  Study Tracker (Terminal Heatmap)", "study_tracker_terminal"))
        items.append(("📈  Open Contribution Chart (SVG / Browser)", "study_tracker_chart"))

        return items

    @classmethod
    def execute_action(
        cls,
        timer: PomodoroTimer,
        action: str,
        backend: Optional[str] = None,
        custom_cmd: Optional[str] = None,
    ) -> None:
        """
        Executes the chosen action and refreshes Waybar.
        """
        if not action or action == "noop":
            return

        if action == "pause":
            timer.pause()
        elif action == "resume":
            timer.resume()
        elif action == "start":
            timer.start()
        elif action == "skip":
            timer.skip()
        elif action in ("reset", "stop"):
            timer.reset()
        elif action.startswith("preset:"):
            try:
                mins = int(action.split(":", 1)[1])
                timer.start(duration_seconds=mins * 60)
            except ValueError:
                pass
        elif action == "adjust:+5m":
            timer.adjust(300)
        elif action == "adjust:-5m":
            timer.adjust(-300)
        elif action == "custom_duration":
            val = cls.prompt_input(
                title="Custom Duration",
                prompt="Enter duration (e.g. 25m, 45, 1800s)",
                backend=backend,
                custom_cmd=custom_cmd,
            )
            if val:
                sec = parse_menu_duration(val)
                if sec and sec > 0:
                    timer.start(duration_seconds=sec)
        elif action in ("show_stats", "show_summary"):
            timer.notifier.send_notification("🍅 Pomodoro Statistics", timer.stats.format_summary())
        elif action == "study_tracker_chart":
            timer.stats.export_chart(open_browser=True)
        elif action == "study_tracker_terminal":
            if shutil.which("zenity"):
                summary = timer.stats.render_heatmap(weeks=36, use_color=False)
                subprocess.Popen(
                    [
                        "zenity",
                        "--text-info",
                        "--title=Pomodoro Study Tracker",
                        "--font=Monospace 10",
                        "--width=780",
                        "--height=420",
                    ],
                    stdin=subprocess.PIPE,
                    text=True,
                ).communicate(input=summary)
            else:
                timer.stats.export_chart(open_browser=True)

    @classmethod
    def run(
        cls,
        timer: PomodoroTimer,
        backend: Optional[str] = None,
        custom_cmd: Optional[str] = None,
    ) -> int:
        """
        Builds, renders, and handles the interactive popup menu.
        """
        active_backend = backend or getattr(timer.config, "menu_backend", "auto")
        active_custom = custom_cmd or getattr(timer.config, "menu_custom_command", "")

        detected = cls.detect_backend(preferred=active_backend)
        if not detected and not active_custom:
            err_msg = (
                "No supported GUI menu launcher found.\n"
                "Please install rofi, wofi, fuzzel, tofi, or zenity, "
                "or configure 'menu_custom_command' in ~/.config/waybar-pomodoro/config.json"
            )
            print(err_msg)
            timer.notifier.send_notification("Pomodoro Menu", err_msg)
            return 1

        menu_items = cls.build_menu_items(timer)
        display_texts = [item[0] for item in menu_items]
        action_map = {item[0]: item[1] for item in menu_items}

        selected_text = cls.show_menu(
            items=display_texts,
            prompt="🍅 Pomodoro",
            backend=detected,
            custom_cmd=active_custom,
        )

        if not selected_text or selected_text not in action_map:
            return 0

        action = action_map[selected_text]
        cls.execute_action(
            timer,
            action,
            backend=detected,
            custom_cmd=active_custom,
        )
        return 0
