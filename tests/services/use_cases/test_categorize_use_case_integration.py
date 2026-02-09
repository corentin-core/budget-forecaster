"""Integration tests for CategorizeUseCase with real dependencies."""

from datetime import date
from pathlib import Path

import pytest
from dateutil.relativedelta import relativedelta

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.date_range import RecurringDay
from budget_forecaster.core.types import Category, LinkType
from budget_forecaster.domain.account.account import Account
from budget_forecaster.domain.operation.historic_operation import HistoricOperation
from budget_forecaster.domain.operation.operation_link import OperationLink
from budget_forecaster.domain.operation.planned_operation import PlannedOperation
from budget_forecaster.infrastructure.persistence.persistent_account import (
    PersistentAccount,
)
from budget_forecaster.infrastructure.persistence.sqlite_repository import (
    SqliteRepository,
)
from budget_forecaster.services.forecast.forecast_service import ForecastService
from budget_forecaster.services.operation.operation_link_service import (
    OperationLinkService,
)
from budget_forecaster.services.operation.operation_service import OperationService
from budget_forecaster.services.use_cases.categorize_use_case import CategorizeUseCase
from budget_forecaster.services.use_cases.matcher_cache import MatcherCache


@pytest.fixture(name="repository")
def repository_fixture(tmp_path: Path) -> SqliteRepository:
    """Create a real SQLite repository in a temp directory."""
    repo = SqliteRepository(tmp_path / "test.db")
    repo.initialize()
    return repo


@pytest.fixture(name="persistent_account")
def persistent_account_fixture(repository: SqliteRepository) -> PersistentAccount:
    """Create a PersistentAccount seeded with operations."""
    repository.set_aggregated_account_name("Test")
    repository.upsert_account(
        Account(
            name="BNP",
            balance=1000.0,
            currency="EUR",
            balance_date=date(2025, 1, 15),
            operations=(
                HistoricOperation(
                    unique_id=1,
                    description="LOYER JANVIER",
                    amount=Amount(-800.0),
                    category=Category.UNCATEGORIZED,
                    operation_date=date(2025, 1, 2),
                ),
                HistoricOperation(
                    unique_id=2,
                    description="CARREFOUR MARKET",
                    amount=Amount(-65.30),
                    category=Category.UNCATEGORIZED,
                    operation_date=date(2025, 1, 5),
                ),
            ),
        )
    )
    return PersistentAccount(repository)


@pytest.fixture(name="use_case")
def use_case_fixture(
    persistent_account: PersistentAccount,
    repository: SqliteRepository,
) -> CategorizeUseCase:
    """Create a CategorizeUseCase with real dependencies."""
    forecast_service = ForecastService(persistent_account.account, repository)
    return CategorizeUseCase(
        OperationService(persistent_account),
        OperationLinkService(repository),
        MatcherCache(forecast_service),
    )


class TestCategorizeOperationsIntegration:
    """Integration: categorize operations and verify outcomes."""

    def test_category_updated_and_link_created(
        self,
        use_case: CategorizeUseCase,
        repository: SqliteRepository,
    ) -> None:
        """Categorizing an operation updates category and creates heuristic link."""
        # Add a planned operation matching RENT for heuristic linking
        planned_op = PlannedOperation(
            record_id=None,
            description="Loyer",
            amount=Amount(-800.0),
            category=Category.RENT,
            date_range=RecurringDay(date(2025, 1, 1), relativedelta(months=1)),
        )
        op_id = repository.upsert_planned_operation(planned_op)

        results = use_case.categorize_operations((1,), Category.RENT)

        assert len(results) == 1
        assert results[0].operation.category == Category.RENT
        assert results[0].category_changed is True

        # Verify a heuristic link was created (persisted in DB)
        link = repository.get_link_for_operation(1)
        assert link is not None
        assert link.target_type == LinkType.PLANNED_OPERATION
        assert link.target_id == op_id
        assert link.is_manual is False

    def test_heuristic_link_deleted_on_category_change(
        self,
        use_case: CategorizeUseCase,
        repository: SqliteRepository,
    ) -> None:
        """Changing category deletes the existing heuristic link."""
        # Seed a planned operation and an initial heuristic link
        planned_op = PlannedOperation(
            record_id=None,
            description="Loyer",
            amount=Amount(-800.0),
            category=Category.RENT,
            date_range=RecurringDay(date(2025, 1, 1), relativedelta(months=1)),
        )
        op_id = repository.upsert_planned_operation(planned_op)

        initial_link = OperationLink(
            operation_unique_id=1,
            target_type=LinkType.PLANNED_OPERATION,
            target_id=op_id,
            iteration_date=date(2025, 1, 1),
            is_manual=False,
        )
        repository.upsert_link(initial_link)

        # Categorize to GROCERIES: the old RENT link should be deleted
        use_case.categorize_operations((1,), Category.GROCERIES)

        link = repository.get_link_for_operation(1)
        # No matching GROCERIES target exists, so no new link is created
        assert link is None
