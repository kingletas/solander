#!/usr/bin/env bash
#
# uninstall.sh -- remove the launcher, desktop entry, and icon that install.sh placed.
#
# Usage:
#   scripts/uninstall.sh [PREFIX]    PREFIX defaults to ~/bin

set -euo pipefail

PREFIX="${1:-${PREFIX:-$HOME/bin}}"
DATA_HOME="${DATA_HOME:-${XDG_DATA_HOME:-$HOME/.local/share}}"
APP_ID="com.kingletas.Solander"

rm -fv "$PREFIX/solander" \
  "$DATA_HOME/applications/$APP_ID.desktop" \
  "$DATA_HOME/icons/hicolor/scalable/apps/$APP_ID.svg"

if [ -f "$DATA_HOME/icons/hicolor/icon-theme.cache" ]; then
  command -v gtk-update-icon-cache >/dev/null 2>&1 \
    && gtk-update-icon-cache -f -q "$DATA_HOME/icons/hicolor" 2>/dev/null \
    || rm -f "$DATA_HOME/icons/hicolor/icon-theme.cache"
fi
