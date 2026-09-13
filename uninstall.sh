#!/usr/bin/env bash
set -e

PREFIX="${PREFIX:-$HOME/.local}"
BIN_DIR="$PREFIX/bin"
LIB_DIR="$PREFIX/lib/waybar-pomodoro"

echo "Uninstalling waybar-pomodoro from $PREFIX..."

rm -f "$BIN_DIR/waybar-pomodoro"
rm -rf "$LIB_DIR"

echo "waybar-pomodoro binary and libraries removed."
echo "Note: Configuration at ~/.config/waybar-pomodoro and statistics at ~/.local/share/waybar-pomodoro were kept."
