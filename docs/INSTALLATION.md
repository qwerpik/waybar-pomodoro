# Multi-Distribution Installation & Environment Guide

This guide covers installing, configuring, and verifying **`waybar-pomodoro`** across major Linux distributions, handling distro-specific quirks (such as PEP 668 on Debian/Ubuntu), setting up audio alert backends, configuring `$PATH`, and verifying fonts for Waybar icons.

---

## 📋 Quick Distro Summary

| Distribution | Recommended Method | System Dependencies |
| :--- | :--- | :--- |
| **Arch Linux / Artix** | Local PKGBUILD (`makepkg -si`) or `./install.sh` | `python`, `procps-ng`, `libcanberra`, `pipewire` |
| **Debian / Ubuntu / Mint** | `pipx` (PEP 668 safe) or `./install.sh` | `python3-pipx`, `procps`, `libcanberra-gtk3-module`, `sound-theme-freedesktop` |
| **Fedora** | `pipx` or `./install.sh` | `python3`, `pipx`, `procps-ng`, `libcanberra-gtk3`, `sound-theme-freedesktop` |
| **NixOS / Nix** | Nix Flake / `nix-shell` | `python3`, `procps`, `libcanberra-gtk3`, `pipewire` |

---

## 📦 Distribution-Specific Instructions

### 1. Arch Linux / Artix Linux

Arch Linux provides cutting-edge packages where Python 3 is modern and system tools are standard.

#### Option A: Package via `PKGBUILD` (Recommended for pacman integration)
A clean, Arch-compliant `PKGBUILD` is provided in the repository under `packaging/`.

```bash
git clone https://github.com/qwerpik/waybar-pomodoro.git
cd waybar-pomodoro/packaging
makepkg -si
```

This installs `waybar-pomodoro` cleanly to `/usr/bin/waybar-pomodoro` and tracks it via `pacman`.

#### Option B: Standalone `./install.sh`
```bash
git clone https://github.com/qwerpik/waybar-pomodoro.git
cd waybar-pomodoro
./install.sh
```

#### Arch Runtime Dependencies
```bash
# Core execution and process signaling
sudo pacman -S --needed python procps-ng

# Audio chime notification engines (at least one recommended)
sudo pacman -S --needed libcanberra pipewire-audio sound-theme-freedesktop

# Desktop notification daemon (if not already installed)
sudo pacman -S --needed mako # or dunst / swaync
```

> **Note on Artix / OpenRC / Runit**: Ensure `procps-ng` is installed. The standard `pkill -x -u $UID` flags are fully supported by `procps-ng`.

---

### 2. Debian / Ubuntu / Linux Mint

Modern Debian (Debian 12+ Bookworm) and Ubuntu (23.04+ Lunar, 24.04+ Noble, 24.10+) strictly enforce **PEP 668** to prevent users and third-party scripts from breaking system Python packages.

#### ⚠️ Understanding PEP 668 (`externally-managed-environment`)
If you run `pip install .` directly in system Python on Debian or Ubuntu, you will encounter:
```text
error: externally-managed-environment
× This environment is externally managed
╰─> To install Python packages system-wide, try apt install
    python3-xyz, where xyz is the package you are trying to
    install.
```
**Never use `--break-system-packages`** unless inside a disposable container. Instead, use one of the two supported methods below:

#### Method 1: Isolated Install via `pipx` (Recommended)
`pipx` automatically creates an isolated virtual environment in `~/.local/pipx/venvs/` and safely symlinks the executable to `~/.local/bin/waybar-pomodoro`.

```bash
# 1. Install pipx and runtime packages
sudo apt update
sudo apt install -y python3-pipx procps libcanberra-gtk3-module pipewire-audio-client-libraries sound-theme-freedesktop

# 2. Ensure ~/.local/bin is in PATH
pipx ensurepath

# 3. Install waybar-pomodoro
pipx install git+https://github.com/qwerpik/waybar-pomodoro.git

# Or install from local cloned folder:
# pipx install .
```

#### Method 2: Zero-Dependency User Install via `./install.sh`
Because `waybar-pomodoro` is written using **pure Python standard libraries** (zero pip dependencies), the included `./install.sh` script installs the package directly into `~/.local/lib/waybar-pomodoro/` and creates a standalone wrapper in `~/.local/bin/waybar-pomodoro` without violating PEP 668:

