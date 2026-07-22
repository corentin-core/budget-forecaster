"""v7 -> v8: add the source_ref dedup key and backfill existing rows.

The column stays nullable (SQLite cannot add a NOT NULL column without a
default); it is always populated by the app.
"""

import sqlite3
from datetime import date

from budget_forecaster.domain.operation.content_ref import content_ref


def run(conn: sqlite3.Connection) -> None:
    """Add source_ref and backfill each row with its content ref."""
    conn.execute("ALTER TABLE operations ADD COLUMN source_ref TEXT")
    rows = conn.execute(
        "SELECT unique_id, description, amount, date FROM operations"
    ).fetchall()
    for row in rows:
        ref = content_ref(
            row["description"], row["amount"], date.fromisoformat(row["date"])
        )
        conn.execute(
            "UPDATE operations SET source_ref = ? WHERE unique_id = ?",
            (ref, row["unique_id"]),
        )
    conn.commit()
