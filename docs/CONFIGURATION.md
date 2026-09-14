# 🔧 Configuration Guide (`config.json`)

`waybar-pomodoro` is designed to work out-of-the-box with sensible defaults, while offering granular configuration for session durations, display styles, audio chimes, desktop notifications, and state paths.

---

## 📑 Table of Contents

1. [Configuration File Location](#configuration-file-location)
2. [CLI Configuration Helpers](#cli-configuration-helpers)
3. [Full Configuration Reference](#full-configuration-reference)
4. [Display Styles & Template Formatting](#display-styles--template-formatting)
5. [Audio Alerts & Notification System](#audio-alerts--notification-system)
6. [Auto-Start & Cycle Management](#auto-start--cycle-management)
7. [Waybar Signal Integration](#waybar-signal-integration)
8. [Practical Configuration Recipes](#practical-configuration-recipes)
9. [Related Documentation](#related-documentation)

---

## 📍 Configuration File Location

`waybar-pomodoro` adheres strictly to the **XDG Base Directory Specification**:

| Target | Default Path | Environment Variable Override |
| :--- | :--- | :--- |
| **Configuration** | `~/.config/waybar-pomodoro/config.json` | `$XDG_CONFIG_HOME/waybar-pomodoro/config.json` |
| **Runtime State** | `~/.cache/waybar-pomodoro/state.json` | `$XDG_CACHE_HOME/waybar-pomodoro/state.json` |
| **Statistics** | `~/.local/share/waybar-pomodoro/stats.json` | `$XDG_DATA_HOME/waybar-pomodoro/stats.json` |

---

## 💻 CLI Configuration Helpers

You can inspect and manage your active configuration directly from the command line:

```bash
# Generate a default config.json if one does not already exist
waybar-pomodoro config --init

# Print the active configuration JSON (including defaults and overrides)
waybar-pomodoro config --show

# Run any command using a custom configuration file path
waybar-pomodoro --config ~/my-custom-pomodoro.json status
```

---

## 📋 Full Configuration Reference

Below is the complete reference of all 21 configuration options supported in `config.json`:

| Parameter | Type | Default | Valid Range / Choices | Description |
| :--- | :--- | :--- | :--- | :--- |
| `work_duration` | `int` | `30` | `1` – `1440` (min) | Duration of a work/focus session in minutes. |
| `short_break_duration` | `int` | `5` | `1` – `360` (min) | Duration of a short break in minutes. |
| `long_break_duration` | `int` | `15` | `1` – `360` (min) | Duration of a long break in minutes. |
| `cycles_before_long_break` | `int` | `4` | `1` – `100` | Number of work sessions before triggering a long break. |
| `style` | `string` | `"minimal"` | `"minimal"`, `"icon"`, `"custom"` | Rendering format style for the Waybar module. |
| `format_work` | `string` | `"{time}"` | Template string | Custom template string for active work sessions. |
| `format_short_break` | `string` | `"{time}"` | Template string | Custom template string for short break sessions. |
| `format_long_break` | `string` | `"{time}"` | Template string | Custom template string for long break sessions. |
| `format_paused` | `string` | `"⏸ {time}"` | Template string | Custom template string when the timer is paused. |
| `format_idle` | `string` | `"{time}"` | Template string | Custom template string when the timer is idle. |
| `icon_work` | `string` | `"🍅"` | UTF-8 glyph | Icon prepended in `"icon"` style or `{icon}` token during work. |
| `icon_short_break` | `string` | `"☕"` | UTF-8 glyph | Icon prepended during short breaks. |
| `icon_long_break` | `string` | `"🌴"` | UTF-8 glyph | Icon prepended during long breaks. |
| `icon_paused` | `string` | `"⏸"` | UTF-8 glyph | Icon prepended when paused. |
| `icon_idle` | `string` | `"⏱"` | UTF-8 glyph | Icon prepended when idle. |
| `sound_enabled` | `bool` | `true` | `true`, `false` | Enable or disable audio sound alerts upon phase completion. |
| `sound_work_end` | `string` | `"/usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga"` | File path or theme stem | Sound file or event sound played when a work session ends. |
| `sound_break_end` | `string` | `"/usr/share/sounds/freedesktop/stereo/complete.oga"` | File path or theme stem | Sound file or event sound played when a break ends. |
| `notification_enabled` | `bool` | `true` | `true`, `false` | Enable or disable desktop notifications via `notify-send`. |
| `notification_urgency_work_end` | `string` | `"critical"` | `"low"`, `"normal"`, `"critical"` | Notification urgency level when a work session completes. |
| `notification_urgency_break_end` | `string` | `"normal"` | `"low"`, `"normal"`, `"critical"` | Notification urgency level when a break completes. |
| `notification_timeout` | `int` | `10000` | `0` – `300000` (ms) | Notification expiration timeout in milliseconds (`0` = daemon default). |
| `notification_category` | `string` | `"timer"` | String | Desktop notification category identifier (`-c`). |
| `auto_start_break` | `bool` | `true` | `true`, `false` | Automatically begin the break countdown when work ends. |
| `auto_start_work` | `bool` | `true` | `true`, `false` | Automatically begin the next work session when break ends. |
| `waybar_signal` | `int` | `8` | `0` – `30` | Realtime signal offset (`SIGRTMIN + N`) used to trigger Waybar UI updates (`0` = disabled). |
| `menu_backend` | `string` | `"auto"` | `"auto"`, `"rofi"`, `"wofi"`, `"fuzzel"`, `"tofi"`, `"zenity"`, `"gtk"` | Backend engine used when launching `waybar-pomodoro menu`. |
| `menu_custom_command` | `string` | `""` | Command string | Optional custom launcher command string (e.g. `"rofi -dmenu -theme ~/.config/rofi/pomodoro.rasi"`). |
| `menu_presets` | `list[int]` | `[15, 25, 45, 60]` | List of ints (`1`–`1440`) | Quick duration presets shown in the right-click popup menu. |
| `state_file` | `string` | `~/.cache/waybar-pomodoro/state.json` | Valid path | Absolute or tilde path for the atomic state file. |
| `stats_file` | `string` | `~/.local/share/waybar-pomodoro/stats.json` | Valid path | Absolute or tilde path for the focus history and streak database. |

---

## 🎨 Display Styles & Template Formatting

### 1. Minimal Style (`"style": "minimal"`)
The default distraction-free mode. Displays only digits:
- **Idle**: `30:00`
- **Running**: `24:50`
- **Paused**: `⏸ 24:50`

### 2. Icon Style (`"style": "icon"`)
Prepends the configured UTF-8 emoji or Nerd Font glyph:
- **Idle**: `⏱ 30:00`
- **Work**: `🍅 24:50`
- **Short Break**: `☕ 04:30`
- **Long Break**: `🌴 14:15`
- **Paused**: `⏸ 24:50`

### 3. Custom Style (`"style": "custom"`)
Evaluates custom format strings (`format_work`, `format_short_break`, `format_long_break`, `format_paused`, `format_idle`) with dynamic interpolation tokens:

| Token | Replacement Value | Example |
| :--- | :--- | :--- |
| `{time}` | Remaining minutes and seconds (`MM:SS`) | `25:00` |
| `{icon}` | Corresponding phase icon | `🍅` or `☕` |
| `{cycle}` | Current cycle index | `1`, `2`, `3`, `4` |
| `{phase}` | Capitalized phase name | `Work`, `Short Break`, `Long Break` |

#### Custom Format Example
```json
{
  "style": "custom",
  "format_work": "{icon} [{cycle}/4] {time}",
  "format_short_break": "☕ Break: {time}",
  "format_long_break": "🌴 Long: {time}",
  "format_paused": "⏸ ({time})"
}
```

---

## 🔔 Audio Alerts & Notification System

### Audio Player Priority Fallback
When a session completes and `sound_enabled = true`, `waybar-pomodoro` automatically detects available system players in order of preference:
1. `canberra-gtk-play` (lowest latency; supports Freedesktop sound themes and event names)
2. `pw-play` (native PipeWire audio player)
3. `paplay` (native PulseAudio player)
4. `ogg123` (Vorbis audio player)
5. `ffplay` (FFmpeg headless player)
6. `mpv` (Headless MPV playback)
7. `aplay` (ALSA PCM player, used if sound file is `.wav`)
8. Terminal bell (`\a` fallback if no sound daemon is installed)

### Desktop Notification Spam Prevention
- Notifications use replace ID `4082` (`notify-send -r 4082`). Successive notifications replace previous ones on modern daemons (Mako, Dunst, SwayNC) rather than stacking into an unreadable column.
- System suspend / sleep detection: If the system wakes up after being asleep for more than 30 minutes, delayed alarm bursts and phantom focus time are suppressed.

---

## 🔄 Auto-Start & Cycle Management

The Pomodoro cycle alternates between work and break sessions:
```text
[Work 1] ➔ [Short Break] ➔ [Work 2] ➔ [Short Break] ➔ [Work 3] ➔ [Short Break] ➔ [Work 4] ➔ [Long Break (Reward)]
```
- Set `"auto_start_break": false` if you prefer to take a manual pause before starting break countdowns.
- Set `"auto_start_work": false` if you prefer to manually start your next work session when a break finishes.

---

## ⚡ Waybar Signal Integration

Waybar modules typically poll on an interval. To achieve **instant zero-latency updates** on click or scroll:
1. In `config.json`: `"waybar_signal": 8`
2. In Waybar's `config.jsonc`: `"signal": 8`

When you click or scroll on the module, `waybar-pomodoro` sends `pkill -x -u $UID -RTMIN+8 waybar`, instructing Waybar to immediately repaint without waiting for the 1-second interval tick.

---

## 💡 Practical Configuration Recipes

### Recipe 1: 50/10 Ultradian Focus Rhythm
For developers who prefer longer, deeper focus sprints:
```json
{
  "work_duration": 50,
  "short_break_duration": 10,
  "long_break_duration": 30,
  "cycles_before_long_break": 3
}
```

### Recipe 2: Stealth Silent Mode
Zero audio chimes and non-critical low-urgency notifications:
```json
{
  "sound_enabled": false,
  "notification_urgency_work_end": "low",
  "notification_urgency_break_end": "low",
  "notification_timeout": 5000
}
```

### Recipe 3: Nerd Fonts Custom Style
Using Nerd Font icons instead of color emojis:
```json
{
  "style": "custom",
  "icon_work": "󰄉",
  "icon_short_break": "󰤄",
  "icon_long_break": "󰂚",
  "icon_paused": "󰏤",
  "icon_idle": "󰔛",
  "format_work": "{icon} {time}",
  "format_short_break": "{icon} {time}",
  "format_long_break": "{icon} {time}",
  "format_paused": "{icon} {time}",
  "format_idle": "{icon} {time}"
}
```

### Recipe 4: Interactive Right-Click Popup Menu
Configure custom launcher behavior and sprint presets in `config.json`:
```json
{
  "menu_backend": "auto",
  "menu_presets": [15, 25, 45, 60]
}
```

Then in Waybar's `config.jsonc`, trigger the menu on right-click:
```jsonc
"custom/pomodoro": {
    "exec": "waybar-pomodoro status",
    "return-type": "json",
    "interval": 1,
    "signal": 8,
    "on-click": "waybar-pomodoro toggle",
    "on-click-right": "waybar-pomodoro menu",
    "on-click-middle": "waybar-pomodoro skip",
    "on-scroll-up": "waybar-pomodoro adjust +1m",
    "on-scroll-down": "waybar-pomodoro adjust -1m"
}
```

*(Alternative)* If you prefer Waybar's native GTK context menu directly anchored to your bar, copy [`docs/waybar-menu.xml`](waybar-menu.xml) to `~/.config/waybar/pomodoro-menu.xml` and configure:
```jsonc
"custom/pomodoro": {
    "exec": "waybar-pomodoro status",
    "return-type": "json",
    "interval": 1,
    "signal": 8,
    "on-click": "waybar-pomodoro toggle",
    "menu": "on-click-right",
    "menu-file": "$HOME/.config/waybar/pomodoro-menu.xml",
    "menu-actions": {
        "start_pause": "waybar-pomodoro toggle",
        "skip": "waybar-pomodoro skip",
        "reset": "waybar-pomodoro reset",
        "preset_15": "waybar-pomodoro start 15m",
        "preset_25": "waybar-pomodoro start 25m",
        "preset_45": "waybar-pomodoro start 45m",
        "preset_60": "waybar-pomodoro start 60m",
        "study_tracker": "waybar-pomodoro stats --chart"
    }
}
```

---

## 📚 Related Documentation

- 📖 **[Main README](../README.md)**: Overview, quick start, and theme presets.
- 💻 **[Command Line Interface (CLI) Guide](CLI.md)**: Subcommands, flags, scripting examples, and window manager keybindings.
- 🌐 **[Multi-Distribution Installation Guide](INSTALLATION.md)**: Arch, Debian, Ubuntu, Fedora, and NixOS instructions.
- 🎨 **[CSS Themes](themes/)**: Modern capsule pill badges for Gruvbox, Catppuccin, Tokyo Night, Nord, Dracula, and Minimal Black.
