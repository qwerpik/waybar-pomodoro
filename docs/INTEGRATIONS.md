# 🔌 Integrations & Compositors Guide

`waybar-pomodoro` v2.0 is engineered for universal compatibility across Wayland and X11 tiling window managers and desktop environments, with dedicated turnkey integrations for **MangoWM**, **Hyprland**, **Sway**, and **i3**.

---

## 📑 Table of Contents

- [Automated Setup CLI](#automated-setup-cli)
- [Compositor Keybindings](#compositor-keybindings)
  - [MangoWM](#mangowm)
  - [Hyprland](#hyprland)
  - [Sway](#sway)
  - [i3](#i3)
- [Waybar Module Configuration](#waybar-module-configuration)
- [Screen Lock & Idle Detection](#screen-lock--idle-detection)
  - [Hypridle (Hyprland)](#hypridle-hyprland)
  - [Swayidle (Sway / Wayland)](#swayidle-sway--wayland)
  - [systemd-logind Lock Hook](#systemd-logind-lock-hook)
- [Focus Do Not Disturb (DND)](#focus-do-not-disturb-dnd)
  - [Supported Daemons](#supported-daemons)
  - [Automatic DND Configuration](#automatic-dnd-configuration)
  - [Manual DND CLI](#manual-dnd-cli)
- [Lifecycle Event Hooks & Visuals](#lifecycle-event-hooks--visuals)
  - [Hook Scripts Directory](#hook-scripts-directory)
  - [Config.json Callbacks](#configjson-callbacks)
  - [Environment Variables](#environment-variables)
  - [Example: Dynamic Window Border Color](#example-dynamic-window-border-color)
  - [Example: Smart Light / Home Assistant Sync](#example-smart-light--home-assistant-sync)

---

## ⚡ Automated Setup CLI

`waybar-pomodoro` can generate and automatically append idiomatic keybindings to your compositor configuration files with backup protection:

```bash
# Print keybindings and Waybar config for all compositors:
waybar-pomodoro setup

# Print specific compositor snippet:
waybar-pomodoro setup mangowm
waybar-pomodoro setup hyprland

# Safely append keybindings to your active compositor config:
waybar-pomodoro setup mangowm --append
waybar-pomodoro setup hyprland --append

# Dry-run preview without modifying files:
waybar-pomodoro setup hyprland --append --dry-run
```

> [!NOTE]
> When using `--append`, existing configurations are backed up to `.bak.<timestamp>` before writing, and all generated keybindings are wrapped in markers (`# >>> waybar-pomodoro keybindings >>>`), making subsequent runs completely idempotent.

---

## ⌨️ Compositor Keybindings

### MangoWM

Add the following to `~/.config/mango/config.conf` (or `keybindings.conf`):

```ini
# >>> waybar-pomodoro keybindings >>>
bind=SUPER,p,spawn,waybar-pomodoro toggle
bind=SUPER,s,spawn,waybar-pomodoro skip
bind=SUPER,r,spawn,waybar-pomodoro reset
bind=SUPER,m,spawn,waybar-pomodoro menu
# <<< waybar-pomodoro keybindings <<<
```

### Hyprland

Add the following to `~/.config/hypr/hyprland.conf`:

```ini
# >>> waybar-pomodoro keybindings >>>
bind = $mainMod ALT, P, exec, waybar-pomodoro toggle
bind = $mainMod ALT, S, exec, waybar-pomodoro skip
bind = $mainMod ALT, R, exec, waybar-pomodoro reset
bind = $mainMod ALT, M, exec, waybar-pomodoro menu
bind = $mainMod ALT, UP, exec, waybar-pomodoro adjust +1m
bind = $mainMod ALT, DOWN, exec, waybar-pomodoro adjust -1m
# <<< waybar-pomodoro keybindings <<<
```

### Sway

Add the following to `~/.config/sway/config`:

```ini
# >>> waybar-pomodoro keybindings >>>
bindsym $mod+Mod1+p exec waybar-pomodoro toggle
bindsym $mod+Mod1+s exec waybar-pomodoro skip
bindsym $mod+Mod1+r exec waybar-pomodoro reset
bindsym $mod+Mod1+m exec waybar-pomodoro menu
bindsym $mod+Mod1+Up exec waybar-pomodoro adjust +1m
bindsym $mod+Mod1+Down exec waybar-pomodoro adjust -1m
# <<< waybar-pomodoro keybindings <<<
```

### i3

Add the following to `~/.config/i3/config`:

```ini
# >>> waybar-pomodoro keybindings >>>
bindsym $mod+Mod1+p exec waybar-pomodoro toggle
bindsym $mod+Mod1+s exec waybar-pomodoro skip
bindsym $mod+Mod1+r exec waybar-pomodoro reset
bindsym $mod+Mod1+m exec waybar-pomodoro menu
bindsym $mod+Mod1+Up exec waybar-pomodoro adjust +1m
bindsym $mod+Mod1+Down exec waybar-pomodoro adjust -1m
# <<< waybar-pomodoro keybindings <<<
```

---

## 📊 Waybar Module Configuration

For 0.00% CPU overhead and instantaneous reaction to state changes, configure `custom/pomodoro` in `~/.config/waybar/config.jsonc` with the persistent streaming daemon:

```jsonc
"custom/pomodoro": {
  "format": "{}",
  "return-type": "json",
  "exec": "waybar-pomodoro stream",
  "on-click": "waybar-pomodoro toggle",
  "on-click-right": "waybar-pomodoro menu",
  "on-click-middle": "waybar-pomodoro skip",
  "on-scroll-up": "waybar-pomodoro adjust +1m",
  "on-scroll-down": "waybar-pomodoro adjust -1m"
}
```

Add `"custom/pomodoro"` to your `modules-left`, `modules-center`, or `modules-right` array.

---

## 🔒 Screen Lock & Idle Detection

When you step away from your workstation or lock your screen, `waybar-pomodoro` can automatically pause your focus session and resume or notify you upon return without losing progress.

### Hypridle (Hyprland)

Add a listener to `~/.config/hypr/hypridle.conf`:

```ini
listener {
    timeout = 300                                # 5 minutes of inactivity
    on-timeout = waybar-pomodoro idle-pause      # Auto-pause session
    on-resume = waybar-pomodoro idle-resume      # Resume session upon return
}
```

### Swayidle (Sway / Wayland)

Add to `~/.config/sway/config`:

```ini
exec swayidle -w \
    timeout 300 'waybar-pomodoro idle-pause' \
    resume 'waybar-pomodoro idle-resume' \
    before-sleep 'waybar-pomodoro idle-pause'
```

### systemd-logind Lock Hook

If you use `loginctl lock-session` with `hyprlock`, `swaylock`, or `gtklock`:

```bash
# In your lock script:
waybar-pomodoro lock-hook pause
swaylock
waybar-pomodoro lock-hook resume
```

> [!TIP]
> `idle-pause` marks the session with `paused_by_idle: true`. If you manually paused your timer *before* walking away, `idle-resume` detects this and **preserves your manual pause**, preventing unwanted session restarts.

---

## 🔕 Focus Do Not Disturb (DND)

`waybar-pomodoro` integrates with Linux notification daemons to silence distracting notifications during work sessions and restore them during breaks.

### Supported Daemons

- **SwayNC** (`swaync-client`)
- **Dunst** (`dunstctl`)
- **Mako** (`makoctl`)

### Automatic DND Configuration

In `~/.config/waybar-pomodoro/config.json`:

```json
{
  "auto_dnd": true,
  "dnd_provider": "auto"
}
```

- `"auto_dnd": true`: Automatically enables DND when a work session starts and disables DND during breaks or when the timer is reset.
- `"dnd_provider"`: `"auto"` (auto-detect active daemon), or explicitly `"swaync"`, `"dunst"`, or `"mako"`.

### Manual DND CLI

```bash
waybar-pomodoro dnd --on        # Enable Do Not Disturb
waybar-pomodoro dnd --off       # Disable Do Not Disturb
waybar-pomodoro dnd --status    # Output "DND: on" or "DND: off"
```

---

## 🎨 Lifecycle Event Hooks & Visuals

`waybar-pomodoro` dispatches non-blocking events whenever the timer transitions between states. You can execute custom shell scripts or commands to alter window border colors, trigger smart home automations, or change system themes.

### Supported Events

| Event | Triggered When |
|---|---|
| `work_start` | Work session begins (fresh start, un-paused into work, or auto-started) |
| `break_start` | Short break or long break begins |
| `pause` | Session is paused (manually or by screen lock) |
| `resume` | Session is resumed |
| `reset` | Timer is stopped or reset to initial duration |
| `complete` | Any phase (work or break) naturally counts down to zero |

### Hook Scripts Directory

Create executable scripts in `~/.config/waybar-pomodoro/hooks/`:

```
~/.config/waybar-pomodoro/hooks/
├── on_work_start.sh
├── on_break_start.sh
├── on_pause.sh
├── on_resume.sh
└── on_complete.sh
```

Ensure scripts have execute permissions (`chmod +x ~/.config/waybar-pomodoro/hooks/*.sh`).

### Config.json Callbacks

Alternatively, configure one-line commands directly in `config.json`:

```json
{
  "hooks_enabled": true,
  "hooks": {
    "work_start": "notify-send 'Focus' 'Work session started'",
    "break_start": "notify-send 'Break' 'Time to stretch!'"
  }
}
```

### Environment Variables

Every hook script and callback command receives the following environment variables:

| Variable | Description | Example |
|---|---|---|
| `$POMODORO_EVENT` | Transition event name | `work_start`, `break_start`, `pause` |
| `$POMODORO_PHASE` | Current phase | `work`, `short_break`, `long_break` |
| `$POMODORO_STATE` | Current timer state | `running`, `paused`, `idle` |
| `$POMODORO_TIME_REMAINING` | Remaining seconds | `1500` |
| `$POMODORO_TOTAL_TIME` | Total phase seconds | `1500` |
| `$POMODORO_CYCLE` | Current session cycle | `1`, `2`, `3` |

### Example: Dynamic Window Border Color

Change Hyprland active window border to crimson during focus and emerald during breaks:

`~/.config/waybar-pomodoro/hooks/on_work_start.sh`:
```bash
#!/usr/bin/env bash
# Crimson border during work
hyprctl keyword general:col.active_border "rgba(f38ba8ee) rgba(ea6962ee) 45deg"
```

`~/.config/waybar-pomodoro/hooks/on_break_start.sh`:
```bash
#!/usr/bin/env bash
# Green border during break
hyprctl keyword general:col.active_border "rgba(a6e3a1ee) rgba(b8bb26ee) 45deg"
```

`~/.config/waybar-pomodoro/hooks/on_reset.sh`:
```bash
#!/usr/bin/env bash
# Reset to default blue border
hyprctl keyword general:col.active_border "rgba(89b4faee) rgba(74c7ecee) 45deg"
```

### Example: Smart Light / Home Assistant Sync

Toggle desk light red during focus and warm white during breaks:

`~/.config/waybar-pomodoro/hooks/on_work_start.sh`:
```bash
#!/usr/bin/env bash
curl -s -X POST -H "Authorization: Bearer $HASS_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"entity_id": "light.desk_light", "rgb_color": [255, 60, 60]}' \
     http://homeassistant.local:8123/api/services/light/turn_on
```
