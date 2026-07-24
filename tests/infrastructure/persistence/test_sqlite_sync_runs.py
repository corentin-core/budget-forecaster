"""Tests for the sync_runs table (v011 migration) and its repository methods."""

from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path

import pytest

from budget_forecaster.core.types import SyncRun, SyncRunStatus
from budget_forecaster.infrastructure.persistence.repository_interface import (
    RepositoryInterface,
)
from budget_forecaster.infrastructure.persistence.sqlite_repository import (
    SqliteRepository,
)


@pytest.fixture(name="repository")
def repository_fixture(tmp_path: Path) -> Iterator[RepositoryInterface]:
    """An initialized repository over a temporary database."""
    with SqliteRepository(tmp_path / "test.db") as repo:
        yield repo


def _run(ran_at: datetime, **kwargs: object) -> SyncRun:
    """Build a SyncRun with an OK default, overridable per test."""
    return SyncRun(ran_at=ran_at, status=SyncRunStatus.OK, **kwargs)


class TestSyncRunsTable:
    """add_sync_run / get_recent_sync_runs round-trip and ordering."""

    def test_empty_by_default(self, repository: RepositoryInterface) -> None:
        """No runs recorded yet yields an empty tuple."""
        assert repository.get_recent_sync_runs(10) == ()

    def test_records_and_reads_success_run(
        self, repository: RepositoryInterface
    ) -> None:
        """A success run round-trips with all its fields."""
        ran_at = datetime(2026, 7, 23, 6, 0, tzinfo=timezone.utc)
        repository.add_sync_run(
            _run(ran_at, new_count=3, duplicate_count=41, balance=4812.55)
        )
        (run,) = repository.get_recent_sync_runs(10)
        assert run == SyncRun(
            ran_at=ran_at,
            status=SyncRunStatus.OK,
            new_count=3,
            duplicate_count=41,
            balance=4812.55,
        )

    def test_records_failure_run(self, repository: RepositoryInterface) -> None:
        """A failure run keeps its error and leaves the count fields empty."""
        ran_at = datetime(2026, 7, 21, 6, 0, tzinfo=timezone.utc)
        repository.add_sync_run(
            SyncRun(ran_at, SyncRunStatus.FAILED, error="NoConsentError: expired")
        )
        (run,) = repository.get_recent_sync_runs(10)
        assert run.status is SyncRunStatus.FAILED
        assert run.error == "NoConsentError: expired"
        assert run.new_count is None
        assert run.balance is None

    def test_newest_first(self, repository: RepositoryInterface) -> None:
        """Runs come back newest first, by insertion order."""
        first = datetime(2026, 7, 21, 6, 0, tzinfo=timezone.utc)
        second = datetime(2026, 7, 22, 6, 0, tzinfo=timezone.utc)
        repository.add_sync_run(_run(first))
        repository.add_sync_run(_run(second))
        runs = repository.get_recent_sync_runs(10)
        assert [r.ran_at for r in runs] == [second, first]

    def test_limit_caps_results(self, repository: RepositoryInterface) -> None:
        """limit bounds how many runs are returned."""
        for day in (20, 21, 22):
            repository.add_sync_run(
                _run(datetime(2026, 7, day, 6, 0, tzinfo=timezone.utc))
            )
        assert len(repository.get_recent_sync_runs(2)) == 2
