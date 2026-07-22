"""Stable content reference for operations without an external reference."""
import hashlib
from datetime import date

# Field separator unlikely to appear in a description.
_SEP = "\x1f"


def content_ref(description: str, amount: float, operation_date: date) -> str:
    """Return a stable dedup key derived from an operation's content.

    Stable across processes, unlike the builtin hash of a string. Two operations
    with the same description, amount and day collapse to the same key.

    Currency is not part of the key: only use within a single-currency scope
    (dedup is per account, and an account has one currency).
    """
    canonical = _SEP.join(
        (description, str(round(amount * 100)), operation_date.isoformat())
    )
    return hashlib.sha256(canonical.encode()).hexdigest()
