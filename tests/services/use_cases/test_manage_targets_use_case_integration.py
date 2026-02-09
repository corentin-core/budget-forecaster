"""Integration tests for ManageTargetsUseCase with real dependencies."""

from datetime import date
from pathlib import Path

import pytest
from dateutil.relativedelta import relativedelta

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.date_range import RecurringDay
from budget_forecaster.core.types import Category, LinkType
from budget_forecaster.domain.account.account import Account
from budget_forecaster.domain.operation.historic_operation import HistoricOperation
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
from budget_forecaster.services.use_cases.manage_targets_use_case import (
    ManageTargetsUseCase,
)
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
                    category=Category.RENT,
                    operation_date=date(2025, 1, 2),
                ),
                HistoricOperation(
                    unique_id=2,
                    description="LOYER FEVRIER",
                    amount=Amount(-800.0),
                    category=Category.RENT,
                    operation_date=date(2025, 2, 1),
                ),
            ),
        )
    )
    return PersistentAccount(repository)


@pytest.fixture(name="use_case")
def use_case_fixture(
    persistent_account: PersistentAccount,
    repository: SqliteRepository,
) -> ManageTargetsUseCase:
    """Create a ManageTargetsUseCase with real dependencies."""
    forecast_service = ForecastService(persistent_account.account, repository)
    return ManageTargetsUseCase(
        forecast_service,
        persistent_account,
        OperationLinkService(repository),
        MatcherCache(forecast_service),
    )


class TestManageTargetsIntegration:
    """Integration: manage planned operations and verify persistence + links."""

    def test_add_persists_and_creates_heuristic_links(
        self,
        use_case: ManageTargetsUseCase,
        repository: SqliteRepository,
    ) -> None:
        """Adding a planned operation persists it and creates heuristic links."""
        planned_op = PlannedOperation(
            record_id=None,
            description="Loyer",
            amount=Amount(-800.0),
            category=Category.RENT,
            date_range=RecurringDay(date(2025, 1, 1), relativedelta(months=1)),
        )

        result = use_case.add_planned_operation(planned_op)

        # Verify the planned operation is persisted with an ID
        assert result.id is not None
        persisted = repository.get_planned_operation_by_id(result.id)
        assert persisted is not None
        assert persisted.description == "Loyer"
        assert persisted.amount == -800.0

        # Verify heuristic links were created for matching operations
        link_op1 = repository.get_link_for_operation(1)
        assert link_op1 is not None
        assert link_op1.target_type == LinkType.PLANNED_OPERATION
        assert link_op1.target_id == result.id
        assert link_op1.is_manual is False

    def test_delete_removes_operation_and_links(
        self,
        use_case: ManageTargetsUseCase,
        repository: SqliteRepository,
    ) -> None:
        """Deleting a planned operation removes it and its links from DB."""
        # First add an operation (which creates heuristic links)
        planned_op = PlannedOperation(
            record_id=None,
            description="Loyer",
            amount=Amount(-800.0),
            category=Category.RENT,
            date_range=RecurringDay(date(2025, 1, 1), relativedelta(months=1)),
        )
        result = use_case.add_planned_operation(planned_op)
        assert result.id is not None

        # Verify link exists
        assert repository.get_link_for_operation(1) is not None

        # Delete the operation
        use_case.delete_planned_operation(result.id)

        # Verify operation and links are gone
        assert repository.get_planned_operation_by_id(result.id) is None
        assert repository.get_link_for_operation(1) is None
