"""One version, declared once, and everything a release names agreeing with it.

2.2.1 shipped announcing 2.2.0, and 2.2.4 was tagged with the changelog section
still headed Unreleased. Both were a version copied into a second place and only
one copy updated, and both were caught by CI after the tag was public rather
than by the working tree before it.
"""

import re
import subprocess
import tomllib
from pathlib import Path

import solander

ROOT = Path(__file__).resolve().parent.parent


def test_the_version_is_declared_in_exactly_one_place():
    """A second literal is what both version defects were made of."""
    with (ROOT / "pyproject.toml").open("rb") as handle:
        pyproject = tomllib.load(handle)

    assert "version" not in pyproject["project"], "pyproject declares a second version literal"
    assert "version" in pyproject["project"].get("dynamic", [])

    source = ROOT / pyproject["tool"]["hatch"]["version"]["path"]
    assert source == ROOT / "src" / "solander" / "__init__.py"
    assert f'__version__ = "{solander.__version__}"' in source.read_text(encoding="utf-8")


def test_the_shell_helper_reads_the_same_version_the_package_does():
    """Its pattern is the one thing tying the build scripts to the literal."""
    printed = subprocess.run(
        [str(ROOT / "packaging" / "version.sh")],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    assert printed == solander.__version__


def test_the_changelog_has_a_released_section_for_this_version():
    """A tag whose version is still headed Unreleased publishes empty notes."""
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    heading = re.compile(
        rf"^## {re.escape(solander.__version__)} — \d{{4}}-\d\d-\d\d$", re.MULTILINE
    )

    assert heading.search(changelog), (
        f"CHANGELOG.md has no dated section for {solander.__version__}: "
        "make release promotes the Unreleased section into one"
    )


def test_the_metainfo_newest_release_is_this_version():
    """The software centre reads this file, and no other check looks at it."""
    metainfo = (ROOT / "data" / "com.kingletas.Solander.metainfo.xml").read_text(encoding="utf-8")
    releases = re.findall(r'<release version="([^"]+)" date="([^"]+)"', metainfo)

    assert releases, "the metainfo declares no releases at all"
    newest, date = releases[0]
    assert newest == solander.__version__, (
        f"the metainfo's newest release is {newest}, the package is {solander.__version__}"
    )
    assert re.fullmatch(r"\d{4}-\d\d-\d\d", date), f"{newest} has a malformed date: {date}"


def test_the_newest_release_entry_has_a_summary_written():
    """release.sh seeds a placeholder, because no script can write this paragraph."""
    metainfo = (ROOT / "data" / "com.kingletas.Solander.metainfo.xml").read_text(encoding="utf-8")

    assert "RELEASE SUMMARY NOT WRITTEN" not in metainfo, (
        "the AppStream entry still carries release.sh's placeholder: a software "
        "centre would show it as this release's description"
    )
