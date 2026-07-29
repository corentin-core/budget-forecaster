"""Tests for the iteration_resolutions table and its repository methods."""

from collections.abc import Iterator
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from dateutil.relativedelta import relativedelta

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.date_range import RecurringDay
from budget_forecaster.core.types import Category, IterationAction
from budget_forecaster.domain.operation.iteration_resolution import IterationResolution
from budget_forecaster.domain.operation.planned_operation import PlannedOperation
from budget_forecaster.infrastructure.persistence.repository_interface import (
    RepositoryInterface,
)
from budget_forecaster.infrastructure.persistence.sqlite_repository import (
    SqliteRepository,
)


@pytest.fixture(name="repository")
def repository_fixture(tmp_path: Path) -> Iterator[RepositoryInterface]:
    """An initialized repository over a temporary database."""
    with SqliteRepository(tmp_path / "test.db") as repo:
        yield repo


@pytest.fixture(name="planned_op_id")
def planned_op_id_fixture(repository: RepositoryInterface) -> int:
    """A stored planned operation to attach decisions to."""
    return repository.upsert_planned_operation(
        PlannedOperation(
            record_id=None,
            description="Rent",
            amount=Amount(-850.0, "EUR"),
            category=Category.RENT,
            date_range=RecurringDay(date(2025, 1, 5), relativedelta(months=1)),
        )
    )


class TestIterationResolutionsTable:
    """Round-trip, ordering and uniqueness."""

    def test_empty_by_default(self, repository: RepositoryInterface) -> None:
        """No decision taken yet yields an empty tuple."""
        assert repository.get_iteration_resolutions() == ()

    def test_skip_round_trips(
        self, repository: RepositoryInterface, planned_op_id: int
    ) -> None:
        """A skip comes back with all its fields."""
        decided_at = datetime(2025, 3, 20, 8, 30, tzinfo=timezone.utc)
        repository.upsert_iteration_resolution(
            IterationResolution(
                planned_operation_id=planned_op_id,
                iteration_date=date(2025, 3, 5),
                action=IterationAction.SKIP,
                note="landlord waived it",
                decided_at=decided_at,
            )
        )
        (resolution,) = repository.get_iteration_resolutions()
        assert resolution == IterationResolution(
            planned_operation_id=planned_op_id,
            iteration_date=date(2025, 3, 5),
            action=IterationAction.SKIP,
            note="landlord waived it",
            decided_at=decided_at,
        )

    def test_postpone_round_trips(
        self, repository: RepositoryInterface, planned_op_id: int
    ) -> None:
        """A postponement keeps its new date."""
        repository.upsert_iteration_resolution(
            IterationResolution(
                planned_operation_id=planned_op_id,
                iteration_date=date(2025, 3, 5),
                action=IterationAction.POSTPONE,
                postponed_to=date(2025, 4, 2),
                decided_at=datetime(2025, 3, 20, tzinfo=timezone.utc),
            )
        )
        (resolution,) = repository.get_iteration_resolutions()
        assert resolution.action is IterationAction.POSTPONE
        assert resolution.postponed_to == date(2025, 4, 2)

    def test_second_decision_on_the_same_iteration_replaces_the_first(
        self, repository: RepositoryInterface, planned_op_id: int
    ) -> None:
        """Changing one's mind updates the row instead of piling up."""
        iteration = date(2025, 3, 5)
        repository.upsert_iteration_resolution(
            IterationResolution(
                planned_operation_id=planned_op_id,
                iteration_date=iteration,
                action=IterationAction.SKIP,
                decided_at=datetime(2025, 3, 20, tzinfo=timezone.utc),
            )
        )
        repository.upsert_iteration_resolution(
            IterationResolution(
                planned_operation_id=planned_op_id,
                iteration_date=iteration,
                action=IterationAction.POSTPONE,
                postponed_to=date(2025, 4, 2),
                decided_at=datetime(2025, 3, 21, tzinfo=timezone.utc),
            )
        )
        (resolution,) = repository.get_iteration_resolutions()
        assert resolution.action is IterationAction.POSTPONE

    def test_reads_are_ordered_oldest_iteration_first(
        self, repository: RepositoryInterface, planned_op_id: int
    ) -> None:
        """The overdue list wants the oldest first."""
        for iteration in (date(2025, 3, 5), date(2025, 1, 5), date(2025, 2, 5)):
            repository.upsert_iteration_resolution(
                IterationResolution(
                    planned_operation_id=planned_op_id,
                    iteration_date=iteration,
                    action=IterationAction.SKIP,
                    decided_at=datetime(2025, 3, 20, tzinfo=timezone.utc),
                )
            )
        resolutions = repository.get_iteration_resolutions()
        assert [r.iteration_date for r in resolutions] == [
            date(2025, 1, 5),
            date(2025, 2, 5),
            date(2025, 3, 5),
        ]

    def test_reads_can_be_restricted_to_one_operation(
        self, repository: RepositoryInterface, planned_op_id: int
    ) -> None:
        """The edit page only wants its own decisions."""
        other_id = repository.upsert_planned_operation(
            PlannedOperation(
                record_id=None,
                description="Gym",
                amount=Amount(-30.0, "EUR"),
                category=Category.LEISURE,
                date_range=RecurringDay(date(2025, 1, 8), relativedelta(months=1)),
            )
        )
        for op_id in (planned_op_id, other_id):
            repository.upsert_iteration_resolution(
                IterationResolution(
                    planned_operation_id=op_id,
                    iteration_date=date(2025, 3, 5),
                    action=IterationAction.SKIP,
                    decided_at=datetime(2025, 3, 20, tzinfo=timezone.utc),
                )
            )
        (resolution,) = repository.get_iteration_resolutions(planned_op_id)
        assert resolution.planned_operation_id == planned_op_id

    def test_delete_restores_the_derived_state(
        self, repository: RepositoryInterface, planned_op_id: int
    ) -> None:
        """Undoing a decision removes its row."""
        iteration = date(2025, 3, 5)
        repository.upsert_iteration_resolution(
            IterationResolution(
                planned_operation_id=planned_op_id,
                iteration_date=iteration,
                action=IterationAction.SKIP,
                decided_at=datetime(2025, 3, 20, tzinfo=timezone.utc),
            )
        )
        repository.delete_iteration_resolution(planned_op_id, iteration)
        assert repository.get_iteration_resolutions() == ()

    def test_deleting_the_planned_operation_drops_its_decisions(
        self, repository: RepositoryInterface, planned_op_id: int
    ) -> None:
        """Orphan decisions would resurface if the id were reused."""
        repository.upsert_iteration_resolution(
            IterationResolution(
                planned_operation_id=planned_op_id,
                iteration_date=date(2025, 3, 5),
                action=IterationAction.SKIP,
                decided_at=datetime(2025, 3, 20, tzinfo=timezone.utc),
            )
        )
        repository.delete_planned_operation(planned_op_id)
        assert repository.get_iteration_resolutions() == ()
