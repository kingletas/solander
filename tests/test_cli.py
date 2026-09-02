"""The sandbox preflight: refuses with guidance where WebKit would abort cryptically."""

import os
import stat

from solander import cli


def fake_bwrap(tmp_path, exit_code: int, monkeypatch) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    shim = bin_dir / "bwrap"
    shim.write_text(f"#!/bin/sh\nexit {exit_code}\n")
    shim.chmod(shim.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ['PATH']}")


def test_ready_when_bwrap_succeeds(tmp_path, monkeypatch):
    fake_bwrap(tmp_path, 0, monkeypatch)
    assert cli.sandbox_ready()
    assert cli.check_sandbox() == ""


def test_refuses_with_guidance_when_bwrap_is_blocked(tmp_path, monkeypatch):
    fake_bwrap(tmp_path, 1, monkeypatch)
    monkeypatch.delenv("SOLANDER_SKIP_SANDBOX_CHECK", raising=False)
    monkeypatch.setattr(cli, "PROFILE_PATH", str(tmp_path / "absent-profile"))
    assert not cli.sandbox_ready()
    message = cli.check_sandbox()
    assert "user namespaces" in message
    assert "profile solander" in message
    assert "/etc/apparmor.d/solander" in message


def test_installed_but_unattached_profile_names_the_shebang_trap(tmp_path, monkeypatch):
    fake_bwrap(tmp_path, 1, monkeypatch)
    monkeypatch.delenv("SOLANDER_SKIP_SANDBOX_CHECK", raising=False)
    profile = tmp_path / "solander-profile"
    profile.write_text("profile solander ...")
    monkeypatch.setattr(cli, "PROFILE_PATH", str(profile))
    monkeypatch.setattr(cli, "current_label", lambda: "unconfined")
    message = cli.check_sandbox()
    assert "already installed" in message
    assert "shebang" in message


def test_attached_profile_with_blocked_bwrap_gets_the_full_help(tmp_path, monkeypatch):
    fake_bwrap(tmp_path, 1, monkeypatch)
    monkeypatch.delenv("SOLANDER_SKIP_SANDBOX_CHECK", raising=False)
    profile = tmp_path / "solander-profile"
    profile.write_text("profile solander ...")
    monkeypatch.setattr(cli, "PROFILE_PATH", str(profile))
    monkeypatch.setattr(cli, "current_label", lambda: "solander (unconfined)")
    assert "user namespaces" in cli.check_sandbox()


def test_skip_variable_bypasses_the_check(tmp_path, monkeypatch):
    fake_bwrap(tmp_path, 1, monkeypatch)
    monkeypatch.setenv("SOLANDER_SKIP_SANDBOX_CHECK", "1")
    assert cli.check_sandbox() == ""


def test_no_bwrap_means_no_opinion(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    assert cli.sandbox_ready()


def test_profile_names_the_running_interpreter():
    profile = cli.rendered_profile()
    assert profile.startswith("abi <abi/4.0>,")
    assert "userns," in profile
    assert "python" in profile


def test_setup_command_is_one_pasteable_block():
    from solander.cli import PROFILE_PATH, rendered_profile, setup_command

    command = setup_command(rendered_profile(), PROFILE_PATH)
    assert command.startswith(f"sudo tee {PROFILE_PATH}")
    assert "userns," in command
    assert command.rstrip().endswith(f"sudo apparmor_parser -r {PROFILE_PATH}")


def test_force_setup_variable_trips_the_preflight(monkeypatch):
    from solander import cli

    monkeypatch.setenv("SOLANDER_FORCE_SETUP", "1")
    monkeypatch.delenv("SOLANDER_SKIP_SANDBOX_CHECK", raising=False)
    assert cli.check_sandbox() != ""


def test_a_venv_install_names_its_own_interpreter(monkeypatch):
    """A private interpreter is already as narrow as a profile can be."""
    from solander import cli

    monkeypatch.setattr(cli.sys, "prefix", "/opt/app/.venv")
    monkeypatch.setattr(cli.sys, "base_prefix", "/usr")
    monkeypatch.setattr(cli.sys, "executable", "/opt/app/.venv/bin/python")
    assert cli.profile_target() == "/opt/app/.venv/bin/python"


def test_a_system_install_names_the_entry_point_not_the_shared_interpreter(monkeypatch, tmp_path):
    """Naming /usr/bin/python3 would grant user namespaces to every Python process."""
    from solander import cli

    entry = tmp_path / "solander"
    entry.write_text("#!/usr/bin/python3\n")
    monkeypatch.setattr(cli.sys, "prefix", "/usr")
    monkeypatch.setattr(cli.sys, "base_prefix", "/usr")
    monkeypatch.setattr(cli.sys, "executable", "/usr/bin/python3.12")
    monkeypatch.setattr(cli.sys, "argv", [str(entry)])
    assert cli.profile_target() == str(entry)


def test_the_sandbox_probe_is_skipped_inside_flatpak(monkeypatch):
    """The probe cannot succeed inside Flatpak, and does not need to.

    A Flatpak process is already in Flatpak's own user namespace, so nesting
    another is refused — while WebKit's sandbox works, because Flatpak is the
    confinement. Running the probe there refuses to start the application and
    prints an AppArmor fix that could never change the result.
    """
    calls = []
    monkeypatch.setattr(cli.shutil, "which", lambda name: calls.append(name) or "/usr/bin/bwrap")
    monkeypatch.setattr(cli.os.path, "exists", lambda path: path == "/.flatpak-info")

    assert cli.sandbox_ready() is True
    assert calls == [], "the probe ran inside Flatpak"


def test_the_sandbox_probe_still_runs_outside_flatpak(monkeypatch):
    """The exclusion must be Flatpak-only, or the guard is gone everywhere."""
    monkeypatch.setattr(cli.os.path, "exists", lambda path: False)
    monkeypatch.setattr(cli.shutil, "which", lambda name: None)

    # which() returning None is the "cannot probe" path, which answers True --
    # what matters is that inside_flatpak() did not short-circuit ahead of it.
    assert cli.inside_flatpak() is False


def test_the_version_the_app_prints_is_the_version_it_was_built_as():
    """__version__ and pyproject are two literals that can disagree, and did.

    2.2.1 shipped reporting 2.2.0: the release job compares the tag, pyproject
    and the changelog, and never looks at this one.
    """
    import tomllib
    from pathlib import Path

    import solander

    root = Path(__file__).resolve().parent.parent
    with (root / "pyproject.toml").open("rb") as handle:
        declared = tomllib.load(handle)["project"]["version"]
    assert solander.__version__ == declared
