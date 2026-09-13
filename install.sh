#!/usr/bin/env bash
set -e

PREFIX="${PREFIX:-$HOME/.local}"
BIN_DIR="$PREFIX/bin"
LIB_DIR="$PREFIX/lib/waybar-pomodoro"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/waybar-pomodoro"

echo "Installing waybar-pomodoro to $PREFIX..."

mkdir -p "$BIN_DIR"
mkdir -p "$LIB_DIR"
mkdir -p "$CONFIG_DIR"

# Copy library files
cp -r src/waybar_pomodoro "$LIB_DIR/"

# Create executable runner in BIN_DIR
cat <<EOF > "$BIN_DIR/waybar-pomodoro"
#!/usr/bin/env python3
import sys
sys.path.insert(0, "$LIB_DIR")
from waybar_pomodoro.cli import main
if __name__ == "__main__":
    sys.exit(main())
EOF

chmod +x "$BIN_DIR/waybar-pomodoro"

# Create default config if none exists
if [ ! -f "$CONFIG_DIR/config.json" ]; then
    "$BIN_DIR/waybar-pomodoro" config --init >/dev/null 2>&1 || true
    echo "Created default config at $CONFIG_DIR/config.json"
fi

echo "=========================================================="
echo "Installation complete!"
echo "Binary installed at: $BIN_DIR/waybar-pomodoro"
echo ""
echo "Verify installation:"
echo "  $BIN_DIR/waybar-pomodoro status --plain"
echo ""
echo "Ensure '$BIN_DIR' is in your PATH."
echo "=========================================================="
