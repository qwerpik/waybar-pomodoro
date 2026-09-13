# 🍅 waybar-pomodoro Showcase & Community Pack

Ready-to-publish social showcase materials, Reddit posts (`r/unixporn`, `r/hyprland`, `r/swaywm`), release notes, and copy-paste configuration snippets for Wayland window managers and compositors.

---

## 📱 Reddit Community Post (`r/unixporn`, `r/hyprland`, `r/swaywm`)

**Post Title:**
> [OC] I built a race-free, capsule-styled Pomodoro timer for Waybar with live Pango progress bars & zero dependencies!

**Post Body (Markdown):**

```markdown
Hey everyone! 👋

I was looking for a distraction-free Pomodoro timer for my Waybar setup that looked like a sleek modern capsule pill, gave instant feedback on mouse-wheel scrolling, and wouldn't break or leave zombie files when my laptop went to sleep.

Most existing scripts either required heavy Python dependencies or had nasty race conditions where scrolling your mouse wheel to adjust duration would clobber the JSON file and crash the bar.

So I built **`waybar-pomodoro`**: a lightweight, concurrency-hardened, pure-Python timer designed specifically for Waybar!

### ✨ Highlights
* **Zero External Dependencies**: Pure Python 3 standard library. No bloated pip dependencies or venvs.
* **Race-Free Concurrency**: Process synchronization via POSIX advisory locks (`fcntl.flock`) and atomic file writes (`fsync` + rename) — spin your mouse wheel as fast as you want!
* **Rich Pango Tooltip**: 12-segment character progress bar (`▰▰▰▰▰▰▱▱▱▱▱▱`), session ratio counter `[1/4]`, and persistent daily focus streak tracking `🔥`.
* **Instant Signal Feedback**: Dispatches `SIGRTMIN+8` on every click or scroll for zero-latency UI updates.
* **Sleep/Suspend Drift Protection**: Intelligently detects when your machine went to sleep, preventing phantom stats or 2 AM alarm blasts upon waking.
* **Modern Capsule Pill Badges**: Included CSS themes for Gruvbox, Catppuccin Mocha, Tokyo Night, Nord, Dracula, and Minimal Black.
* **Desktop & Audio Alerts**: Native freedesktop notifications with icons (`appointment-soon`, `preferences-system-time`) and audio fallback engine (`canberra-gtk-play`, `pw-play`, `paplay`, `mpv`).

### 📸 What the Tooltip Looks Like
```text
🍅 Focus Session [2/4]               Running
▰▰▰▰▰▰▱▱▱▱▱▱  12:30 (50%)
─────────────────────────────
• Left-click:   Toggle / Pause
• Right-click:  Reset Session
• Middle-click: Skip Phase
• Scroll:       ±1 min
─────────────────────────────
Today:  3 session(s) • 90m focus
Streak: 5 day(s) 🔥
```

### 🔗 Links & Installation
* **GitHub**: [https://github.com/qwerpik/waybar-pomodoro](https://github.com/qwerpik/waybar-pomodoro)
* **Installation**:
  * **Arch**: `cd packaging && makepkg -si`
  * **Debian/Ubuntu/Fedora**: `pipx install git+https://github.com/qwerpik/waybar-pomodoro.git`
  * **Generic**: `./install.sh`

Feedback and contributions are super welcome! Hope this helps keep you in the focus zone. 🍅
```

---

## 🏷️ Release Notes (v1.0.1)

### `v1.0.1 — The Aesthetic & Multi-Distro Edition`

#### 🎨 Visual & UI/UX Upgrades
* **Dynamic Pango Markup Tooltip**:
  * Added 12-segment monospace character progress bar (`render_progress_bar`) using `▰` and `▱` glyphs.
  * Added phase session ratios (`[1/4]` through `[4/4]` and `[Reward]`).
  * Dynamic color accents for Focus (`#f38ba8`), Breaks (`#a6e3a1`), and Pause (`#f9e2af`) with Pango alpha dimming (`alpha='30%'`, `alpha='60%'`).
