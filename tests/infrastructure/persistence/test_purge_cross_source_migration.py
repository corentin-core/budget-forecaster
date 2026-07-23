"""Tests for the v10 cross-source duplicate purge migration."""

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from budget_forecaster.infrastructure.persistence.migrations import (
    v010_purge_cross_source_duplicates as v010,
)
from budget_forecaster.infrastructure.persistence.sqlite_repository import (
    SqliteRepository,
)


@pytest.fixture(name="conn")
def conn_fixture(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    """An initialized database seeded with one aggregated account."""
    with SqliteRepository(tmp_path / "test.db") as repo:
        conn = repo._get_connection()  # pylint: disable=protected-access
        conn.execute("INSERT INTO aggregated_accounts (id, name) VALUES (1, 'All')")
        conn.execute(
            "INSERT INTO accounts (id, aggregated_account_id, name, balance, "
            "currency, balance_date) VALUES (1, 1, 'BNP', 100.0, 'EUR', '2025-01-31')"
        )
        yield conn


def _insert_op(
    conn: sqlite3.Connection,
    unique_id: int,
    op_date: str,
    amount: float,
    source_ref: str | None,
) -> None:
    conn.execute(
        "INSERT INTO operations (unique_id, account_id, description, category, "
        "date, amount, currency, source_ref) "
        "VALUES (?, 1, 'op', 'uncategorized', ?, ?, 'EUR', ?)",
        (unique_id, op_date, amount, source_ref),
    )


def _op_ids(conn: sqlite3.Connection) -> set[int]:
    return {
        row["unique_id"] for row in conn.execute("SELECT unique_id FROM operations")
    }


def test_cross_source_pair_is_collapsed(conn: sqlite3.Connection) -> None:
    """The API copy is deleted and the file op survives."""
    _insert_op(conn, 1, "2025-01-10", 3574.0, source_ref=None)  # file
    _insert_op(conn, 2, "2025-01-12", 3574.0, source_ref="ref-1")  # API dup

    v010.run(conn)

    assert _op_ids(conn) == {1}


def test_distinct_ops_are_kept(conn: sqlite3.Connection) -> None:
    """Ops outside the window or of a different amount are left alone."""
    _insert_op(conn, 1, "2025-01-10", 3574.0, source_ref=None)
    _insert_op(conn, 2, "2025-01-20", 3574.0, source_ref="ref-1")  # too far
    _insert_op(conn, 3, "2025-01-10", 50.0, source_ref="ref-2")  # other amount

    v010.run(conn)

    assert _op_ids(conn) == {1, 2, 3}


def test_matching_is_one_to_one(conn: sqlite3.Connection) -> None:
    """A single API op collapses one of two same-amount file ops."""
    _insert_op(conn, 1, "2025-01-10", -3.5, source_ref=None)
    _insert_op(conn, 2, "2025-01-10", -3.5, source_ref=None)
    _insert_op(conn, 3, "2025-01-10", -3.5, source_ref="ref-1")

    v010.run(conn)

    assert _op_ids(conn) == {1, 2}


def test_manual_link_repointed_to_survivor(conn: sqlite3.Connection) -> None:
    """A manual link on the deleted API op moves to the surviving file op."""
    _insert_op(conn, 1, "2025-01-10", 3574.0, source_ref=None)  # file, no link
    _insert_op(conn, 2, "2025-01-12", 3574.0, source_ref="ref-1")  # API, manual link
    conn.execute(
        "INSERT INTO operation_links (operation_unique_id, target_type, target_id, "
        "iteration_date, is_manual) VALUES (2, 'planned_operation', 7, '2025-01-12', 1)"
    )

    v010.run(conn)

    rows = conn.execute(
        "SELECT operation_unique_id, target_id FROM operation_links"
    ).fetchall()
    assert [(r["operation_unique_id"], r["target_id"]) for r in rows] == [(1, 7)]


def test_manual_link_dropped_when_survivor_already_linked(
    conn: sqlite3.Connection,
) -> None:
    """The survivor keeps its own link; the API op's link is discarded."""
    _insert_op(conn, 1, "2025-01-10", 3574.0, source_ref=None)  # file, manual link
    _insert_op(conn, 2, "2025-01-12", 3574.0, source_ref="ref-1")  # API, manual link
    conn.executemany(
        "INSERT INTO operation_links (operation_unique_id, target_type, target_id, "
        "iteration_date, is_manual) VALUES (?, 'budget', ?, '2025-01-12', 1)",
        [(1, 5), (2, 9)],
    )

    v010.run(conn)

    rows = conn.execute(
        "SELECT operation_unique_id, target_id FROM operation_links"
    ).fetchall()
    assert [(r["operation_unique_id"], r["target_id"]) for r in rows] == [(1, 5)]


def test_automatic_link_is_not_repointed(conn: sqlite3.Connection) -> None:
    """An automatic link on the API op is dropped, not moved (categorizer rebuilds)."""
    _insert_op(conn, 1, "2025-01-10", 3574.0, source_ref=None)
    _insert_op(conn, 2, "2025-01-12", 3574.0, source_ref="ref-1")
    conn.execute(
        "INSERT INTO operation_links (operation_unique_id, target_type, target_id, "
        "iteration_date, is_manual) VALUES (2, 'budget', 3, '2025-01-12', 0)"
    )

    v010.run(conn)

    assert conn.execute("SELECT COUNT(*) FROM operation_links").fetchone()[0] == 0


def test_manual_link_wins_over_survivor_automatic_link(
    conn: sqlite3.Connection,
) -> None:
    """A manual link on the API op overwrites an automatic link on the survivor."""
    _insert_op(conn, 1, "2025-01-10", 3574.0, source_ref=None)  # file, auto link
    _insert_op(conn, 2, "2025-01-12", 3574.0, source_ref="ref-1")  # API, manual link
    conn.executemany(
        "INSERT INTO operation_links (operation_unique_id, target_type, target_id, "
        "iteration_date, is_manual) VALUES (?, 'budget', ?, '2025-01-12', ?)",
        [(1, 5, 0), (2, 9, 1)],
    )

    v010.run(conn)

    rows = conn.execute(
        "SELECT operation_unique_id, target_id, is_manual FROM operation_links"
    ).fetchall()
    assert [
        (r["operation_unique_id"], r["target_id"], r["is_manual"]) for r in rows
    ] == [(1, 9, 1)]


def test_migration_is_idempotent(conn: sqlite3.Connection) -> None:
    """Running the purge twice leaves the same rows the second time."""
    _insert_op(conn, 1, "2025-01-10", 3574.0, source_ref=None)
    _insert_op(conn, 2, "2025-01-12", 3574.0, source_ref="ref-1")

    v010.run(conn)
    v010.run(conn)

    assert _op_ids(conn) == {1}


def test_multiple_pairs_matched_by_nearest_date(conn: sqlite3.Connection) -> None:
    """Each API op pairs with the nearest file op, so none is stranded."""
    _insert_op(conn, 1, "2025-01-10", -3.5, source_ref=None)
    _insert_op(conn, 2, "2025-01-11", -3.5, source_ref=None)
    _insert_op(conn, 3, "2025-01-11", -3.5, source_ref="ref-a")  # nearest to op 2
    _insert_op(conn, 4, "2025-01-07", -3.5, source_ref="ref-b")  # falls back to op 1

    v010.run(conn)

    assert _op_ids(conn) == {1, 2}
