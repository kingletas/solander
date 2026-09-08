"""What a report pasted out of this reader is allowed to say about somebody's vault."""

from pathlib import Path

from solander.core.session import describe_run


def test_a_report_names_no_vault_and_no_path():
    """It is written to leave the machine. How large the vault is helps; where it is does not."""
    details = describe_run("2.3.0", notes=2, theme="stone")
    assert str(Path.home()) not in details
    assert "vault: open" in details
    assert "notes: 2" in details
    assert "theme: stone" in details


def test_a_run_with_no_vault_says_so_rather_than_reporting_a_size():
    details = describe_run("2.3.0", notes=None, theme="stone")
    assert "vault: none" in details
    assert "notes:" not in details


def test_a_path_shown_to_a_person_carries_no_account_name():
    """A message naming a missing file loses nothing by leaving the account out."""
    from solander.core.session import shown_path

    assert shown_path(Path.home() / "Documents/My Notes") == "~/Documents/My Notes"
    assert shown_path(Path.home()) == "~"
    # A different account whose name merely starts the same way is not under home.
    assert shown_path(f"{Path.home()}x/notes") == f"{Path.home()}x/notes"
    assert shown_path("/etc/solander") == "/etc/solander"