* **Capsule Pill Badge CSS Suite**:
  * Completely redesigned all themes in `docs/themes/` (`catppuccin-mocha.css`, `tokyo-night.css`, `nord.css`, `gruvbox.css`, `dracula.css`, `minimal-black.css`).
  * Pill geometry (`border-radius: 9999px;`, `padding: 2px 14px;`), subtle borders, hover transition effects, and faded pause states (`opacity: 0.85;`).
* **Desktop Notification Polish**:
  * Added freedesktop icon tagging (`-i preferences-system-time`, `-i appointment-soon`).
  * Formatted notification body with session stats and break duration highlights.

#### 📦 Distribution & Packaging
* **Multi-Distribution Documentation**:
  * Added `docs/INSTALLATION.md` with comprehensive guides for Arch, Debian/Ubuntu (PEP 668 mitigation), Fedora, and Nix.
  * Shell `$PATH` configuration guide for Bash, Zsh, and Fish.
  * Audio backend priority and troubleshooting matrix.
* **Engineering Case Study**:
  * Published `docs/ARTICLE.md` detailing POSIX advisory locks, atomic file durability, sleep drift, and RT signals.
* **Installer Enhancement**:
  * `./install.sh` now detects missing `$PATH` and outputs copy-paste shell export commands.

---

## 🖥️ Window Manager & Compositor Configurations

Add global keybindings to control the timer from anywhere in your workflow. *(For the complete command matrix, flags, and scripting automation recipes, see [`docs/CLI.md`](CLI.md).)*

### 1. Hyprland Integration (`~/.config/hypr/hyprland.conf`)

Add global keybindings to control the timer from anywhere in your workflow:

```ini
# --- Waybar Pomodoro Shortcuts ---
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

### 2. Sway / i3 Integration (`~/.config/sway/config` or `~/.config/i3/config`)

```i3config
# --- Waybar Pomodoro Shortcuts ---
bindsym $mod+p exec waybar-pomodoro toggle
bindsym $mod+Shift+p exec waybar-pomodoro reset
bindsym $mod+Mod1+p exec waybar-pomodoro skip
bindsym $mod+Shift+bracketright exec waybar-pomodoro adjust +5m
bindsym $mod+Shift+bracketleft exec waybar-pomodoro adjust -5m
```

---

### 3. MangoWM Integration (`~/.config/mango/init.sh` or `config.toml`)

If using the [Mango Wayland Compositor](https://github.com/mangowm/mango):

```bash
# In your MangoWM startup script:
# Ensure local bin is available to Waybar and child processes
export PATH="$HOME/.local/bin:$PATH"

# MangoWM keybinds (adjust syntax to your MangoWM settings)
mango-bind --key "Super+p" --exec "waybar-pomodoro toggle"
mango-bind --key "Super+Shift+p" --exec "waybar-pomodoro reset"
mango-bind --key "Super+Alt+p" --exec "waybar-pomodoro skip"
mango-bind --key "Super+Shift+equal" --exec "waybar-pomodoro adjust +5m"
mango-bind --key "Super+Shift+minus" --exec "waybar-pomodoro adjust -1m"
```

---

## 🎨 Waybar Full Module Reference

### `~/.config/waybar/config.jsonc`
```jsonc
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
```

### `~/.config/waybar/style.css` (Gruvbox Capsule Pill)
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
    border-color: rgba(235, 219, 178, 0.40);
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

---

## 🔗 Related Documentation

* 📖 **[Main README](../README.md)**: Overview, features, and quickstart.
* 💻 **[CLI & Scripting Guide](CLI.md)**: Complete CLI command matrix, global flags, and window manager keybindings.
* 📦 **[Multi-Distribution Installation Guide](INSTALLATION.md)**: Distro packages, PEP 668, `$PATH`, and audio backends.
* 🔬 **[Engineering Case Study](ARTICLE.md)**: POSIX advisory locking, atomic durability, and drift protection.
* 🎨 **[CSS Capsule Themes](themes/)**: Ready-to-use color schemes.

