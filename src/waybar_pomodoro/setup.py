"""
Compositor and Window Manager configuration generator for waybar-pomodoro.
Supports MangoWM, Hyprland, Sway, and i3.
"""

from __future__ import annotations

import shutil
import time
from pathlib import Path
from typing import Optional, Tuple

SUPPORTED_COMPOSITORS = ("mangowm", "hyprland", "sway", "i3", "all")

MARKER_START = "# >>> waybar-pomodoro keybindings >>>"
MARKER_END = "# <<< waybar-pomodoro keybindings <<<"


def get_default_config_path(compositor: str) -> Optional[Path]:
    home = Path.home()
    if compositor == "hyprland":
        return home / ".config" / "hypr" / "hyprland.conf"
    if compositor == "mangowm":
        # Check standard mango locations
        p1 = home / ".config" / "mango" / "config.conf"
        p2 = home / ".config" / "mango" / "keybindings.conf"
        if p2.exists():
            return p2
        return p1
    if compositor == "sway":
        return home / ".config" / "sway" / "config"
    if compositor == "i3":
        return home / ".config" / "i3" / "config"
    return None


def get_keybinding_snippet(compositor: str) -> str:
    if compositor == "hyprland":
        return f"""{MARKER_START}
bind = $mainMod ALT, P, exec, waybar-pomodoro toggle
bind = $mainMod ALT, S, exec, waybar-pomodoro skip
bind = $mainMod ALT, R, exec, waybar-pomodoro reset
bind = $mainMod ALT, M, exec, waybar-pomodoro menu
bind = $mainMod ALT, UP, exec, waybar-pomodoro adjust +1m
bind = $mainMod ALT, DOWN, exec, waybar-pomodoro adjust -1m
{MARKER_END}"""
    if compositor == "mangowm":
        return f"""{MARKER_START}
bind=SUPER,p,spawn,waybar-pomodoro toggle
bind=SUPER,s,spawn,waybar-pomodoro skip
bind=SUPER,r,spawn,waybar-pomodoro reset
bind=SUPER,m,spawn,waybar-pomodoro menu
{MARKER_END}"""
    if compositor in ("sway", "i3"):
        return f"""{MARKER_START}
bindsym $mod+Mod1+p exec waybar-pomodoro toggle
bindsym $mod+Mod1+s exec waybar-pomodoro skip
bindsym $mod+Mod1+r exec waybar-pomodoro reset
bindsym $mod+Mod1+m exec waybar-pomodoro menu
bindsym $mod+Mod1+Up exec waybar-pomodoro adjust +1m
bindsym $mod+Mod1+Down exec waybar-pomodoro adjust -1m
{MARKER_END}"""
    return ""


def get_waybar_module_snippet() -> str:
    return """    "custom/pomodoro": {
      "format": "{}",
      "return-type": "json",
      "exec": "waybar-pomodoro stream",
      "on-click": "waybar-pomodoro toggle",
      "on-click-right": "waybar-pomodoro menu",
      "on-click-middle": "waybar-pomodoro skip",
      "on-scroll-up": "waybar-pomodoro adjust +1m",
      "on-scroll-down": "waybar-pomodoro adjust -1m"
    }"""


def get_idle_snippet(compositor: str) -> str:
    if compositor == "hyprland":
        return """# Add to ~/.config/hypr/hypridle.conf:
listener {
    timeout = 300
    on-timeout = waybar-pomodoro idle-pause
    on-resume = waybar-pomodoro idle-resume
}"""
    if compositor == "sway":
        return """# Add to ~/.config/sway/config:
exec swayidle -w \\
    timeout 300 'waybar-pomodoro idle-pause' \\
    resume 'waybar-pomodoro idle-resume' \\
    before-sleep 'waybar-pomodoro idle-pause'"""
    return """# Idle lock integration:
# Call 'waybar-pomodoro idle-pause' when screen locks
# Call 'waybar-pomodoro idle-resume' when screen unlocks"""


def append_keybindings(config_path: Path, snippet: str, dry_run: bool = False) -> Tuple[bool, str]:
    """
    Safely and idempotently appends or updates keybindings in the target config.
    Creates a timestamped backup (.bak) before modifying.
    """
    if not config_path.exists():
        if dry_run:
            return True, f"[dry-run] Would create {config_path} with keybindings."
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(snippet + "\n", encoding="utf-8")
        return True, f"Created {config_path} with pomodoro keybindings."

    content = config_path.read_text(encoding="utf-8")

    # Replace existing marker block if already present
    if MARKER_START in content and MARKER_END in content:
        start_idx = content.find(MARKER_START)
        end_idx = content.find(MARKER_END) + len(MARKER_END)
        new_content = content[:start_idx] + snippet + content[end_idx:]
    else:
        new_content = content.rstrip() + "\n\n" + snippet + "\n"

    if dry_run:
        return True, f"[dry-run] Would update {config_path} with keybindings."

    backup_path = config_path.with_suffix(f".bak.{int(time.time())}")
    shutil.copy2(config_path, backup_path)
    config_path.write_text(new_content, encoding="utf-8")
    return True, f"Updated {config_path} (backup saved to {backup_path.name})."


def run_setup(
    compositor: str = "all",
    dry_run: bool = False,
    print_only: bool = False,
    append: bool = False,
) -> int:
    """
    CLI handler for generating or appending compositor keybindings and Waybar config.
    """
    comp_target = compositor.lower().strip()
    if comp_target not in SUPPORTED_COMPOSITORS:
        supported = ", ".join(SUPPORTED_COMPOSITORS)
        print(f"Error: Unknown compositor '{compositor}'. Supported: {supported}")
        return 1

    targets = ["mangowm", "hyprland", "sway", "i3"] if comp_target == "all" else [comp_target]

    if append:
        all_ok = True
        for comp in targets:
            target_path = get_default_config_path(comp)
            if not target_path:
                print(f"[-] Could not resolve default config path for {comp}.")
                all_ok = False
                continue
            snippet = get_keybinding_snippet(comp)
            ok, msg = append_keybindings(target_path, snippet, dry_run=dry_run)
            print(f"[{comp}] {msg}")
            if not ok:
                all_ok = False

        print("\n--- Waybar Module Configuration ---")
        print("Add the following module to your ~/.config/waybar/config.jsonc:")
        print(get_waybar_module_snippet())
        return 0 if all_ok else 1

    # Default or --print: output keybindings and instructions
    for comp in targets:
        title = "MangoWM" if comp == "mangowm" else comp.capitalize()
        cfg_path = get_default_config_path(comp)
        path_str = ""
        if cfg_path:
            try:
                rel = cfg_path.relative_to(Path.home())
                path_str = f" (~/{rel})"
            except ValueError:
                path_str = f" ({cfg_path})"

        print(f"=== {title} Keybindings{path_str} ===")
        print(get_keybinding_snippet(comp))
        print("\n" + get_idle_snippet(comp))
        print()

    print("=== Waybar Module Configuration (~/.config/waybar/config.jsonc) ===")
    print(get_waybar_module_snippet())
    print("\nTip: Run 'waybar-pomodoro setup <compositor> --append' to append keybindings.")
    return 0
