"""The app mark exists once in spirit: the packaged copy must equal the desktop icon."""

from importlib import resources
from pathlib import Path

import pytest


def test_packaged_mark_matches_the_desktop_icon():
    packaged = resources.files("solander.assets").joinpath("icons/mark.svg")
    repo_icon = Path(__file__).resolve().parents[1] / "data/com.kingletas.Solander.svg"
    if not repo_icon.is_file():
        pytest.skip("repo data/ layout not present in this installation")
    assert packaged.read_text("utf-8") == repo_icon.read_text("utf-8")


def mark_markup() -> str:
    return resources.files("solander.assets").joinpath("icons/mark.svg").read_text("utf-8")


def test_the_mark_is_one_self_contained_symbol():
    """No gradients, filters, masks, rasters or text: it has to survive 16px and any renderer."""
    markup = mark_markup()
    for forbidden in ("<linearGradient", "<radialGradient", "<filter", "<mask", "<image",
                      "<text", "<style", "url(", "href", "font"):
        assert forbidden not in markup
    assert markup.count("<path") == 3
    assert 'viewBox="0 0 128 128"' in markup


def test_the_mark_can_wear_any_theme():
    """The welcome page inlines it, so CSS re-tints these three parts per theme."""
    markup = mark_markup()
    for part in ("mark-board", "mark-face", "mark-seal"):
        assert f'class="{part}"' in markup
    blood = (
        resources.files("solander.assets")
        .joinpath("theme-archive.css")
        .read_text("utf-8")
    )
    for part in ("mark-board", "mark-face", "mark-seal"):
        assert f".{part} {{ fill:" in blood


def test_the_desktop_entry_and_metainfo_agree_with_the_app_id():
    """A rename that misses one of these leaves the window without its icon."""
    from solander import APP_ID

    data = Path(__file__).resolve().parents[1] / "data"
    if not data.is_dir():
        pytest.skip("repo data/ layout not present in this installation")
    desktop = data / f"{APP_ID}.desktop"
    metainfo = data / f"{APP_ID}.metainfo.xml"
    icon = data / f"{APP_ID}.svg"
    assert desktop.is_file() and metainfo.is_file() and icon.is_file()
    assert f"Icon={APP_ID}" in desktop.read_text("utf-8")
    assert f"<id>{APP_ID}</id>" in metainfo.read_text("utf-8")
