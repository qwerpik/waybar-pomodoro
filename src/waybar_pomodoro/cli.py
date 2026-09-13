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
from .timer import PomodoroTimer


def parse_duration_delta(value: str) -> int:
    """
    Parses a string like "+1m", "-30s", "+5", "-2m" into seconds.
    Default unit is minutes if not specified or if suffixed with 'm'.
    """
    cleaned = value.strip().lower()
    match = re.match(r"^([+-]?\d+)\s*(s|sec|seconds|m|min|minutes)?$", cleaned)
    if not match:
        try:
            val = int(cleaned)
            return val * 60
        except ValueError:
            raise argparse.ArgumentTypeError(f"Invalid duration format: '{value}'. Use e.g. '+1m' or '-30s'.")

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
    status_parser = subparsers.add_parser("status", help="Output current status (for Waybar or terminal)")
    status_parser.add_argument(
        "--plain",
        action="store_true",
        help="Output plain text instead of JSON",
    )

    # toggle, start, pause, resume, reset, skip
    subparsers.add_parser("toggle", help="Toggle between start, pause, and resume")
    subparsers.add_parser("start", help="Start or resume the timer")
    subparsers.add_parser("pause", help="Pause the active timer")
    subparsers.add_parser("resume", help="Resume a paused timer")
    subparsers.add_parser("reset", help="Reset timer back to initial work session")
    subparsers.add_parser("skip", help="Skip the current phase")

    # adjust
    adjust_parser = subparsers.add_parser("adjust", help="Adjust timer duration (+/- time, ideal for wheel scroll)")
    adjust_parser.add_argument(
        "delta",
        type=parse_duration_delta,
        help="Delta time to adjust, e.g. +1m, -1m, +30s",
    )

    # stats
    subparsers.add_parser("stats", help="Display Pomodoro completion statistics")

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
        config.work_duration = args.work
    if getattr(args, "short_break", None) is not None:
        config.short_break_duration = args.short_break
    if getattr(args, "long_break", None) is not None:
        config.long_break_duration = args.long_break
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

    if command == "toggle":
        timer.toggle()
        return 0

    if command == "start":
        timer.start()
        return 0

    if command == "pause":
        timer.pause()
        return 0

    if command == "resume":
        timer.resume()
        return 0

    if command == "reset":
        timer.reset()
        return 0

    if command == "skip":
        timer.skip()
        return 0

    if command == "adjust":
        timer.adjust(args.delta)
        return 0

    if command == "stats":
        print(timer.stats.format_summary())
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
