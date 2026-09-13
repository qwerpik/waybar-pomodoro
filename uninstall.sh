#!/usr/bin/env bash
set -euo pipefail

PREFIX="${PREFIX:-$HOME/.local}"
BIN_DIR="$PREFIX/bin"
LIB_DIR="$PREFIX/lib/waybar-pomodoro"

echo "Uninstalling waybar-pomodoro from $PREFIX..."

rm -f "$BIN_DIR/waybar-pomodoro"

if [ -n "$LIB_DIR" ] && [ -d "$LIB_DIR" ]; then
    rm -rf "$LIB_DIR"
fi

if [ "${1:-}" = "--purge" ]; then
    echo "Purging configuration, cache, and statistics..."
    rm -rf "${XDG_CONFIG_HOME:-$HOME/.config}/waybar-pomodoro"
    rm -rf "${XDG_DATA_HOME:-$HOME/.local/share}/waybar-pomodoro"
    rm -rf "${XDG_CACHE_HOME:-$HOME/.cache}/waybar-pomodoro"
fi

echo "waybar-pomodoro binary and libraries removed."
