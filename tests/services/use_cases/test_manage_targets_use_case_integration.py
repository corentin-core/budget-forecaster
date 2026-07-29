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
from budget_forecaster.domain.operation.operation_link import OperationLink
from budget_forecaster.domain.operation.planned_operation import PlannedOperation
from budget_forecaster.exceptions import PlannedOperationNotFoundError
from budget_forecaster.infrastructure.persistence.persistent_account import (
    PersistentAccount,
)
from budget_forecaster.infrastructure.persistence.sqlite_repository import (
    SqliteRepository,
)
from budget_forecaster.services.forecast.forecast_service import ForecastService
from budget_forecaster.services.operation.iteration_resolution_service import (
    IterationResolutionService,
)
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
                    description="RENT JANUARY",
                    amount=Amount(-800.0),
                    category=Category.RENT,
                    operation_date=date(2025, 1, 2),
                ),
                HistoricOperation(
                    unique_id=2,
                    description="RENT FEBRUARY",
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
    forecast_service = ForecastService(persistent_account, repository)
    return ManageTargetsUseCase(
        forecast_service,
        persistent_account,
        OperationLinkService(repository),
        IterationResolutionService(repository),
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
            description="Rent",
            amount=Amount(-800.0),
            category=Category.RENT,
            date_range=RecurringDay(date(2025, 1, 1), relativedelta(months=1)),
        )

        result = use_case.add_planned_operation(planned_op)

        # Verify the planned operation is persisted with an ID
        assert result.id is not None
        persisted = repository.get_planned_operation_by_id(result.id)
        expected = PlannedOperation(
            record_id=result.id,
            description="Rent",
            amount=Amount(-800.0),
            category=Category.RENT,
            date_range=RecurringDay(date(2025, 1, 1), relativedelta(months=1)),
        )
        assert persisted == expected

        # Verify heuristic links were created for matching operations
        link_op1 = repository.get_link_for_operation(1)
        assert link_op1 is not None
        assert link_op1 == OperationLink(
            operation_unique_id=1,
            target_type=LinkType.PLANNED_OPERATION,
            target_id=result.id,
            iteration_date=date(2025, 1, 1),
            is_manual=False,
            notes=None,
            link_id=link_op1.link_id,
        )

    def test_delete_removes_operation_and_links(
        self,
        use_case: ManageTargetsUseCase,
        repository: SqliteRepository,
    ) -> None:
        """Deleting a planned operation removes it and its links from DB."""
        # First add an operation (which creates heuristic links)
        planned_op = PlannedOperation(
            record_id=None,
            description="Rent",
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
        with pytest.raises(PlannedOperationNotFoundError):
            repository.get_planned_operation_by_id(result.id)
        assert repository.get_link_for_operation(1) is None


class TestIterationDecisionsAcrossEdits:
    """A decision must follow the iteration it was taken on."""

    @staticmethod
    def _monthly_rent() -> PlannedOperation:
        """A monthly rent starting in January."""
        return PlannedOperation(
            record_id=None,
            description="Rent",
            amount=Amount(-800.0),
            category=Category.RENT,
            date_range=RecurringDay(date(2025, 1, 1), relativedelta(months=1)),
        )

    def test_split_moves_later_decisions_to_the_continuation(
        self,
        use_case: ManageTargetsUseCase,
        repository: SqliteRepository,
    ) -> None:
        """Left behind, a skipped amount would quietly come back to the forecast."""
        original = use_case.add_planned_operation(self._monthly_rent())
        assert original.id is not None
        service = IterationResolutionService(repository)
        service.skip(original.id, date(2025, 2, 1))
        service.skip(original.id, date(2025, 6, 1))

        continuation = use_case.split_planned_operation_at_date(
            original.id, date(2025, 6, 1), new_amount=Amount(-850.0)
        )

        assert [
            r.iteration_date
            for r in service.get_resolutions_for_planned_operation(original.id)
        ] == [date(2025, 2, 1)]
        assert continuation.id is not None
        assert [
            r.iteration_date
            for r in service.get_resolutions_for_planned_operation(continuation.id)
        ] == [date(2025, 6, 1)]

    def test_split_keeps_a_postponement_and_its_date(
        self,
        use_case: ManageTargetsUseCase,
        repository: SqliteRepository,
    ) -> None:
        """The chosen date survives the move."""
        original = use_case.add_planned_operation(self._monthly_rent())
        assert original.id is not None
        service = IterationResolutionService(repository)
        service.postpone(
            original.id, date(2025, 6, 1), date(2025, 6, 20), "landlord away"
        )

        continuation = use_case.split_planned_operation_at_date(
            original.id, date(2025, 6, 1), new_amount=Amount(-850.0)
        )

        assert continuation.id is not None
        (moved,) = service.get_resolutions_for_planned_operation(continuation.id)
        assert moved.postponed_to == date(2025, 6, 20)
        assert moved.note == "landlord away"

    def test_editing_the_start_date_forgets_orphan_decisions(
        self,
        use_case: ManageTargetsUseCase,
        repository: SqliteRepository,
    ) -> None:
        """A decision on an iteration the operation no longer has applies to nothing."""
        original = use_case.add_planned_operation(self._monthly_rent())
        assert original.id is not None
        service = IterationResolutionService(repository)
        service.skip(original.id, date(2025, 2, 1))

        use_case.update_planned_operation(
            original.replace(
                date_range=RecurringDay(date(2025, 1, 15), relativedelta(months=1))
            )
        )

        assert service.get_resolutions_for_planned_operation(original.id) == ()

    def test_editing_keeps_a_decision_that_still_applies(
        self,
        use_case: ManageTargetsUseCase,
        repository: SqliteRepository,
    ) -> None:
        """An unrelated edit must not throw the user's decisions away."""
        original = use_case.add_planned_operation(self._monthly_rent())
        assert original.id is not None
        service = IterationResolutionService(repository)
        service.skip(original.id, date(2025, 2, 1))

        use_case.update_planned_operation(original.replace(amount=Amount(-820.0)))

        assert len(service.get_resolutions_for_planned_operation(original.id)) == 1
