"""The window's scripts in a note's page stay the two it is known to run."""

import re
from pathlib import Path

import pytest

from solander.core.pagescripts import READ_SCROLL, SCRIPT_WORLD, block_text, restore_scroll

GUI = Path(__file__).resolve().parents[1] / "src" / "solander" / "gui"


def test_restoring_formats_a_number_into_a_fixed_script():
    assert restore_scroll(0.5) == (
        "window.scrollTo(0, 0.50000 * "
        "(document.documentElement.scrollHeight - window.innerHeight))"
    )


def test_anything_that_is_not_a_number_never_becomes_script():
    with pytest.raises((TypeError, ValueError)):
        restore_scroll("0); alert(1); (0")


def test_the_window_runs_only_these_scripts_and_only_in_its_own_world():
    """Every call the window makes passes one of the three, in SCRIPT_WORLD."""
    calls = []
    for source in GUI.glob("*.py"):
        text = source.read_text(encoding="utf-8")
        calls += re.findall(r"evaluate_javascript\(\s*([^,]+),\s*-1,\s*([^,]+),", text)
    assert calls, "no evaluate_javascript calls found, so nothing was checked"
    for script, world in calls:
        allowed = ("READ_SCROLL", "restore_scroll(fraction)", "block_text(index)")
        assert script.strip() in allowed, script
        assert world.strip() == "SCRIPT_WORLD", world
    assert SCRIPT_WORLD == "solander"


def test_reading_the_position_is_a_constant():
    assert READ_SCROLL.startswith("(() => {") and "document" in READ_SCROLL


def test_reading_a_block_formats_a_whole_number_and_nothing_else():
    assert "querySelectorAll('a.copy-block')[3];" in block_text(3)
    assert block_text(3).startswith("(() => {") and block_text(3).endswith("})()")
    for not_a_number in ("0]; alert(1); [0", "x", None):
        with pytest.raises((TypeError, ValueError)):
            block_text(not_a_number)
