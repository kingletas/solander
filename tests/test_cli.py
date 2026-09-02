"""The sandbox preflight: refuses with guidance where WebKit would abort cryptically."""

import os
import stat

from obsidian_reader import cli


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
    monkeypatch.delenv("OBSIDIAN_READER_SKIP_SANDBOX_CHECK", raising=False)
    monkeypatch.setattr(cli, "PROFILE_PATH", str(tmp_path / "absent-profile"))
    assert not cli.sandbox_ready()
    message = cli.check_sandbox()
    assert "user namespaces" in message
    assert "profile obsidian-reader" in message
    assert "/etc/apparmor.d/obsidian-reader" in message


def test_installed_but_unattached_profile_names_the_shebang_trap(tmp_path, monkeypatch):
    fake_bwrap(tmp_path, 1, monkeypatch)
    monkeypatch.delenv("OBSIDIAN_READER_SKIP_SANDBOX_CHECK", raising=False)
    profile = tmp_path / "obsidian-reader-profile"
    profile.write_text("profile obsidian-reader ...")
    monkeypatch.setattr(cli, "PROFILE_PATH", str(profile))
    monkeypatch.setattr(cli, "current_label", lambda: "unconfined")
    message = cli.check_sandbox()
    assert "already installed" in message
    assert "shebang" in message


def test_attached_profile_with_blocked_bwrap_gets_the_full_help(tmp_path, monkeypatch):
    fake_bwrap(tmp_path, 1, monkeypatch)
    monkeypatch.delenv("OBSIDIAN_READER_SKIP_SANDBOX_CHECK", raising=False)
    profile = tmp_path / "obsidian-reader-profile"
    profile.write_text("profile obsidian-reader ...")
    monkeypatch.setattr(cli, "PROFILE_PATH", str(profile))
    monkeypatch.setattr(cli, "current_label", lambda: "obsidian-reader (unconfined)")
    assert "user namespaces" in cli.check_sandbox()


def test_skip_variable_bypasses_the_check(tmp_path, monkeypatch):
    fake_bwrap(tmp_path, 1, monkeypatch)
    monkeypatch.setenv("OBSIDIAN_READER_SKIP_SANDBOX_CHECK", "1")
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
    from obsidian_reader.cli import PROFILE_PATH, rendered_profile
    from obsidian_reader.gui.setup import setup_command

    command = setup_command(rendered_profile(), PROFILE_PATH)
    assert command.startswith(f"sudo tee {PROFILE_PATH}")
    assert "userns," in command
    assert command.rstrip().endswith(f"sudo apparmor_parser -r {PROFILE_PATH}")


def test_force_setup_variable_trips_the_preflight(monkeypatch):
    from obsidian_reader import cli

    monkeypatch.setenv("OBSIDIAN_READER_FORCE_SETUP", "1")
    monkeypatch.delenv("OBSIDIAN_READER_SKIP_SANDBOX_CHECK", raising=False)
    assert cli.check_sandbox() != ""
