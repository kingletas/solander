"""Runs every Dataview block and inline expression in a real vault through the engine.

Usage: uv run python scripts/dataview-acceptance.py /path/to/vault
Prints evaluated/failed counts and a histogram of failure reasons — the honest
coverage number for the changelog.
"""

import re
import sys
import time
from collections import Counter
from pathlib import Path

from solander.core.dataview import DataviewEngine
from solander.core.dql import DqlError
from solander.core.graph import VaultGraph
from solander.core.indexing import sync_indexes
from solander.core.store import IndexStore
from solander.core.vault import Vault

FENCE = re.compile(r"```dataview\n(.*?)```", re.DOTALL)
INLINE = re.compile(r"`= ([^`]+)`")


def main() -> int:
    root = Path(sys.argv[1]).expanduser().resolve()
    vault = Vault.open(root)
    cache = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    started = time.monotonic()
    if cache is not None:
        graph = sync_indexes(vault, IndexStore(cache)).graph
    else:
        graph = VaultGraph.build(vault)
    print(f"graph built in {time.monotonic() - started:.1f}s over {len(vault.notes)} notes")
    engine = DataviewEngine(graph)

    queries = failed_queries = 0
    inlines = failed_inlines = 0
    reasons: Counter = Counter()
    examples: dict[str, str] = {}
    query_seconds = 0.0

    for rel in vault.notes:
        note = vault.read_note(rel)
        if note.error:
            continue
        for body in FENCE.findall(note.text):
            block = "\n".join(line.lstrip("> ") for line in body.strip().split("\n"))
            queries += 1
            begin = time.monotonic()
            try:
                engine.run_query(block, rel)
            except DqlError as error:
                failed_queries += 1
                reasons[str(error)] += 1
                examples.setdefault(str(error), rel)
            query_seconds += time.monotonic() - begin
        for expression in INLINE.findall(note.text):
            inlines += 1
            try:
                engine.run_inline(expression.strip(), rel)
            except DqlError as error:
                failed_inlines += 1
                reasons[f"inline: {error}"] += 1
                examples.setdefault(f"inline: {error}", rel)

    print(f"queries: {queries - failed_queries}/{queries} evaluated "
          f"({query_seconds * 1000 / max(queries, 1):.0f}ms avg)")
    print(f"inline:  {inlines - failed_inlines}/{inlines} evaluated")
    for reason, count in reasons.most_common(15):
        print(f"  {count:4d}  {reason}   e.g. {examples[reason]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
