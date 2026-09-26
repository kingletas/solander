"""The shortcuts window lists exactly the keys the window binds."""

import re
from pathlib import Path

from solander.shortcuts import ACCELERATORS, SHORTCUTS

WINDOW = Path(__file__).resolve().parents[1] / "src/solander/gui/window.py"

MODIFIERS = {"<Control>": "Ctrl+", "<Shift>": "Shift+", "<Alt>": "Alt+"}
KEY_NAMES = {"plus": "+", "equal": "=", "minus": "-", "question": "?", "Escape": "Esc"}

# A listed key that looks like an accelerator: a Ctrl or Alt chord, a function
# key, or Esc. Ctrl+click is a mouse gesture and is left out.
ACCELERATOR_LIKE = re.compile(r"^(?:(?:Ctrl|Alt)\+(?!click$).+|F\d+|Esc)$")


def shown_as(accelerator: str) -> str:
    """A GTK accelerator the way the shortcuts window writes it: `<Control>p` is `Ctrl+P`."""
    prefix = ""
    rest = accelerator
    while rest.startswith("<"):
        modifier, rest = rest[: rest.index(">") + 1], rest[rest.index(">") + 1 :]
        prefix += MODIFIERS[modifier]
    key = KEY_NAMES.get(rest, rest.upper() if len(rest) == 1 else rest)
    return prefix + key


def listed_keys() -> set[str]:
    """Every key or gesture named in the left-hand column, one per alternative."""
    keys = set()
    for combination, _ in SHORTCUTS:
        keys.update(part.strip() for part in re.split(r" / | or |, ", combination))
    return keys


def test_the_formatting_matches_what_the_window_prints():
    assert shown_as("<Control><Shift>f") == "Ctrl+Shift+F"
    assert shown_as("<Control>plus") == "Ctrl++"
    assert shown_as("<Alt>Left") == "Alt+Left"
    assert shown_as("F5") == "F5"
    assert shown_as("Escape") == "Esc"


def test_every_bound_key_is_listed():
    listed = listed_keys()
    missing = sorted(
        f"{shown_as(accel)} ({action})"
        for action, accels in ACCELERATORS.items()
        for accel in accels
        if shown_as(accel) not in listed
    )
    assert missing == [], f"bound but not in the shortcuts window: {missing}"


def test_every_listed_key_is_bound():
    bound = {shown_as(accel) for accels in ACCELERATORS.values() for accel in accels}
    claimed = sorted(key for key in listed_keys() if ACCELERATOR_LIKE.match(key))
    unbound = [key for key in claimed if key not in bound]
    assert claimed, "the pattern stopped matching anything in the list"
    assert unbound == [], f"listed but bound to nothing: {unbound}"


def test_every_action_with_keys_is_one_the_window_installs():
    """A key for an action the window never adds would be silently dead."""
    source = WINDOW.read_text(encoding="utf-8")
    installed = set(re.findall(r'add\(\s*"([a-z-]+)"', source))
    assert installed, "found no add() calls in the window"
    assert sorted(set(ACCELERATORS) - installed) == []
