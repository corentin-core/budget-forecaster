"""Tests for the iteration resolution service."""

from collections.abc import Iterator
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from dateutil.relativedelta import relativedelta

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.date_range import RecurringDay
from budget_forecaster.core.types import Category, IterationAction
from budget_forecaster.domain.operation.planned_operation import PlannedOperation
from budget_forecaster.infrastructure.persistence.sqlite_repository import (
    SqliteRepository,
)
from budget_forecaster.services.operation.iteration_resolution_service import (
    IterationResolutionService,
)


@pytest.fixture(name="repository")
def repository_fixture(tmp_path: Path) -> Iterator[SqliteRepository]:
    """An initialized repository over a temporary database."""
    with SqliteRepository(tmp_path / "test.db") as repo:
        yield repo


@pytest.fixture(name="planned_op_id")
def planned_op_id_fixture(repository: SqliteRepository) -> int:
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


@pytest.fixture(name="service")
def service_fixture(repository: SqliteRepository) -> IterationResolutionService:
    """The service over a real repository."""
    return IterationResolutionService(repository)


class TestRecordingDecisions:
    """Decisions are stamped and stored."""

    def test_skip_is_stored_and_stamped(
        self, service: IterationResolutionService, planned_op_id: int
    ) -> None:
        """The decision time is recorded in aware UTC."""
        before = datetime.now(timezone.utc)
        service.skip(planned_op_id, date(2025, 3, 5), note="waived")

        (stored,) = service.get_all_resolutions()
        assert stored.action is IterationAction.SKIP
        assert stored.note == "waived"
        assert stored.decided_at is not None
        assert stored.decided_at >= before

    def test_postpone_is_stored_with_its_date(
        self, service: IterationResolutionService, planned_op_id: int
    ) -> None:
        """The chosen date survives the round-trip."""
        service.postpone(planned_op_id, date(2025, 3, 5), date(2025, 4, 2))

        (stored,) = service.get_all_resolutions()
        assert stored.action is IterationAction.POSTPONE
        assert stored.postponed_to == date(2025, 4, 2)

    def test_postponing_backwards_is_refused(
        self, service: IterationResolutionService, planned_op_id: int
    ) -> None:
        """The domain invariant applies before anything is stored."""
        with pytest.raises(ValueError):
            service.postpone(planned_op_id, date(2025, 3, 5), date(2025, 2, 1))
        assert service.get_all_resolutions() == ()

    def test_restore_removes_the_decision(
        self, service: IterationResolutionService, planned_op_id: int
    ) -> None:
        """Undoing leaves no trace, so the state is derived again."""
        service.skip(planned_op_id, date(2025, 3, 5))
        service.restore(planned_op_id, date(2025, 3, 5))
        assert service.get_all_resolutions() == ()

    def test_decisions_can_be_read_per_operation(
        self, service: IterationResolutionService, planned_op_id: int
    ) -> None:
        """The edit page reads only its own."""
        service.skip(planned_op_id, date(2025, 3, 5))
        assert len(service.get_resolutions_for_planned_operation(planned_op_id)) == 1
        assert service.get_resolutions_for_planned_operation(planned_op_id + 1) == ()
