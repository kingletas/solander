"""The kanban renderer: columns, cards, archive, and wikilinks inside cards."""

from obsidian_reader.core.graph import VaultGraph
from obsidian_reader.core.kanban import parse_kanban
from obsidian_reader.core.render import NoteRenderer

BOARD = (
    "---\nkanban-plugin: board\n---\n\n"
    "## To Do\n\n- [ ] [[Projects/Alpha|Ship Alpha]]\n- [ ] plain card\n\n"
    "## Done\n\n- [x] finished thing\n\n***\n\n- [ ] archived card\n"
)


def test_parse_columns_cards_and_archive():
    columns = parse_kanban(BOARD.split("---\n")[-1])
    titles = [column.title for column in columns]
    assert titles == ["To Do", "Done", "Archive"]
    assert columns[0].cards[1] == (" ", "plain card")
    assert columns[2].cards == [(" ", "archived card")]


def test_board_note_renders_as_board_with_links(vault, vault_dir):
    (vault_dir / "Board.md").write_text(BOARD)
    vault.reindex()
    renderer = NoteRenderer(vault, graph_provider=lambda: VaultGraph.build(vault))
    body = renderer.render("Board.md").body
    assert 'class="kanban"' in body
    assert body.count("kanban-column") >= 3
    assert 'href="reader:///note/Projects/Alpha.md"' in body
    assert "kanban-done" in body


def test_non_board_notes_are_untouched(vault):
    body = NoteRenderer(vault).render("Index.md").body
    assert "kanban" not in body
