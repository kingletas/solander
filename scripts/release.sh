#!/usr/bin/env bash
#
# release.sh -- promote the working tree to a release version.
#
# Usage:
#   scripts/release.sh 2.2.5
#   scripts/release.sh -n 2.2.5      show what would change, write nothing
#   scripts/release.sh -h
#
# The version is typed once, here. This writes __version__ -- which pyproject
# and every build script read -- retitles the changelog's Unreleased section
# with that version and today's date, and adds the release entry a software
# centre reads. Nothing is committed and no tag is created.
#
# The AppStream entry is seeded with a placeholder, because that paragraph is
# what a software centre shows and no script can write it. `make check` refuses
# the placeholder, so a release cannot ship with it unwritten.
#
# Refuses a version that already has a changelog section, and refuses to
# release an Unreleased section with nothing under it.
#
# Environment overrides:
#   DATE   release date (default: today, YYYY-MM-DD)

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATE="${DATE:-$(date +%F)}"
PLACEHOLDER="RELEASE SUMMARY NOT WRITTEN"
DRY_RUN=0

usage() { sed -n '2,/^$/p' "${BASH_SOURCE[0]}" | sed 's/^#\{1,2\} \{0,1\}//'; }

while getopts ":nh" option; do
  case "$option" in
    n) DRY_RUN=1 ;;
    h) usage; exit 0 ;;
    *) echo "release.sh: unknown option -$OPTARG" >&2; exit 2 ;;
  esac
done
shift $((OPTIND - 1))

VERSION="${1:-}"
[ -n "$VERSION" ] || { echo "usage: release.sh [-n] VERSION" >&2; exit 2; }

if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "release.sh: '$VERSION' is not a MAJOR.MINOR.PATCH version" >&2
  exit 2
fi

INIT="$HERE/src/solander/__init__.py"
CHANGELOG="$HERE/CHANGELOG.md"
METAINFO="$HERE/data/com.kingletas.Solander.metainfo.xml"

current="$("$HERE/packaging/version.sh")"

if grep -qE "^## ${VERSION//./\\.} " "$CHANGELOG"; then
  echo "release.sh: $VERSION already has a changelog section" >&2
  exit 1
fi

if ! grep -qE '^## Unreleased$' "$CHANGELOG"; then
  echo "release.sh: no '## Unreleased' section in the changelog to promote" >&2
  exit 1
fi

# An Unreleased heading with nothing under it would publish an empty release.
notes="$(awk '/^## Unreleased$/ { found = 1; next } found && /^## / { exit } found { print }' \
  "$CHANGELOG" | tr -d '[:space:]')"
if [ -z "$notes" ]; then
  echo "release.sh: the Unreleased section is empty -- nothing to release" >&2
  exit 1
fi

echo "solander ${current} -> ${VERSION}, dated ${DATE}"
if [ "$DRY_RUN" -eq 1 ]; then
  echo "  would write __version__      in $(realpath --relative-to="$HERE" "$INIT")"
  echo "  would retitle ## Unreleased  in $(realpath --relative-to="$HERE" "$CHANGELOG")"
  echo "  would add <release>          in $(realpath --relative-to="$HERE" "$METAINFO")"
  echo "nothing written (-n)"
  exit 0
fi

sed -i "s/^__version__ = \".*\"$/__version__ = \"${VERSION}\"/" "$INIT"
sed -i "s/^## Unreleased$/## ${VERSION} — ${DATE}/" "$CHANGELOG"

# Newest first: the software centre and the test both read the first entry.
awk -v version="$VERSION" -v date="$DATE" -v placeholder="$PLACEHOLDER" '
  { print }
  /^  <releases>$/ && !done {
    printf "    <release version=\"%s\" date=\"%s\">\n", version, date
    print  "      <description>"
    printf "        <p>%s</p>\n", placeholder
    print  "      </description>"
    print  "    </release>"
    done = 1
  }
' "$METAINFO" > "$METAINFO.tmp" && mv "$METAINFO.tmp" "$METAINFO"

grep -q "$PLACEHOLDER" "$METAINFO" || { echo "release.sh: the release entry was not added" >&2; exit 1; }

cat <<SUMMARY

Written. Two things left, in order:

  1. Replace "$PLACEHOLDER" in
     data/com.kingletas.Solander.metainfo.xml with one paragraph describing
     this release for a software centre. make check refuses the placeholder.

  2. make check && git commit

Then tag it -- that is what builds and publishes the packages:

  git tag v${VERSION} && git push origin main --tags
SUMMARY
