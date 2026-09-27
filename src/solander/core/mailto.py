"""What a `mailto:` link would put in a new email, said before it opens."""

from urllib.parse import parse_qs, unquote, urlparse

MAX_NAMED_RECIPIENTS = 3
# The fields a link can fill in besides the address, in the order they are named.
_FILLED_FIELDS = {
    "cc": "a copy",
    "bcc": "a hidden copy",
    "subject": "the subject",
    "body": "the message",
}


def describe_mailto(uri: str) -> str:
    """One or two sentences naming who the email is to and what else it fills in.

    A note can carry a link that fills in a subject, a message and copies to
    other people, so the confirmation says so rather than showing only the
    first address.
    """
    parsed = urlparse(uri)
    query = {key.casefold(): values for key, values in parse_qs(parsed.query).items()}
    recipients = [unquote(part).strip() for part in parsed.path.split(",") if part.strip()]
    recipients += [
        address.strip()
        for value in query.get("to", [])
        for address in value.split(",")
        if address.strip()
    ]
    if not recipients:
        sentence = "It starts an email with no address."
    else:
        named = ", ".join(recipients[:MAX_NAMED_RECIPIENTS])
        rest = len(recipients) - MAX_NAMED_RECIPIENTS
        if rest > 0:
            named += f" and {rest} more"
        sentence = f"It starts an email to {named}."
    filled = [words for field, words in _FILLED_FIELDS.items() if query.get(field)]
    if filled:
        sentence += f" The link also fills in {_joined(filled)}."
    return sentence


def _joined(named: list[str]) -> str:
    if len(named) == 1:
        return named[0]
    return ", ".join(named[:-1]) + " and " + named[-1]
