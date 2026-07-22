"""Integration tests for SyncUseCase with real persistence.

The Enable Banking HTTP client is the only mocked boundary; everything from the
source mapping down to the SQLite merge runs for real.
"""

from datetime import date
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from dateutil.relativedelta import relativedelta

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.date_range import RecurringDay
from budget_forecaster.core.types import Category
from budget_forecaster.domain.account.account import Account
from budget_forecaster.domain.operation.planned_operation import PlannedOperation
from budget_forecaster.infrastructure.bank_sources.enable_banking.source import (
    EnableBankingSource,
)
from budget_forecaster.infrastructure.persistence.persistent_account import (
    PersistentAccount,
)
from budget_forecaster.infrastructure.persistence.sqlite_repository import (
    SqliteRepository,
)
from budget_forecaster.services.bank_sync_service import BankSyncService
from budget_forecaster.services.forecast.forecast_service import ForecastService
from budget_forecaster.services.operation.historic_operation_factory import (
    HistoricOperationFactory,
)
from budget_forecaster.services.operation.operation_link_service import (
    OperationLinkService,
)
from budget_forecaster.services.use_cases.matcher_cache import MatcherCache
from budget_forecaster.services.use_cases.sync_use_case import SyncUseCase

ACCOUNT_NAME = "bnp"


def _transaction(
    entry_reference: str,
    description: str,
    amount: str,
    indicator: str,
    booking_date: str,
) -> dict[str, Any]:
    """Build a booked Enable Banking transaction payload."""
    return {
        "status": "BOOK",
        "entry_reference": entry_reference,
        "booking_date": booking_date,
        "credit_debit_indicator": indicator,
        "transaction_amount": {"currency": "EUR", "amount": amount},
        "remittance_information": [description],
    }


API_TRANSACTIONS = (
    _transaction("ref-coffee", "COFFEE", "3.50", "DBIT", "2026-01-10"),
    _transaction("ref-salary", "SALARY", "2000.00", "CRDT", "2026-01-05"),
    _transaction("ref-rent", "RENT", "800.00", "DBIT", "2026-01-02"),
)
API_BALANCES = ({"balance_type": "CLBD", "balance_amount": {"amount": "1500.00"}},)


@pytest.fixture(name="repository")
def repository_fixture(tmp_path: Path) -> SqliteRepository:
    """Create a real SQLite repository seeded with an aggregated name."""
    repository = SqliteRepository(tmp_path / "test.db")
    repository.initialize()
    repository.set_aggregated_account_name("Test")
    return repository


def _seed_account(
    repository: SqliteRepository,
    operations: tuple = (),
    balance: float = 0.0,
    balance_date: date = date(2025, 1, 1),
) -> None:
    repository.upsert_account(
        Account(
            name=ACCOUNT_NAME,
            balance=balance,
            currency="EUR",
            balance_date=balance_date,
            operations=operations,
        )
    )


def _build_use_case(
    repository: SqliteRepository,
    persistent_account: PersistentAccount,
) -> tuple[SyncUseCase, MagicMock]:
    """Wire a SyncUseCase over a mocked Enable Banking client."""
    client = MagicMock()
    client.get_transactions.return_value = API_TRANSACTIONS
    client.get_balances.return_value = API_BALANCES
    source = EnableBankingSource(client, name=ACCOUNT_NAME)
    use_case = SyncUseCase(
        BankSyncService(persistent_account, source),
        persistent_account,
        OperationLinkService(repository),
        MatcherCache(ForecastService(persistent_account, repository)),
    )
    return use_case, client


class TestSyncIntegration:
    """Full sync, re-sync idempotency, and xls reconciliation."""

    def test_creates_operations_and_updates_balance(
        self, repository: SqliteRepository
    ) -> None:
        """A first sync imports the API operations and the CLBD balance."""
        _seed_account(repository)
        persistent_account = PersistentAccount(repository)
        use_case, _ = _build_use_case(repository, persistent_account)

        stats = use_case.sync("acc-1")

        assert stats.new_operations == 3
        assert stats.duplicates_skipped == 0
        account = PersistentAccount(repository).account
        assert len(account.operations) == 3
        assert account.balance == 1500.0
        descriptions = {op.description for op in account.operations}
        assert descriptions == {"COFFEE", "SALARY", "RENT"}

    def test_second_sync_adds_no_duplicates(self, repository: SqliteRepository) -> None:
        """Re-running the sync is idempotent: no new operations."""
        _seed_account(repository)
        persistent_account = PersistentAccount(repository)
        use_case, _ = _build_use_case(repository, persistent_account)

        use_case.sync("acc-1")
        second = use_case.sync("acc-1")

        assert second.new_operations == 0
        assert second.duplicates_skipped == 3
        assert len(PersistentAccount(repository).account.operations) == 3

    def test_overlapping_file_operation_is_reconciled(
        self, repository: SqliteRepository
    ) -> None:
        """An operation already imported from an xls file is not duplicated."""
        factory = HistoricOperationFactory(0)
        # xls op with no source_ref matching the COFFEE API transaction by content
        xls_coffee = factory.create_operation(
            description="COFFEE",
            amount=Amount(-3.5, "EUR"),
            category=Category.UNCATEGORIZED,
            operation_date=date(2026, 1, 10),
            source_ref=None,
        )
        _seed_account(
            repository,
            operations=(xls_coffee,),
            balance=1000.0,
            balance_date=date(2026, 1, 5),
        )
        persistent_account = PersistentAccount(repository)
        use_case, _ = _build_use_case(repository, persistent_account)

        stats = use_case.sync("acc-1")

        # COFFEE reconciled by content; only SALARY and RENT are new.
        assert stats.new_operations == 2
        assert stats.duplicates_skipped == 1
        account = PersistentAccount(repository).account
        assert len(account.operations) == 3
        coffee_ops = [op for op in account.operations if op.description == "COFFEE"]
        assert len(coffee_ops) == 1

    def test_sync_creates_heuristic_links(self, repository: SqliteRepository) -> None:
        """A synced operation matching a planned operation gets linked."""
        # RENT (-800 on 2026-01-02) matches this monthly planned operation.
        repository.upsert_planned_operation(
            PlannedOperation(
                record_id=None,
                description="Rent",
                amount=Amount(-800.0),
                category=Category.UNCATEGORIZED,
                date_range=RecurringDay(date(2026, 1, 1), relativedelta(months=1)),
            )
        )
        _seed_account(repository)
        persistent_account = PersistentAccount(repository)
        use_case, _ = _build_use_case(repository, persistent_account)

        use_case.sync("acc-1")

        links = repository.get_all_links()
        assert len(links) > 0
        assert all(not link.is_manual for link in links)
