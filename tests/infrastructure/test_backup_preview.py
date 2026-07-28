"""Tests for the read-only backup preview."""

import sqlite3
from datetime import date
from pathlib import Path

import pytest

from budget_forecaster.core.amount import Amount
from budget_forecaster.exceptions import BackupError
from budget_forecaster.infrastructure.backup_preview import (
    BackupMetrics,
    preview_backup,
)


def _make_db(
    path: Path,
    *,
    balance: float,
    op_dates: list[str],
    version: int | None,
    currency: str = "EUR",
) -> None:
    """Write a minimal database with the tables the preview reads."""
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE accounts (balance REAL, currency TEXT)")
    conn.execute("CREATE TABLE operations (date TEXT)")
    conn.execute(
        "INSERT INTO accounts (balance, currency) VALUES (?, ?)", (balance, currency)
    )
    conn.executemany(
        "INSERT INTO operations (date) VALUES (?)", [(d,) for d in op_dates]
    )
    if version is not None:
        conn.execute("CREATE TABLE schema_version (version INTEGER)")
        conn.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))
    conn.commit()
    conn.close()


class TestPreviewBackup:
    """Tests for computing preview metrics."""

    def test_reads_metrics_for_both_files(self, tmp_path: Path) -> None:
        """Current and backup metrics are read side by side."""
        current = tmp_path / "budget.db"
        backup = tmp_path / "budget_2025-01-17_100000.db"
        _make_db(
            current, balance=1240.5, op_dates=["2026-07-27", "2026-07-28"], version=7
        )
        _make_db(backup, balance=1190.0, op_dates=["2026-07-27"], version=6)

        preview = preview_backup(current, backup)

        assert preview.current == BackupMetrics(
            total_balance=Amount(1240.5, "EUR"),
            operation_count=2,
            latest_operation_date=date(2026, 7, 28),
            schema_version=7,
        )
        assert preview.backup == BackupMetrics(
            total_balance=Amount(1190.0, "EUR"),
            operation_count=1,
            latest_operation_date=date(2026, 7, 27),
            schema_version=6,
        )

    def test_empty_database(self, tmp_path: Path) -> None:
        """No accounts or operations yields a zero balance and no latest date."""
        db = tmp_path / "budget.db"
        _make_db(db, balance=0.0, op_dates=[], version=7)
        # Remove the seeded account row to exercise the empty case.
        conn = sqlite3.connect(db)
        conn.execute("DELETE FROM accounts")
        conn.commit()
        conn.close()

        metrics = preview_backup(db, db).backup

        assert metrics == BackupMetrics(
            total_balance=Amount(0.0, "EUR"),
            operation_count=0,
            latest_operation_date=None,
            schema_version=7,
        )

    def test_missing_schema_version_table(self, tmp_path: Path) -> None:
        """A backup without a schema_version table reports version 0."""
        db = tmp_path / "budget.db"
        _make_db(db, balance=10.0, op_dates=["2026-01-01"], version=None)

        assert preview_backup(db, db).backup.schema_version == 0

    def test_does_not_mutate_the_backup(self, tmp_path: Path) -> None:
        """Preview opens read-only and leaves the file byte-identical."""
        db = tmp_path / "budget.db"
        _make_db(db, balance=10.0, op_dates=["2026-01-01"], version=7)
        before = db.read_bytes()

        preview_backup(db, db)

        assert db.read_bytes() == before

    def test_corrupt_file_raises(self, tmp_path: Path) -> None:
        """A file that is not a database surfaces a clean error."""
        current = tmp_path / "budget.db"
        _make_db(current, balance=10.0, op_dates=[], version=7)
        corrupt = tmp_path / "budget_bad.db"
        corrupt.write_text("not a database")

        with pytest.raises(BackupError):
            preview_backup(current, corrupt)

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        """A backup deleted before preview surfaces a clean error."""
        current = tmp_path / "budget.db"
        _make_db(current, balance=10.0, op_dates=[], version=7)

        with pytest.raises(BackupError):
            preview_backup(current, tmp_path / "gone.db")
