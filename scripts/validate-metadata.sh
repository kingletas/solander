#!/usr/bin/env bash
#
# validate-metadata.sh -- check the desktop entry and the AppStream metainfo.
#
# These two files are what a software centre reads: the desktop entry decides
# whether the app appears in the applications grid at all, and the metainfo
# decides how its page looks -- summary, screenshots, release notes, links.
# Neither is exercised by the test suite, and both fail silently, so an invalid
# metainfo shows up as an app that simply never appears in GNOME Software.
#
# Flathub refuses a submission whose metainfo does not validate.
#
# Usage:
#   scripts/validate-metadata.sh
#
# Exit status:
#   0  both files valid, or the validators are not installed locally
#   1  a validator ran and rejected a file
#
# The validators are optional locally -- they live in different packages on
# every distribution -- but CI installs both, so the check always runs there.
# A skip says so out loud rather than passing quietly.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DESKTOP="$ROOT/data/com.kingletas.Solander.desktop"
METAINFO="$ROOT/data/com.kingletas.Solander.metainfo.xml"

status=0

if command -v desktop-file-validate >/dev/null 2>&1; then
    if desktop-file-validate "$DESKTOP"; then
        echo "desktop entry: valid"
    else
        echo "desktop entry: INVALID" >&2
        status=1
    fi
else
    echo "desktop entry: skipped -- desktop-file-validate not installed (apt install desktop-file-utils)"
fi

if command -v appstreamcli >/dev/null 2>&1; then
    # Pedantic findings are style notes and do not fail the build. The component
    # id carries a capital S, which is the desktop id, the icon name, the
    # Flatpak id and the Wayland app_id of a published release -- changing it
    # would orphan every installed copy.
    if appstreamcli validate --no-net "$METAINFO"; then
        echo "metainfo: valid"
    else
        echo "metainfo: INVALID" >&2
        status=1
    fi
else
    echo "metainfo: skipped -- appstreamcli not installed (apt install appstream)"
fi

exit "$status"
