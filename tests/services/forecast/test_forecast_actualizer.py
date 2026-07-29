"""Module with tests for the ForecastActualizer class."""
from datetime import date

import pytest
from dateutil.relativedelta import relativedelta

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.date_range import (
    DateRange,
    RecurringDateRange,
    RecurringDay,
    SingleDay,
)
from budget_forecaster.core.types import Category, LinkType
from budget_forecaster.domain.account.account import Account
from budget_forecaster.domain.forecast.forecast import Forecast
from budget_forecaster.domain.operation.budget import Budget
from budget_forecaster.domain.operation.historic_operation import HistoricOperation
from budget_forecaster.domain.operation.operation_link import OperationLink
from budget_forecaster.domain.operation.planned_operation import PlannedOperation
from budget_forecaster.services.forecast.forecast_actualizer import ForecastActualizer


@pytest.fixture
def account() -> Account:
    """Fixture with an account with one executed operation."""
    return Account(
        name="Test Account",
        balance=1000.0,
        currency="EUR",
        balance_date=date(2023, 1, 1),
        operations=(
            HistoricOperation(
                unique_id=1,
                description="Executed Operation",
                amount=Amount(50.0, "EUR"),
                category=Category.GROCERIES,
                operation_date=date(2023, 1, 1),
            ),
        ),
    )


