"""
Notification and audio alerts for waybar-pomodoro.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional


class Notifier:
    def __init__(self, sound_enabled: bool = True, notification_enabled: bool = True):
        self.sound_enabled = sound_enabled
        self.notification_enabled = notification_enabled
        self._audio_player = self._detect_audio_player()

    def _detect_audio_player(self) -> Optional[str]:
        for player in ["canberra-gtk-play", "paplay", "pw-play", "aplay", "mpv"]:
            if shutil.which(player):
                return player
        return None

    def send_notification(
        self,
        title: str,
        message: str,
        urgency: str = "normal",
        icon: str = "dialog-information",
    ) -> None:
        if not self.notification_enabled:
            return

        if not shutil.which("notify-send"):
            return

        cmd = [
            "notify-send",
            "-a", "Pomodoro",
            "-u", urgency,
            "-i", icon,
            title,
            message,
        ]
        try:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    def play_sound(self, sound_path: str) -> None:
        if not self.sound_enabled or not self._audio_player:
            return

        target = Path(sound_path)
        if not target.is_file():
            # If path doesn't exist, try canberra event sound name if using canberra
            if self._audio_player == "canberra-gtk-play":
                try:
                    subprocess.Popen(
                        ["canberra-gtk-play", "-i", target.stem],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                except Exception:
                    pass
            return

        cmd = []
        if self._audio_player == "canberra-gtk-play":
            cmd = ["canberra-gtk-play", "-f", str(target)]
        elif self._audio_player in ["paplay", "pw-play", "aplay"]:
            cmd = [self._audio_player, str(target)]
        elif self._audio_player == "mpv":
            cmd = ["mpv", "--no-video", "--really-quiet", str(target)]

        if cmd:
            try:
                subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass
