"""Read-only preview of a backup before restoring it.

Reads lightweight metrics straight from the backup file on a read-only
connection, without touching the live connection or running migrations, so a
preview never affects other viewers and works on older-schema backups.
"""

import sqlite3
from datetime import date
from pathlib import Path
from typing import Any, NamedTuple

from budget_forecaster.core.amount import Amount
from budget_forecaster.exceptions import BackupError


class BackupMetrics(NamedTuple):
    """Summary metrics of a single database file."""

    total_balance: Amount
    operation_count: int
    latest_operation_date: date | None
    schema_version: int


class BackupPreview(NamedTuple):
    """Current database and a candidate backup, side by side."""

    current: BackupMetrics
    backup: BackupMetrics


def preview_backup(database_path: Path, backup_path: Path) -> BackupPreview:
    """Compute metrics for the live database and a backup for comparison.

    Raises:
        BackupError: If either file cannot be read as a database.
    """
    return BackupPreview(
        current=_read_metrics(database_path),
        backup=_read_metrics(backup_path),
    )


def _read_metrics(path: Path) -> BackupMetrics:
    """Read summary metrics from a database file on a read-only connection."""
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.OperationalError as e:
        raise BackupError(f"Cannot open database: {path.name}") from e
    conn.row_factory = sqlite3.Row
    try:
        currency = _scalar(conn, "SELECT currency FROM accounts LIMIT 1") or "EUR"
        balance = _scalar(conn, "SELECT SUM(balance) FROM accounts") or 0.0
        count = _scalar(conn, "SELECT COUNT(*) FROM operations") or 0
        latest = _scalar(conn, "SELECT MAX(date) FROM operations")
        version = _schema_version(conn)
    except sqlite3.DatabaseError as e:
        raise BackupError(f"Cannot read database: {path.name}") from e
    finally:
        conn.close()

    return BackupMetrics(
        total_balance=Amount(float(balance), currency),
        operation_count=int(count),
        latest_operation_date=date.fromisoformat(latest) if latest else None,
        schema_version=version,
    )


def _scalar(conn: sqlite3.Connection, query: str) -> Any:
    """Run a query and return the first column of the first row, or None."""
    row = conn.execute(query).fetchone()
    return row[0] if row else None


def _schema_version(conn: sqlite3.Connection) -> int:
    """Read the schema version, or 0 if the table is absent."""
    try:
        return int(_scalar(conn, "SELECT version FROM schema_version LIMIT 1") or 0)
    except sqlite3.OperationalError:
        return 0
