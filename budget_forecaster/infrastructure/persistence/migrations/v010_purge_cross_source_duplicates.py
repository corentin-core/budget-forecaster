"""v9 -> v10: purge cross-source duplicate operations.

Databases populated from a file export and later synced from the Enable Banking
API hold the same transaction twice: the two sources give it different
descriptions, so the content-ref dedup never recognised the pair. Each pair is
collapsed here by keeping the file op and deleting the API copy, matching on
signed amount and a small date window. A manual link carried only by the API
copy is repointed to the surviving file op so no user intent is lost.
"""

import logging
import sqlite3
from datetime import date
from functools import partial
from typing import NamedTuple

from budget_forecaster.domain.operation import cross_source

logger = logging.getLogger(__name__)


class _Op(NamedTuple):
    """An operation row reduced to the fields the pairing needs."""

    unique_id: int
    op_date: date
    amount_cents: int


def run(conn: sqlite3.Connection) -> None:
    """Collapse cross-source duplicate operations across every account."""
    purged = 0
    for (account_id,) in conn.execute("SELECT id FROM accounts").fetchall():
        for api_id, file_id in _pairs_for_account(conn, account_id):
            _reassign_manual_link(conn, from_op=api_id, to_op=file_id)
            conn.execute(
                "DELETE FROM operation_links WHERE operation_unique_id = ?", (api_id,)
            )
            conn.execute("DELETE FROM operations WHERE unique_id = ?", (api_id,))
            purged += 1
    conn.commit()
    logger.info("Purged %d cross-source duplicate operations", purged)


def _pairs_for_account(
    conn: sqlite3.Connection, account_id: int
) -> tuple[tuple[int, int], ...]:
    """Greedily pair each API op with a file op of matching amount and date.

    Returns (api_unique_id, file_unique_id) pairs; matching is one-to-one so
    distinct transactions sharing an amount and date are never collapsed. The
    nearest date wins, mirroring the ingest-time reconciliation.
    """
    file_ops = _load_ops(conn, account_id, with_source_ref=False)
    api_ops = _load_ops(conn, account_id, with_source_ref=True)

    matched_files: set[int] = set()
    pairs: list[tuple[int, int]] = []
    for api in api_ops:
        candidates = [
            file_op
            for file_op in file_ops
            if file_op.unique_id not in matched_files
            and cross_source.is_amount_date_match(
                file_op.amount_cents, file_op.op_date, api.amount_cents, api.op_date
            )
        ]
        if not candidates:
            continue
        best = min(candidates, key=partial(_match_key, api.op_date))
        matched_files.add(best.unique_id)
        pairs.append((api.unique_id, best.unique_id))
    return tuple(pairs)


def _match_key(api_date: date, file_op: _Op) -> tuple[int, int]:
    """Rank file candidates: nearest date first, lowest id to break ties."""
    return (cross_source.date_gap(api_date, file_op.op_date), file_op.unique_id)


def _load_ops(
    conn: sqlite3.Connection, account_id: int, with_source_ref: bool
) -> tuple[_Op, ...]:
    """Load the file ops (no source_ref) or API ops (with source_ref)."""
    predicate = "IS NOT NULL" if with_source_ref else "IS NULL"
    cursor = conn.execute(
        f"SELECT unique_id, date, amount FROM operations "  # noqa: S608
        f"WHERE account_id = ? AND source_ref {predicate} "
        f"ORDER BY date, unique_id",
        (account_id,),
    )
    return tuple(
        _Op(
            unique_id=row["unique_id"],
            op_date=date.fromisoformat(row["date"]),
            amount_cents=cross_source.amount_cents(row["amount"]),
        )
        for row in cursor.fetchall()
    )


def _reassign_manual_link(conn: sqlite3.Connection, from_op: int, to_op: int) -> None:
    """Move a manual link off the doomed op onto the survivor.

    Skips when the doomed op has no manual link. A manual link on the survivor
    wins and is kept; an automatic one is overwritten, since manual intent
    outranks a categorizer-derived link.
    """
    if not _has_manual_link(conn, from_op):
        return
    if _has_manual_link(conn, to_op):
        logger.warning(
            "Discarding manual link on op %d: survivor op %d is already "
            "manually linked",
            from_op,
            to_op,
        )
        return
    conn.execute("DELETE FROM operation_links WHERE operation_unique_id = ?", (to_op,))
    conn.execute(
        "UPDATE operation_links SET operation_unique_id = ? "
        "WHERE operation_unique_id = ?",
        (to_op, from_op),
    )


def _has_manual_link(conn: sqlite3.Connection, operation_id: int) -> bool:
    """Whether the operation carries a manual (user-set) link."""
    row = conn.execute(
        "SELECT is_manual FROM operation_links WHERE operation_unique_id = ?",
        (operation_id,),
    ).fetchone()
    return row is not None and bool(row["is_manual"])
