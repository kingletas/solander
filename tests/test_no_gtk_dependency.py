"""The suite must pass on a machine with no GObject bindings.

CI is exactly such a machine, and the local virtualenv is not: it is built with
`--system-site-packages` so the application can reach the system bindings, which
means a stray GTK import in the core — or a unit test that reaches into the
window layer — passes here and fails only after a push. These two checks move
that failure back to `make check`.
"""

import re
import subprocess
import sys
from pathlib import Path

# A fresh interpreter, because importing modules a second time inside the test
# session resets constants other tests have already read — which is a way of
# breaking three tests to check one.
PROBE = """
import importlib
import pkgutil
import sys

# Binding a name to None in sys.modules makes importing it raise ImportError.
sys.modules["gi"] = None

import solander.core

names = ["solander", "solander.cli"] + [
    f"solander.core.{module.name}" for module in pkgutil.iter_modules(solander.core.__path__)
]
for name in names:
    importlib.import_module(name)
print(len(names))
"""

GTK_IMPORT = re.compile(r"^\s*(from|import)\s+solander\.gui\b", re.MULTILINE)


def test_the_core_and_the_cli_import_without_gtk():
    probe = subprocess.run(  # noqa: S603 - fixed argv, no untrusted input
        [sys.executable, "-c", PROBE],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert probe.returncode == 0, f"the core needs GTK to import:\n{probe.stderr}"
    assert int(probe.stdout.strip()) > 10


def test_no_unit_test_reaches_into_the_gtk_layer():
    """The window layer is covered by the live smoke run, never by this suite."""
    here = Path(__file__)
    offenders = sorted(
        path.name
        for path in here.parent.glob("test_*.py")
        if path != here and GTK_IMPORT.search(path.read_text(encoding="utf-8"))
    )
    assert offenders == [], f"these import the GTK layer: {offenders}"
