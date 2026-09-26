"""The desktop's text scaling, as the factor the reading page is sized by."""

from solander.core.fonts import text_scale


def test_the_standard_dpi_is_no_scaling():
    assert text_scale(96 * 1024) == 1.0


def test_large_text_scales_by_its_factor():
    assert text_scale(120 * 1024) == 1.25
    assert text_scale(144 * 1024) == 1.5


def test_an_unset_dpi_is_no_scaling():
    assert text_scale(-1) == 1.0
    assert text_scale(0) == 1.0


def test_a_wild_dpi_is_held_to_a_readable_range():
    assert text_scale(10 * 1024) == 0.5
    assert text_scale(1000 * 1024) == 3.0
