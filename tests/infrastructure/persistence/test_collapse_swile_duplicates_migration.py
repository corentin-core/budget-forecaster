"""Tests for the v14 migration collapsing Swile duplicate operations."""

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from budget_forecaster.infrastructure.persistence.migrations import (
    v014_collapse_swile_duplicates as v014,
)
from budget_forecaster.infrastructure.persistence.sqlite_repository import (
    SqliteRepository,
)

_V4_REF = "3f2a9c1e-5b7d-4ade-b7ec-2218df32ede5"
_V7_REF = "019f6a2b-8c3d-7ade-b7ec-2218df32ede5"


@pytest.fixture(name="conn")
def conn_fixture(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    """An initialized database seeded with a Swile and a BNP account."""
    with SqliteRepository(tmp_path / "test.db") as repo:
        conn = repo._get_connection()  # pylint: disable=protected-access
        conn.execute("INSERT INTO aggregated_accounts (id, name) VALUES (1, 'All')")
        conn.executemany(
            "INSERT INTO accounts (id, aggregated_account_id, name, balance, "
            "currency, balance_date) VALUES (?, 1, ?, 100.0, 'EUR', '2026-09-30')",
            [(1, "Swile"), (2, "BNP")],
        )
        yield conn


def _insert_op(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    conn: sqlite3.Connection,
    unique_id: int,
    source_ref: str | None,
    op_date: str = "2026-08-03",
    amount: float = -14.2,
    category: str = "uncategorized",
    account_id: int = 1,
    description: str = "PICARD",
) -> None:
    conn.execute(
        "INSERT INTO operations (unique_id, account_id, description, category, "
        "date, amount, currency, source_ref) "
        "VALUES (?, ?, ?, ?, ?, ?, 'EUR', ?)",
        (unique_id, account_id, description, category, op_date, amount, source_ref),
    )


def _ops(conn: sqlite3.Connection) -> list[tuple[int, str, str]]:
    return [
        (row["unique_id"], row["category"], row["source_ref"])
        for row in conn.execute(
            "SELECT unique_id, category, source_ref FROM operations "
            "ORDER BY unique_id"
        )
    ]


def test_old_op_kept_with_its_category_and_the_new_id(
    conn: sqlite3.Connection,
) -> None:
    """The v4 op survives, keeps its category and adopts the v7 id."""
    _insert_op(conn, 1, _V4_REF, category="groceries")
    _insert_op(conn, 2, _V7_REF)

    v014.run(conn)

    assert _ops(conn) == [(1, "groceries", _V7_REF)]


def test_old_op_adopts_the_copy_category_when_uncategorized(
    conn: sqlite3.Connection,
) -> None:
    """A category set on the copy only is not lost."""
    _insert_op(conn, 1, _V4_REF)
    _insert_op(conn, 2, _V7_REF, category="groceries")

    v014.run(conn)

    assert _ops(conn) == [(1, "groceries", _V7_REF)]


def test_link_on_the_copy_moves_to_the_kept_op(conn: sqlite3.Connection) -> None:
    """A manual link set on the copy is repointed, not deleted."""
    _insert_op(conn, 1, _V4_REF)
    _insert_op(conn, 2, _V7_REF)
    conn.execute(
        "INSERT INTO operation_links (operation_unique_id, target_type, target_id, "
        "iteration_date, is_manual) VALUES (2, 'budget', 4, '2026-08-01', 1)"
    )

    v014.run(conn)

    rows = conn.execute(
        "SELECT operation_unique_id, target_id FROM operation_links"
    ).fetchall()
    assert [(r["operation_unique_id"], r["target_id"]) for r in rows] == [(1, 4)]


def _links(conn: sqlite3.Connection) -> list[tuple[int, int, int]]:
    return [
        (r["operation_unique_id"], r["target_id"], r["is_manual"])
        for r in conn.execute(
            "SELECT operation_unique_id, target_id, is_manual FROM operation_links"
        )
    ]


def _link(conn: sqlite3.Connection, op_id: int, target_id: int, manual: int) -> None:
    conn.execute(
        "INSERT INTO operation_links (operation_unique_id, target_type, target_id, "
        "iteration_date, is_manual) VALUES (?, 'budget', ?, '2026-08-01', ?)",
        (op_id, target_id, manual),
    )


@pytest.mark.parametrize(
    ("kept_manual", "copy_manual"),
    [(0, 0), (1, 0), (1, 1)],
    ids=["both automatic", "kept manual", "both manual"],
)
def test_kept_op_link_wins(
    conn: sqlite3.Connection, kept_manual: int, copy_manual: int
) -> None:
    """The established op's link is kept; the copy's is dropped."""
    _insert_op(conn, 1, _V4_REF)
    _insert_op(conn, 2, _V7_REF)
    _link(conn, 1, 4, kept_manual)
    _link(conn, 2, 9, copy_manual)

    v014.run(conn)

    assert _links(conn) == [(1, 4, kept_manual)]


def test_manual_link_on_copy_beats_automatic_one(conn: sqlite3.Connection) -> None:
    """A link the user set on the copy outranks a heuristic one."""
    _insert_op(conn, 1, _V4_REF)
    _insert_op(conn, 2, _V7_REF)
    _link(conn, 1, 4, 0)
    _link(conn, 2, 9, 1)

    v014.run(conn)

    assert _links(conn) == [(1, 9, 1)]


@pytest.mark.parametrize(
    "copy",
    [
        {"op_date": "2026-08-04"},
        {"amount": -14.3},
        {"account_id": 2},
        {"source_ref": "019f6a2b-8c3d-7bcd-a111-000000000001"},
    ],
    ids=["other date", "other amount", "other account", "other tail"],
)
def test_distinct_transactions_are_kept(conn: sqlite3.Connection, copy: dict) -> None:
    """Only a pair matching on account, tail, date and amount collapses."""
    _insert_op(conn, 1, _V4_REF)
    _insert_op(conn, 2, **{"source_ref": _V7_REF, **copy})

    v014.run(conn)

    assert [op[0] for op in _ops(conn)] == [1, 2]


def test_non_uuid_refs_are_left_alone(conn: sqlite3.Connection) -> None:
    """Enable Banking refs are never paired."""
    _insert_op(conn, 1, "2026080300001-ab12", account_id=2)
    _insert_op(conn, 2, "2026080300002-ab12", account_id=2)

    v014.run(conn)

    assert [op[0] for op in _ops(conn)] == [1, 2]


def test_migration_is_idempotent(conn: sqlite3.Connection) -> None:
    """A second run finds nothing left to collapse."""
    _insert_op(conn, 1, _V4_REF)
    _insert_op(conn, 2, _V7_REF)

    v014.run(conn)
    v014.run(conn)

    assert _ops(conn) == [(1, "uncategorized", _V7_REF)]


_FR = "Crédit titres-resto"
_EN = "Meal vouchers credit"


def _insert_credit(
    conn: sqlite3.Connection, unique_id: int, description: str, category: str
) -> None:
    _insert_op(
        conn,
        unique_id,
        None,
        op_date="2025-03-28",
        amount=153.0,
        category=category,
        description=description,
    )


def test_english_credit_copy_is_dropped(conn: sqlite3.Connection) -> None:
    """The French op survives and inherits the English op's category."""
    _insert_credit(conn, 1, _FR, "uncategorized")
    _insert_credit(conn, 2, _EN, "salary")

    v014.run(conn)

    assert _ops(conn) == [(1, "salary", None)]


def test_credit_pairing_is_one_to_one(conn: sqlite3.Connection) -> None:
    """Two French credits on the same day keep one of them unpaired."""
    _insert_credit(conn, 1, _FR, "salary")
    _insert_credit(conn, 2, _FR, "salary")
    _insert_credit(conn, 3, _EN, "salary")

    v014.run(conn)

    assert [op[0] for op in _ops(conn)] == [1, 2]


def test_two_french_credits_are_kept(conn: sqlite3.Connection) -> None:
    """Only a French/English label pair is a duplicate."""
    _insert_credit(conn, 1, _FR, "salary")
    _insert_credit(conn, 2, _FR, "salary")

    v014.run(conn)

    assert [op[0] for op in _ops(conn)] == [1, 2]
