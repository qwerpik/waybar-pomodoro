"""
Command line interface for waybar-pomodoro.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import List, Optional

from .config import PomodoroConfig, load_config, save_config
from .dnd import get_dnd_status, set_dnd
from .idle import handle_idle_pause, handle_idle_resume
from .menu import MenuLauncher
from .setup import run_setup
from .streaming import run_stream
from .timer import PomodoroTimer


def parse_duration_delta(value: str) -> int:
    """
    Parses a string like "+1m", "-30s", "+5", "25m", "1500s" into seconds.
    Default unit is minutes if not specified or if suffixed with 'm'.
    """
    cleaned = value.strip().lower()
    match = re.match(r"^([+-]?\d+)\s*(s|sec|seconds|m|min|minutes)?$", cleaned)
    if not match:
        raise argparse.ArgumentTypeError(
            f"Invalid duration format: '{value}'. Use e.g. '25m', '+1m', or '-30s'."
        )

    num = int(match.group(1))
    unit = match.group(2)
    if unit in ("s", "sec", "seconds"):
        return num
    # default to minutes
    return num * 60


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="waybar-pomodoro",
        description="A lightweight, feature-rich Pomodoro timer for Waybar.",
    )
    parser.add_argument(
        "--config",
        "-c",
        type=Path,
        default=None,
        help="Path to custom configuration file",
    )
    parser.add_argument(
        "--work",
        "-w",
        type=int,
        default=None,
        help="Override work session duration in minutes",
    )
    parser.add_argument(
        "--short-break",
        "-s",
        type=int,
        default=None,
        help="Override short break duration in minutes",
    )
    parser.add_argument(
        "--long-break",
        "-l",
        type=int,
        default=None,
        help="Override long break duration in minutes",
    )
    parser.add_argument(
        "--style",
        choices=["minimal", "icon", "custom"],
        default=None,
        help="Display style in Waybar",
    )

    subparsers = parser.add_subparsers(dest="command", help="Subcommand to run")

    # status
    status_parser = subparsers.add_parser(
        "status", help="Output current status (for Waybar or terminal)"
    )
    status_parser.add_argument(
        "--plain",
        action="store_true",
        help="Output plain text instead of JSON",
    )

    # time-left
    time_left_parser = subparsers.add_parser("time-left", help="Print remaining timer duration")
    time_left_parser.add_argument(
        "--seconds",
        "-s",
        action="store_true",
        help="Print raw remaining seconds",
    )

    # toggle, start, pause, resume, reset, stop, skip
    subparsers.add_parser("toggle", help="Toggle between start, pause, and resume")

    start_parser = subparsers.add_parser("start", help="Start or resume the timer")
    start_parser.add_argument(
        "duration",
        nargs="?",
        type=parse_duration_delta,
        default=None,
        help="Optional ad-hoc duration to start (e.g. 25m, 45m, 1500s)",
    )

    subparsers.add_parser("pause", help="Pause the active timer")
    subparsers.add_parser("resume", help="Resume a paused timer")

    reset_parser = subparsers.add_parser("reset", help="Reset timer back to initial work session")
    reset_parser.add_argument(
        "duration",
        nargs="?",
        type=parse_duration_delta,
        default=None,
        help="Optional ad-hoc duration to reset to (e.g. 25m, 45m)",
    )

    subparsers.add_parser("stop", help="Stop and reset timer back to idle")
    subparsers.add_parser("skip", help="Skip the current phase")

    # adjust
    adjust_parser = subparsers.add_parser(
        "adjust", help="Adjust timer duration (+/- time, ideal for wheel scroll)"
    )
    adjust_parser.add_argument(
        "delta",
        type=parse_duration_delta,
        help="Delta time to adjust, e.g. +1m, -1m, +30s",
    )

    # stats
    stats_parser = subparsers.add_parser("stats", help="Display or manage Pomodoro statistics")
    stats_parser.add_argument(
        "--json",
        action="store_true",
        help="Output statistics in JSON format",
    )
    stats_parser.add_argument(
        "--csv",
        action="store_true",
        help="Export daily statistics in CSV format",
    )
    stats_parser.add_argument(
        "--heatmap",
        "-H",
        action="store_true",
        help="Display GitHub-style contribution heatmap in the terminal",
    )
    stats_parser.add_argument(
        "--chart",
        action="store_true",
        help="Export and open the GitHub-style contribution chart (SVG)",
    )
    stats_parser.add_argument(
        "--export-chart",
        type=Path,
        default=None,
        metavar="PATH",
        help="Export contribution chart SVG to a specific file path",
    )
    stats_parser.add_argument(
        "--weeks",
        "-w",
        type=int,
        default=None,
        help="Weeks to show in heatmap/chart (default: auto/52)",
    )
    stats_parser.add_argument(
        "--theme",
        choices=["github-dark", "catppuccin", "gruvbox", "tokyo-night", "nord"],
        default="github-dark",
        help="Color theme for the SVG chart",
    )
    stats_parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI colors in terminal heatmap",
    )
    stats_parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset all saved statistics",
    )

    # menu
    menu_parser = subparsers.add_parser(
        "menu", help="Open the interactive popup menu (Rofi/Wofi/Fuzzel/Zenity/GTK)"
    )
    menu_parser.add_argument(
        "--backend",
        "-b",
        choices=["auto", "rofi", "wofi", "fuzzel", "tofi", "zenity", "gtk"],
        default=None,
        help="Override popup menu launcher backend",
    )
    menu_parser.add_argument(
        "--command",
        "-C",
        dest="custom_command",
        type=str,
        default=None,
        help="Custom launcher command (e.g. 'rofi -dmenu -theme ~/custom.rasi')",
    )

    # test-alert
    subparsers.add_parser("test-alert", help="Trigger a test desktop notification and audio chime")

    # stream
    subparsers.add_parser(
        "stream",
        help="Run the persistent Waybar streaming daemon (newline-delimited JSON)",
    )

    # setup
    setup_parser = subparsers.add_parser(
        "setup",
        help="Generate or install compositor keybindings and Waybar module config",
    )
    setup_parser.add_argument(
        "compositor",
        nargs="?",
        choices=["mangowm", "hyprland", "sway", "i3", "all"],
        default="all",
        help="Target compositor / window manager (default: all)",
    )
    setup_parser.add_argument(
        "--print",
        action="store_true",
        help="Print configuration snippets to stdout (default)",
    )
    setup_parser.add_argument(
        "--append",
        action="store_true",
        help="Safely append keybindings to target compositor config file",
    )
    setup_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate appending without modifying files",
    )

    # idle-pause
    subparsers.add_parser(
        "idle-pause",
        help="Pause running timer when screen locks or inactivity occurs",
    )

    # idle-resume
    idle_resume_parser = subparsers.add_parser(
        "idle-resume",
        help="Resume timer when screen unlocks or user returns",
    )
    idle_resume_parser.add_argument(
        "--no-notify",
        action="store_true",
        help="Do not show desktop notification upon resume",
    )

    # lock-hook
    lock_hook_parser = subparsers.add_parser(
        "lock-hook",
        help="Screen lock hook integration (pause or resume)",
    )
    lock_hook_parser.add_argument(
        "action",
        choices=["pause", "resume"],
        help="Action to perform on screen lock/unlock",
    )

    # dnd
    dnd_parser = subparsers.add_parser("dnd", help="Manage Focus Do Not Disturb mode")
    dnd_group = dnd_parser.add_mutually_exclusive_group()
    dnd_group.add_argument("--on", action="store_true", help="Enable Do Not Disturb")
    dnd_group.add_argument("--off", action="store_true", help="Disable Do Not Disturb")
    dnd_group.add_argument(
        "--status", action="store_true", help="Check current Do Not Disturb status"
    )
    dnd_parser.add_argument(
        "--provider",
        choices=["auto", "swaync", "dunst", "mako"],
        default="auto",
        help="Notification daemon provider",
    )

    # config
    config_parser = subparsers.add_parser("config", help="Manage configuration")
    config_parser.add_argument(
        "--init",
        action="store_true",
        help="Create a default configuration file if not already present",
    )
    config_parser.add_argument(
        "--show",
        action="store_true",
        help="Print current active configuration JSON",
    )

    return parser


def apply_overrides(config: PomodoroConfig, args: argparse.Namespace) -> PomodoroConfig:
    if getattr(args, "work", None) is not None:
        config.work_duration = max(1, args.work)
    if getattr(args, "short_break", None) is not None:
        config.short_break_duration = max(1, args.short_break)
    if getattr(args, "long_break", None) is not None:
        config.long_break_duration = max(1, args.long_break)
    if getattr(args, "style", None) is not None:
        config.style = args.style
    return config


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # Load configuration
    config = load_config(args.config)
    config = apply_overrides(config, args)

    command = args.command or "status"

    if command == "config":
        if args.init:
            target = save_config(config, args.config)
            print(f"Configuration written to: {target}")
            return 0
        if args.show:
            print(json.dumps(config.to_dict(), indent=2))
            return 0
        parser.parse_args(["config", "--help"])
        return 0

    timer = PomodoroTimer(config)

    if command == "status":
        payload = timer.get_status_payload()
        if getattr(args, "plain", False):
            print(payload["text"])
        else:
            print(json.dumps(payload, ensure_ascii=False))
        return 0

    if command == "time-left":
        as_seconds = getattr(args, "seconds", False)
        print(timer.get_time_left(as_seconds=as_seconds))
        return 0

    if command == "toggle":
        timer.toggle()
        return 0

    if command == "start":
        duration = getattr(args, "duration", None)
        timer.start(duration_seconds=duration)
        return 0

    if command == "pause":
        timer.pause()
        return 0

    if command == "resume":
        timer.resume()
        return 0

    if command in ("reset", "stop"):
        duration = getattr(args, "duration", None)
        timer.reset(duration_seconds=duration)
        return 0

    if command == "skip":
        timer.skip()
        return 0

    if command == "adjust":
        timer.adjust(args.delta)
        return 0

    if command == "menu":
        backend = getattr(args, "backend", None) or config.menu_backend
        custom_cmd = getattr(args, "custom_command", None) or config.menu_custom_command
        return MenuLauncher.run(timer, backend=backend, custom_cmd=custom_cmd)

    if command == "stats":
        if getattr(args, "reset", False):
            timer.stats.reset()
            print("Pomodoro statistics reset successfully.")
            return 0
        if getattr(args, "heatmap", False):
            no_color = getattr(args, "no_color", False)
            use_color = False if no_color else None
            weeks = getattr(args, "weeks", None)
            print(timer.stats.render_heatmap(weeks=weeks, use_color=use_color))
            return 0
        if getattr(args, "chart", False) or getattr(args, "export_chart", None):
            export_path = getattr(args, "export_chart", None)
            theme = getattr(args, "theme", "github-dark")
            open_browser = getattr(args, "chart", False)
            saved = timer.stats.export_chart(
                output_path=export_path, theme=theme, open_browser=open_browser
            )
            print(f"Contribution chart exported to: {saved}")
            return 0
        if getattr(args, "json", False):
            print(timer.stats.to_json())
            return 0
        if getattr(args, "csv", False):
            print(timer.stats.to_csv(), end="")
            return 0
        print(timer.stats.format_summary())
        return 0

    if command == "test-alert":
        print("Testing notification and audio alerts...")
        timer.notifier.send_notification(
            "Pomodoro Test", "This is a test notification from waybar-pomodoro."
        )
        timer.notifier.play_sound(timer.config.sound_work_end)
        print("Test alert sent.")
        return 0

    if command == "stream":
        return run_stream(timer)

    if command == "setup":
        return run_setup(
            compositor=getattr(args, "compositor", "all"),
            dry_run=getattr(args, "dry_run", False),
            print_only=getattr(args, "print", False),
            append=getattr(args, "append", False),
        )

    if command == "idle-pause":
        ok, msg = handle_idle_pause(timer)
        print(msg)
        return 0 if ok else 1

    if command == "idle-resume":
        notify = not getattr(args, "no_notify", False)
        if not notify:
            timer.config.idle_resume_notify = False
        ok, msg = handle_idle_resume(timer, auto_resume=True)
        print(msg)
        return 0 if ok else 1

    if command == "lock-hook":
        action = getattr(args, "action", "pause")
        if action == "pause":
            ok, msg = handle_idle_pause(timer)
        else:
            ok, msg = handle_idle_resume(timer, auto_resume=True)
        print(msg)
        return 0 if ok else 1

    if command == "dnd":
        provider = getattr(args, "provider", "auto")
        if getattr(args, "on", False):
            ok = set_dnd(True, provider)
            status_text = "enabled" if ok else "failed to enable"
            print(f"Do Not Disturb {status_text} ({provider}).")
            return 0 if ok else 1
        elif getattr(args, "off", False):
            ok = set_dnd(False, provider)
            status_text = "disabled" if ok else "failed to disable"
            print(f"Do Not Disturb {status_text} ({provider}).")
            return 0 if ok else 1
        else:
            status = get_dnd_status(provider)
            if status is None:
                print(f"DND provider '{provider}' not active or unsupported.")
                return 1
            print("DND: on" if status else "DND: off")
            return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
