#!/usr/bin/env bash
#
# build.sh -- build the Solander .deb.
#
# Usage:
#   packaging/deb/build.sh [OUTDIR]     OUTDIR defaults to dist/
#
# The package is Architecture: all -- every dependency is pure Python, so there
# is nothing compiled to match an architecture against. The application and its
# dependencies are vendored into /usr/lib/solander rather than taken from apt,
# because latex2mathml and mdit-py-plugins are not in Ubuntu at all and pinning
# the rest against whatever the distribution ships is a version-skew problem
# with no upside.
#
# The GObject bindings are NOT vendored and cannot be: python3-gi and the gir1.2
# typelibs are system packages, and the deb declares them as dependencies.
#
# Environment overrides:
#   VERSION   package version (default: read from pyproject.toml)
#   PYTHON    the interpreter that installs the vendored dependencies
#             (default: /usr/bin/python3 -- the same one the launcher runs, so
#             what is packaged is what will import)

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUTDIR="${1:-$HERE/dist}"
VERSION="${VERSION:-$(sed -n 's/^version = "\(.*\)"/\1/p' "$HERE/pyproject.toml" | head -1)}"
APP_ID="com.kingletas.Solander"
# Deliberately the absolute system interpreter, not whatever `python3` resolves
# to on this PATH: the launcher runs /usr/bin/python3, and packaging with a
# different one can vendor code that interpreter cannot import.
PYTHON="${PYTHON:-/usr/bin/python3}"

[ -n "$VERSION" ] || { echo "build.sh: no version in pyproject.toml" >&2; exit 1; }
[ -x "$PYTHON" ] || { echo "build.sh: no interpreter at $PYTHON" >&2; exit 1; }
if ! "$PYTHON" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)'; then
  echo "build.sh: $PYTHON is older than 3.12, which the package requires" >&2
  exit 1
fi

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

echo "building solander ${VERSION}"

install -d "$STAGE/usr/lib/solander" \
           "$STAGE/usr/bin" \
           "$STAGE/usr/share/applications" \
           "$STAGE/usr/share/icons/hicolor/scalable/apps" \
           "$STAGE/usr/share/metainfo" \
           "$STAGE/usr/share/doc/solander" \
           "$STAGE/etc/apparmor.d" \
           "$STAGE/DEBIAN"

# The app and its pure-Python dependencies, together, with no .venv involved.
"$PYTHON" -m pip install --quiet --target "$STAGE/usr/lib/solander" "$HERE"
# pip leaves its bookkeeping behind; a package does not need it.
rm -rf "$STAGE/usr/lib/solander"/*.dist-info "$STAGE/usr/lib/solander/bin"

# The entry point AppArmor names. It is executed directly (not through a #!
# console script inside a virtualenv), which is what lets a profile attach.
cat > "$STAGE/usr/bin/solander" <<'LAUNCHER'
#!/usr/bin/python3
"""Solander's entry point, kept apart from the package so AppArmor can name it."""

import sys

sys.path.insert(0, "/usr/lib/solander")

from solander.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
LAUNCHER
chmod 0755 "$STAGE/usr/bin/solander"

sed 's|@LAUNCHER@|/usr/bin/solander|' "$HERE/data/$APP_ID.desktop" \
  > "$STAGE/usr/share/applications/$APP_ID.desktop"
install -m 0644 "$HERE/data/$APP_ID.svg" \
  "$STAGE/usr/share/icons/hicolor/scalable/apps/$APP_ID.svg"
install -m 0644 "$HERE/data/$APP_ID.metainfo.xml" \
  "$STAGE/usr/share/metainfo/$APP_ID.metainfo.xml"
install -m 0644 "$HERE/LICENSE" "$STAGE/usr/share/doc/solander/copyright"
install -m 0644 "$HERE/README.md" "$STAGE/usr/share/doc/solander/README.md"

# WebKit sandboxes its renderers with bubblewrap, which needs an unprivileged
# user namespace; Ubuntu 24.04+ grants those only through an AppArmor profile.
# Naming the entry point rather than /usr/bin/python3 keeps the grant to this
# application, which is the shape Ubuntu's own profiles for packaged Python
# applications use. A deb user never has to install this by hand.
cat > "$STAGE/etc/apparmor.d/solander" <<'PROFILE'
abi <abi/4.0>,
include <tunables/global>

profile solander /usr/bin/solander flags=(unconfined) {
  userns,

  include if exists <local/solander>
}
PROFILE
chmod 0644 "$STAGE/etc/apparmor.d/solander"

INSTALLED_KB="$(du -ks "$STAGE/usr" "$STAGE/etc" | awk '{total += $1} END {print total}')"

cat > "$STAGE/DEBIAN/control" <<CONTROL
Package: solander
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: all
Depends: python3 (>= 3.12), python3-gi, gir1.2-gtk-4.0, gir1.2-adw-1, gir1.2-webkit-6.0
Recommends: gir1.2-poppler-0.18
Suggests: apparmor
Installed-Size: ${INSTALLED_KB}
Maintainer: Luis Tineo <code@kingletas.com>
Homepage: https://github.com/kingletas/solander
Description: Read-only reading application for Markdown vaults
 Solander opens a folder of Markdown in place and never writes into it: no
 caches, no plugins, no scripts, no network. It is fluent in Obsidian's
 dialect -- wikilinks, embeds, callouts, frontmatter, tags, canvases, kanban
 boards, .base views and Dataview queries all render as themselves.
 .
 A solander is the clamshell box an archive keeps its documents in: open it
 to look at something, close it, and nothing has changed.
CONTROL

cat > "$STAGE/DEBIAN/postinst" <<'POSTINST'
#!/bin/sh
set -e

if [ "$1" = "configure" ]; then
    # A profile that is installed but never parsed does nothing at all.
    if command -v apparmor_parser >/dev/null 2>&1 && [ -d /sys/kernel/security/apparmor ]; then
        apparmor_parser -r -T -W /etc/apparmor.d/solander || true
    fi
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database -q /usr/share/applications || true
    fi
    # A stale icon cache hides a newly installed icon entirely.
    if command -v gtk-update-icon-cache >/dev/null 2>&1; then
        gtk-update-icon-cache -q -f -t /usr/share/icons/hicolor || true
    fi
fi
POSTINST

cat > "$STAGE/DEBIAN/prerm" <<'PRERM'
#!/bin/sh
set -e

if [ "$1" = "remove" ] && command -v apparmor_parser >/dev/null 2>&1; then
    apparmor_parser -R /etc/apparmor.d/solander 2>/dev/null || true
fi
PRERM

cat > "$STAGE/DEBIAN/postrm" <<'POSTRM'
#!/bin/sh
set -e

if [ "$1" = "purge" ]; then
    rm -f /etc/apparmor.d/solander
fi
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q /usr/share/applications || true
fi
POSTRM

cat > "$STAGE/DEBIAN/conffiles" <<'CONFFILES'
/etc/apparmor.d/solander
CONFFILES

chmod 0755 "$STAGE/DEBIAN/postinst" "$STAGE/DEBIAN/prerm" "$STAGE/DEBIAN/postrm"

install -d "$OUTDIR"
DEB="$OUTDIR/solander_${VERSION}_all.deb"
dpkg-deb --root-owner-group --build "$STAGE" "$DEB" >/dev/null

echo "built $DEB"
