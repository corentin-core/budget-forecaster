"""SQLite schema migrations, one file per version.

A file named vNNN_<slug>.sql is a schema-only script; vNNN_<slug>.py exposes
run(conn) for a data migration. The registry is built from the directory
contents, so adding a migration means dropping in a new file.
"""

import importlib
import re
import sqlite3
from pathlib import Path
from typing import Callable

_MIGRATIONS_DIR = Path(__file__).parent
_VERSION_PREFIX = re.compile(r"^v(\d+)_")

Migration = str | Callable[[sqlite3.Connection], None]


def _load() -> dict[int, Migration]:
    migrations: dict[int, Migration] = {}
    for path in sorted(_MIGRATIONS_DIR.glob("v[0-9]*")):
        match = _VERSION_PREFIX.match(path.name)
        if match is None or path.suffix not in (".sql", ".py"):
            continue
        if (version := int(match.group(1))) in migrations:
            raise ValueError(f"Duplicate migration for version {version}")
        if path.suffix == ".sql":
            migrations[version] = path.read_text(encoding="utf-8")
        else:
            module = importlib.import_module(f"{__name__}.{path.stem}")
            migrations[version] = module.run
    if sorted(migrations) != list(range(1, len(migrations) + 1)):
        raise ValueError(
            f"Migration versions must form a contiguous chain from 1: "
            f"{sorted(migrations)}"
        )
    return migrations


MIGRATIONS: dict[int, Migration] = _load()
CURRENT_SCHEMA_VERSION = max(MIGRATIONS)