```bash
git clone https://github.com/qwerpik/waybar-pomodoro.git
cd waybar-pomodoro
./install.sh
```

#### Debian / Ubuntu System Dependencies
```bash
sudo apt update && sudo apt install -y \
  python3 \
  procps \
  libcanberra-gtk3-module \
  sound-theme-freedesktop \
  libnotify-bin
```

---

### 3. Fedora

Fedora ships modern Python versions and packages `pipx` in the official repositories.

```bash
# 1. Install prerequisites
sudo dnf install -y python3 pipx procps-ng libcanberra-gtk3 pipewire-utils sound-theme-freedesktop libnotify

# 2. Install waybar-pomodoro via pipx
pipx ensurepath
pipx install git+https://github.com/qwerpik/waybar-pomodoro.git

# Or via install.sh
# ./install.sh
```

---

<a id="4-nixos--nix"></a>
<a id="nixos-nix"></a>
### 4. NixOS / Nix

`waybar-pomodoro` provides first-class, declarative support for Nix and NixOS via **Nix Flakes** (`flake.nix`), traditional `default.nix`, and an integrated **Home Manager module**.

The package is wrapped with Nixpkgs' `makeWrapper`, ensuring `procps` (`pkill -x -u`) and `libcanberra-gtk3` (`canberra-gtk-play`) are automatically available in the binary's private `$PATH` without polluting your global environment.

#### Option A: Quick Ad-Hoc Run via Flakes
Run the latest release directly without installing:
```bash
nix run github:qwerpik/waybar-pomodoro -- status
```

#### Option B: Home Manager Module (Recommended)
Add `waybar-pomodoro` to your Flake inputs (`flake.nix`):
```nix
{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    home-manager.url = "github:nix-community/home-manager";
    waybar-pomodoro.url = "github:qwerpik/waybar-pomodoro";
  };

  outputs = { nixpkgs, home-manager, waybar-pomodoro, ... }: {
    # In your home-manager configuration:
    homeConfigurations."user" = home-manager.lib.homeManagerConfiguration {
      # ...
      modules = [
        waybar-pomodoro.homeManagerModules.default
        {
          programs.waybar-pomodoro = {
            enable = true;
            settings = {
              work_duration = 25;
              short_break_duration = 5;
              long_break_duration = 15;
              cycles_before_long_break = 4;
              sound_enabled = true;
              notification_enabled = true;
            };
          };
        }
      ];
    };
  };
}
```

#### Option C: NixOS System Configuration (`configuration.nix`)
To make the binary available system-wide:
```nix
# In your NixOS flake.nix:
environment.systemPackages = [
  waybar-pomodoro.packages.''${pkgs.system}.default
];
```

#### Option D: Traditional `nix-build` / `nix-shell`
Without Flakes, you can build or test using `default.nix`:
```bash
# Build binary
nix-build

# Enter interactive development shell
nix-shell -p 'import ./default.nix {}'
```

---

## 🛠️ User Environment & Shell Configuration

<a id="1-verifying-and-adding-localbin-to-path"></a>
<a id="path-configuration"></a>
### 1. Verifying and Adding `~/.local/bin` to `$PATH`

When installing via `./install.sh` or `pipx`, the executable is placed in `~/.local/bin/waybar-pomodoro`. If Waybar fails to execute the module (showing an empty string or error), your shell session or Waybar process likely does not have `~/.local/bin` in its `$PATH`.

#### Test from Terminal:
```bash
which waybar-pomodoro
```
If this prints nothing or returns an error, configure your shell below:

#### Bash (`~/.bashrc` or `~/.bash_profile`)
Add to the end of the file:
```bash
export PATH="$HOME/.local/bin:$PATH"
```
Reload with: `source ~/.bashrc`

#### Zsh (`~/.zshrc`)
Add to the end of the file:
```zsh
export PATH="$HOME/.local/bin:$PATH"
```
Reload with: `source ~/.zshrc`

#### Fish (`~/.config/fish/config.fish`)
Run in Fish terminal:
```fish
fish_add_path $HOME/.local/bin
```
Or add to `config.fish`:
```fish
set -gx PATH $HOME/.local/bin $PATH
```