class TestForecastActualizer:
    """Tests for the ForecastActualizer class without operation links."""

    def test_no_operations(self, account: Account) -> None:
        """Empty forecast remains empty."""
        forecast = Forecast(operations=(), budgets=())
        actualizer = ForecastActualizer(account)
        actualized_forecast = actualizer(forecast)
        assert not actualized_forecast.operations
        assert not actualized_forecast.budgets

    def test_one_time_operation_within_late_horizon_stays_counted(
        self, account: Account
    ) -> None:
        """A one-time operation missed weeks ago still weighs on the forecast.

        The matcher's 5-day tolerance says how far an operation may be recognised
        from its planned date; it does not decide when the money is forgotten.
        """
        forecast = Forecast(
            operations=(
                PlannedOperation(
                    record_id=1,
                    description="Past Operation",
                    amount=Amount(50.0, "EUR"),
                    category=Category.GROCERIES,
                    # 31 days before balance_date (Jan 1): the horizon boundary
                    date_range=SingleDay(date(2022, 12, 1)),
                ),
            ),
            budgets=(),
        )
        actualizer = ForecastActualizer(account)
        actualized_forecast = actualizer(forecast)
        assert len(actualized_forecast.operations) == 1
        assert actualized_forecast.operations[0].date_range.start_date == date(
            2023, 1, 2
        )

    def test_one_time_operation_beyond_late_horizon_stops_being_counted(
        self, account: Account
    ) -> None:
        """Past the late horizon an undecided iteration leaves the forecast.

        It is still reported as overdue, so the money does not vanish unnoticed.
        """
        forecast = Forecast(
            operations=(
                PlannedOperation(
                    record_id=1,
                    description="Forgotten Operation",
                    amount=Amount(50.0, "EUR"),
                    category=Category.GROCERIES,
                    date_range=SingleDay(date(2022, 11, 15)),
                ),
            ),
            budgets=(),
        )
        actualizer = ForecastActualizer(account)
        actualized_forecast = actualizer(forecast)
        assert not actualized_forecast.operations

    def test_one_time_operation_on_balance_date_is_postponed(
        self, account: Account
    ) -> None:
        """
        A one-time planned operation due exactly on balance_date without links is
        pending (not yet posted): postponed to tomorrow, not removed.
        """
        forecast = Forecast(
            operations=(
                PlannedOperation(
                    record_id=1,
                    description="Due Today",
                    amount=Amount(50.0, "EUR"),
                    category=Category.GROCERIES,
                    date_range=SingleDay(date(2023, 1, 1)),
                ),
            ),
            budgets=(),
        )
        actualizer = ForecastActualizer(account)
        actualized_forecast = actualizer(forecast)
        # Postponed to tomorrow, no periodic continuation for a one-time op
        assert len(actualized_forecast.operations) == 1
        op = actualized_forecast.operations[0]
        assert isinstance(op.date_range, SingleDay)
        assert op.date_range.start_date == date(2023, 1, 2)

    def test_periodic_past_operation_outside_tolerance_stays_counted(
        self, account: Account
    ) -> None:
        """
        A periodic iteration missed beyond the matcher tolerance is late, not
        skipped: it is counted the day after the balance date and the recurrence
        carries on.
        """
        forecast = Forecast(
            operations=(
                PlannedOperation(
                    record_id=1,
                    description="Periodic Operation",
                    amount=Amount(100.0, "EUR"),
                    category=Category.OTHER,
                    # Monthly operation starting Dec 20 - iteration is 12 days
                    # before balance_date (Jan 1), outside the 5-day tolerance
                    date_range=RecurringDay(
                        date(2022, 12, 20), relativedelta(months=1)
                    ),
                ),
            ),
            budgets=(),
        )
        actualizer = ForecastActualizer(account)
        actualized_forecast = actualizer(forecast)
        assert len(actualized_forecast.operations) == 2
        late_op, periodic_op = actualized_forecast.operations
        assert isinstance(late_op.date_range, SingleDay)
        assert late_op.date_range.start_date == date(2023, 1, 2)
        assert periodic_op.date_range.start_date == date(2023, 1, 20)

    def test_periodic_past_operation_within_tolerance_is_late(
        self, account: Account
    ) -> None:
        """
        A periodic planned operation in the past, within the tolerance window
        (5 days or less before balance_date), is considered late and postponed
        to tomorrow.
        """
        forecast = Forecast(
            operations=(
                PlannedOperation(
                    record_id=1,
                    description="Monthly Salary",
                    amount=Amount(3000.0, "EUR"),
                    category=Category.SALARY,
                    # Monthly operation starting Dec 28 - iteration is 4 days
                    # before balance_date (Jan 1), within the 5-day tolerance
                    date_range=RecurringDay(
                        date(2022, 12, 28), relativedelta(months=1)
                    ),
                ),
            ),
            budgets=(),
        )
        actualizer = ForecastActualizer(account)
        actualized_forecast = actualizer(forecast)
        # Within tolerance window: iteration is late, postponed to tomorrow
        # Result: 1 postponed operation + 1 periodic operation for next month
        assert len(actualized_forecast.operations) == 2
        # First: postponed late operation (one-time, tomorrow)
        postponed_op = actualized_forecast.operations[0]
        assert postponed_op.date_range.start_date == date(2023, 1, 2)
        assert isinstance(postponed_op.date_range, SingleDay)
        # Second: periodic operation continues from next month
        periodic_op = actualized_forecast.operations[1]
        assert periodic_op.date_range.start_date == date(2023, 1, 28)

    def test_recurring_iteration_on_balance_date_is_postponed(
        self, account: Account
    ) -> None:
        """A recurring income due exactly on balance_date, not yet matched, is
        postponed to tomorrow instead of being dropped.

        Before the fix, the on-date iteration was skipped and the operation
        advanced straight to next period, losing that period's amount.
        """
        account_on_due_date = account._replace(balance_date=date(2023, 1, 26))
        forecast = Forecast(
            operations=(
                PlannedOperation(
                    record_id=1,
                    description="Monthly Salary",
                    amount=Amount(3000.0, "EUR"),
                    category=Category.SALARY,
                    # Monthly, iteration Jan 26 falls exactly on balance_date
                    date_range=RecurringDay(
                        date(2022, 12, 26), relativedelta(months=1)
                    ),
                ),
            ),
            budgets=(),
        )
        # December was received, so only the on-date iteration is unmatched
        links = (
            OperationLink(
                operation_unique_id=1,
                target_type=LinkType.PLANNED_OPERATION,
                target_id=1,
                iteration_date=date(2022, 12, 26),
            ),
        )
        actualizer = ForecastActualizer(account_on_due_date, operation_links=links)
        actualized_forecast = actualizer(forecast)
        # Postponed one-time op tomorrow + periodic continuation next month
        assert len(actualized_forecast.operations) == 2
        postponed_op = actualized_forecast.operations[0]
        assert isinstance(postponed_op.date_range, SingleDay)
        assert postponed_op.date_range.start_date == date(2023, 1, 27)
        periodic_op = actualized_forecast.operations[1]
        assert periodic_op.date_range.start_date == date(2023, 2, 26)

    def test_future_operation_without_links_is_kept(self, account: Account) -> None:
        """
        A planned operation in the future without links is kept as-is.
        """
        forecast = Forecast(
            operations=(
                PlannedOperation(
                    record_id=1,
                    description="Future Operation",
                    amount=Amount(100.0, "EUR"),
                    category=Category.OTHER,
                    date_range=SingleDay(date(2023, 1, 5)),
                ),
            ),
            budgets=(),
        )
        actualizer = ForecastActualizer(account)
        actualized_forecast = actualizer(forecast)
        assert len(actualized_forecast.operations) == 1
        op = actualized_forecast.operations[0]
        assert op.date_range.start_date == date(2023, 1, 5)

    def test_budget_without_links_is_not_consumed(self, account: Account) -> None:
        """
        A budget without links is not consumed by operations, even if they match
        by category. The budget amount stays intact.
        """
        forecast = Forecast(
            operations=(),
            budgets=(
                Budget(
                    record_id=1,
                    description="Groceries Budget",
                    amount=Amount(100.0, "EUR"),
                    category=Category.GROCERIES,
                    date_range=DateRange(date(2023, 1, 1), relativedelta(months=1)),
                ),
            ),
        )
        actualizer = ForecastActualizer(account)
        actualized_forecast = actualizer(forecast)
        assert len(actualized_forecast.budgets) == 1
        budget = actualized_forecast.budgets[0]
        # Budget is NOT consumed without links
        assert budget.amount == 100.0
        # But the time range is adjusted to start from tomorrow
        assert budget.date_range.start_date == date(2023, 1, 2)

    def test_expired_budget_is_discarded(self, account: Account) -> None:
        """An expired budget is discarded regardless of links."""
        forecast = Forecast(
            operations=(),
            budgets=(
                Budget(
                    record_id=1,
                    description="Expired Budget",
                    amount=Amount(100.0, "EUR"),
                    category=Category.GROCERIES,
                    date_range=DateRange(date(2022, 12, 31), relativedelta(days=1)),
                ),
            ),
        )
        actualizer = ForecastActualizer(account)
        actualized_forecast = actualizer(forecast)
        assert not actualized_forecast.budgets

    def test_future_budget_without_links_is_kept(self, account: Account) -> None:
        """A future budget without links is kept as-is."""
        forecast = Forecast(
            operations=(),
            budgets=(
                Budget(
                    record_id=1,
                    description="Future Budget",
                    amount=Amount(100.0, "EUR"),
                    category=Category.GROCERIES,
                    date_range=DateRange(date(2023, 2, 1), relativedelta(months=1)),
                ),
            ),
        )
        actualizer = ForecastActualizer(account)
        actualized_forecast = actualizer(forecast)
        assert len(actualized_forecast.budgets) == 1
        budget = actualized_forecast.budgets[0]
        assert budget.amount == 100.0
        assert budget.date_range.start_date == date(2023, 2, 1)


