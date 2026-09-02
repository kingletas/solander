"""Command-line entry point: version, path arguments, and environment preflight."""

import os
import shutil
import subprocess
import sys

from . import __version__

USAGE = """\
solander [PATH]

Opens PATH as a vault (directory) or a note (.md file) in a read-only reader.
With no PATH, reopens the last session.

Options:
  --sandbox         print the AppArmor profile this installation needs, and nothing
                    else, so it can be piped: solander --sandbox | sudo tee PROFILE
  --sandbox-status  report whether that profile is installed, attached, and working
  --version         print the version and exit
  -h, --help        this text
"""

SANDBOX_HELP = """\
solander: WebKit's sandbox cannot start under this system's security policy.

Ubuntu restricts unprivileged user namespaces, and the sandbox WebKitGTK wraps
around its rendering processes needs one. Without it the app aborts with
"bwrap: setting up uid map: Permission denied".

The fix is a one-time AppArmor profile granting exactly this application's
interpreter that permission. The profile, rendered for this installation:

{profile}

Install it as /etc/apparmor.d/solander and reload AppArmor — the exact
steps are in the README under "The sandbox and Ubuntu's user-namespace policy".

To bypass this check and try anyway, set SOLANDER_SKIP_SANDBOX_CHECK=1.
"""

SHEBANG_HELP = """\
solander: WebKit's sandbox cannot start, but the AppArmor profile for it
is already installed — it just did not attach to this process.

That happens when the app is started through the venv console script or another
`#!` shebang: AppArmor attaches the profile by interpreter path, and a shebang
launch bypasses that. Start the app through the `solander` launcher
(installed by `make install`), which executes the interpreter directly.

To bypass this check and try anyway, set SOLANDER_SKIP_SANDBOX_CHECK=1.
"""

PROFILE_PATH = "/etc/apparmor.d/solander"

PROFILE_TEMPLATE = """\
abi <abi/4.0>,
include <tunables/global>

profile solander {interpreter} flags=(unconfined) {{
  userns,
}}
"""


def inside_flatpak() -> bool:
    """Reports whether this process is running inside a Flatpak sandbox."""
    return os.path.exists("/.flatpak-info")