> **Important for Wayland Compositors (Hyprland, Sway, MangoWM)**: Compositors started via display managers (SDDM, GDM, Ly, greetd) launch system sessions where `~/.bashrc` may not be sourced. Ensure `export PATH="$HOME/.local/bin:$PATH"` is placed in `~/.profile` or configured in your compositor launch script (e.g. `~/.config/mango/init.sh` or `~/.config/hypr/hyprland.conf`: `env = PATH,$HOME/.local/bin:$PATH`).

---

## 🔊 Audio Backend Priority & Fallbacks

`waybar-pomodoro` automatically detects available audio playback utilities at runtime and selects the best tool in this strict priority order:

| Priority | Player Binary | Description & Recommended Use Case | System Package |
| :---: | :--- | :--- | :--- |
| **1** | `canberra-gtk-play` | **Recommended**. Low latency, non-blocking freedesktop event player. | `libcanberra` (Arch) / `libcanberra-gtk3-module` (Debian) |
| **2** | `pw-play` | Native PipeWire low-latency audio player. | `pipewire` (Arch) / `pipewire-utils` (Fedora) / `pipewire-audio-client-libraries` (Debian) |
| **3** | `paplay` | Native PulseAudio client player. | `pulseaudio-utils` or `pipewire-pulse` |
| **4** | `ogg123` | Lightweight Vorbis command-line audio player. | `vorbis-tools` |
| **5** | `ffplay` | FFmpeg audio player (run headless `-nodisp -autoexit`). | `ffmpeg` |
| **6** | `mpv` | Versatile command-line media player. | `mpv` |

> 🚫 **Note on `aplay`**: `aplay` (from `alsa-utils`) is intentionally rejected by `waybar-pomodoro` because standard ALSA `aplay` cannot decode compressed `.oga` (Ogg Vorbis) sound files and emits loud garbage noise or fails with header read errors.

### Testing Audio Alerts
To test your audio configuration and desktop notification immediately:
```bash
waybar-pomodoro test-alert
```

If sound is not heard:
1. Verify system sound files exist:
   ```bash
   ls -la /usr/share/sounds/freedesktop/stereo/complete.oga
   ```
   If missing, install `sound-theme-freedesktop`.
2. Test player directly:
   ```bash
   canberra-gtk-play -i complete || pw-play /usr/share/sounds/freedesktop/stereo/complete.oga
   ```
3. Set custom audio files in `~/.config/waybar-pomodoro/config.json`:
   ```json
   {
     "sound_enabled": true,
     "sound_work_end": "/path/to/custom-work-alarm.oga",
     "sound_break_end": "/path/to/custom-break-alarm.oga"
   }
   ```

---

## 🔤 Font Requirements & Glyphs

If Waybar renders missing character glyphs (such as empty boxes `󰀦` or ``), ensure your font stack includes Unicode symbols and Nerd Fonts:

### Recommended Font Packages
* **Arch Linux**:
  ```bash
  sudo pacman -S ttf-nerd-fonts-symbols noto-fonts-emoji ttf-jetbrains-mono-nerd
  ```
* **Debian / Ubuntu**:
  ```bash
  sudo apt install fonts-noto-color-emoji fonts-firacode
  # Or download JetBrainsMono Nerd Font from nerd-fonts releases
  ```
* **Fedora**:
  ```bash
  sudo dnf install google-noto-color-emoji-fonts jetbrains-mono-fonts-all
  ```

### Waybar CSS Font Stack
In `~/.config/waybar/style.css`, specify a robust font family fallback:
```css
* {
    font-family: "JetBrainsMono Nerd Font", "Symbols Nerd Font", "Noto Color Emoji", sans-serif;
}
```

---

## 🔗 Related Documentation

* 📖 **[Main README](../README.md)**: Overview, features, and quickstart.
* 💻 **[CLI & Scripting Guide](CLI.md)**: Complete CLI command matrix, global flags, and window manager keybindings.
* 🔬 **[Engineering Case Study](ARTICLE.md)**: POSIX advisory locking, atomic durability, and drift protection.
* 🚀 **[Showcase & Presets](SHOWCASE.md)**: Capsule themes and community showcases.
* 🎨 **[CSS Capsule Themes](themes/)**: Ready-to-use color schemes.

