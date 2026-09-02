#!/usr/bin/env bash
#
# install.sh -- put the launcher on PATH and register the desktop entry and icon.
#
# Usage:
#   scripts/install.sh [PREFIX]      PREFIX defaults to ~/bin
#
# Environment overrides:
#   PREFIX      launcher directory (default: ~/bin)
#   DATA_HOME   XDG data directory (default: ~/.local/share)

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PREFIX="${1:-${PREFIX:-$HOME/bin}}"
DATA_HOME="${DATA_HOME:-${XDG_DATA_HOME:-$HOME/.local/share}}"
APP_ID="com.kingletas.Solander"

# The venv must see the system GObject bindings: python3-gi is an apt package,
# and a venv built on uv's own interpreter cannot import it. uv sync alone would
# create exactly that venv on a machine that has none yet.
if [ ! -d "$HERE/.venv" ]; then
  uv venv "$HERE/.venv" --python /usr/bin/python3 --system-site-packages -q
fi
uv sync --project "$HERE" -q

if ! "$HERE/.venv/bin/python" -c "import gi" 2>/dev/null; then
  echo "install.sh: the virtualenv cannot import gi -- the app will not start." >&2
  echo "  Install the bindings, delete $HERE/.venv, and run make install again:" >&2
  echo "  sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 gir1.2-webkit-6.0" >&2
  exit 1
fi

# Localize the venv interpreter: an AppArmor profile can then name this app's
# interpreter alone instead of the system Python every other process shares.
venv_python="$HERE/.venv/bin/python"
if [ -L "$venv_python" ]; then
  real="$(readlink -f "$venv_python")"
  cp "$real" "$venv_python.tmp"
  mv -f "$venv_python.tmp" "$venv_python"
  echo "localized: $venv_python (copy of $real)"
fi

install -D -m 0755 "$HERE/bin/solander" "$PREFIX/solander"

desktop_dir="$DATA_HOME/applications"
icon_dir="$DATA_HOME/icons/hicolor/scalable/apps"
install -d "$desktop_dir" "$icon_dir"
sed "s|@LAUNCHER@|$PREFIX/solander|" "$HERE/data/$APP_ID.desktop" \
  > "$desktop_dir/$APP_ID.desktop"
install -m 0644 "$HERE/data/$APP_ID.svg" "$icon_dir/$APP_ID.svg"

command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$desktop_dir" || true

echo "installed: $PREFIX/solander"
echo "installed: $desktop_dir/$APP_ID.desktop"
echo "installed: $icon_dir/$APP_ID.svg"
