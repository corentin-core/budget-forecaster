"""SQLite schema migrations, one file per version.

A file named vNNN_<slug>.sql is a schema-only script; vNNN_<slug>.py exposes
run(conn) for a data migration. The registry is built from the directory
contents, so adding a migration means dropping in a new file.
"""

import importlib
import re
import sqlite3
from pathlib import Path
from typing import Callable, NamedTuple


class Migration(NamedTuple):
    """A schema migration: the version it upgrades from and how to apply it."""

    from_version: int
    run: str | Callable[[sqlite3.Connection], None]


_MIGRATIONS_DIR = Path(__file__).parent
_VERSION_PREFIX = re.compile(r"^v(\d+)_")


def _load() -> dict[int, Migration]:
    migrations: dict[int, Migration] = {}
    for path in sorted(_MIGRATIONS_DIR.glob("v[0-9]*")):
        match = _VERSION_PREFIX.match(path.name)
        if match is None or path.suffix not in (".sql", ".py"):
            continue
        version = int(match.group(1))
        if path.suffix == ".sql":
            run: str | Callable[[sqlite3.Connection], None] = path.read_text(
                encoding="utf-8"
            )
        else:
            module = importlib.import_module(f"{__name__}.{path.stem}")
            run = module.run
        migrations[version] = Migration(from_version=version - 1, run=run)
    return migrations


MIGRATIONS: dict[int, Migration] = _load()
CURRENT_SCHEMA_VERSION = max(MIGRATIONS)