class TestForecastActualizerWithLinks:
    """Tests for ForecastActualizer using operation links as source of truth."""

    def test_planned_operation_with_linked_iterations_no_late(
        self, account: Account
    ) -> None:
        """
        When all iterations in the approximation window have links, there are no
        late iterations, and the planned operation advances normally.
        """
        planned_op = PlannedOperation(
            record_id=1,
            description="Linked Operation",
            amount=Amount(50.0, "EUR"),
            category=Category.GROCERIES,
            date_range=RecurringDay(date(2022, 12, 27), relativedelta(days=1)),
        )

        # Link every past iteration: Dec 27-31 plus the one on balance_date (Jan 1)
        links = tuple(
            OperationLink(
                operation_unique_id=i,
                target_type=LinkType.PLANNED_OPERATION,
                target_id=1,
                iteration_date=iteration_date,
                is_manual=False,
            )
            for i, iteration_date in enumerate(
                (
                    date(2022, 12, 27),
                    date(2022, 12, 28),
                    date(2022, 12, 29),
                    date(2022, 12, 30),
                    date(2022, 12, 31),
                    date(2023, 1, 1),
                ),
                start=1,
            )
        )

        forecast = Forecast(operations=(planned_op,), budgets=())
        actualizer = ForecastActualizer(account, operation_links=links)
        actualized_forecast = actualizer(forecast)

        # Every past iteration is matched, so none is late:
        # the operation advances to Jan 2 (next after the last linked Jan 1)
        assert len(actualized_forecast.operations) == 1
        op = actualized_forecast.operations[0]
        assert op.date_range.start_date == date(2023, 1, 2)

    def test_missing_links_in_window_are_late(self, account: Account) -> None:
        """
        Every past iteration without a link is late and counted the day after the
        balance date, whatever its distance from the matcher tolerance.
        """
        planned_op = PlannedOperation(
            record_id=2,
            description="Partially Linked Operation",
            amount=Amount(100.0, "EUR"),
            category=Category.OTHER,
            date_range=RecurringDay(date(2022, 12, 25), relativedelta(days=1)),
        )

        # Link only Dec 28, leaving Dec 25-27 and Dec 29 to Jan 1 unmatched
        links = (
            OperationLink(
                operation_unique_id=10,
                target_type=LinkType.PLANNED_OPERATION,
                target_id=2,
                iteration_date=date(2022, 12, 28),
                is_manual=True,
            ),
        )

        forecast = Forecast(operations=(planned_op,), budgets=())
        actualizer = ForecastActualizer(account, operation_links=links)
        actualized_forecast = actualizer(forecast)

        # Seven unmatched iterations, each counted on Jan 2, plus the daily
        # recurrence continuing from Jan 3
        assert len(actualized_forecast.operations) == 8

        *late_ops, periodic_op = actualized_forecast.operations
        for op in late_ops:
            assert isinstance(op.date_range, SingleDay)
            assert op.date_range.start_date == date(2023, 1, 2)

        # Jan 2 is itself a daily iteration, so the recurrence resumes there
        assert periodic_op.date_range.start_date == date(2023, 1, 2)

    def test_budget_with_linked_operations(self, account: Account) -> None:
        """
        When operation links exist for a budget, only linked operations
        consume the budget amount.
        """
        # Account with multiple operations
        account_with_ops = account._replace(
            operations=(
                HistoricOperation(
                    unique_id=1,
                    description="Linked Expense",
                    amount=Amount(30.0, "EUR"),
                    category=Category.GROCERIES,
                    operation_date=date(2023, 1, 1),
                ),
                HistoricOperation(
                    unique_id=2,
                    description="Unlinked Expense",
                    amount=Amount(40.0, "EUR"),
                    category=Category.GROCERIES,
                    operation_date=date(2023, 1, 1),
                ),
            )
        )

        budget = Budget(
            record_id=1,
            description="Groceries Budget",
            amount=Amount(100.0, "EUR"),
            category=Category.GROCERIES,
            date_range=DateRange(date(2023, 1, 1), relativedelta(months=1)),
        )

        # Only link operation 1 to the budget
        links = (
            OperationLink(
                operation_unique_id=1,
                target_type=LinkType.BUDGET,
                target_id=1,
                iteration_date=date(2023, 1, 1),
                is_manual=False,
            ),
        )

        forecast = Forecast(operations=(), budgets=(budget,))
        actualizer = ForecastActualizer(account_with_ops, operation_links=links)
        actualized_forecast = actualizer(forecast)

        # Only the linked 30 EUR operation should be consumed, leaving 70 EUR
        assert len(actualized_forecast.budgets) == 1
        updated_budget = actualized_forecast.budgets[0]
        assert updated_budget.amount == 70.0

    def test_link_to_future_iteration_with_past_operation_is_actualized(
        self, account: Account
    ) -> None:
        """
        When an operation that already happened is linked to a future iteration,
        the iteration is considered actualized (the user manually linked them).
        """
        planned_op = PlannedOperation(
            record_id=1,
            description="Future Linked Operation",
            amount=Amount(50.0, "EUR"),
            category=Category.GROCERIES,
            # Starts after balance_date (Jan 1) so the on-date late path doesn't
            # apply; this isolates the future-link actualization behavior
            date_range=RecurringDay(date(2023, 1, 2), relativedelta(days=1)),
        )

        # Link operation 1 (which happened Jan 1) to future iteration Jan 5
        # Since the operation already happened, the iteration is actualized
        links = (
            OperationLink(
                operation_unique_id=1,  # Operation date is Jan 1 (from fixture)
                target_type=LinkType.PLANNED_OPERATION,
                target_id=1,
                iteration_date=date(2023, 1, 5),
                is_manual=True,
            ),
        )

        forecast = Forecast(operations=(planned_op,), budgets=())
        actualizer = ForecastActualizer(account, operation_links=links)
        actualized_forecast = actualizer(forecast)

        # The iteration is actualized because the linked operation already happened
        assert len(actualized_forecast.operations) == 1
        op = actualized_forecast.operations[0]
        # Advances to Jan 6 (day after the actualized iteration Jan 5)
        assert op.date_range.start_date == date(2023, 1, 6)

    def test_links_without_matching_planned_operation_id_are_ignored(
        self, account: Account
    ) -> None:
        """
        Links for non-existent planned operation IDs are ignored.
        The planned operation without matching links is treated as having no links.
        """
        planned_op = PlannedOperation(
            record_id=5,
            description="Unrelated Operation",
            amount=Amount(200.0, "EUR"),
            category=Category.OTHER,
            date_range=SingleDay(date(2023, 1, 2)),
        )

        # Links for a different planned operation ID
        links = (
            OperationLink(
                operation_unique_id=1,
                target_type=LinkType.PLANNED_OPERATION,
                target_id=999,  # Different ID
                iteration_date=date(2023, 1, 1),
                is_manual=False,
            ),
        )

        forecast = Forecast(operations=(planned_op,), budgets=())
        actualizer = ForecastActualizer(account, operation_links=links)
        actualized_forecast = actualizer(forecast)

        # The planned operation is future, so it's kept as-is
        assert len(actualized_forecast.operations) == 1
        assert actualized_forecast.operations[0].description == "Unrelated Operation"
        assert actualized_forecast.operations[0].date_range.start_date == date(
            2023, 1, 2
        )

    def test_budget_links_from_other_iterations_do_not_consume_current_budget(
        self, account: Account
    ) -> None:
        """
        Regression test: Budget links are indexed by (budget_id, iteration_date).
        Operations linked to a different iteration should not consume the current
        month's budget.
        """
        # Account with balance_date in January
        account_jan = account._replace(
            balance_date=date(2023, 1, 15),
            operations=(
                # Operation from December, linked to December's budget iteration
                HistoricOperation(
                    unique_id=1,
                    description="December Groceries",
                    amount=Amount(-200.0, "EUR"),
                    category=Category.GROCERIES,
                    operation_date=date(2022, 12, 15),
                ),
                # Operation from January, linked to January's budget iteration
                HistoricOperation(
                    unique_id=2,
                    description="January Groceries",
                    amount=Amount(-30.0, "EUR"),
                    category=Category.GROCERIES,
                    operation_date=date(2023, 1, 10),
                ),
            ),
        )

        # Monthly budget: -100 EUR per month
        budget = Budget(
            record_id=1,
            description="Groceries Budget",
            amount=Amount(-100.0, "EUR"),
            category=Category.GROCERIES,
            date_range=RecurringDateRange(
                DateRange(date(2022, 12, 1), relativedelta(months=1)),
                relativedelta(months=1),
            ),
        )

        # Links for both operations to the same budget, but different iterations
        links = (
            OperationLink(
                operation_unique_id=1,
                target_type=LinkType.BUDGET,
                target_id=1,
                iteration_date=date(2022, 12, 1),  # December iteration
                is_manual=False,
            ),
            OperationLink(
                operation_unique_id=2,
                target_type=LinkType.BUDGET,
                target_id=1,
                iteration_date=date(2023, 1, 1),  # January iteration
                is_manual=False,
            ),
        )

        forecast = Forecast(operations=(), budgets=(budget,))
        actualizer = ForecastActualizer(account_jan, operation_links=links)
        actualized_forecast = actualizer(forecast)

        # January's budget should only be consumed by January's operation (-30)
        # leaving -70 EUR remaining, NOT -100 + 200 + 30 = +130 (if all ops consumed)
        january_budgets = [
            b for b in actualized_forecast.budgets if b.date_range.start_date.month == 1
        ]
        assert len(january_budgets) == 1
        assert january_budgets[0].amount == -70.0  # -100 - (-30) = -70


