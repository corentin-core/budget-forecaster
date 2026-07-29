"""Tests for the IterationResolution invariants."""

from datetime import date, datetime

import pytest

from budget_forecaster.core.types import IterationAction
from budget_forecaster.domain.operation.iteration_resolution import IterationResolution


class TestPostponeInvariants:
    """A postponement must say where the iteration goes."""

    def test_postpone_without_a_date_is_rejected(self) -> None:
        """Moving an iteration nowhere would silently drop it from the forecast."""
        with pytest.raises(ValueError, match="needs a new date"):
            IterationResolution(
                planned_operation_id=1,
                iteration_date=date(2025, 3, 5),
                action=IterationAction.POSTPONE,
            )

    @pytest.mark.parametrize("postponed_to", [date(2025, 3, 5), date(2025, 3, 4)])
    def test_postpone_must_move_forward(self, postponed_to: date) -> None:
        """A date on or before the iteration is not a postponement."""
        with pytest.raises(ValueError, match="must be after the iteration date"):
            IterationResolution(
                planned_operation_id=1,
                iteration_date=date(2025, 3, 5),
                action=IterationAction.POSTPONE,
                postponed_to=postponed_to,
            )

    def test_postpone_forward_is_accepted(self) -> None:
        """A later date is the normal case."""
        resolution = IterationResolution(
            planned_operation_id=1,
            iteration_date=date(2025, 3, 5),
            action=IterationAction.POSTPONE,
            postponed_to=date(2025, 4, 2),
        )
        assert resolution.postponed_to == date(2025, 4, 2)


class TestSkipInvariants:
    """A skipped iteration has no new date."""

    def test_skip_with_a_date_is_rejected(self) -> None:
        """Carrying a date would make the state ambiguous."""
        with pytest.raises(ValueError, match="cannot carry a new date"):
            IterationResolution(
                planned_operation_id=1,
                iteration_date=date(2025, 3, 5),
                action=IterationAction.SKIP,
                postponed_to=date(2025, 4, 2),
            )

    def test_skip_alone_is_accepted(self) -> None:
        """The normal case: the payment never happened."""
        resolution = IterationResolution(
            planned_operation_id=1,
            iteration_date=date(2025, 3, 5),
            action=IterationAction.SKIP,
        )
        assert resolution.postponed_to is None


class TestDateTypeGuard:
    """A datetime would poison every later read of the table."""

    def test_datetime_iteration_date_is_refused(self) -> None:
        """datetime subclasses date, so nothing else would catch it."""
        with pytest.raises(TypeError, match="iteration_date must be a date"):
            IterationResolution(
                planned_operation_id=1,
                iteration_date=datetime(2025, 3, 5, 12, 0),
                action=IterationAction.SKIP,
            )

    def test_datetime_postponed_to_is_refused(self) -> None:
        """Same guard on the chosen date."""
        with pytest.raises(TypeError, match="postponed_to must be a date"):
            IterationResolution(
                planned_operation_id=1,
                iteration_date=date(2025, 3, 5),
                action=IterationAction.POSTPONE,
                postponed_to=datetime(2025, 4, 2, 9, 30),
            )
