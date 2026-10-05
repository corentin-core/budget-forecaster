"""v13 -> v14: collapse operations Swile stored twice.

Swile moved its transaction ids from UUIDv4 to UUIDv7 and one sync re-added the
transactions it had renumbered. A pair shares the transaction key, date and
amount within an account. The old op is kept with its category and links, and
adopts the new id so later syncs match it exactly; the new copy is deleted.

Before #334 the API answered in English, so some meal-voucher credits exist
both under the French file label and the English API label, neither with a
source_ref. Those pairs keep the French op.
"""

import logging
import sqlite3
from typing import NamedTuple

from budget_forecaster.core.types import Category
from budget_forecaster.domain.operation import cross_source
from budget_forecaster.domain.operation.transaction_key import transaction_key

logger = logging.getLogger(__name__)

_UNCATEGORIZED = Category.UNCATEGORIZED.value
_FRENCH_CREDIT_LABEL = "Crédit titres-resto"
_ENGLISH_CREDIT_LABEL = "Meal vouchers credit"


class _Op(NamedTuple):
    """An operation row reduced to the fields the pairing needs."""

    unique_id: int
    source_ref: str | None
    category: str


def run(conn: sqlite3.Connection) -> None:
    """Collapse renumbered-id pairs and French/English credit pairs."""
    renumbered = _renumbered_pairs(conn)
    for kept, dropped in renumbered:
        _collapse(conn, kept=kept, dropped=dropped)
        conn.execute(
            "UPDATE operations SET source_ref = ? WHERE unique_id = ?",
            (dropped.source_ref, kept.unique_id),
        )
    relabeled = _relabeled_credit_pairs(conn)
    for kept, dropped in relabeled:
        _collapse(conn, kept=kept, dropped=dropped)
    conn.commit()
    logger.info(
        "Collapsed %d renumbered Swile ops and %d relabeled credits",
        len(renumbered),
        len(relabeled),
    )


def _collapse(conn: sqlite3.Connection, kept: _Op, dropped: _Op) -> None:
    """Delete the copy, keeping its category when the survivor has none."""
    if kept.category == _UNCATEGORIZED and dropped.category != _UNCATEGORIZED:
        conn.execute(
            "UPDATE operations SET category = ? WHERE unique_id = ?",
            (dropped.category, kept.unique_id),
        )
    _keep_one_link(conn, kept=kept.unique_id, dropped=dropped.unique_id)
    conn.execute("DELETE FROM operations WHERE unique_id = ?", (dropped.unique_id,))


def _keep_one_link(conn: sqlite3.Connection, kept: int, dropped: int) -> None:
    """Keep the survivor's link; the copy's moves over only if it says more.

    It moves when the survivor has no link, or when it is manual and the
    survivor's is automatic.
    """
    kept_manual = _link_is_manual(conn, kept)
    dropped_manual = _link_is_manual(conn, dropped)
    if dropped_manual is not None and (
        kept_manual is None or (dropped_manual and not kept_manual)
    ):
        conn.execute(
            "DELETE FROM operation_links WHERE operation_unique_id = ?", (kept,)
        )
        conn.execute(
            "UPDATE operation_links SET operation_unique_id = ? "
            "WHERE operation_unique_id = ?",
            (kept, dropped),
        )
        return
    conn.execute(
        "DELETE FROM operation_links WHERE operation_unique_id = ?", (dropped,)
    )


def _link_is_manual(conn: sqlite3.Connection, operation_id: int) -> bool | None:
    """Whether the op's link is manual, None when it has no link."""
    row = conn.execute(
        "SELECT is_manual FROM operation_links WHERE operation_unique_id = ?",
        (operation_id,),
    ).fetchone()
    return None if row is None else bool(row["is_manual"])


def _renumbered_pairs(conn: sqlite3.Connection) -> tuple[tuple[_Op, _Op], ...]:
    """(old v4 op, new v7 op) pairs sharing account, key, date and amount."""
    groups: dict[tuple[int, str, str, int], dict[str, _Op]] = {}
    cursor = conn.execute(
        "SELECT unique_id, account_id, date, amount, category, source_ref "
        "FROM operations WHERE source_ref IS NOT NULL ORDER BY unique_id"
    )
    for row in cursor.fetchall():
        if (key := transaction_key(row["source_ref"])) is None:
            continue
        version = row["source_ref"][14]
        group = groups.setdefault(
            (
                row["account_id"],
                key,
                row["date"],
                cross_source.amount_cents(row["amount"]),
            ),
            {},
        )
        group.setdefault(
            version, _Op(row["unique_id"], row["source_ref"], row["category"])
        )
    return tuple(
        (group["4"], group["7"])
        for group in groups.values()
        if "4" in group and "7" in group
    )


def _relabeled_credit_pairs(
    conn: sqlite3.Connection,
) -> tuple[tuple[_Op, _Op], ...]:
    """(French op, English op) credit pairs, matched one-to-one, lowest id first."""
    cursor = conn.execute(
        "SELECT french.unique_id AS french_id, french.category AS french_category, "
        "english.unique_id AS english_id, english.category AS english_category "
        "FROM operations french JOIN operations english "
        "ON english.account_id = french.account_id AND english.date = french.date "
        "AND ROUND(english.amount * 100) = ROUND(french.amount * 100) "
        "WHERE french.description = ? AND english.description = ? "
        "AND french.source_ref IS NULL AND english.source_ref IS NULL "
        "AND french.amount > 0 ORDER BY french.unique_id, english.unique_id",
        (_FRENCH_CREDIT_LABEL, _ENGLISH_CREDIT_LABEL),
    )
    used: set[int] = set()
    pairs: list[tuple[_Op, _Op]] = []
    for row in cursor.fetchall():
        if row["french_id"] in used or row["english_id"] in used:
            continue
        used.update((row["french_id"], row["english_id"]))
        pairs.append(
            (
                _Op(row["french_id"], None, row["french_category"]),
                _Op(row["english_id"], None, row["english_category"]),
            )
        )
    return tuple(pairs)
