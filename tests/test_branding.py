"""The app mark exists once in spirit: the packaged copy must equal the desktop icon."""

from importlib import resources
from pathlib import Path

import pytest


def test_packaged_mark_matches_the_desktop_icon():
    packaged = resources.files("obsidian_reader.assets").joinpath("icons/mark.svg")
    repo_icon = Path(__file__).resolve().parents[1] / "data/com.kingletas.ObsidianReader.svg"
    if not repo_icon.is_file():
        pytest.skip("repo data/ layout not present in this installation")
    assert packaged.read_text("utf-8") == repo_icon.read_text("utf-8")


def mark_markup() -> str:
    return resources.files("obsidian_reader.assets").joinpath("icons/mark.svg").read_text("utf-8")


def test_the_mark_is_one_self_contained_symbol():
    """No gradients, filters, masks, rasters or text: it has to survive 16px and any renderer."""
    markup = mark_markup()
    for forbidden in ("<linearGradient", "<radialGradient", "<filter", "<mask", "<image",
                      "<text", "<style", "url(", "href", "font"):
        assert forbidden not in markup
    assert markup.count("<path") == 3
    assert 'viewBox="0 0 128 128"' in markup


def test_the_mark_can_wear_either_theme():
    """The welcome page inlines it, so CSS re-tints these three parts per theme."""
    markup = mark_markup()
    for part in ("mark-board", "mark-face", "mark-seal"):
        assert f'class="{part}"' in markup
    blood = (
        resources.files("obsidian_reader.assets")
        .joinpath("theme-blood-record.css")
        .read_text("utf-8")
    )
    for part in ("mark-board", "mark-face", "mark-seal"):
        assert f".{part} {{ fill:" in blood
