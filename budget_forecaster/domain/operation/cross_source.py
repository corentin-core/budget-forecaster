"""Shared cross-source reconciliation parameters and matching primitives.

The same transaction gets a different description from a file export and from
the API, so a file op and an API op are matched by signed amount and a small
date window rather than by content. The ingest-time dedup and the purge
migration both build on these primitives, so their pairing can never drift.
"""
from datetime import date

# Max day gap between a file op and an API op recognised as the same transaction,
# absorbing the booking-date vs value-date drift.
RECONCILE_WINDOW_DAYS = 3


def amount_cents(amount: float) -> int:
    """Signed amount rounded to whole cents, the unit cross-source matching uses."""
    return round(amount * 100)


def date_gap(reference: date, other: date) -> int:
    """Absolute day gap; the primary key when ranking reconciliation candidates."""
    return abs((reference - other).days)


def is_amount_date_match(
    cents_a: int, date_a: date, cents_b: int, date_b: date
) -> bool:
    """Whether two ops line up on signed amount and a date within the window."""
    return cents_a == cents_b and date_gap(date_a, date_b) <= RECONCILE_WINDOW_DAYS
