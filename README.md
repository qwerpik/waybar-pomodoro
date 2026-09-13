# 🍅 waybar-pomodoro

A lightweight, distraction-free, and highly customizable Pomodoro timer module built specifically for [Waybar](https://github.com/Alexays/Waybar).

Designed with zero heavy dependencies (pure Python 3 standard library), instant reactive signal updates, mouse wheel duration adjustments, customizable sound/desktop notifications, and daily focus statistics.

---

## ✨ Features

- **⚡ Zero External Dependencies**: Written in pure Python 3 using standard libraries. No bloated virtual environments or pip dependencies required.
- **🎯 Instant Waybar Updates**: Leverages Waybar's realtime real-time signals (`SIGRTMIN+8`) for zero-latency UI updates on click or action.
- **🖱️ Full Mouse & Wheel Interaction**:
  - **Left Click**: Start / Pause / Resume
  - **Right Click**: Reset timer back to initial session
  - **Middle Click**: Skip to next phase (Work ↔ Break)
  - **Scroll Wheel**: Fine-tune timer on the fly (`+1m` / `-1m`)
- **🔇 Minimalist & Distraction-Free**: Supports clean numbers-only mode (e.g. `30:00`), icon mode (`🍅 30:00`), or custom formatted templates.
- **🔔 Desktop & Sound Alerts**: Native `notify-send` alerts with urgency levels, plus audio chime playback using `canberra-gtk-play`, `paplay`, `pw-play`, `aplay`, or `mpv`.
- **📊 Focus Statistics & Streaks**: Persistently tracks completed Pomodoro sessions, focus time in minutes/hours, and daily streaks.
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

### Option 2: Pip / Pipx

```bash
pip install .
# or with pipx:
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

### 2. Style in `~/.config/waybar/style.css`

#### Minimal Black Theme (Default Gruvbox / Dark)
```css
#custom-pomodoro {
    background-color: #1b1a1a;
    color: #ebdbb2;
    padding: 0px 14px;
    border-radius: 100px;
    margin: 0px 4px;
}

#custom-pomodoro.stopped,
#custom-pomodoro.idle,
#custom-pomodoro.work {
    background-color: #1b1a1a;
    color: #ebdbb2;
}

#custom-pomodoro.paused {
    background-color: #1b1a1a;
    color: #928374;
}

#custom-pomodoro.break {
    background-color: #1b1a1a;
    color: #b8bb26;
}
```

*More CSS themes (Catppuccin, Nord, Tokyo Night, Gruvbox) are available in the [`docs/themes/`](docs/themes/) folder.*

### 3. Reload Waybar

```bash
pkill -SIGUSR2 waybar
```

---

## 📖 Command Line Interface (CLI)

`waybar-pomodoro` can also be controlled directly from your terminal, scripts, or window manager keybindings:

```bash
waybar-pomodoro status           # Output Waybar JSON payload
waybar-pomodoro status --plain   # Output plain text (e.g. "30:00")
waybar-pomodoro toggle           # Start / Pause / Resume
waybar-pomodoro start            # Start timer
waybar-pomodoro pause            # Pause timer
waybar-pomodoro resume           # Resume timer
waybar-pomodoro reset            # Reset back to 30:00
waybar-pomodoro skip             # Skip current phase to break or work
waybar-pomodoro adjust +5m       # Add 5 minutes to current timer
waybar-pomodoro adjust -1m       # Subtract 1 minute
waybar-pomodoro stats            # Show daily & overall focus stats
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

The Waybar tooltip also shows today's completed session count automatically!

---

## 🧪 Running Tests

A complete unit test suite is included:

```bash
make test
# or:
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

---

## 📄 License

MIT License © 2026 [qwerpik](https://github.com/qwerpik).
See [LICENSE](LICENSE) for details.
