"""Version-independent key for UUID-shaped source references.

Swile moved its transaction ids from random UUIDv4 to time-ordered UUIDv7 and
kept everything after the version nibble: the same transaction now comes back
under a new id whose tail matches the old one. The tail recognizes the pair;
any other reference (Enable Banking's opaque entry reference) has no key.
"""
import re

_RENUMBERED_UUID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[47]([0-9a-f]{3}-[0-9a-f]{4}-[0-9a-f]{12})$",
    re.IGNORECASE,
)


def transaction_key(source_ref: str) -> str | None:
    """The tail after the version nibble of a UUIDv4 or v7, None for other refs."""
    if (match := _RENUMBERED_UUID.match(source_ref)) is None:
        return None
    return match.group(1).lower()