def sandbox_ready() -> bool:
    """Reports whether bubblewrap can build a user namespace under this confinement.

    Inside Flatpak the answer is always yes, and the probe below cannot say so:
    the process is already in Flatpak's own user namespace, nesting another one
    is refused, and WebKit's sandbox works regardless because Flatpak provides
    the confinement. Probing there reports a failure no AppArmor profile could
    ever fix, so the app would refuse to start and hand out unfollowable advice.
    """
    if inside_flatpak():
        return True
    bwrap = shutil.which("bwrap")
    true_bin = shutil.which("true")
    if bwrap is None or true_bin is None:
        return True
    try:
        probe = subprocess.run(  # noqa: S603 — fixed argv, no untrusted input
            [bwrap, "--unshare-user", "--ro-bind", "/", "/", true_bin],
            capture_output=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return True
    return probe.returncode == 0


def profile_target() -> str:
    """The path AppArmor should attach the profile to, which differs by install.

    From a source install the app runs on a private interpreter inside its own
    virtualenv, and naming that is as narrow as it gets. From a system package
    the interpreter is the shared `/usr/bin/python3`, and naming *that* would
    grant user namespaces to every Python process on the machine — so the entry
    point is named instead, which is what Ubuntu's own profiles for packaged
    Python applications do.
    """
    interpreter = os.path.realpath(sys.executable)
    # sys.prefix diverges from base_prefix exactly when running inside a venv.
    if sys.prefix != sys.base_prefix:
        return interpreter
    entry = os.path.realpath(sys.argv[0]) if sys.argv and sys.argv[0] else ""
    return entry if entry and os.path.isfile(entry) else interpreter


def setup_command(profile: str, profile_path: str) -> str:
    """One paste-able command: write the profile, then reload AppArmor.

    It lives here rather than with the setup window because it is a string and
    nothing else — and a test for it must not have to import GTK.
    """
    marker = "SOLANDER_PROFILE"
    return (
        f"sudo tee {profile_path} > /dev/null << '{marker}'\n"
        f"{profile}\n"
        f"{marker}\n"
        f"sudo apparmor_parser -r {profile_path}"
    )


def rendered_profile() -> str:
    """Renders the AppArmor profile for however this copy of the app was installed."""
    return PROFILE_TEMPLATE.format(interpreter=profile_target()).rstrip("\n")


def current_label() -> str:
    """Reads this process's AppArmor label, empty where none is readable."""
    try:
        with open("/proc/self/attr/apparmor/current") as handle:
            return handle.read().strip()
    except OSError:
        return ""


def check_sandbox() -> str:
    """Returns the remediation text when the sandbox cannot start, empty when it can."""
    if os.environ.get("SOLANDER_SKIP_SANDBOX_CHECK", "") == "1":
        return ""
    if sandbox_ready() and os.environ.get("SOLANDER_FORCE_SETUP", "") != "1":
        return ""
    if os.path.exists(PROFILE_PATH) and not current_label().startswith("solander"):
        return SHEBANG_HELP
    interpreter = os.path.realpath(sys.executable)
    help_text = SANDBOX_HELP.format(profile=rendered_profile())
    if not interpreter.startswith(sys.prefix):
        help_text += (
            "\nNote: this interpreter is the system Python, so the profile above would\n"
            "cover every Python process. Run `make install` first — it gives the app\n"
            "a private interpreter copy the profile can name narrowly.\n"
        )
    return help_text


def sandbox_status() -> tuple[str, int]:
    """Reports the sandbox in one line per fact, and whether it is ready to run."""
    interpreter = profile_target()
    installed = os.path.exists(PROFILE_PATH)
    label = current_label()
    ready = sandbox_ready()
    lines = [
        f"profile     {PROFILE_PATH} {'installed' if installed else 'NOT installed'}",
        f"interpreter {interpreter}",
        f"label       {label or '(none)'}",
        f"sandbox     {'works' if ready else 'REFUSED — WebKit cannot start'}",
    ]
    if not interpreter.startswith(sys.prefix):
        lines.append(
            "warning     this is a shared interpreter, so the profile would cover "
            "every process using it; run `make install` for a private copy"
        )
    if installed and not label.startswith("solander"):
        lines.append(
            "warning     the profile is installed but did not attach here — it names "
            "a different path, or this process came through a #! shebang"
        )
    if not ready:
        lines.append(f"fix         solander --sandbox | sudo tee {PROFILE_PATH}")
        lines.append(f"            sudo apparmor_parser -r {PROFILE_PATH}")
    return "\n".join(lines), 0 if ready else 1


def main() -> int:
    """Parses the trivial flags, then hands the real arguments to the GTK application."""
    arguments = sys.argv[1:]
    if "--version" in arguments:
        print(f"solander {__version__}")
        return 0
    if "--sandbox" in arguments:
        # Only the profile reaches stdout: this output is meant for a pipe.
        print(rendered_profile())
        return 0
    if "--sandbox-status" in arguments:
        report, code = sandbox_status()
        print(report)
        return code
    if "-h" in arguments or "--help" in arguments:
        print(USAGE, end="")
        return 0
    sandbox_problem = check_sandbox()
    if sandbox_problem:
        print(sandbox_problem, file=sys.stderr)
        # From the applications grid there is no terminal to read that on, so a
        # plain-GTK setup window guides the fix wherever a display exists.
        if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
            from .gui.setup import run_setup

            shebang = sandbox_problem is SHEBANG_HELP
            command = setup_command(rendered_profile(), PROFILE_PATH)

            def recheck() -> bool:
                return sandbox_ready() and os.environ.get(
                    "SOLANDER_FORCE_SETUP", ""
                ) != "1"

            return run_setup(command, shebang, recheck)
        return 1
    try:
        import gi

        gi.require_version("Gtk", "4.0")
        gi.require_version("Adw", "1")
        gi.require_version("WebKit", "6.0")
    except (ImportError, ValueError) as error:
        print(
            "solander needs the system GTK bindings:\n"
            "  sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 gir1.2-webkit-6.0\n"
            f"({error})",
            file=sys.stderr,
        )
        return 1
    from .gui.app import ReaderApplication

    return ReaderApplication().run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
