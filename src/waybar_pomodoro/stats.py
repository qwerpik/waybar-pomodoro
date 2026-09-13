"""
Statistics and activity tracking for waybar-pomodoro.
"""

from __future__ import annotations

import csv
import fcntl
import io
import json
import os
import tempfile
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


class PomodoroStats:
    def __init__(self, stats_file: Path | str):
        self.stats_file = Path(stats_file)
        self.lock_file = self.stats_file.with_suffix(".lock")
        self.data: Dict[str, Any] = self._load()

    def _default_data(self) -> Dict[str, Any]:
        return {
            "days": {},  # "YYYY-MM-DD": {"completed_sessions": int, "focus_seconds": int}
            "total_completed": 0,
            "total_focus_seconds": 0,
        }

    def _load(self) -> Dict[str, Any]:
        default = self._default_data()
        if self.stats_file.is_file():
            try:
                with open(self.stats_file, "r", encoding="utf-8") as f:
                    content = json.load(f)
                    if isinstance(content, dict):
                        return {**default, **content}
            except Exception:
                pass
        return default

    def _save(self) -> None:
        self.stats_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.stats_file.parent, 0o700)
        except OSError:
            pass

        temp_path = None
        with open(self.lock_file, "a") as lock_f:
            fcntl.flock(lock_f.fileno(), fcntl.LOCK_EX)
            try:
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    dir=self.stats_file.parent,
                    encoding="utf-8",
                    delete=False,
                    prefix=f".{self.stats_file.name}.",
                    suffix=".tmp",
                ) as tmp:
                    temp_path = Path(tmp.name)
                    os.chmod(tmp.fileno(), 0o600)
                    json.dump(self.data, tmp, indent=2)
                    tmp.flush()
                    os.fsync(tmp.fileno())

                temp_path.replace(self.stats_file)
            except Exception:
                if temp_path and temp_path.exists():
                    try:
                        temp_path.unlink()
                    except OSError:
                        pass
                raise
            finally:
                fcntl.flock(lock_f.fileno(), fcntl.LOCK_UN)

    def record_session(self, duration_seconds: int, session_date: Optional[date] = None) -> None:
        """Records a completed work session with process synchronization."""
        self.stats_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.stats_file.parent, 0o700)
        except OSError:
            pass

        temp_path = None
        with open(self.lock_file, "a") as lock_f:
            fcntl.flock(lock_f.fileno(), fcntl.LOCK_EX)
            try:
                # Reload fresh state under lock to prevent lost updates
                self.data = self._load()
                today_str = (session_date or date.today()).isoformat()
                if today_str not in self.data["days"]:
                    self.data["days"][today_str] = {"completed_sessions": 0, "focus_seconds": 0}

                self.data["days"][today_str]["completed_sessions"] += 1
                self.data["days"][today_str]["focus_seconds"] += max(0, duration_seconds)
                self.data["total_completed"] += 1
                self.data["total_focus_seconds"] += max(0, duration_seconds)

                with tempfile.NamedTemporaryFile(
                    mode="w",
                    dir=self.stats_file.parent,
                    encoding="utf-8",
                    delete=False,
                    prefix=f".{self.stats_file.name}.",
                    suffix=".tmp",
                ) as tmp:
                    temp_path = Path(tmp.name)
                    os.chmod(tmp.fileno(), 0o600)
                    json.dump(self.data, tmp, indent=2)
                    tmp.flush()
                    os.fsync(tmp.fileno())

                temp_path.replace(self.stats_file)
            except Exception:
                if temp_path and temp_path.exists():
                    try:
                        temp_path.unlink()
                    except OSError:
                        pass
                raise
            finally:
                fcntl.flock(lock_f.fileno(), fcntl.LOCK_UN)

    def get_today_stats(self, data: Optional[Dict[str, Any]] = None) -> Dict[str, int]:
        d = data if data is not None else self._load()
        today_str = date.today().isoformat()
        res = d.get("days", {}).get(today_str, {"completed_sessions": 0, "focus_seconds": 0})
        return {
            "completed_sessions": int(res.get("completed_sessions", 0)),
            "focus_seconds": int(res.get("focus_seconds", 0)),
        }

    def get_streak(self, data: Optional[Dict[str, Any]] = None) -> int:
        """Calculates current streak of consecutive active days."""
        d = data if data is not None else self._load()
        days_dict = d.get("days", {})
        if not days_dict:
            return 0

        today = date.today()
        yesterday = today - timedelta(days=1)

        today_sessions = days_dict.get(today.isoformat(), {}).get("completed_sessions", 0)
        yesterday_sessions = days_dict.get(yesterday.isoformat(), {}).get("completed_sessions", 0)

        # If user has completed a session today, streak starts from today.
        # If user hasn't completed a session today yet, but was active yesterday,
        # yesterday's streak is still alive!
        if today_sessions > 0:
            current = today
        elif yesterday_sessions > 0:
            current = yesterday
        else:
            return 0

        streak = 0
        while (
            current.isoformat() in days_dict
            and days_dict[current.isoformat()].get("completed_sessions", 0) > 0
        ):
            streak += 1
            current -= timedelta(days=1)

        return streak

    def get_today_and_streak(self) -> Tuple[Dict[str, int], int]:
        """Loads stats once from disk and returns both today's stats and streak."""
        d = self._load()
        return self.get_today_stats(data=d), self.get_streak(data=d)

    def format_summary(self) -> str:
        self.data = self._load()
        today = self.get_today_stats()
        today_mins = today["focus_seconds"] // 60
        total_hours = self.data.get("total_focus_seconds", 0) / 3600
        streak = self.get_streak()

        lines = [
            "Pomodoro Statistics",
            "─" * 36,
            "Today:",
            f"  • Completed Sessions : {today['completed_sessions']}",
            f"  • Focus Time         : {today_mins} min",
            "",
            "Overall:",
            f"  • Total Sessions     : {self.data.get('total_completed', 0)}",
            f"  • Total Focus Time   : {total_hours:.1f} hours",
            f"  • Daily Streak       : {streak} day(s)",
            "─" * 36,
        ]
        return "\n".join(lines)

    def to_json(self) -> str:
        self.data = self._load()
        payload = {
            **self.data,
            "current_streak": self.get_streak(),
            "today": self.get_today_stats(),
        }
        return json.dumps(payload, indent=2)

    def to_csv(self) -> str:
        self.data = self._load()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["date", "completed_sessions", "focus_minutes"])
        for day_str in sorted(self.data.get("days", {}).keys()):
            entry = self.data["days"][day_str]
            mins = entry.get("focus_seconds", 0) // 60
            writer.writerow([day_str, entry.get("completed_sessions", 0), mins])
        return output.getvalue()

    def reset(self) -> None:
        self.data = self._default_data()
        self._save()
