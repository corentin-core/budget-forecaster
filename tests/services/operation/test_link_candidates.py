"""Ranking the two ends of a link against each other."""

from datetime import date, timedelta

from dateutil.relativedelta import relativedelta

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.date_range import RecurringDay, SingleDay
from budget_forecaster.core.types import Category
from budget_forecaster.domain.operation.budget import Budget
from budget_forecaster.domain.operation.historic_operation import HistoricOperation
from budget_forecaster.domain.operation.planned_operation import PlannedOperation
from budget_forecaster.services.operation.link_candidates import (
    AmountMatch,
    amount_match,
    best_score,
    rank_operations,
    rank_targets,
)

_ITERATION = date(2026, 3, 12)


def _monthly(
    record_id: int,
    amount: float,
    *,
    description: str = "Home insurance",
    category: Category = Category.HOUSE_INSURANCE,
    start: date = _ITERATION,
) -> PlannedOperation:
    """A monthly planned operation whose first occurrence is on start."""
    return PlannedOperation(
        record_id,
        description,
        Amount(amount, "EUR"),
        category,
        RecurringDay(start, relativedelta(months=1)),
    )


def _operation(
    unique_id: int,
    amount: float,
    *,
    description: str = "PRLV SEPA AXA",
    category: Category = Category.HOUSE_INSURANCE,
    day: date = _ITERATION,
) -> HistoricOperation:
    """A historic operation, expense by default."""
    return HistoricOperation(
        unique_id=unique_id,
        description=description,
        amount=Amount(amount, "EUR"),
        category=category,
        operation_date=day,
    )


class TestAmountMatch:
    """The amount is the strongest of the four signals, so it is named."""

    def test_equal_amounts_of_opposite_sign_still_match(self) -> None:
        """A planned expense is stored negative; the operation's sign is its own."""
        assert (
            amount_match(_operation(1, -38.90), _monthly(1, -38.90))
            is AmountMatch.EXACT
        )

    def test_within_the_ratio_is_close(self) -> None:
        """The default tolerance is 5% of the planned amount."""
        assert (
            amount_match(_operation(1, -40.0), _monthly(1, -38.90)) is AmountMatch.CLOSE
        )

    def test_beyond_the_ratio_says_nothing(self) -> None:
        """No hint rather than a misleading one."""
        assert (
            amount_match(_operation(1, -80.0), _monthly(1, -38.90)) is AmountMatch.OFF
        )

    def test_a_zero_target_is_never_close(self) -> None:
        """A ratio of zero would divide the tolerance away."""
        assert amount_match(_operation(1, -1.0), _monthly(1, 0.0)) is AmountMatch.OFF


class TestBestScore:
    """Ranking a target the user has not picked an occurrence for yet."""

    def test_it_takes_the_best_fitting_occurrence(self) -> None:
        """An operation two months late still recognizes its own recurrence."""
        target = _monthly(1, -38.90, start=date(2026, 1, 12))
        near = _operation(1, -38.90, day=date(2026, 3, 12))

        assert best_score(near, target) == best_score(
            _operation(2, -38.90, day=date(2026, 1, 12)), target
        )

    def test_an_occurrence_outside_the_window_does_not_count(self) -> None:
        """A one-off yields its single day whatever from_date the walk asks for."""
        one_off = PlannedOperation(
            1,
            "Taxe",
            Amount(-38.90, "EUR"),
            Category.HOUSE_INSURANCE,
            SingleDay(date(2026, 1, 1)),
        )
        far = _operation(1, -38.90, day=date(2026, 6, 1))

        assert best_score(far, one_off, window=timedelta(days=60)) == 0.0
        assert best_score(far, one_off, window=timedelta(days=200)) > 0.0


class TestRankTargets:
    """From an operation, which budget or planned payment is it."""

    def test_best_first(self) -> None:
        """The order is the score's, so it agrees with automatic matching."""
        operation = _operation(1, -38.90)
        right = _monthly(1, -38.90)
        wrong = _monthly(2, -500.0, description="Rent", category=Category.RENT)

        ranked = rank_targets(operation, (wrong, right))

        assert [scored.target_id for scored in ranked] == [1, 2]
        assert ranked[0].amount_match is AmountMatch.EXACT

    def test_an_unsaved_target_is_not_offered(self) -> None:
        """Linking to it could not be persisted."""
        unsaved = PlannedOperation(
            None,
            "Draft",
            Amount(-38.90, "EUR"),
            Category.HOUSE_INSURANCE,
            SingleDay(_ITERATION),
        )

        assert not rank_targets(_operation(1, -38.90), (unsaved,))

    def test_a_budget_is_ranked_too(self) -> None:
        """Both link target kinds go through the same ranking."""
        budget = Budget(
            1,
            "Groceries",
            Amount(-400.0, "EUR"),
            Category.GROCERIES,
            RecurringDay(_ITERATION, relativedelta(months=1)),
        )

        ranked = rank_targets(_operation(1, -38.90), (budget,))

        assert len(ranked) == 1
        assert ranked[0].score > 0


class TestRankOperations:
    """From an occurrence, which operation paid it."""

    def test_best_first(self) -> None:
        """The amount decides between operations of the same day."""
        target = _monthly(1, -38.90)
        exact = _operation(1, -38.90)
        off = _operation(2, -12.0)

        ranked = rank_operations(target, _ITERATION, (off, exact))

        assert [scored.operation.unique_id for scored in ranked] == [1, 2]

    def test_a_credit_never_pays_an_expense(self) -> None:
        """Comparing absolute amounts would otherwise rank a refund first."""
        target = _monthly(1, -38.90)
        credit = _operation(1, 38.90)

        assert not rank_operations(target, _ITERATION, (credit,))

    def test_an_income_is_matched_by_income(self) -> None:
        """The rule is same sign, not sign negative."""
        salary = _monthly(1, 2500.0, description="Salary", category=Category.SALARY)
        received = _operation(1, 2500.0, category=Category.SALARY)

        assert len(rank_operations(salary, _ITERATION, (received,))) == 1

    def test_ties_break_on_distance_then_id(self) -> None:
        """A stable order, so the list does not shuffle between requests."""
        target = _monthly(1, -38.90)
        far = _operation(9, -38.90, day=_ITERATION + timedelta(days=3))
        near_high_id = _operation(8, -38.90, day=_ITERATION)
        near_low_id = _operation(7, -38.90, day=_ITERATION)

        ranked = rank_operations(target, _ITERATION, (far, near_high_id, near_low_id))

        assert [scored.operation.unique_id for scored in ranked] == [7, 8, 9]

    def test_it_scores_the_given_occurrence_not_the_best_one(self) -> None:
        """The caller fixed the occurrence; a nearer one must not flatter the score."""
        target = _monthly(1, -38.90, start=date(2026, 1, 12))
        operation = _operation(1, -38.90, day=date(2026, 1, 12))

        on_its_own_date = rank_operations(target, date(2026, 1, 12), (operation,))
        two_months_later = rank_operations(target, date(2026, 3, 12), (operation,))

        assert on_its_own_date[0].score > two_months_later[0].score
