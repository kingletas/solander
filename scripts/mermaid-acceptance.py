"""Runs every mermaid block in a real vault through the renderer and reports coverage."""

import re
import sys
import traceback
from collections import Counter
from pathlib import Path

from solander.core.mermaid import MermaidError, MermaidUnsupported, render_mermaid
from solander.core.sanitize import sanitize

FENCE = re.compile(r"^```mermaid\s*$(.*?)^```", re.M | re.S)

root = Path(sys.argv[1]).expanduser()
outcomes = Counter()
failures = []
for path in root.rglob("*.md"):
    if "99 Archive" in str(path) or ".trash" in str(path):
        continue
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        continue
    for block in FENCE.findall(text):
        try:
            svg = render_mermaid(block)
        except MermaidUnsupported as error:
            outcomes[f"unsupported:{error.kind}"] += 1
            continue
        except MermaidError as error:
            outcomes["not drawn"] += 1
            failures.append((str(path), str(error)))
            continue
        except Exception:
            outcomes["CRASH"] += 1
            failures.append((str(path), traceback.format_exc().splitlines()[-1]))
            continue
        cleaned = sanitize(svg)
        if "<svg" not in cleaned or cleaned.count("<") < svg.count("<") * 0.9:
            outcomes["sanitizer stripped"] += 1
            failures.append((str(path), "sanitizer removed elements"))
        else:
            outcomes["rendered"] += 1

total = sum(outcomes.values())
print(f"{total} blocks")
for key, count in outcomes.most_common():
    print(f"  {key}: {count} ({count / total * 100:.1f}%)")
for path, why in failures[:25]:
    print(f"  FAIL {path}: {why}")
