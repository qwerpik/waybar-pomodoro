"""
Statistics and activity tracking for waybar-pomodoro.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional


class PomodoroStats:
    def __init__(self, stats_file: Path | str):
        self.stats_file = Path(stats_file)
        self.data: Dict[str, Any] = self._load()

    def _load(self) -> Dict[str, Any]:
        default_data = {
            "days": {},  # "YYYY-MM-DD": {"completed_sessions": int, "focus_seconds": int}
            "total_completed": 0,
            "total_focus_seconds": 0,
        }
        if self.stats_file.is_file():
            try:
                with open(self.stats_file, "r", encoding="utf-8") as f:
                    content = json.load(f)
                    if isinstance(content, dict):
                        return {**default_data, **content}
            except Exception:
                pass
        return default_data

    def _save(self) -> None:
        try:
            self.stats_file.parent.mkdir(parents=True, exist_ok=True)
            temp_file = self.stats_file.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
            temp_file.replace(self.stats_file)
        except Exception:
            pass

    def record_session(self, duration_seconds: int, session_date: Optional[date] = None) -> None:
        """Records a completed work session."""
        today_str = (session_date or date.today()).isoformat()
        if today_str not in self.data["days"]:
            self.data["days"][today_str] = {"completed_sessions": 0, "focus_seconds": 0}

        self.data["days"][today_str]["completed_sessions"] += 1
        self.data["days"][today_str]["focus_seconds"] += duration_seconds
        self.data["total_completed"] += 1
        self.data["total_focus_seconds"] += duration_seconds
        self._save()

    def get_today_stats(self) -> Dict[str, int]:
        today_str = date.today().isoformat()
        return self.data["days"].get(today_str, {"completed_sessions": 0, "focus_seconds": 0})

    def get_streak(self) -> int:
        """Calculates current streak of consecutive active days."""
        days_set = set(self.data.get("days", {}).keys())
        if not days_set:
            return 0

        today = date.today()
        yesterday = today - timedelta(days=1)
        
        # Check if active today or yesterday
        current = today if today.isoformat() in days_set else (yesterday if yesterday.isoformat() in days_set else None)
        if not current:
            return 0

        streak = 0
        while current.isoformat() in days_set and self.data["days"][current.isoformat()].get("completed_sessions", 0) > 0:
            streak += 1
            current -= timedelta(days=1)

        return streak

    def format_summary(self) -> str:
        today = self.get_today_stats()
        today_mins = today["focus_seconds"] // 60
        total_hours = self.data["total_focus_seconds"] / 3600
        streak = self.get_streak()

        lines = [
            "Pomodoro Statistics",
            "─" * 36,
            "Today:",
            f"  • Completed Sessions : {today['completed_sessions']}",
            f"  • Focus Time         : {today_mins} min",
            "",
            "Overall:",
            f"  • Total Sessions     : {self.data['total_completed']}",
            f"  • Total Focus Time   : {total_hours:.1f} hours",
            f"  • Daily Streak       : {streak} day(s)",
            "─" * 36,
        ]
        return "\n".join(lines)
