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
    assert not cli.sandbox_ready()
    message = cli.check_sandbox()
    assert "user namespaces" in message
    assert "profile obsidian-reader" in message
    assert "/etc/apparmor.d/obsidian-reader" in message


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
