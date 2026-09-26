"""Session persistence lives outside the vault and survives corruption."""

from solander.core.session import SessionStore, reading_fraction


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


def test_pinned_notes_persist_per_vault(tmp_path):
    store = SessionStore(tmp_path / "conf")
    store.state.pinned_notes["/vault"] = ["Projects/Alpha.md"]
    store.save()
    reloaded = SessionStore(tmp_path / "conf")
    assert reloaded.state.pinned_notes == {"/vault": ["Projects/Alpha.md"]}


def test_outline_visibility_persists(tmp_path):
    store = SessionStore(tmp_path / "conf")
    store.state.outline_visible = True
    store.save()
    assert SessionStore(tmp_path / "conf").state.outline_visible is True


def test_quick_section_expansion_persists(tmp_path):
    store = SessionStore(tmp_path / "conf")
    store.state.quick_expanded = False
    store.save()
    assert SessionStore(tmp_path / "conf").state.quick_expanded is False



def test_state_from_the_former_name_is_adopted_rather_than_left_behind(tmp_path):
    """A rename that abandons the old directory is indistinguishable from a reset."""
    former = tmp_path / "obsidian-reader"
    former.mkdir()
    (former / "session.json").write_text('{"last_vault": "/kept"}')
    store = SessionStore(tmp_path / "solander")
    assert store.state.last_vault == "/kept"
    assert not former.exists()


def test_adoption_never_overwrites_state_that_already_exists(tmp_path):
    former = tmp_path / "obsidian-reader"
    former.mkdir()
    (former / "session.json").write_text('{"last_vault": "/old"}')
    current = tmp_path / "solander"
    current.mkdir()
    (current / "session.json").write_text('{"last_vault": "/current"}')
    store = SessionStore(current)
    assert store.state.last_vault == "/current"
    assert former.is_dir()


def test_scroll_positions_round_trip(tmp_path):
    store = SessionStore(tmp_path / "conf")
    store.state.scroll_positions = {"Projects/Alpha.md": 0.42}
    store.save()
    assert SessionStore(tmp_path / "conf").state.scroll_positions == {"Projects/Alpha.md": 0.42}


def test_a_reading_fraction_is_a_number_between_top_and_bottom():
    assert reading_fraction("0.5") == 0.5
    assert reading_fraction(0.25) == 0.25
    assert reading_fraction("1.7") == 1.0
    assert reading_fraction("-3") == 0.0


def test_anything_that_is_not_a_position_is_no_position():
    for value in ("", "none", "nan", "inf", None, [], {"y": 1}):
        assert reading_fraction(value) is None
