"""
Notification and audio alerts for waybar-pomodoro.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional


class Notifier:
    def __init__(
        self,
        sound_enabled: bool = True,
        notification_enabled: bool = True,
        notification_timeout: int = 10000,
        notification_category: str = "timer",
    ):
        self.sound_enabled = sound_enabled
        self.notification_enabled = notification_enabled
        self.notification_timeout = notification_timeout
        self.notification_category = notification_category

    def _find_audio_player(self, file_suffix: str = "") -> Optional[str]:
        """Detects available audio players, filtering out those that cannot decode the file."""
        candidates = ["canberra-gtk-play", "pw-play", "paplay", "ogg123", "ffplay", "mpv"]
        if file_suffix.lower() == ".wav":
            candidates.append("aplay")

        for player in candidates:
            if shutil.which(player):
                return player
        return None

    def send_notification(
        self,
        title: str,
        message: str,
        urgency: str = "normal",
        icon: str = "alarm-clock",
    ) -> None:
        if not self.notification_enabled:
            return

        if not shutil.which("notify-send"):
            return

        cmd = [
            "notify-send",
            "-a",
            "Pomodoro",
            "-u",
            urgency,
            "-c",
            self.notification_category,
            "-r",
            "4082",  # Replace ID to prevent notification stacking
            "-t",
            str(self.notification_timeout),
            "-i",
            icon,
            title,
            message,
        ]

        try:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    def _resolve_sound_path(self, sound_path: str) -> Optional[Path]:
        target = Path(sound_path)
        if target.is_file():
            return target

        # Search standard system sound fallbacks
        stem = target.stem
        fallback_dirs = [
            Path("/usr/share/sounds/freedesktop/stereo"),
            Path("/usr/share/sounds/gnome/default/alerts"),
            Path("/usr/share/sounds/ubuntu/stereo"),
            Path("/usr/share/sounds"),
        ]

        for d in fallback_dirs:
            if d.is_dir():
                for ext in [".oga", ".ogg", ".wav", ".mp3"]:
                    candidate = d / f"{stem}{ext}"
                    if candidate.is_file():
                        return candidate

        # If any sound file exists in freedesktop stereo, use it
        default_dir = Path("/usr/share/sounds/freedesktop/stereo")
        if default_dir.is_dir():
            for f in default_dir.glob("*.oga"):
                return f

        return None

    def play_sound(self, sound_path: str) -> None:
        if not self.sound_enabled:
            return

        resolved = self._resolve_sound_path(sound_path)
        player = self._find_audio_player(resolved.suffix if resolved else "")

        if not player:
            # Fallback to terminal bell if audio player is unavailable
            try:
                sys.stdout.write("\a")
                sys.stdout.flush()
            except Exception:
                pass
            return

        if resolved and resolved.is_file():
            cmd: List[str] = []
            if player == "canberra-gtk-play":
                cmd = ["canberra-gtk-play", "-f", str(resolved)]
            elif player in ("paplay", "pw-play", "aplay"):
                cmd = [player, str(resolved)]
            elif player == "ogg123":
                cmd = ["ogg123", "-q", str(resolved)]
            elif player == "ffplay":
                cmd = ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", str(resolved)]
            elif player == "mpv":
                cmd = ["mpv", "--no-video", "--really-quiet", str(resolved)]

            if cmd:
                try:
                    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    return
                except Exception:
                    pass

        # If file couldn't be resolved, try canberra event sound name if canberra is available
        if player == "canberra-gtk-play":
            event_name = Path(sound_path).stem
            try:
                subprocess.Popen(
                    ["canberra-gtk-play", "-i", event_name],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return
            except Exception:
                pass

        # Terminal bell fallback
        try:
            sys.stdout.write("\a")
            sys.stdout.flush()
        except Exception:
            pass
