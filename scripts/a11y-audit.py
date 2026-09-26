"""Reads the running window the way a screen reader does, and fails on what it cannot name.

The window is started as its own process on a small vault of invented notes, and
this script walks its accessibility tree over AT-SPI, the same bus Orca reads.
Asking from inside the window's own process would deadlock: the window has to
answer on its main loop while the question is waiting on it.

For each sidebar panel in turn (opened through the panel tab's own "click"
action, as assistive technology would), every control that is on screen is
checked for two things:

  - a name. A button, tab, entry, checkbox or link with no name is announced as
    its role alone ("button"), which tells a person nothing.
  - keyboard focus, for buttons, tabs and entries, which a person who cannot use
    a pointer reaches by Tab and nothing else.

A node with no size is not on screen, whatever its state says: GTK reports the
folded find bar's text as showing. It is skipped.

Usage:
    python scripts/a11y-audit.py          prints every control, exits 1 on a finding

It needs a running desktop session with the accessibility bus, which GNOME
starts. It does not press keys, so it proves that focus can land on a control,
not the order Tab takes.
"""

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import gi

gi.require_version("Atspi", "2.0")
from gi.repository import Atspi

STARTUP_SECONDS = 7
PANEL_SETTLE_SECONDS = 1.5
MAX_DEPTH = 60
MAX_CHILDREN = 400

NAMED_ROLES = {
    "push button", "toggle button", "menu button", "check box", "radio button",
    "page tab", "entry", "text", "link", "list item", "tree item", "combo box",
    "spin button", "slider", "switch", "menu item",
}
FOCUSABLE_ROLES = {"push button", "toggle button", "menu button", "page tab", "entry"}
PANELS = ("Files", "Search", "Links", "Tags", "Bookmarks", "Graph")


def write_vault(root: Path) -> None:
    """A vault with one of each thing a note can put in front of a person."""
    (root / ".obsidian").mkdir(parents=True)
    (root / "Folder").mkdir()
    (root / "A.md").write_text(
        "# A\n\nSee [[B]] and [a site](https://example.com). An #alpha tag.\n\n"
        "- [ ] an open task\n- [x] a done task\n\n> [!note]\n> A callout.\n"
    )
    (root / "B.md").write_text("# B\n\nBack to [[A]].\n")
    (root / "Folder" / "C.md").write_text("# C\n")
    (root / ".obsidian" / "bookmarks.json").write_text(
        '{"items":[{"type":"file","path":"B.md"}]}'
    )


def application_for(pid: int):
    desktop = Atspi.get_desktop(0)
    for index in range(desktop.get_child_count()):
        child = desktop.get_child_at_index(index)
        if child is not None and child.get_process_id() == pid:
            return child
    return None


def controls(node, depth=0):
    """Every control on screen below `node`, as (role, name, focusable)."""
    if node is None or depth > MAX_DEPTH:
        return
    try:
        role = node.get_role_name()
        states = node.get_state_set()
    except Exception:  # a node can vanish while it is being read
        return
    try:
        width = node.get_extents(Atspi.CoordType.WINDOW).width
    except Exception:  # the application and the window frame have no geometry
        width = 0
    on_screen = states.contains(Atspi.StateType.SHOWING) and width > 0
    if role in NAMED_ROLES and on_screen:
        name = (node.get_name() or "").strip()
        yield role, name, states.contains(Atspi.StateType.FOCUSABLE)
    for index in range(min(node.get_child_count(), MAX_CHILDREN)):
        yield from controls(node.get_child_at_index(index), depth + 1)


def find(node, role: str, name: str, depth=0):
    if node is None or depth > MAX_DEPTH:
        return None
    try:
        if node.get_role_name() == role and node.get_name() == name:
            return node
        for index in range(min(node.get_child_count(), MAX_CHILDREN)):
            hit = find(node.get_child_at_index(index), role, name, depth + 1)
            if hit is not None:
                return hit
    except Exception:
        return None
    return None


def audit(app) -> list[str]:
    findings: list[str] = []
    for panel in PANELS:
        tab = find(app, "page tab", panel)
        if tab is None:
            findings.append(f"no panel tab named {panel}")
            continue
        Atspi.Action.do_action(tab, 0)
        time.sleep(PANEL_SETTLE_SECONDS)
        print(f"{panel} panel")
        found = list(controls(app))
        if not found:
            findings.append(f"{panel} panel: no controls found, so nothing was checked")
        # A menu button is a wrapper that cannot take focus around a toggle of the
        # same name that can, so focus is judged by name across the two.
        reachable = {name for _role, name, focusable in found if focusable}
        for role, name, _focusable in found:
            print(f"  {role:14} {name or '(no name)'}")
            if not name:
                findings.append(f"{panel} panel: a {role} with no name")
            if role in FOCUSABLE_ROLES and name not in reachable:
                findings.append(f"{panel} panel: {role} '{name}' cannot take keyboard focus")
    return findings


def main() -> int:
    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch)
        write_vault(root / "vault")
        env = dict(
            os.environ,
            XDG_CONFIG_HOME=str(root / "config"),
            XDG_CACHE_HOME=str(root / "cache"),
        )
        process = subprocess.Popen(
            [sys.executable, "-m", "solander.cli", str(root / "vault" / "A.md")],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            time.sleep(STARTUP_SECONDS)
            app = application_for(process.pid)
            if app is None:
                print("FAIL: the window is not on the accessibility bus")
                return 1
            findings = sorted(set(audit(app)))
        finally:
            process.terminate()
            process.wait(timeout=10)
    for finding in findings:
        print(f"FAIL: {finding}")
    print("RESULT: " + ("FAIL" if findings else "PASS"))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
