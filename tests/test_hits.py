"""Search words marked in a rendered page: every word, whole or begun, and never inside markup."""

from solander.core.hits import FIRST_HIT_ID, mark_terms

PAGE = (
    "<html><head><title>Cat notes</title><style>.cat { color: red }</style></head>"
    '<body><main class="note"><h1>Cat notes</h1>'
    '<p>Our cat and the <a href="cat.md">catalogue</a> of a Café.</p>'
    "<svg><text>cat</text></svg><p>Tom &amp; Jerry</p></main></body></html>"
)


def test_every_word_is_marked_not_only_the_first():
    page, count = mark_terms(PAGE, ["cat", "cafe"])
    assert count == 4
    assert page.count('class="search-hit"') == 4


def test_a_word_is_marked_where_it_begins_a_longer_word():
    page, _ = mark_terms(PAGE, ["cat"])
    assert '<mark class="search-hit">cat</mark>alogue' in page


def test_accents_and_case_do_not_hide_a_hit():
    page, _ = mark_terms(PAGE, ["cafe"])
    assert '>Café</mark>' in page and '<mark class="search-hit"' in page


def test_markup_titles_styles_and_drawings_are_left_alone():
    page, _ = mark_terms(PAGE, ["cat"])
    assert "<title>Cat notes</title>" in page
    assert ".cat { color: red }" in page
    assert 'href="cat.md"' in page
    assert "<svg><text>cat</text></svg>" in page


def test_the_first_hit_carries_the_anchor_the_window_scrolls_to():
    page, _ = mark_terms(PAGE, ["cat"])
    assert page.count(f'id="{FIRST_HIT_ID}"') == 1
    assert page.index(f'id="{FIRST_HIT_ID}"') < page.index("Our")


def test_a_word_inside_a_longer_word_is_not_a_hit():
    page, count = mark_terms("<p>concatenate</p>", ["cat"])
    assert count == 0 and page == "<p>concatenate</p>"


def test_an_entity_is_never_split():
    page, count = mark_terms(PAGE, ["amp"])
    assert count == 0 and "Tom &amp; Jerry" in page


def test_no_words_leave_the_page_as_it_was():
    assert mark_terms(PAGE, []) == (PAGE, 0)
