# 💻 Command Line Interface (CLI) & Scripting Guide

`waybar-pomodoro` is not only a status bar module for Waybar—it also provides a full-featured, zero-dependency command-line interface. You can control the timer from your terminal, bind global shortcuts in your window manager, trigger ad-hoc focus sprints, query real-time status in custom status bars, and automate your workflow with shell scripts.

---

## 📑 Table of Contents

1. [Global Options and Flags](#global-options-and-flags)
2. [Command Reference](#command-reference)
3. [Practical CLI Examples](#practical-cli-examples)
   - [Status Polling](#1-status-polling)
   - [Plain Text Output](#2-plain-text-output)
   - [Ad-Hoc Timers](#3-ad-hoc-timers)
   - [Scroll Wheel Adjustments](#4-scroll-wheel-adjustments)
   - [Statistics and Study Tracker](#5-statistics-and-study-tracker)
   - [Interactive Popup Menu](#6-interactive-popup-menu)
   - [Configuration Management](#7-configuration-management)
   - [Testing Alerts](#8-testing-alerts)
4. [Window Manager Keybinding Configurations](#window-manager-keybinding-configurations)
   - [Hyprland](#1-hyprland)
   - [Sway and i3](#2-sway-and-i3)
   - [MangoWM](#3-mangowm)
5. [Scripting Tips and Automation](#scripting-tips-and-automation)
   - [Custom Status Bars](#1-custom-status-bars)
   - [Desktop Notification Hooks](#2-desktop-notification-hooks)
6. [Related Documentation](#related-documentation)

---

<a id="global-options-and-flags"></a>
## ⚙️ Global Options and Flags

Global options can be supplied to `waybar-pomodoro` before any subcommand to override configuration parameters dynamically:

| Flag | Argument | Default | Description |
| :--- | :--- | :--- | :--- |
| `-h`, `--help` | — | — | Show help message and command syntax |
| `-c`, `--config` | `PATH` | `~/.config/waybar-pomodoro/config.json` | Path to custom configuration file |
| `-w`, `--work` | `MINUTES` | `30` | Override work session duration in minutes |
| `-s`, `--short-break` | `MINUTES` | `5` | Override short break duration in minutes |
| `-l`, `--long-break` | `MINUTES` | `15` | Override long break duration in minutes |
| `--style` | `minimal \| icon \| custom` | `minimal` | Override Waybar display style format |

### Example: Running with Custom Durations
```bash
# Launch a 50-minute work session with 10-minute short break without editing config.json
waybar-pomodoro -w 50 -s 10 start
```

---

<a id="command-reference"></a>
## 📋 Command Reference

Below is the complete matrix of all subcommands supported by `waybar-pomodoro`:

| Command | Arguments / Flags | Description | Example |
| :--- | :--- | :--- | :--- |
| `status` | `[--plain]` | Output current status payload (Waybar JSON by default, or plain text) | `waybar-pomodoro status --plain` |
| `time-left` | `[-s, --seconds]` | Print remaining duration (`MM:SS` or raw seconds with `-s`) | `waybar-pomodoro time-left -s` |
| `toggle` | — | Toggle between start, pause, and resume states | `waybar-pomodoro toggle` |
| `start` | `[duration]` | Start or resume the timer (optionally set ad-hoc duration, e.g. `45m`) | `waybar-pomodoro start 45m` |
| `pause` | — | Pause the active timer | `waybar-pomodoro pause` |
| `resume` | — | Resume a paused timer | `waybar-pomodoro resume` |
| `reset` | `[duration]` | Reset timer back to configured work duration (or ad-hoc duration) | `waybar-pomodoro reset 25m` |
| `stop` | — | Stop timer and reset back to idle state | `waybar-pomodoro stop` |
| `skip` | — | Skip current phase (Work ↔ Break) | `waybar-pomodoro skip` |
| `adjust` | `<delta>` | Adjust timer duration on the fly (`+1m`, `-1m`, `+30s`, `+5`) | `waybar-pomodoro adjust +5m` |
| `menu` | `[-b BACKEND] [-C CMD]` | Open interactive popup menu (Rofi, Wofi, Fuzzel, Tofi, Zenity, GTK) | `waybar-pomodoro menu` |
| `stats` | `[--heatmap \| --chart \| --json \| --csv \| --reset]` | View stats summary, terminal contribution heatmap, or SVG chart | `waybar-pomodoro stats --heatmap` |
| `test-alert` | — | Test desktop notification and audio chime playback | `waybar-pomodoro test-alert` |
| `config` | `[--show \| --init]` | Display active configuration or create default config file | `waybar-pomodoro config --show` |

---

<a id="practical-cli-examples"></a>
## 💡 Practical CLI Examples

<a id="status-polling"></a>
<a id="1-status-polling"></a>
### 1. Status Polling

#### Waybar JSON Payload (Default)
By default, `status` outputs standard JSON adhering to Waybar's custom module protocol:

```bash
waybar-pomodoro status
```

Example output:
```json
{
  "text": "24:50",
  "alt": "work",
  "tooltip": "<span font_desc='monospace'>🍅 Focus Session [1/4]</span>...",
  "class": "work",
  "percentage": 82.8
}
```

#### Terminal Polling Loop
To watch the timer tick live in your terminal:
```bash
watch -n 1 waybar-pomodoro status --plain
```

---

<a id="plain-text-output"></a>
<a id="2-plain-text-output"></a>
### 2. Plain Text Output

When integrating with simpler status bars (such as Polybar, i3blocks, Tint2, or Tmux), use `--plain` or `time-left`:

```bash
# Output plain text formatted according to active style (minimal/icon/custom)
waybar-pomodoro status --plain
# Output: 25:00

# Output only the MM:SS remaining time
waybar-pomodoro time-left
# Output: 24:15

# Output remaining time as raw integer seconds (ideal for arithmetic in scripts)
waybar-pomodoro time-left -s
# Output: 1455
```

---

<a id="ad-hoc-timers"></a>
<a id="3-ad-hoc-timers"></a>
### 3. Ad-Hoc Timers

You can start or reset the timer with an explicit duration without altering your default configuration:

```bash
# Start an ad-hoc 45-minute deep focus sprint
waybar-pomodoro start 45m

# Start a quick 10-minute task
waybar-pomodoro start 10m

# Start a short 90-second sprint
waybar-pomodoro start 90s

# Reset timer to 25 minutes
waybar-pomodoro reset 25m
```

> **Note on duration parsing**: Units `m`, `min`, `minutes`, `s`, `sec`, `seconds` are supported. If no unit suffix is given (e.g. `25`), minutes are assumed.

---

<a id="scroll-wheel-adjustments"></a>
<a id="4-scroll-wheel-adjustments"></a>
### 4. Scroll Wheel Adjustments

The `adjust` command modifies the current session on the fly. It is concurrency-safe and guarded by POSIX advisory file locks (`fcntl.flock`), making it safe for rapid invocation via mouse wheel events:

```bash
# Add 1 minute (used by Waybar "on-scroll-up")
waybar-pomodoro adjust +1m

# Subtract 1 minute (used by Waybar "on-scroll-down")
waybar-pomodoro adjust -1m

# Add 5 minutes to an ongoing session
waybar-pomodoro adjust +5m

# Subtract 30 seconds
waybar-pomodoro adjust -30s
```

---

<a id="statistics-and-data-export"></a>
<a id="5-statistics-and-data-export"></a>
### 5. Statistics and Data Export

`waybar-pomodoro` tracks completed sessions, focus time, and daily streaks in `~/.local/share/waybar-pomodoro/stats.json`.

#### Formatted Summary
```bash
waybar-pomodoro stats
```
Output:
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

#### Terminal Study Tracker (GitHub Contribution Heatmap)
Render a rich 7-row GitHub-style contribution heatmap right inside your terminal:
```bash
# Auto-detect terminal width and display color-graded activity grid
waybar-pomodoro stats --heatmap

# Display specific number of weeks (e.g. 52 weeks or 26 weeks)
waybar-pomodoro stats --heatmap --weeks 52

# Monochrome / ASCII mode (plain unicode blocks without ANSI colors)
waybar-pomodoro stats --heatmap --no-color
```

Example terminal render:
```text
🍅 POMODORO STUDY TRACKER (30 Weeks)
───────────────────────────────────────────────────────────────
      Mar       Apr     May     Jun       Jul     Aug       Sep
Mon · · · · · · · · · · · · · · · · · · · · · · · · · · · · · ·
    · · · · · · · · · · · · · · · · · · · · · · · · · · · · ·
Wed · · · · · · · · · · · · · · · · · · · · · · · · · · · · ·
    · · · · · · · · · · · · · · · · · · · · · · · · · · · · ·
Fri · · · · · · · · · · · · · · · · · · · · · · · · · · · · ·
    · · · · · · · · · · · · · · · · · · · · · · · · · · · · ·
Sun · · · · · · · · · · · · · · · · · · · · · · · · · · · · ·

    Less · ■ ■ ■ ■ More
───────────────────────────────────────────────────────────────
  • Total Focus: 42.5h (85 sessions)
  • Current Streak: 6 day(s) 🔥
  • Best Streak: 14 day(s) 🏆
  • Active Days: 28 days
```

#### Vector Contribution Chart (SVG Export & Browser View)
Generate a pixel-perfect standalone SVG graphic matching GitHub's contribution chart:
```bash
# Generate and immediately open the chart in your default image viewer or browser
waybar-pomodoro stats --chart

# Export chart with custom theme (github-dark, catppuccin, gruvbox, tokyo-night, nord)
waybar-pomodoro stats --chart --theme catppuccin

# Export SVG to a specific file destination
waybar-pomodoro stats --export-chart ~/Pictures/pomodoro-tracker.svg --theme gruvbox
```

#### JSON Export
Export data for custom dashboards or reporting scripts:
```bash
waybar-pomodoro stats --json
```

#### CSV Export
Export full daily activity history for spreadsheets or graphing:
```bash
waybar-pomodoro stats --csv > ~/pomodoro_history.csv
```

#### Resetting Statistics
```bash
waybar-pomodoro stats --reset
```

---

<a id="interactive-popup-menu"></a>
<a id="6-interactive-popup-menu"></a>
### 6. Interactive Popup Menu

`waybar-pomodoro menu` launches an interactive graphical menu on Wayland/X11 to control timer sessions, select quick duration presets, make adjustments, and inspect study progress.

```bash
# Launch menu with automatic backend detection (rofi -> wofi -> fuzzel -> tofi -> zenity -> gtk)
waybar-pomodoro menu

# Force a specific launcher backend
waybar-pomodoro menu --backend rofi
waybar-pomodoro menu --backend wofi
waybar-pomodoro menu --backend zenity

# Use a custom launcher command with specific themes
waybar-pomodoro menu -C "rofi -dmenu -theme ~/.config/rofi/pomodoro.rasi -i -p '🍅 Focus'"
```

**Popup Menu Actions:**
- **Dynamic Header**: Displays active phase (`WORK`, `SHORT BREAK`, `LONG BREAK`), remaining countdown `MM:SS`, current cycle `[X/4]`, and streak `🔥`.
- **Playback**: Instant Toggle, Pause, Resume, Skip Phase, Reset, or Stop & Idle.
- **Quick Presets**: `⚡ 15m Sprint`, `🍅 25m Classic`, `🎯 45m Deep Work`, `🏆 60m Marathon`.
- **On-the-Fly Adjustments**: Add `+5m` or Subtract `-5m`.
- **Custom Duration Input**: Type any ad-hoc time string (e.g. `35m`, `1500s`).
- **Study Tracker**: Direct access to view your historical heatmap and launch the SVG contribution chart.

---

<a id="configuration-management"></a>
<a id="7-configuration-management"></a>
### 7. Configuration Management

```bash
# View active resolved configuration including defaults
waybar-pomodoro config --show

# Generate default configuration file at ~/.config/waybar-pomodoro/config.json
waybar-pomodoro config --init
```

---

<a id="testing-alerts"></a>
<a id="8-testing-alerts"></a>
### 8. Testing Alerts

Verify that desktop notifications (`notify-send`) and audio players (`canberra-gtk-play`, `pw-play`, `paplay`, `ogg123`, etc.) are functioning properly:

```bash
waybar-pomodoro test-alert
```

---

<a id="window-manager-keybinding-configurations"></a>
## 🖥️ Window Manager Keybinding Configurations

Bind global keyboard shortcuts to manage your Pomodoro sessions from anywhere in your workflow.

<a id="hyprland"></a>
<a id="1-hyprland"></a>
### 1. Hyprland

Add these bindings to `~/.config/hypr/hyprland.conf`:

```ini
# ==========================================
# 🍅 Waybar Pomodoro Shortcuts
# ==========================================

# Super + P: Toggle timer (start / pause / resume)
bind = $mainMod, P, exec, waybar-pomodoro toggle

# Super + Shift + P: Reset timer back to work duration
bind = $mainMod SHIFT, P, exec, waybar-pomodoro reset

# Super + Alt + P: Skip current phase (work <-> break)
bind = $mainMod ALT, P, exec, waybar-pomodoro skip

# Super + Shift + Plus / Minus: Adjust time on the fly
bind = $mainMod SHIFT, equal, exec, waybar-pomodoro adjust +5m
bind = $mainMod SHIFT, minus, exec, waybar-pomodoro adjust -1m
```

---

<a id="sway-and-i3"></a>
<a id="sway"></a>
<a id="i3"></a>
<a id="2-sway-and-i3"></a>
### 2. Sway and i3

Add these bindings to `~/.config/sway/config` or `~/.config/i3/config`:

```i3config
# ==========================================
# 🍅 Waybar Pomodoro Shortcuts
# ==========================================

# Mod + p: Toggle timer (start / pause / resume)
bindsym $mod+p exec waybar-pomodoro toggle

# Mod + Shift + p: Reset timer
bindsym $mod+Shift+p exec waybar-pomodoro reset

# Mod + Alt + p: Skip phase
bindsym $mod+Mod1+p exec waybar-pomodoro skip

# Mod + Shift + ] / [: Adjust time on the fly
bindsym $mod+Shift+bracketright exec waybar-pomodoro adjust +5m
bindsym $mod+Shift+bracketleft exec waybar-pomodoro adjust -5m
```

---

<a id="mangowm"></a>
<a id="3-mangowm"></a>
### 3. MangoWM

If using the [Mango Wayland Compositor](https://github.com/mangowm/mango), add these bindings to your startup script (`~/.config/mango/init.sh`) or configuration:

```bash
# Ensure ~/.local/bin is in PATH for Waybar and child processes
export PATH="$HOME/.local/bin:$PATH"

# MangoWM keybindings (or adjust syntax to ~/.config/mango/config.toml)
mango-bind --key "Super+p" --exec "waybar-pomodoro toggle"
mango-bind --key "Super+Shift+p" --exec "waybar-pomodoro reset"
mango-bind --key "Super+Alt+p" --exec "waybar-pomodoro skip"
mango-bind --key "Super+Shift+equal" --exec "waybar-pomodoro adjust +5m"
mango-bind --key "Super+Shift+minus" --exec "waybar-pomodoro adjust -1m"
```

---

<a id="scripting-tips-and-automation"></a>
## 🛠️ Scripting Tips and Automation

<a id="custom-status-bars"></a>
<a id="1-custom-status-bars"></a>
### 1. Custom Status Bars

If you use a different status bar or terminal multiplexer, `waybar-pomodoro` integrates cleanly:

#### Tmux Status Line (`~/.tmux.conf`)
```tmux
# Update every 5 seconds
set -g status-interval 5
set -g status-right "#[fg=colour208]🍅 #(waybar-pomodoro status --plain) #[default]| %H:%M"
```

#### Polybar Module (`~/.config/polybar/config.ini`)
```ini
[module/pomodoro]
type = custom/script
exec = waybar-pomodoro status --plain
interval = 1
click-left = waybar-pomodoro toggle
click-right = waybar-pomodoro reset
click-middle = waybar-pomodoro skip
scroll-up = waybar-pomodoro adjust +1m
scroll-down = waybar-pomodoro adjust -1m
```

---

<a id="interactive-launcher-menu"></a>
<a id="2-interactive-launcher-menu"></a>
### 2. Interactive Launcher Menu

Create a convenient GUI popup menu to control `waybar-pomodoro` (requires `rofi`, `wofi`, or `dmenu`, and optionally `libnotify` for statistics notifications):

Save this script as `~/.local/bin/pomodoro-menu` (make it executable with `chmod +x`):

```bash
#!/usr/bin/env bash
# Interactive Pomodoro control menu using Rofi, Wofi, or Dmenu

MENU_CMD=""
if command -v rofi >/dev/null 2>&1; then
    MENU_CMD="rofi -dmenu -i -p '🍅 Pomodoro'"
elif command -v wofi >/dev/null 2>&1; then
    MENU_CMD="wofi --dmenu --prompt '🍅 Pomodoro'"
elif command -v dmenu >/dev/null 2>&1; then
    MENU_CMD="dmenu -p '🍅 Pomodoro:'"
else
    echo "Error: rofi, wofi, or dmenu is required to display the interactive menu." >&2
    exit 1
fi

CHOICE=$(cat << 'EOF_MENU' | eval "$MENU_CMD"
▶️  Toggle (Start / Pause / Resume)
⏭️  Skip Current Phase
🔄  Reset to Default (30m)
⏱️  Start 15m Sprint
⏱️  Start 25m Classic
⏱️  Start 45m Deep Work
➕  Add 5 Minutes (+5m)
➖  Subtract 1 Minute (-1m)
📊  Show Statistics
⏹️  Stop Timer (Idle)
EOF_MENU
)

if [ -z "$CHOICE" ]; then
    exit 0
fi

case "$CHOICE" in
    *"Toggle"*)    waybar-pomodoro toggle ;;
    *"Skip"*)      waybar-pomodoro skip ;;
    *"Reset"*)     waybar-pomodoro reset ;;
    *"15m"*)       waybar-pomodoro start 15m ;;
    *"25m"*)       waybar-pomodoro start 25m ;;
    *"45m"*)       waybar-pomodoro start 45m ;;
    *"+5m"*)       waybar-pomodoro adjust +5m ;;
    *"-1m"*)       waybar-pomodoro adjust -1m ;;
    *"Statistics"*)
        if command -v notify-send >/dev/null 2>&1; then
            notify-send "🍅 Pomodoro Statistics" "$(waybar-pomodoro stats)" -i appointment-soon
        else
            waybar-pomodoro stats
        fi
        ;;
    *"Stop"*)      waybar-pomodoro stop ;;
esac
```

---

<a id="desktop-notification-hooks"></a>
<a id="3-desktop-notification-hooks"></a>
### 3. Desktop Notification Hooks

You can inspect the timer state programmatically to trigger custom hooks or automate desktop modes (such as enabling "Do Not Disturb" during focus sessions and disabling it during breaks):

```bash
#!/usr/bin/env bash
# Inspect timer status to toggle desktop "Do Not Disturb" mode

STATUS=$(waybar-pomodoro status)

if command -v jq >/dev/null 2>&1; then
    CLASS=$(echo "$STATUS" | jq -r .class)
    ALT=$(echo "$STATUS" | jq -r .alt)
else
    CLASS=$(echo "$STATUS" | grep -o '"class": "[^"]*' | cut -d'"' -f4)
    ALT=$(echo "$STATUS" | grep -o '"alt": "[^"]*' | cut -d'"' -f4)
fi

if [[ "$CLASS" == *"work"* ]] && [[ "$CLASS" != *"paused"* ]]; then
    SECONDS_LEFT=$(waybar-pomodoro time-left -s)
    echo "Focus session active ($ALT): $SECONDS_LEFT seconds remaining."
    # Hook: silence notifications during focus (e.g. Mako, Dunst, SwayNC)
    # makoctl mode -a dnd
elif [[ "$CLASS" == *"paused"* ]]; then
    echo "Timer is paused ($ALT)."
else
    echo "Timer is idle or on break ($ALT)."
    # Hook: re-enable notifications during breaks or idle
    # makoctl mode -r dnd
fi
```

---

<a id="related-documentation"></a>
## 🔗 Related Documentation

* 📖 **[Main README](../README.md)**: Overview, features, and quickstart.
* 📦 **[Installation Guide](INSTALLATION.md)**: Multi-distribution setup and audio troubleshooting.
* 🔬 **[Engineering Case Study](ARTICLE.md)**: Concurrency, file locking, and drift detection deep dive.
* 🚀 **[Showcase & Presets](SHOWCASE.md)**: Capsule themes and community showcases.
* 🎨 **[CSS Capsule Themes](themes/)**: Ready-to-use color schemes.
