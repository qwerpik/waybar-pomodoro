"""
Statistics and activity tracking for waybar-pomodoro.
"""

from __future__ import annotations

import csv
import fcntl
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


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

    def get_longest_streak(self, data: Optional[Dict[str, Any]] = None) -> int:
        """Calculates the all-time record streak of consecutive active days."""
        d = data if data is not None else self._load()
        days_dict = d.get("days", {})
        if not days_dict:
            return 0

        active_dates = sorted(
            [
                date.fromisoformat(ds)
                for ds, v in days_dict.items()
                if v.get("completed_sessions", 0) > 0
            ]
        )
        if not active_dates:
            return 0

        max_streak = 1
        current_run = 1
        for i in range(1, len(active_dates)):
            diff = (active_dates[i] - active_dates[i - 1]).days
            if diff == 1:
                current_run += 1
                if current_run > max_streak:
                    max_streak = current_run
            elif diff > 1:
                current_run = 1

        return max_streak

    def get_today_and_streak(self) -> Tuple[Dict[str, int], int]:
        """Loads stats once from disk and returns both today's stats and streak."""
        d = self._load()
        return self.get_today_stats(data=d), self.get_streak(data=d)

    def get_contribution_grid(
        self,
        weeks: int = 52,
        end_date: Optional[date] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Builds a 7xN calendar matrix matching GitHub's contribution graph.
        Rows: 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun.
        Columns: weeks (from oldest to most recent).
        """
        d = data if data is not None else self._load()
        days_dict = d.get("days", {})
        today = end_date or date.today()

        # End grid on the Sunday of the current week so every column is 7 days
        days_until_sunday = 6 - today.weekday()
        grid_end = today + timedelta(days=days_until_sunday)
        # Start weeks * 7 days earlier (guaranteed Monday)
        grid_start = grid_end - timedelta(days=weeks * 7 - 1)

        matrix: List[List[Dict[str, Any]]] = []
        month_labels: List[Tuple[int, str]] = []
        last_month = -1

        for w in range(weeks):
            col_cells: List[Dict[str, Any]] = []
            col_start_date = grid_start + timedelta(days=w * 7)

            if col_start_date.month != last_month and col_start_date.day <= 14:
                month_name = col_start_date.strftime("%b")
                month_labels.append((w, month_name))
                last_month = col_start_date.month

            for r in range(7):
                curr_date = col_start_date + timedelta(days=r)
                iso = curr_date.isoformat()
                is_future = curr_date > today

                if is_future:
                    col_cells.append(
                        {
                            "date": iso,
                            "sessions": 0,
                            "focus_seconds": 0,
                            "level": 0,
                            "is_future": True,
                        }
                    )
                else:
                    entry = days_dict.get(iso, {})
                    sessions = int(entry.get("completed_sessions", 0))
                    focus_sec = int(entry.get("focus_seconds", 0))

                    if sessions == 0:
                        level = 0
                    elif sessions <= 2:
                        level = 1
                    elif sessions <= 4:
                        level = 2
                    elif sessions <= 6:
                        level = 3
                    else:
                        level = 4

                    col_cells.append(
                        {
                            "date": iso,
                            "sessions": sessions,
                            "focus_seconds": focus_sec,
                            "level": level,
                            "is_future": False,
                        }
                    )
            matrix.append(col_cells)

        return {
            "weeks": weeks,
            "start_date": grid_start.isoformat(),
            "end_date": today.isoformat(),
            "month_labels": month_labels,
            "matrix": matrix,
        }

    def render_heatmap(
        self,
        weeks: Optional[int] = None,
        use_color: Optional[bool] = None,
    ) -> str:
        """
        Renders a 7-row GitHub contribution-style heatmap for the terminal.
        """
        d = self._load()
        if weeks is None:
            term_cols = shutil.get_terminal_size((80, 24)).columns
            if term_cols < 65:
                weeks = 20
            elif term_cols < 90:
                weeks = 30
            elif term_cols < 120:
                weeks = 42
            else:
                weeks = 52

        if use_color is None:
            use_color = "NO_COLOR" not in os.environ and sys.stdout.isatty()

        grid_data = self.get_contribution_grid(weeks=weeks, data=d)
        matrix = grid_data["matrix"]
        month_labels = grid_data["month_labels"]

        # ANSI palette for GitHub green contribution scale
        # 0: dim, 1: dark green, 2: medium green, 3: bright green, 4: neon green
        ansi_colors = {
            0: "\033[90m",  # Gray / Dark
            1: "\033[38;2;14;68;41m",  # #0e4429
            2: "\033[38;2;0;109;50m",  # #006d32
            3: "\033[38;2;38;166;65m",  # #26a641
            4: "\033[38;2;57;211;83m",  # #39d353
        }
        reset = "\033[0m"

        chars = {
            0: "·",
            1: "░",
            2: "▒",
            3: "▓",
            4: "█",
        }

        # Build Month Header Line
        # Header starts after 4 char indent for day names
        header_chars = [" "] * (weeks * 2)
        for col_idx, m_name in month_labels:
            pos = col_idx * 2
            if pos + len(m_name) <= len(header_chars):
                for i, ch in enumerate(m_name):
                    header_chars[pos + i] = ch
        month_line = "    " + "".join(header_chars).rstrip()

        # Build Day Rows (Mon=0, ..., Sun=6)
        day_labels = ["Mon", "   ", "Wed", "   ", "Fri", "   ", "Sun"]
        row_lines = []

        for r in range(7):
            row_str = [f"{day_labels[r]} "]
            for w in range(weeks):
                cell = matrix[w][r]
                lvl = cell["level"]
                if cell["is_future"]:
                    row_str.append("  ")
                    continue

                if use_color:
                    # Colored block or dot
                    ch = "■ " if lvl > 0 else "· "
                    color = ansi_colors.get(lvl, "\033[90m")
                    row_str.append(f"{color}{ch}{reset}")
                else:
                    ch = chars.get(lvl, "·")
                    row_str.append(f"{ch} ")
            row_lines.append("".join(row_str).rstrip())

        # Legend & summary
        if use_color:
            legend_cells = [
                f"{ansi_colors[0]}·{reset}",
                f"{ansi_colors[1]}■{reset}",
                f"{ansi_colors[2]}■{reset}",
                f"{ansi_colors[3]}■{reset}",
                f"{ansi_colors[4]}■{reset}",
            ]
        else:
            legend_cells = [chars[i] for i in range(5)]
        legend_str = "    Less " + " ".join(legend_cells) + " More"

        # Summary statistics
        total_sessions = d.get("total_completed", 0)
        total_hours = d.get("total_focus_seconds", 0) / 3600
        curr_streak = self.get_streak(data=d)
        best_streak = self.get_longest_streak(data=d)
        active_days = sum(
            1 for v in d.get("days", {}).values() if v.get("completed_sessions", 0) > 0
        )

        title = f"🍅 POMODORO STUDY TRACKER ({weeks} Weeks)"
        divider = "─" * max(len(month_line), 50)
        stats_line = (
            f"  • Total Focus: {total_hours:.1f}h ({total_sessions} sessions)\n"
            f"  • Current Streak: {curr_streak} day(s) 🔥\n"
            f"  • Best Streak: {best_streak} day(s) 🏆\n"
            f"  • Active Days: {active_days} days"
        )

        output = [
            title,
            divider,
            month_line,
            *row_lines,
            "",
            legend_str,
            divider,
            stats_line,
        ]
        return "\n".join(output)

    def render_svg(self, weeks: int = 52, theme: str = "github-dark") -> str:
        """
        Generates a standalone, beautiful GitHub contributions-style SVG graphic.
        """
        d = self._load()
        grid_data = self.get_contribution_grid(weeks=weeks, data=d)
        matrix = grid_data["matrix"]
        month_labels = grid_data["month_labels"]

        themes = {
            "github-dark": {
                "bg": "#0d1117",
                "card": "#161b22",
                "border": "#30363d",
                "text": "#e6edf3",
                "muted": "#848d97",
                "levels": ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"],
                "cell_border": "rgba(255,255,255,0.05)",
            },
            "catppuccin": {
                "bg": "#1e1e2e",
                "card": "#181825",
                "border": "#313244",
                "text": "#cdd6f4",
                "muted": "#9399b2",
                "levels": ["#313244", "#45475a", "#a6e3a1", "#94e2d5", "#89b4fa"],
                "cell_border": "rgba(255,255,255,0.05)",
            },
            "gruvbox": {
                "bg": "#282828",
                "card": "#1d2021",
                "border": "#504945",
                "text": "#ebdbb2",
                "muted": "#a89984",
                "levels": ["#3c3836", "#504945", "#98971a", "#b8bb26", "#fabd2f"],
                "cell_border": "rgba(255,255,255,0.05)",
            },
            "tokyo-night": {
                "bg": "#1a1b26",
                "card": "#16161e",
                "border": "#292e42",
                "text": "#c0caf5",
                "muted": "#565f89",
                "levels": ["#24283b", "#3b4261", "#73daca", "#7aa2f7", "#bb9af7"],
                "cell_border": "rgba(255,255,255,0.05)",
            },
            "nord": {
                "bg": "#2e3440",
                "card": "#242933",
                "border": "#434c5e",
                "text": "#eceff4",
                "muted": "#88c0d0",
                "levels": ["#3b4252", "#434c5e", "#88c0d0", "#81a1c1", "#5e81ac"],
                "cell_border": "rgba(255,255,255,0.05)",
            },
        }

        pal = themes.get(theme, themes["github-dark"])

        cell_size = 11
        cell_gap = 3
        step = cell_size + cell_gap

        left_pad = 40
        top_pad = 70
        width = left_pad + (weeks * step) + 30
        height = top_pad + (7 * step) + 65

        total_sessions = d.get("total_completed", 0)
        total_hours = d.get("total_focus_seconds", 0) / 3600
        curr_streak = self.get_streak(data=d)
        best_streak = self.get_longest_streak(data=d)

        bg_col = pal["bg"]
        border_col = pal["border"]
        txt_col = pal["text"]
        muted_col = pal["muted"]

        summary_subtitle = (
            f"{total_sessions} sessions · {total_hours:.1f}h · "
            f"Streak: {curr_streak}d 🔥 · Best: {best_streak}d 🏆"
        )

        svg_parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" '
            f'font-family="system-ui, -apple-system, Segoe UI, sans-serif">',
            f'  <rect width="{width}" height="{height}" rx="12" '
            f'fill="{bg_col}" stroke="{border_col}" stroke-width="1"/>',
            # Header Title & Summary Badges
            f'  <text x="{left_pad}" y="32" font-size="16" font-weight="bold" '
            f'fill="{txt_col}">🍅 Pomodoro Study Tracker</text>',
            f'  <text x="{left_pad}" y="50" font-size="12" '
            f'fill="{muted_col}">{summary_subtitle}</text>',
        ]

        # Month labels
        for col_idx, m_name in month_labels:
            mx = left_pad + (col_idx * step)
            my = top_pad - 8
            svg_parts.append(
                f'  <text x="{mx}" y="{my}" font-size="10" fill="{muted_col}">{m_name}</text>'
            )

        # Day labels (Mon, Wed, Fri)
        day_names = ["Mon", "", "Wed", "", "Fri", "", ""]
        for r, day_name in enumerate(day_names):
            if day_name:
                dy = top_pad + (r * step) + 9
                svg_parts.append(
                    f'  <text x="{left_pad - 8}" y="{dy}" text-anchor="end" '
                    f'font-size="10" fill="{muted_col}">{day_name}</text>'
                )

        # Contribution cells
        for w in range(weeks):
            for r in range(7):
                cell = matrix[w][r]
                if cell["is_future"]:
                    continue

                cx = left_pad + (w * step)
                cy = top_pad + (r * step)
                color = pal["levels"][cell["level"]]
                sessions = cell["sessions"]
                mins = cell["focus_seconds"] // 60
                date_str = cell["date"]

                tooltip = f"{date_str}: {sessions} sessions ({mins} mins)"
                svg_parts.append(
                    f'  <rect x="{cx}" y="{cy}" width="{cell_size}" height="{cell_size}" rx="2" '
                    f'fill="{color}" stroke="{pal["cell_border"]}" stroke-width="0.5">'
                    f"<title>{tooltip}</title></rect>"
                )

        # Legend at bottom right
        legend_y = top_pad + (7 * step) + 30
        legend_start_x = width - 30 - (5 * step) - 70
        svg_parts.append(
            f'  <text x="{legend_start_x - 6}" y="{legend_y + 9}" text-anchor="end" '
            f'font-size="10" fill="{muted_col}">Less</text>'
        )

        for i in range(5):
            lx = legend_start_x + (i * step)
            color = pal["levels"][i]
            svg_parts.append(
                f'  <rect x="{lx}" y="{legend_y}" width="{cell_size}" height="{cell_size}" '
                f'rx="2" fill="{color}"/>'
            )

        svg_parts.append(
            f'  <text x="{legend_start_x + (5 * step) + 6}" y="{legend_y + 9}" '
            f'font-size="10" fill="{muted_col}">More</text>'
        )

        svg_parts.append("</svg>")
        return "\n".join(svg_parts)

    def export_chart(
        self,
        output_path: Optional[Path | str] = None,
        theme: str = "github-dark",
        open_browser: bool = False,
    ) -> Path:
        """
        Exports the Study Tracker SVG (and optional HTML wrapper) to file.
        """
        if output_path is None:
            target = self.stats_file.parent / "study-tracker.svg"
        else:
            target = Path(output_path).expanduser().resolve()

        target.parent.mkdir(parents=True, exist_ok=True)
        svg_content = self.render_svg(weeks=52, theme=theme)

        with open(target, "w", encoding="utf-8") as f:
            f.write(svg_content)

        if open_browser:
            try:
                subprocess.Popen(
                    ["xdg-open", str(target)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception:
                pass

        return target

    def format_summary(self) -> str:
        self.data = self._load()
        today = self.get_today_stats()
        today_mins = today["focus_seconds"] // 60
        total_hours = self.data.get("total_focus_seconds", 0) / 3600
        streak = self.get_streak()
        best_streak = self.get_longest_streak()

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
            f"  • Record Streak      : {best_streak} day(s)",
            "─" * 36,
        ]
        return "\n".join(lines)

    def to_json(self) -> str:
        self.data = self._load()
        payload = {
            **self.data,
            "current_streak": self.get_streak(),
            "longest_streak": self.get_longest_streak(),
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
