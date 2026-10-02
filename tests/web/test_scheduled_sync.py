"""The web app's own daily sync: when it is due, and the loop that runs it."""

import asyncio
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock

import pytest
from starlette.datastructures import State

from budget_forecaster.core.types import SyncRun, SyncRunStatus, SyncSource
from budget_forecaster.infrastructure.persistence.sqlite_repository import (
    SqliteRepository,
)
from budget_forecaster.web import scheduled_sync

_NOW = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)
_RECENT = _NOW - timedelta(hours=2)
_DAY_OLD = _NOW - timedelta(days=1)


@pytest.fixture(name="repository")
def repository_fixture(tmp_path: Path) -> Iterator[SqliteRepository]:
    """A real repository, so run timestamps round-trip through storage."""
    with SqliteRepository(tmp_path / "test.db") as repo:
        yield repo


def _state(
    repository: SqliteRepository, *, bank: bool = False, swile: bool = False
) -> State:
    """A state with the bank and Swile connected or not."""
    consent_service = Mock()
    consent_service.current_consent.return_value = Mock() if bank else None
    token_store = Mock()
    token_store.load.return_value = "rt" if swile else None
    return State(
        {
            "repository": repository,
            "config": Mock(enable_banking=Mock()),
            "consent_service": consent_service,
            "swile_token_store": token_store,
        }
    )


def _record(
    repository: SqliteRepository,
    source: SyncSource,
    ran_at: datetime,
    status: SyncRunStatus = SyncRunStatus.OK,
) -> None:
    repository.add_sync_run(SyncRun(ran_at, status, source=source))


class TestIsSyncDue:
    """Due when a connected source's latest run is missing or a day old."""

    def test_not_due_when_nothing_is_connected(
        self, repository: SqliteRepository
    ) -> None:
        """No connected source: nothing to sync, however old the runs."""
        assert scheduled_sync.is_sync_due(_state(repository), _NOW) is False

    def test_due_when_a_connected_source_never_synced(
        self, repository: SqliteRepository
    ) -> None:
        """A connected source without any run is synced right away."""
        assert scheduled_sync.is_sync_due(_state(repository, bank=True), _NOW) is True

    @pytest.mark.parametrize(
        "ran_at,status,expected",
        [
            (_RECENT, SyncRunStatus.OK, False),
            (_RECENT, SyncRunStatus.FAILED, False),
            (_DAY_OLD, SyncRunStatus.OK, True),
        ],
        ids=["recent-ok", "recent-failure", "a-day-old"],
    )
    def test_follows_the_latest_run(
        self,
        repository: SqliteRepository,
        ran_at: datetime,
        status: SyncRunStatus,
        expected: bool,
    ) -> None:
        """A failed run counts as much as a successful one."""
        _record(repository, SyncSource.ENABLE_BANKING, ran_at, status)
        state = _state(repository, bank=True)
        assert scheduled_sync.is_sync_due(state, _NOW) is expected

    def test_a_recent_swile_run_does_not_postpone_the_bank(
        self, repository: SqliteRepository
    ) -> None:
        """Enrolling Swile records a run; the bank stays due on its own schedule."""
        _record(repository, SyncSource.ENABLE_BANKING, _DAY_OLD)
        _record(repository, SyncSource.SWILE, _RECENT)
        state = _state(repository, bank=True, swile=True)
        assert scheduled_sync.is_sync_due(state, _NOW) is True


def test_sync_if_due_never_raises(
    repository: SqliteRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failing sync is logged, so the app still boots and the loop goes on."""

    def failing_sync(_state: State) -> tuple[SyncRun, ...]:
        raise RuntimeError("boom")

    # The app's logging setup stops propagation, so caplog would not see it.
    logger = Mock()
    monkeypatch.setattr(scheduled_sync, "logger", logger)
    monkeypatch.setattr(scheduled_sync, "sync_and_refresh", failing_sync)
    scheduled_sync.sync_if_due(_state(repository, bank=True))
    logger.exception.assert_called_once_with("Scheduled sync failed")


def test_daily_loop_checks_repeatedly(monkeypatch: pytest.MonkeyPatch) -> None:
    """The loop keeps checking until cancelled."""
    checks: list[str] = []
    monkeypatch.setattr(scheduled_sync, "_CHECK_INTERVAL_SECONDS", 0)
    monkeypatch.setattr(
        scheduled_sync, "sync_if_due", lambda _state: checks.append("check")
    )

    async def run_three_checks() -> None:
        task = asyncio.create_task(scheduled_sync.sync_daily(State()))
        while len(checks) < 3:
            await asyncio.sleep(0)
        task.cancel()

    asyncio.run(run_three_checks())
    assert checks == ["check", "check", "check"]
