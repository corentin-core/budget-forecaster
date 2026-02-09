"""Integration tests for ManageLinksUseCase with real dependencies."""

from datetime import date
from pathlib import Path

import pytest
from dateutil.relativedelta import relativedelta

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.date_range import RecurringDay
from budget_forecaster.core.types import Category, LinkType
from budget_forecaster.domain.account.account import Account
from budget_forecaster.domain.operation.budget import Budget
from budget_forecaster.domain.operation.historic_operation import HistoricOperation
from budget_forecaster.domain.operation.planned_operation import PlannedOperation
from budget_forecaster.infrastructure.persistence.persistent_account import (
    PersistentAccount,
)
from budget_forecaster.infrastructure.persistence.sqlite_repository import (
    SqliteRepository,
)
from budget_forecaster.services.operation.operation_link_service import (
    OperationLinkService,
)
from budget_forecaster.services.use_cases.manage_links_use_case import (
    ManageLinksUseCase,
)


@pytest.fixture(name="repository")
def repository_fixture(tmp_path: Path) -> SqliteRepository:
    """Create a real SQLite repository in a temp directory."""
    repo = SqliteRepository(tmp_path / "test.db")
    repo.initialize()
    return repo


@pytest.fixture(name="persistent_account")
def persistent_account_fixture(repository: SqliteRepository) -> PersistentAccount:
    """Create a PersistentAccount seeded with one account."""
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
            ),
        )
    )
    return PersistentAccount(repository)


@pytest.fixture(name="use_case")
def use_case_fixture(repository: SqliteRepository) -> ManageLinksUseCase:
    """Create a ManageLinksUseCase with real dependencies."""
    return ManageLinksUseCase(OperationLinkService(repository))


class TestCreateManualLinkIntegration:
    """Integration: create a manual link and verify it is persisted."""

    def test_link_persisted_for_planned_operation(
        self,
        use_case: ManageLinksUseCase,
        persistent_account: PersistentAccount,
        repository: SqliteRepository,
    ) -> None:
        """Creating a manual link persists it in the database."""
        operation = persistent_account.account.operations[0]

        planned_op = PlannedOperation(
            record_id=None,
            description="Loyer",
            amount=Amount(-800.0),
            category=Category.RENT,
            date_range=RecurringDay(date(2025, 1, 1), relativedelta(months=1)),
        )
        op_id = repository.upsert_planned_operation(planned_op)
        saved_op = planned_op.replace(record_id=op_id)

        link = use_case.create_manual_link(operation, saved_op, date(2025, 1, 1))

        assert link.target_type == LinkType.PLANNED_OPERATION
        assert link.is_manual is True

        # Verify the link is actually persisted
        persisted = repository.get_link_for_operation(operation.unique_id)
        assert persisted is not None
        assert persisted.target_id == saved_op.id
        assert persisted.iteration_date == date(2025, 1, 1)
        assert persisted.is_manual is True

    def test_link_persisted_for_budget(
        self,
        use_case: ManageLinksUseCase,
        persistent_account: PersistentAccount,
        repository: SqliteRepository,
    ) -> None:
        """Creating a manual link to a budget persists it correctly."""
        operation = persistent_account.account.operations[0]

        budget = Budget(
            record_id=None,
            description="Courses",
            amount=Amount(-300.0),
            category=Category.GROCERIES,
            date_range=RecurringDay(date(2025, 1, 1), relativedelta(months=1)),
        )
        budget_id = repository.upsert_budget(budget)
        saved_budget = budget.replace(record_id=budget_id)

        link = use_case.create_manual_link(operation, saved_budget, date(2025, 1, 1))

        assert link.target_type == LinkType.BUDGET

        persisted = repository.get_link_for_operation(operation.unique_id)
        assert persisted is not None
        assert persisted.target_id == saved_budget.id
        assert persisted.is_manual is True
