"""The all-sources orchestrator: attempt each connected source, skip the rest."""

from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from budget_forecaster.core.types import SyncRun, SyncRunStatus, SyncSource
from budget_forecaster.infrastructure.bank_sources import sync_all
from budget_forecaster.infrastructure.bank_sources.sync_all import sync_all_sources

_RAN_AT = datetime(2026, 7, 28, 6, 0, tzinfo=timezone.utc)


def _run(source: SyncSource, status: SyncRunStatus = SyncRunStatus.OK) -> SyncRun:
    return SyncRun(_RAN_AT, status, source=source)


@pytest.fixture
def runners(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[str]]:
    """Replace both source runners with call-recording doubles."""
    calls: dict[str, list[str]] = {"bank": [], "swile": []}

    def fake_bank(*_args: object, **_kwargs: object) -> SyncRun:
        calls["bank"].append("run")
        return _run(SyncSource.ENABLE_BANKING)

    def fake_swile(*_args: object, **_kwargs: object) -> SyncRun:
        calls["swile"].append("run")
        return _run(SyncSource.SWILE)

    monkeypatch.setattr(sync_all, "perform_enable_banking_sync", fake_bank)
    monkeypatch.setattr(sync_all, "perform_swile_sync", fake_swile)
    return calls


def _config(*, enable_banking: object | None) -> Mock:
    config = Mock()
    config.enable_banking = enable_banking
    return config


def _consent(*, connected: bool) -> Mock:
    service = Mock()
    service.current_consent.return_value = object() if connected else None
    return service


def _token_store(*, token: str | None) -> Mock:
    store = Mock()
    store.load.return_value = token
    return store


def test_both_connected_syncs_both_in_order(runners: dict[str, list[str]]) -> None:
    """Both connected: Enable Banking first, then Swile."""
    runs = sync_all_sources(
        Mock(),
        _config(enable_banking=object()),
        _consent(connected=True),
        _token_store(token="rt"),
    )
    assert [run.source for run in runs] == [
        SyncSource.ENABLE_BANKING,
        SyncSource.SWILE,
    ]
    assert runners == {"bank": ["run"], "swile": ["run"]}


def test_only_swile_connected(runners: dict[str, list[str]]) -> None:
    """Enable Banking configured but unconsented: only Swile runs."""
    runs = sync_all_sources(
        Mock(),
        _config(enable_banking=object()),
        _consent(connected=False),
        _token_store(token="rt"),
    )
    assert [run.source for run in runs] == [SyncSource.SWILE]
    assert runners == {"bank": [], "swile": ["run"]}


def test_nothing_connected_records_no_run(runners: dict[str, list[str]]) -> None:
    """No consent and no token: nothing runs, nothing recorded."""
    runs = sync_all_sources(
        Mock(),
        _config(enable_banking=object()),
        _consent(connected=False),
        _token_store(token=None),
    )
    assert not runs
    assert runners == {"bank": [], "swile": []}


def test_no_consent_service_skips_enable_banking(runners: dict[str, list[str]]) -> None:
    """A missing consent service (Enable Banking not configured) syncs only Swile."""
    runs = sync_all_sources(
        Mock(),
        _config(enable_banking=object()),
        None,
        _token_store(token="rt"),
    )
    assert [run.source for run in runs] == [SyncSource.SWILE]
    assert runners == {"bank": [], "swile": ["run"]}


def test_no_token_store_skips_swile(runners: dict[str, list[str]]) -> None:
    """A missing token store (no web secret key) syncs only Enable Banking."""
    runs = sync_all_sources(
        Mock(),
        _config(enable_banking=object()),
        _consent(connected=True),
        None,
    )
    assert [run.source for run in runs] == [SyncSource.ENABLE_BANKING]
    assert runners == {"bank": ["run"], "swile": []}


def test_failing_source_does_not_stop_the_other(
    runners: dict[str, list[str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A source returning a FAILED run is still collected; the other still runs."""

    def failing_bank(*_args: object, **_kwargs: object) -> SyncRun:
        runners["bank"].append("run")
        return _run(SyncSource.ENABLE_BANKING, SyncRunStatus.FAILED)

    monkeypatch.setattr(sync_all, "perform_enable_banking_sync", failing_bank)

    runs = sync_all_sources(
        Mock(),
        _config(enable_banking=object()),
        _consent(connected=True),
        _token_store(token="rt"),
    )
    assert [(run.source, run.status) for run in runs] == [
        (SyncSource.ENABLE_BANKING, SyncRunStatus.FAILED),
        (SyncSource.SWILE, SyncRunStatus.OK),
    ]