class TestForecastActualizerGaps:
    """Additional tests covering remaining uncovered paths."""

    def test_planned_operation_without_record_id_is_kept(
        self, account: Account
    ) -> None:
        """A planned operation without a record_id is returned unchanged."""
        forecast = Forecast(
            operations=(
                PlannedOperation(
                    record_id=None,
                    description="No ID Operation",
                    amount=Amount(50.0, "EUR"),
                    category=Category.GROCERIES,
                    date_range=SingleDay(date(2023, 1, 5)),
                ),
            ),
            budgets=(),
        )
        planned_op = forecast.operations[0]
        actualizer = ForecastActualizer(account)
        actualized_forecast = actualizer(forecast)
        assert actualized_forecast.operations == (planned_op,)

    def test_one_time_planned_operation_fully_actualized_is_removed(
        self, account: Account
    ) -> None:
        """A one-time planned operation with all iterations actualized is removed."""
        forecast = Forecast(
            operations=(
                PlannedOperation(
                    record_id=1,
                    description="One-time Past",
                    amount=Amount(50.0, "EUR"),
                    category=Category.GROCERIES,
                    date_range=SingleDay(date(2023, 1, 1)),
                ),
            ),
            budgets=(),
        )
        links = (
            OperationLink(
                operation_unique_id=1,
                target_type=LinkType.PLANNED_OPERATION,
                target_id=1,
                iteration_date=date(2023, 1, 1),
                is_manual=False,
            ),
        )
        actualizer = ForecastActualizer(account, operation_links=links)
        actualized_forecast = actualizer(forecast)
        # One-time operation fully actualized: no next period, removed
        assert not actualized_forecast.operations

    def test_budget_link_to_missing_operation_is_ignored(
        self, account: Account
    ) -> None:
        """Budget link pointing to a non-existent operation is ignored."""
        budget = Budget(
            record_id=1,
            description="Groceries Budget",
            amount=Amount(-100.0, "EUR"),
            category=Category.GROCERIES,
            date_range=DateRange(date(2023, 1, 1), relativedelta(months=1)),
        )
        # Link references an operation ID that doesn't exist in the account
        links = (
            OperationLink(
                operation_unique_id=999,
                target_type=LinkType.BUDGET,
                target_id=1,
                iteration_date=date(2023, 1, 1),
                is_manual=False,
            ),
        )
        forecast = Forecast(operations=(), budgets=(budget,))
        actualizer = ForecastActualizer(account, operation_links=links)
        actualized_forecast = actualizer(forecast)
        # Budget amount is unchanged (link was ignored)
        assert len(actualized_forecast.budgets) == 1
        assert actualized_forecast.budgets[0].amount == budget.amount

    def test_budget_link_with_sign_mismatch_is_ignored(self, account: Account) -> None:
        """Budget link where operation sign mismatches budget sign is ignored."""
        # Account has a positive operation
        account_with_positive_op = account._replace(
            operations=(
                HistoricOperation(
                    unique_id=1,
                    description="Positive Op",
                    amount=Amount(50.0, "EUR"),
                    category=Category.GROCERIES,
                    operation_date=date(2023, 1, 1),
                ),
            )
        )
        budget = Budget(
            record_id=1,
            description="Expense Budget",
            amount=Amount(-100.0, "EUR"),
            category=Category.GROCERIES,
            date_range=DateRange(date(2023, 1, 1), relativedelta(months=1)),
        )
        # Link positive operation to negative budget
        links = (
            OperationLink(
                operation_unique_id=1,
                target_type=LinkType.BUDGET,
                target_id=1,
                iteration_date=date(2023, 1, 1),
                is_manual=False,
            ),
        )
        forecast = Forecast(operations=(), budgets=(budget,))
        actualizer = ForecastActualizer(account_with_positive_op, operation_links=links)
        actualized_forecast = actualizer(forecast)
        # Budget amount is unchanged (sign mismatch, link was ignored)
        assert len(actualized_forecast.budgets) == 1
        assert actualized_forecast.budgets[0].amount == budget.amount

    def test_budget_fully_consumed_is_removed(self, account: Account) -> None:
        """A budget fully consumed by linked operations is removed."""
        account_with_ops = account._replace(
            operations=(
                HistoricOperation(
                    unique_id=1,
                    description="Full Expense",
                    amount=Amount(-100.0, "EUR"),
                    category=Category.GROCERIES,
                    operation_date=date(2023, 1, 1),
                ),
            )
        )
        budget = Budget(
            record_id=1,
            description="Groceries Budget",
            amount=Amount(-100.0, "EUR"),
            category=Category.GROCERIES,
            date_range=DateRange(date(2023, 1, 1), relativedelta(months=1)),
        )
        links = (
            OperationLink(
                operation_unique_id=1,
                target_type=LinkType.BUDGET,
                target_id=1,
                iteration_date=date(2023, 1, 1),
                is_manual=False,
            ),
        )
        forecast = Forecast(operations=(), budgets=(budget,))
        actualizer = ForecastActualizer(account_with_ops, operation_links=links)
        actualized_forecast = actualizer(forecast)
        # Budget fully consumed: removed
        assert not actualized_forecast.budgets

    def test_budget_ending_at_balance_date_is_removed_after_actualization(
        self, account: Account
    ) -> None:
        """Budget whose last_date equals balance_date is removed after actualization.

        After actualization, new_budget_start = balance_date + 1 day which is
        past the budget's last_date, so the budget is discarded.
        """
        budget = Budget(
            record_id=1,
            description="Ending Budget",
            amount=Amount(-50.0, "EUR"),
            category=Category.GROCERIES,
            # Budget from Jan 1 for 1 day: last_date = Jan 1 = balance_date
            date_range=DateRange(date(2023, 1, 1), relativedelta(days=1)),
        )
        forecast = Forecast(operations=(), budgets=(budget,))
        actualizer = ForecastActualizer(account)
        actualized_forecast = actualizer(forecast)
        # new_budget_start (Jan 2) > last_date (Jan 1): removed
        assert not actualized_forecast.budgets

    def test_future_iteration_with_link_to_unknown_operation_not_actualized(
        self, account: Account
    ) -> None:
        """A future iteration linked to a non-existent operation is not actualized."""
        planned_op = PlannedOperation(
            record_id=1,
            description="Monthly Op",
            amount=Amount(50.0, "EUR"),
            category=Category.GROCERIES,
            date_range=RecurringDay(date(2022, 12, 1), relativedelta(months=1)),
        )
        # Link references a non-existent operation for a future iteration
        links = (
            OperationLink(
                operation_unique_id=999,  # Not in account
                target_type=LinkType.PLANNED_OPERATION,
                target_id=1,
                iteration_date=date(2023, 1, 5),  # Future
                is_manual=True,
            ),
            # December was matched, leaving only the on-date iteration pending
            OperationLink(
                operation_unique_id=1,
                target_type=LinkType.PLANNED_OPERATION,
                target_id=1,
                iteration_date=date(2022, 12, 1),
            ),
        )
        forecast = Forecast(operations=(planned_op,), budgets=())
        actualizer = ForecastActualizer(account, operation_links=links)
        actualized_forecast = actualizer(forecast)
        # The future link is not actualized (op 999 doesn't exist). The monthly
        # iteration on balance_date (Jan 1) is pending: postponed to Jan 2, then
        # the periodic operation continues from Feb 1.
        assert len(actualized_forecast.operations) == 2
        postponed_op = actualized_forecast.operations[0]
        assert isinstance(postponed_op.date_range, SingleDay)
        assert postponed_op.date_range.start_date == date(2023, 1, 2)
        periodic_op = actualized_forecast.operations[1]
        assert periodic_op.date_range.start_date == date(2023, 2, 1)
