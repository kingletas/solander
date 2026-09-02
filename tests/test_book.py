"""Book ordering and the book page treatment."""

from obsidian_reader.core.book import chapter_title, chapters_in, natural_key
from obsidian_reader.core.csssnippets import sanitize_css
from obsidian_reader.core.render import NoteRenderer
from obsidian_reader.core.vault import Vault


def test_natural_order_shelves_two_before_ten():
    names = ["10 Ten.md", "2 Two.md", "1 One.md"]
    assert sorted(names, key=natural_key) == ["1 One.md", "2 Two.md", "10 Ten.md"]


def test_chapters_come_from_the_folder_in_reading_order(tmp_path):
    root = tmp_path / "v"
    (root / "Book").mkdir(parents=True)
    (root / "Book" / "02 Second.md").write_text("b")
    (root / "Book" / "01 First.md").write_text("a")
    (root / "Book" / "10 Tenth.md").write_text("c")
    (root / "Book" / "Deep").mkdir()
    (root / "Book" / "Deep" / "03 Not a chapter.md").write_text("d")
    vault = Vault.open(root)
    assert chapters_in(vault, "Book") == [
        "Book/01 First.md", "Book/02 Second.md", "Book/10 Tenth.md"
    ]


def test_chapter_titles_drop_the_ordering_prefix():
    assert chapter_title("Book/04 Chapter Four The Training Ground.md") == (
        "Chapter Four The Training Ground"
    )
    assert chapter_title("Book/00 Prologue.md") == "Prologue"


def test_font_faces_survive_with_vault_urls():
    css = sanitize_css(
        '@font-face { font-family: "X Literata"; '
        'src: url("../fonts/Literata[opsz,wght].ttf"); font-weight: 300 800; }'
    )
    assert "@font-face" in css
    assert 'url("vault:///.obsidian/fonts/Literata%5Bopsz%2Cwght%5D.ttf")' in css


def test_remote_font_faces_are_dropped_whole():
    css = sanitize_css(
        '@font-face { font-family: "Evil"; src: url("https://evil.example/x.ttf"); }'
    )
    assert "@font-face" not in css
    assert "evil" not in css


def _book_vault(tmp_path):
    root = tmp_path / "v"
    (root / "Book").mkdir(parents=True)
    (root / "Book" / "01 One.md").write_text("# One\n\nFirst prose. [[Two]]\n")
    (root / "Book" / "02 Two.md").write_text(
        "---\ntitle: The Middle Way\ntags: [x]\n---\nSecond prose.\n"
    )
    (root / "Book" / "03 Three.md").write_text("Last prose.\n")
    return Vault.open(root)


def _context(rel):
    if not rel.startswith("Book/"):
        return None
    return {
        "place": "2 of 3",
        "prev_title": "One",
        "next_title": "Three",
        "default_classes": ["book-default"],
    }


def test_book_pages_are_the_chapter_alone(tmp_path):
    vault = _book_vault(tmp_path)
    page = NoteRenderer(vault, book=_context).render("Book/02 Two.md").page
    assert '<h1 class="inline-title">The Middle Way</h1>' in page
    assert 'class="book-nav"' in page
    assert "2 of 3" in page
    assert "reader:///action/book-next" in page
    assert "← One" in page and "Three →" in page
    assert 'class="crumbs"' not in page
    assert 'class="properties"' not in page
    assert 'class="note-meta"' not in page
    assert "book-page book-default" in page


def test_pages_carry_the_obsidian_preview_section(tmp_path):
    vault = _book_vault(tmp_path)
    page = NoteRenderer(vault).render("Book/01 One.md").page
    assert '<div class="markdown-preview-section"><div>' in page
