#!/usr/bin/env bash
# Fails when a module Solander and Slate carry as identical copies differs between them.
#
# The two apps share their rendering stack as copies, listed in shared-modules.tsv.
# A fix to one copy belongs in both, and this check makes "identical" a fact rather
# than a memory. It needs both checkouts; when the other one is not on this machine it
# says so and passes, because neither repository can require the other to exist.
#
# Usage:
#   scripts/shared-modules.sh
#
# Environment:
#   SOLANDER_TREE, SLATE_TREE   the two checkouts (default: this one, and its sibling)
#   SHARED_MODULES_PENDING      a sentence saying which copy waits on a port, and why;
#                               the difference is then reported and the check passes
set -euo pipefail

here="$(cd "$(dirname "$0")/.." && pwd)"
if [ -d "$here/src/solander" ]; then
    : "${SOLANDER_TREE:=$here}"
    : "${SLATE_TREE:=$(dirname "$here")/slate}"
else
    : "${SLATE_TREE:=$here}"
    : "${SOLANDER_TREE:=$(dirname "$here")/solander}"
fi

for tree in "$SOLANDER_TREE" "$SLATE_TREE"; do
    if [ ! -f "$tree/scripts/shared-modules.tsv" ]; then
        echo "shared modules: skipped, no checkout with scripts/shared-modules.tsv at $tree"
        exit 0
    fi
done

drift=0
while IFS=$'\t' read -r solander slate; do
    case "$solander" in ''|'#'*) continue ;; esac
    if ! cmp -s "$SOLANDER_TREE/$solander" "$SLATE_TREE/$slate"; then
        echo "differs: $solander (Solander) and $slate (Slate)" >&2
        drift=$((drift + 1))
    fi
done < "$SOLANDER_TREE/scripts/shared-modules.tsv"

if [ "$drift" -eq 0 ]; then
    exit 0
fi
if [ -n "${SHARED_MODULES_PENDING:-}" ]; then
    echo "shared modules: $drift differ, declared pending: $SHARED_MODULES_PENDING"
    exit 0
fi
echo "" >&2
echo "shared modules: $drift of the copies Solander and Slate share differ." >&2
echo "Port the change to the other app, or say why it waits:" >&2
echo "  SHARED_MODULES_PENDING='...' make check" >&2
exit 1
