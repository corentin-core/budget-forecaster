"""Tests for the derived state of past planned-operation iterations."""

from datetime import date, timedelta

from dateutil.relativedelta import relativedelta

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.date_range import RecurringDay, SingleDay
from budget_forecaster.core.types import Category, IterationAction, IterationState
from budget_forecaster.domain.operation.iteration_resolution import IterationResolution
from budget_forecaster.domain.operation.planned_operation import PlannedOperation
from budget_forecaster.services.forecast.iteration_lifecycle import (
    LATE_HORIZON,
    derive_past_iterations,
    index_resolutions,
)

_BALANCE_DATE = date(2025, 3, 20)


def _monthly(first_iteration: date) -> PlannedOperation:
    """A monthly rent starting on the given date."""
    return PlannedOperation(
        record_id=7,
        description="Rent",
        amount=Amount(-850.0, "EUR"),
        category=Category.RENT,
        date_range=RecurringDay(first_iteration, relativedelta(months=1)),
    )


def _one_time(iteration: date) -> PlannedOperation:
    """A one-time expense on the given date."""
    return PlannedOperation(
        record_id=7,
        description="Insurance",
        amount=Amount(-145.0, "EUR"),
        category=Category.HOUSE_INSURANCE,
        date_range=SingleDay(iteration),
    )


class TestUndecidedIterations:
    """Without a decision, only the age decides."""

    def test_future_iteration_yields_nothing(self) -> None:
        """The list covers the past only."""
        assert not derive_past_iterations(
            _one_time(_BALANCE_DATE + timedelta(days=1)), _BALANCE_DATE, set(), {}
        )

    def test_iteration_on_the_balance_date_is_late(self) -> None:
        """Due today and not posted yet: still expected."""
        (past,) = derive_past_iterations(
            _one_time(_BALANCE_DATE), _BALANCE_DATE, set(), {}
        )
        assert past.state is IterationState.LATE
        assert past.effective_date == _BALANCE_DATE + timedelta(days=1)

    def test_iteration_on_the_horizon_boundary_is_still_late(self) -> None:
        """The horizon is inclusive, so the boundary day still counts."""
        (past,) = derive_past_iterations(
            _one_time(_BALANCE_DATE - LATE_HORIZON), _BALANCE_DATE, set(), {}
        )
        assert past.state is IterationState.LATE

    def test_iteration_past_the_horizon_expires(self) -> None:
        """One day older and the amount stops being counted."""
        (past,) = derive_past_iterations(
            _one_time(_BALANCE_DATE - LATE_HORIZON - timedelta(days=1)),
            _BALANCE_DATE,
            set(),
            {},
        )
        assert past.state is IterationState.EXPIRED
        assert past.effective_date is None

    def test_matched_iteration_yields_nothing(self) -> None:
        """A linked iteration was paid; nothing to derive."""
        assert not derive_past_iterations(
            _one_time(_BALANCE_DATE), _BALANCE_DATE, {_BALANCE_DATE}, {}
        )

    def test_every_unmatched_iteration_is_listed(self) -> None:
        """A recurring operation yields one entry per missed period."""
        past = derive_past_iterations(
            _monthly(date(2024, 12, 5)), _BALANCE_DATE, set(), {}
        )
        assert [entry.iteration_date for entry in past] == [
            date(2024, 12, 5),
            date(2025, 1, 5),
            date(2025, 2, 5),
            date(2025, 3, 5),
        ]
        # The late horizon starts on 2025-02-17, so only the March iteration is late
        assert [entry.state for entry in past] == [
            IterationState.EXPIRED,
            IterationState.EXPIRED,
            IterationState.EXPIRED,
            IterationState.LATE,
        ]


class TestDecidedIterations:
    """A decision overrides the age."""

    def test_skipped_iteration_is_not_counted(self) -> None:
        """The user said it never happened."""
        iteration = date(2025, 3, 5)
        resolutions = index_resolutions(
            (
                IterationResolution(
                    planned_operation_id=7,
                    iteration_date=iteration,
                    action=IterationAction.SKIP,
                ),
            )
        )
        (past,) = derive_past_iterations(
            _one_time(iteration), _BALANCE_DATE, set(), resolutions[7]
        )
        assert past.state is IterationState.SKIPPED
        assert past.effective_date is None

    def test_postponed_iteration_counts_on_its_new_date(self) -> None:
        """The forecast follows the user's date."""
        iteration = date(2025, 3, 5)
        resolutions = index_resolutions(
            (
                IterationResolution(
                    planned_operation_id=7,
                    iteration_date=iteration,
                    action=IterationAction.POSTPONE,
                    postponed_to=date(2025, 4, 2),
                ),
            )
        )
        (past,) = derive_past_iterations(
            _one_time(iteration), _BALANCE_DATE, set(), resolutions[7]
        )
        assert past.state is IterationState.POSTPONED
        assert past.effective_date == date(2025, 4, 2)

    def test_postponement_that_passed_is_late_again(self) -> None:
        """Nothing matched the chosen date, so the iteration comes back."""
        iteration = date(2025, 3, 1)
        resolutions = index_resolutions(
            (
                IterationResolution(
                    planned_operation_id=7,
                    iteration_date=iteration,
                    action=IterationAction.POSTPONE,
                    postponed_to=date(2025, 3, 10),
                ),
            )
        )
        (past,) = derive_past_iterations(
            _one_time(iteration), _BALANCE_DATE, set(), resolutions[7]
        )
        assert past.state is IterationState.LATE
        assert past.effective_date == _BALANCE_DATE + timedelta(days=1)
        assert past.postponed_to == date(2025, 3, 10)

    def test_postponement_older_than_the_horizon_expires(self) -> None:
        """The age is measured from the chosen date, not the original one."""
        iteration = date(2024, 12, 1)
        resolutions = index_resolutions(
            (
                IterationResolution(
                    planned_operation_id=7,
                    iteration_date=iteration,
                    action=IterationAction.POSTPONE,
                    postponed_to=date(2025, 1, 15),
                ),
            )
        )
        (past,) = derive_past_iterations(
            _one_time(iteration), _BALANCE_DATE, set(), resolutions[7]
        )
        assert past.state is IterationState.EXPIRED

    def test_a_link_wins_over_a_decision(self) -> None:
        """An operation showed up after the user decided: the money did move."""
        iteration = date(2025, 3, 5)
        resolutions = index_resolutions(
            (
                IterationResolution(
                    planned_operation_id=7,
                    iteration_date=iteration,
                    action=IterationAction.SKIP,
                ),
            )
        )
        assert not derive_past_iterations(
            _one_time(iteration), _BALANCE_DATE, {iteration}, resolutions[7]
        )

    def test_decisions_are_indexed_per_operation(self) -> None:
        """Two operations keep their own decisions."""
        first = IterationResolution(
            planned_operation_id=7,
            iteration_date=date(2025, 3, 5),
            action=IterationAction.SKIP,
        )
        second = IterationResolution(
            planned_operation_id=9,
            iteration_date=date(2025, 3, 5),
            action=IterationAction.SKIP,
        )
        assert index_resolutions((first, second)) == {
            7: {first.iteration_date: first},
            9: {second.iteration_date: second},
        }
