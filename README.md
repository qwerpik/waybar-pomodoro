# 🍅 waybar-pomodoro

[![CI Test Suite](https://github.com/qwerpik/waybar-pomodoro/actions/workflows/test.yml/badge.svg)](https://github.com/qwerpik/waybar-pomodoro/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Code style: ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

A lightweight, distraction-free, concurrency-hardened, and highly customizable Pomodoro timer module built specifically for [Waybar](https://github.com/Alexays/Waybar).

Designed with zero external dependencies (pure Python 3 standard library), atomic advisory file locking, instant reactive signal updates (`SIGRTMIN+8`), mouse wheel duration adjustments, customizable sound/desktop notifications, rich Pango tooltips, and daily focus statistics.

---

## ✨ Features

- **⚡ Zero External Dependencies**: Written in pure Python 3 using standard libraries. No bloated virtual environments or pip dependencies required.
- **🔒 Race-Free Concurrency**: Process synchronization via POSIX advisory locks (`fcntl.flock`) and atomic file writes (`fsync` + rename) ensures rapid mouse wheel adjustments never drop increments or corrupt state files.
- **🎯 Instant Waybar Updates**: Leverages Waybar's realtime signals (`SIGRTMIN+8`) for zero-latency UI updates on click or wheel scroll.
- **🖱️ Full Mouse & Wheel Interaction**:
  - **Left Click**: Start / Pause / Resume
  - **Right Click**: Reset timer back to initial session
  - **Middle Click**: Skip to next phase (Work ↔ Break)
  - **Scroll Wheel**: Fine-tune timer on the fly (`+1m` / `-1m`)
- **🔇 Minimalist & Distraction-Free**: Supports clean numbers-only mode (e.g. `30:00`), icon mode (`🍅 30:00`), or custom formatted templates.
- **🏷️ Full Waybar Protocol Support**: Exposes `text`, `alt`, `tooltip`, `class`, and `percentage` fields, allowing native `{alt}` token and Waybar `format-icons` mapping.
- **🔔 Desktop & Sound Alerts**: Native `notify-send` alerts with custom categories (`timer`), notification replacement IDs (no notification spam), and audio chime playback via `canberra-gtk-play`, `pw-play`, `paplay`, `ogg123`, `ffplay`, or `mpv`.
- **💤 Suspend/Sleep Protection**: Intelligently detects system suspend/sleep to prevent phantom sessions or delayed alarm blasts upon waking.
- **📊 Focus Statistics & Streaks**: Persistently tracks completed Pomodoro sessions, focus time in minutes/hours, daily streaks (with day-rollover preservation), and JSON/CSV export.
- **🎨 Theme Presets Included**: Ready-to-use CSS stylesheets for Minimal Black, Gruvbox, Catppuccin Mocha, Nord, Tokyo Night, and Dracula.

---

## 🚀 Installation

### Option 1: Quick Install Script

Clone the repository and run the install script:

```bash
git clone https://github.com/qwerpik/waybar-pomodoro.git
cd waybar-pomodoro
./install.sh
```

This installs the binary to `~/.local/bin/waybar-pomodoro` and creates a default config in `~/.config/waybar-pomodoro/config.json`.

*(Ensure `~/.local/bin` is in your `$PATH`)*

### Option 2: Pipx (Recommended for standalone CLI)

Install directly from GitHub without cloning:

```bash
pipx install git+https://github.com/qwerpik/waybar-pomodoro.git
```

Or from a local clone:

```bash
pipx install .
```

### Option 3: Arch Linux (PKGBUILD)

```bash
cd packaging
makepkg -si
```

---

## ⚙️ Waybar Configuration

### 1. Add module to `~/.config/waybar/config.jsonc`

Add `"custom/pomodoro"` to your `modules-center`, `modules-left`, or `modules-right`:

```jsonc
{
    // ...
    "modules-center": [
        "custom/pomodoro"
    ],
    // ...
    "custom/pomodoro": {
        "format": "{}",
        "return-type": "json",
        "exec": "waybar-pomodoro status",
        "on-click": "waybar-pomodoro toggle",
        "on-click-right": "waybar-pomodoro reset",
        "on-click-middle": "waybar-pomodoro skip",
        "on-scroll-up": "waybar-pomodoro adjust +1m",
        "on-scroll-down": "waybar-pomodoro adjust -1m",
        "interval": 1,
        "signal": 8
    }
}
```

#### Optional: Waybar `format-icons` via `{alt}`

Because `waybar-pomodoro` outputs the native `alt` field (`idle`, `work`, `short_break`, `long_break`, `paused`), you can also let Waybar format icons natively:

```jsonc
    "custom/pomodoro": {
        "format": "{icon} {text}",
        "return-type": "json",
        "exec": "waybar-pomodoro status --plain",
        "format-icons": {
            "work": "🍅",
            "short_break": "☕",
            "long_break": "🌴",
            "paused": "⏸",
            "idle": "⏱"
        },
        "on-click": "waybar-pomodoro toggle",
        "on-click-right": "waybar-pomodoro reset",
        "interval": 1,
        "signal": 8
    }
```

### 2. Rich Pango Tooltip & Progress Bar

Hovering over the module in Waybar renders a rich Pango-formatted tooltip with a 12-segment character progress bar, session ratio counter, controls cheat-sheet, and daily streak tracking:

```text
┌──────────────────────────────────────────────┐
│ 🍅 Focus Session [2/4]               Running │
│ ▰▰▰▰▰▰▱▱▱▱▱▱  12:30 (50%)                    │
│ ───────────────────────────────────────────  │
│ • Left-click:   Toggle / Pause               │
│ • Right-click:  Reset Session                │
│ • Middle-click: Skip Phase                   │
│ • Scroll:       ±1 min                       │
│ ───────────────────────────────────────────  │
│ Today:  3 session(s) • 90m focus             │
│ Streak: 5 day(s) 🔥                          │
└──────────────────────────────────────────────┘
```

### 3. Style in `~/.config/waybar/style.css`

#### Capsule Pill Badge Theme (Gruvbox Dark)
```css
#custom-pomodoro {
    background-color: #282828;
    color: #ebdbb2;
    padding: 2px 14px;
    margin: 3px 4px;
    border-radius: 9999px;
    border: 1px solid rgba(235, 219, 178, 0.15);
    font-weight: bold;
    transition: all 0.2s ease-in-out;
}

#custom-pomodoro:hover {
    border-color: rgba(235, 219, 178, 0.4);
}

#custom-pomodoro.stopped,
#custom-pomodoro.idle {
    background-color: #282828;
    color: #a89984;
    border-color: rgba(168, 153, 132, 0.25);
}

#custom-pomodoro.work {
    background-color: #382321;
    color: #ea6962;
    border-color: rgba(234, 105, 98, 0.45);
}

#custom-pomodoro.break {
    background-color: #2b331f;
    color: #b8bb26;
    border-color: rgba(184, 187, 38, 0.45);
}

#custom-pomodoro.long-break {
    background-color: #20332e;
    color: #8ec07c;
    border-color: rgba(142, 192, 124, 0.45);
}

#custom-pomodoro.paused {
    background-color: #37311d;
    color: #fabd2f;
    border-color: rgba(250, 189, 47, 0.45);
    opacity: 0.85;
}
```

*All modern capsule pill badge themes (Catppuccin Mocha, Dracula, Gruvbox, Nord, Tokyo Night, Minimal Black) are available in the [`docs/themes/`](docs/themes/) folder.*

### 4. Reload Waybar

```bash
pkill -SIGUSR2 waybar
```

---

## 📖 Command Line Interface (CLI)

`waybar-pomodoro` can also be controlled directly from your terminal, scripts, or window manager keybindings:

```bash
waybar-pomodoro status           # Output Waybar JSON payload
waybar-pomodoro status --plain   # Output plain text (e.g. "30:00")
waybar-pomodoro time-left        # Print remaining duration ("25:00")
waybar-pomodoro time-left -s     # Print raw remaining seconds (1500)
waybar-pomodoro toggle           # Start / Pause / Resume
waybar-pomodoro start            # Start timer
waybar-pomodoro start 45m        # Start timer with ad-hoc duration (e.g. 45 min)
waybar-pomodoro pause            # Pause timer
waybar-pomodoro resume           # Resume timer
waybar-pomodoro reset            # Reset back to configured work duration
waybar-pomodoro reset 25m        # Reset back to custom duration
waybar-pomodoro stop             # Stop timer and return to idle
waybar-pomodoro skip             # Skip current phase to break or work
waybar-pomodoro adjust +5m       # Add 5 minutes to current timer
waybar-pomodoro adjust -1m       # Subtract 1 minute
waybar-pomodoro stats            # Show daily & overall focus stats summary
waybar-pomodoro stats --json     # Export stats in JSON format
waybar-pomodoro stats --csv      # Export daily activity history in CSV format
waybar-pomodoro stats --reset    # Clear recorded statistics
waybar-pomodoro test-alert       # Trigger test desktop notification and audio chime
waybar-pomodoro config --show    # Display active JSON configuration
waybar-pomodoro config --init    # Generate default configuration file
```

### Window Manager Keybinding Examples

#### Hyprland (`~/.config/hypr/hyprland.conf`)
```ini
bind = $mainMod, P, exec, waybar-pomodoro toggle
bind = $mainMod SHIFT, P, exec, waybar-pomodoro reset
bind = $mainMod ALT, P, exec, waybar-pomodoro skip
```

#### Sway / i3 (`~/.config/sway/config` or `~/.config/i3/config`)
```i3config
bindsym $mod+p exec waybar-pomodoro toggle
bindsym $mod+Shift+p exec waybar-pomodoro reset
bindsym $mod+Mod1+p exec waybar-pomodoro skip
```

---

## 🔧 Configuration (`config.json`)

Configuration is stored at `~/.config/waybar-pomodoro/config.json`:

```json
{
  "work_duration": 30,
  "short_break_duration": 5,
  "long_break_duration": 15,
  "cycles_before_long_break": 4,
  "style": "minimal",
  "format_work": "{time}",
  "format_short_break": "{time}",
  "format_long_break": "{time}",
  "format_paused": "⏸ {time}",
  "format_idle": "{time}",
  "icon_work": "🍅",
  "icon_short_break": "☕",
  "icon_long_break": "🌴",
  "icon_paused": "⏸",
  "icon_idle": "⏱",
  "sound_enabled": true,
  "sound_work_end": "/usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga",
  "sound_break_end": "/usr/share/sounds/freedesktop/stereo/complete.oga",
  "notification_enabled": true,
  "notification_urgency_work_end": "critical",
  "notification_urgency_break_end": "normal",
  "notification_timeout": 10000,
  "notification_category": "timer",
  "auto_start_break": true,
  "auto_start_work": true,
  "waybar_signal": 8
}
```

### Display Styles
- `"style": "minimal"`: Pure numbers only (e.g. `30:00`, `⏸ 29:45`). Clean and completely distraction-free.
- `"style": "icon"`: Prepends phase icon (e.g. `🍅 30:00`, `☕ 05:00`).
- `"style": "custom"`: Uses the custom format strings defined in `format_work`, `format_paused`, etc. Supported template tags: `{time}`, `{icon}`, `{cycle}`, `{phase}`.

---

## 📊 Statistics Tracking

`waybar-pomodoro` automatically logs every completed focus session to `~/.local/share/waybar-pomodoro/stats.json`.

View your stats at any time with `waybar-pomodoro stats`:

```text
Pomodoro Statistics
────────────────────────────────────
Today:
  • Completed Sessions : 4
  • Focus Time         : 120 min

Overall:
  • Total Sessions     : 28
  • Total Focus Time   : 14.0 hours
  • Daily Streak       : 5 day(s)
────────────────────────────────────
```

The Waybar tooltip also displays today's completed session count and active streak with GTK Pango formatting!

---

## 🧪 Running Tests & Quality Checks

A comprehensive test suite and linters are configured:

```bash
# Run unit tests
make test

# Run code style and lint checks
make lint

# Run static type checking
make typecheck

# Run all checks
make check
```

---

## 📄 License

MIT License © 2026 [qwerpik](https://github.com/qwerpik).  
See [LICENSE](LICENSE) for details.
