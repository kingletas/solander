"""The documentation is checked the way the code is.

Nothing else reads these files, so a link broken by renaming a heading, or a
version left behind by a release, is invisible until a reader hits it. Both
have happened here.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DOCS = [
    ROOT / "README.md",
    ROOT / "CONTRIBUTING.md",
    ROOT / "SECURITY.md",
    ROOT / "CHANGELOG.md",
    ROOT / "docs" / "getting-started.md",
    ROOT / "docs" / "user-guide.md",
]

LINK = re.compile(r"\[([^\]]*)\]\(([^)\s]+)\)")
HEADING = re.compile(r"^#{1,6}\s+(.*)$", re.MULTILINE)


def slug(heading: str) -> str:
    """The anchor GitHub generates for a heading.

    Lowercase, drop everything that is not a word character, space or hyphen,
    then one hyphen per space -- a run of spaces becomes a run of hyphens, so
    an em dash between two words leaves a double hyphen behind.
    """
    text = re.sub(r"[^\w\s-]", "", heading.strip().lower())
    return re.sub(r"\s", "-", text)


def anchors(document: Path) -> set[str]:
    return {slug(h) for h in HEADING.findall(document.read_text(encoding="utf-8"))}


def test_the_slug_matches_github():
    """Pinned to a heading whose anchor GitHub generated, em dash included."""
    assert slug("3. First launch — the one-time sandbox step") == (
        "3-first-launch--the-one-time-sandbox-step"
    )
    assert slug("What it will never do") == "what-it-will-never-do"


@pytest.mark.parametrize("document", DOCS, ids=lambda p: p.name)
def test_every_relative_link_resolves(document):
    broken = []
    for label, target in LINK.findall(document.read_text(encoding="utf-8")):
        if target.startswith(("http://", "https://", "mailto:", "#!")):
            continue
        path, _, fragment = target.partition("#")
        destination = document
        if path:
            destination = (document.parent / path).resolve()
            if not destination.exists():
                broken.append(f"[{label}]({target}) -- no such file")
                continue
        if fragment and destination.suffix == ".md":
            if fragment not in anchors(destination):
                broken.append(f"[{label}]({target}) -- no such heading")
    assert broken == [], f"{document.name}: " + "; ".join(broken)


def test_no_document_names_a_versioned_package():
    """A version written into an install command is stale the next release.

    The install commands take whichever bundle the reader downloaded, so the
    version is never theirs to type. The changelog is the record of what each
    release was, so it names versions by definition.
    """
    named = []
    for document in DOCS:
        if document.name == "CHANGELOG.md":
            continue
        text = document.read_text(encoding="utf-8")
        for found in re.findall(r"solander[_-](\d+\.\d+\.\d+)", text):
            named.append(f"{document.name} names {found}")
    assert named == [], "install commands take a glob, not a version: " + "; ".join(named)


NUMBER_WORDS = {
    "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
}


def test_the_documented_theme_counts_match_the_registry():
    """Three sentences claim how many themes there are. Adding one falsifies all of them."""
    from solander.core.themes import THEMES

    archive = [theme for theme in THEMES.values() if theme.family == "Archive"]
    wrong = []
    for document in DOCS:
        # The changelog records what was true at each release. An entry saying
        # thirteen themes is correct history, not a stale claim.
        if document.name == "CHANGELOG.md":
            continue
        text = document.read_text(encoding="utf-8")
        for word in re.findall(r"\b([A-Za-z]+) themes\b", text):
            claimed = NUMBER_WORDS.get(word.lower())
            if claimed is not None and claimed != len(THEMES):
                wrong.append(f"{document.name}: '{word} themes' but there are {len(THEMES)}")
        for word in re.findall(r"\b([A-Za-z]+) dark themes\b", text):
            claimed = NUMBER_WORDS.get(word.lower())
            if claimed is not None and claimed != len(archive):
                wrong.append(
                    f"{document.name}: '{word} dark themes' but Archive has {len(archive)}"
                )
    assert wrong == [], "; ".join(wrong)
