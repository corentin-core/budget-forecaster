"""perform_sync runs the sync and records exactly one SyncRun either way."""

from datetime import date
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, Mock

import pytest

from budget_forecaster.core.types import SyncRunStatus
from budget_forecaster.domain.account.account import Account
from budget_forecaster.domain.account.account_registry import AccountRegistry
from budget_forecaster.infrastructure.bank_sources.enable_banking import sync_runner
from budget_forecaster.infrastructure.bank_sources.enable_banking.consent_service import (
    NoConsentError,
)
from budget_forecaster.infrastructure.bank_sources.enable_banking.sync_runner import (
    perform_sync,
)
from budget_forecaster.infrastructure.config import EnableBankingConfig
from budget_forecaster.infrastructure.persistence.sqlite_repository import (
    SqliteRepository,
)

ACCOUNT_NAME = "bnp"


def _transaction(reference: str, description: str, amount: str, indicator: str) -> dict:
    return {
        "status": "BOOK",
        "entry_reference": reference,
        "booking_date": "2026-01-10",
        "credit_debit_indicator": indicator,
        "transaction_amount": {"currency": "EUR", "amount": amount},
        "remittance_information": [description],
    }


API_TRANSACTIONS = (
    _transaction("ref-coffee", "COFFEE", "3.50", "DBIT"),
    _transaction("ref-salary", "SALARY", "2000.00", "CRDT"),
)
API_BALANCES = ({"balance_type": "CLBD", "balance_amount": {"amount": "1500.00"}},)

_ENABLE_BANKING = EnableBankingConfig(
    application_id="app",
    private_key_path=Path("key.pem"),
    redirect_url="https://example/callback",
    local_account_name=ACCOUNT_NAME,
)


@pytest.fixture(name="repository")
def repository_fixture(tmp_path: Path) -> SqliteRepository:
    """A real repository seeded with the account the sync targets."""
    repository = SqliteRepository(tmp_path / "test.db")
    repository.initialize()
    repository.set_aggregated_account_name("Test")
    repository.upsert_account(
        Account(
            name=ACCOUNT_NAME,
            balance=0.0,
            currency="EUR",
            balance_date=date(2026, 1, 1),
            operations=(),
        )
    )
    return repository


def _stub_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace the Enable Banking client with a canned-payload double."""
    client = MagicMock()
    client.get_transactions.return_value = API_TRANSACTIONS
    client.get_balances.return_value = API_BALANCES
    monkeypatch.setattr(sync_runner, "EnableBankingClient", lambda *a, **k: client)


def _consent(**kwargs: Any) -> Mock:
    consent = Mock()
    consent.resolve_account_uid.return_value = "acc-1"
    consent.configure_mock(**kwargs)
    return consent


class TestPerformSync:
    """One SyncRun recorded on success and on failure."""

    def test_success_records_ok_run(
        self, repository: SqliteRepository, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A successful sync returns and records an OK run with its stats."""
        _stub_client(monkeypatch)

        run = perform_sync(repository, _consent(), _ENABLE_BANKING, AccountRegistry())

        assert run.status is SyncRunStatus.OK
        assert run.new_count == 2
        assert run.duplicate_count == 0
        assert run.balance == 1500.0
        (recorded,) = repository.get_recent_sync_runs(1)
        assert recorded == run

    def test_failure_records_failed_run(self, repository: SqliteRepository) -> None:
        """A NoConsentError is recorded as a FAILED run, not propagated."""
        consent = _consent()
        consent.resolve_account_uid.side_effect = NoConsentError("Consent expired")

        run = perform_sync(repository, consent, _ENABLE_BANKING, AccountRegistry())

        assert run.status is SyncRunStatus.FAILED
        assert run.error == "NoConsentError: Consent expired"
        assert run.new_count is None
        (recorded,) = repository.get_recent_sync_runs(1)
        assert recorded.status is SyncRunStatus.FAILED
