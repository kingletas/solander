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
