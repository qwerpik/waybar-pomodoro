#!/usr/bin/env bash
set -euo pipefail

PREFIX="${PREFIX:-$HOME/.local}"
BIN_DIR="$PREFIX/bin"
LIB_DIR="$PREFIX/lib/waybar-pomodoro"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/waybar-pomodoro"

echo "Installing waybar-pomodoro to $PREFIX..."

mkdir -p "$BIN_DIR"
mkdir -p "$LIB_DIR"

# Clean previous library directory for idempotent install
rm -rf "$LIB_DIR/waybar_pomodoro"
cp -r src/waybar_pomodoro "$LIB_DIR/"
chmod -R u=rwX,go=rX "$LIB_DIR"

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

# Only initialize user config if this is a user install (not root/system)
if [ "$(id -u)" -ne 0 ] && [ "$PREFIX" = "$HOME/.local" ]; then
    if [ ! -f "$CONFIG_DIR/config.json" ]; then
        mkdir -p "$CONFIG_DIR"
        "$BIN_DIR/waybar-pomodoro" config --init >/dev/null 2>&1 || true
        echo "Created default config at $CONFIG_DIR/config.json"
    fi
fi

echo "=========================================================="
echo "Installation complete!"
echo "Binary installed at: $BIN_DIR/waybar-pomodoro"
echo ""

case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *)
        echo "⚠️  WARNING: '$BIN_DIR' is not in your PATH!"
        echo "   Waybar will not be able to execute 'waybar-pomodoro' until you add it."
        echo ""
        echo "   To add it permanently, append one of the following to your shell config:"
        echo "     • Bash (~/.bashrc):        export PATH=\"\$HOME/.local/bin:\$PATH\""
        echo "     • Zsh (~/.zshrc):          export PATH=\"\$HOME/.local/bin:\$PATH\""
        echo "     • Fish (config.fish):      fish_add_path \$HOME/.local/bin"
        echo ""
        ;;
esac

echo "=========================================================="
