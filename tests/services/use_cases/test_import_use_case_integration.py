"""Integration tests for ImportUseCase with real dependencies."""

from datetime import date
from pathlib import Path

import pytest
from dateutil.relativedelta import relativedelta

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.date_range import RecurringDay
from budget_forecaster.core.types import Category
from budget_forecaster.domain.account.account import Account
from budget_forecaster.domain.operation.planned_operation import PlannedOperation
from budget_forecaster.infrastructure.persistence.persistent_account import (
    PersistentAccount,
)
from budget_forecaster.infrastructure.persistence.sqlite_repository import (
    SqliteRepository,
)
from budget_forecaster.services.forecast.forecast_service import ForecastService
from budget_forecaster.services.import_service import ImportService
from budget_forecaster.services.operation.operation_link_service import (
    OperationLinkService,
)
from budget_forecaster.services.use_cases.import_use_case import ImportUseCase
from budget_forecaster.services.use_cases.matcher_cache import MatcherCache

BNP_FIXTURE = Path(__file__).parents[2] / "fixtures" / "bnp" / "export.xls"


@pytest.fixture(name="repository")
def repository_fixture(tmp_path: Path) -> SqliteRepository:
    """Create a real SQLite repository in a temp directory."""
    repo = SqliteRepository(tmp_path / "test.db")
    repo.initialize()
    return repo


@pytest.fixture(name="persistent_account")
def persistent_account_fixture(repository: SqliteRepository) -> PersistentAccount:
    """Create a PersistentAccount with an initial empty account."""
    repository.set_aggregated_account_name("Test")
    # Seed an empty BNP account so PersistentAccount can load
    repository.upsert_account(
        Account(
            name="bnp",
            balance=0.0,
            currency="EUR",
            balance_date=date(2025, 1, 1),
            operations=(),
        )
    )
    return PersistentAccount(repository)


@pytest.fixture(name="use_case")
def use_case_fixture(
    persistent_account: PersistentAccount,
    repository: SqliteRepository,
    tmp_path: Path,
) -> ImportUseCase:
    """Create an ImportUseCase with real dependencies."""
    import_service = ImportService(persistent_account, tmp_path / "inbox")
    forecast_service = ForecastService(persistent_account.account, repository)
    operation_link_service = OperationLinkService(repository)
    matcher_cache = MatcherCache(forecast_service)
    return ImportUseCase(
        import_service,
        persistent_account,
        operation_link_service,
        matcher_cache,
    )


class TestImportFileIntegration:
    """Integration: import a BNP export file and verify the full chain."""

    def test_import_creates_operations(
        self,
        use_case: ImportUseCase,
        persistent_account: PersistentAccount,
    ) -> None:
        """Importing a BNP file creates operations in the account."""
        result = use_case.import_file(BNP_FIXTURE)

        assert result.success
        assert result.stats is not None
        assert result.stats.new_operations == 3

        # Verify operations are available after reload
        operations = persistent_account.account.operations
        assert len(operations) == 3

    def test_import_creates_heuristic_links(
        self,
        use_case: ImportUseCase,
        persistent_account: PersistentAccount,
        repository: SqliteRepository,
    ) -> None:
        """Importing with existing planned operations creates heuristic links."""
        # BNP adapter maps unknown categories to UNCATEGORIZED, so the planned
        # operation must also be UNCATEGORIZED with matching amount/date to trigger
        # heuristic linking
        planned_op = PlannedOperation(
            record_id=None,
            description="Loyer",
            amount=Amount(-800.0),
            category=Category.UNCATEGORIZED,
            date_range=RecurringDay(date(2025, 1, 1), relativedelta(months=1)),
        )
        repository.upsert_planned_operation(planned_op)

        result = use_case.import_file(BNP_FIXTURE)

        assert result.success

        # At least one heuristic link should have been created
        all_links = repository.get_all_links()
        assert len(all_links) > 0
        assert all(not link.is_manual for link in all_links)
