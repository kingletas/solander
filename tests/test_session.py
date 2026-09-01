"""Session persistence lives outside the vault and survives corruption."""

from obsidian_reader.core.session import SessionStore


def test_state_round_trips(tmp_path):
    store = SessionStore(tmp_path / "conf")
    store.state.last_vault = "/some/vault"
    store.state.zoom = 1.25
    store.save()
    reloaded = SessionStore(tmp_path / "conf")
    assert reloaded.state.last_vault == "/some/vault"
    assert reloaded.state.zoom == 1.25


def test_corrupt_state_file_degrades_to_defaults(tmp_path):
    directory = tmp_path / "conf"
    directory.mkdir()
    (directory / "session.json").write_text("{not json")
    store = SessionStore(directory)
    assert store.state.restore_session is True


def test_wrongly_typed_fields_are_ignored(tmp_path):
    directory = tmp_path / "conf"
    directory.mkdir()
    (directory / "session.json").write_text('{"zoom": "huge", "last_vault": "/v"}')
    store = SessionStore(directory)
    assert store.state.zoom == 1.0
    assert store.state.last_vault == "/v"


def test_recents_deduplicate_and_cap(tmp_path):
    store = SessionStore(tmp_path / "conf")
    for index in range(15):
        store.remember_vault(f"/vault-{index}")
    store.remember_vault("/vault-3")
    assert store.state.recent_vaults[0] == "/vault-3"
    assert len(store.state.recent_vaults) == 10
    assert store.state.last_vault == "/vault-3"
