"""perform_sync runs the Swile sync and records one SyncRun tagged swile."""

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from budget_forecaster.core.types import SyncRunStatus, SyncSource
from budget_forecaster.domain.account.account import Account
from budget_forecaster.domain.account.account_registry import AccountRegistry
from budget_forecaster.infrastructure.bank_sources.swile_oauth.client import TokenBundle
from budget_forecaster.infrastructure.bank_sources.swile_oauth.sync_runner import (
    perform_sync,
)
from budget_forecaster.infrastructure.bank_sources.swile_oauth.token_store import (
    SwileTokenStore,
)
from budget_forecaster.infrastructure.persistence.sqlite_repository import (
    SqliteRepository,
)

ACCOUNT_NAME = "swile"

_OPERATIONS = {
    "items": [
        {
            "name": "Restaurant",
            "transactions": [
                {
                    "status": "CAPTURED",
                    "payment_method": "Wallets::MealVoucherWallet",
                    "date": "2025-01-15T13:50:50.073+01:00",
                    "amount": {"value": -2500, "currency": {"iso_3": "EUR"}},
                }
            ],
        }
    ]
}
_WALLETS = {"wallets": [{"type": "meal_voucher", "balance": {"value": 100.0}}]}


@pytest.fixture(name="repository")
def repository_fixture(tmp_path: Path) -> SqliteRepository:
    """A real repository seeded with the Swile account the sync targets."""
    repository = SqliteRepository(tmp_path / "test.db")
    repository.initialize()
    repository.set_aggregated_account_name("Test")
    repository.upsert_account(
        Account(
            name=ACCOUNT_NAME,
            balance=0.0,
            currency="EUR",
            balance_date=date(2025, 1, 1),
            operations=(),
        )
    )
    return repository


@pytest.fixture(name="token_store")
def token_store_fixture(tmp_path: Path) -> SwileTokenStore:
    """A token store under a temp path."""
    return SwileTokenStore(tmp_path / "token.json", "web-secret-key")


def _client() -> MagicMock:
    client = MagicMock()
    client.refresh.return_value = TokenBundle("acc", "rotated-rt", 1800)
    client.get_operations.return_value = _OPERATIONS
    client.get_wallets.return_value = _WALLETS
    return client


def test_success_records_ok_run(
    repository: SqliteRepository, token_store: SwileTokenStore
) -> None:
    """A successful sync records an OK run tagged swile with its stats."""
    token_store.save("stored-rt")

    run = perform_sync(repository, token_store, AccountRegistry(), client=_client())

    assert run.status is SyncRunStatus.OK
    assert run.source is SyncSource.SWILE
    assert run.new_count == 1
    assert run.balance == 100.0
    (recorded,) = repository.get_recent_sync_runs(1)
    assert recorded == run


def test_success_restores_rotated_token(
    repository: SqliteRepository, token_store: SwileTokenStore
) -> None:
    """The rotated refresh token is persisted after a sync."""
    token_store.save("stored-rt")

    perform_sync(repository, token_store, AccountRegistry(), client=_client())

    assert token_store.load() == "rotated-rt"


def test_missing_enrollment_records_failed_run(
    repository: SqliteRepository, token_store: SwileTokenStore
) -> None:
    """No stored token records a FAILED run, not propagated."""
    run = perform_sync(repository, token_store, AccountRegistry(), client=_client())

    assert run.status is SyncRunStatus.FAILED
    assert run.source is SyncSource.SWILE
    assert run.error is not None and "NotEnrolledError" in run.error
    (recorded,) = repository.get_recent_sync_runs(1)
    assert recorded.status is SyncRunStatus.FAILED


def test_client_error_records_failed_run(
    repository: SqliteRepository, token_store: SwileTokenStore
) -> None:
    """A refresh failure is recorded as a FAILED run."""
    token_store.save("stored-rt")
    client = _client()
    client.refresh.side_effect = RuntimeError("token revoked")

    run = perform_sync(repository, token_store, AccountRegistry(), client=client)

    assert run.status is SyncRunStatus.FAILED
    assert run.error == "RuntimeError: token revoked"
