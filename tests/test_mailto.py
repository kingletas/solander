"""A mail link says what it would send before the mail app opens."""

from solander.core.mailto import describe_mailto


def test_one_address():
    assert describe_mailto("mailto:ana@example.org") == "It starts an email to ana@example.org."


def test_encoded_addresses_are_shown_decoded():
    text = describe_mailto("mailto:ana%40example.org,ben@example.org")
    assert text == "It starts an email to ana@example.org, ben@example.org."


def test_addresses_in_the_query_count_too():
    text = describe_mailto("mailto:ana@example.org?to=ben@example.org")
    assert "ana@example.org, ben@example.org" in text


def test_a_long_list_is_counted_not_listed():
    uri = "mailto:" + ",".join(f"p{n}@example.org" for n in range(5))
    assert describe_mailto(uri) == (
        "It starts an email to p0@example.org, p1@example.org, p2@example.org and 2 more."
    )


def test_what_the_link_fills_in_is_named():
    text = describe_mailto("mailto:ana@example.org?Subject=Hi&body=Text&bcc=eve@example.org")
    assert text.endswith("The link also fills in a hidden copy, the subject and the message.")


def test_no_address():
    assert describe_mailto("mailto:?subject=Hi") == (
        "It starts an email with no address. The link also fills in the subject."
    )
