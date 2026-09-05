#!/usr/bin/env bash
#
# version.sh -- print the version this working tree builds as.
#
# Usage:
#   packaging/version.sh
#
# The version is declared once, as __version__ in src/solander/__init__.py, and
# pyproject.toml reads it from there through hatchling. Everything that needs it
# outside Python asks this script, so the pattern that finds it exists in one
# place rather than in each build script and CI job.
#
# Exits 1 when no version can be read, so a caller cannot build an artifact
# named after an empty string.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE="${SOURCE:-$HERE/src/solander/__init__.py}"

version="$(sed -n 's/^__version__ = "\(.*\)"$/\1/p' "$SOURCE" | head -1)"

if [ -z "$version" ]; then
  echo "version.sh: no __version__ in $SOURCE" >&2
  exit 1
fi

printf '%s\n' "$version"
