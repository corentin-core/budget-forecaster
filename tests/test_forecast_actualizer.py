"""Module with tests for the ForecastActualizer class."""
from datetime import datetime

import pytest
from dateutil.relativedelta import relativedelta

from budget_forecaster.account.account import Account
from budget_forecaster.amount import Amount
from budget_forecaster.forecast.forecast import Forecast
from budget_forecaster.forecast.forecast_actualizer import ForecastActualizer
from budget_forecaster.operation_range.budget import Budget
from budget_forecaster.operation_range.historic_operation import HistoricOperation
from budget_forecaster.operation_range.operation_link import LinkType, OperationLink
from budget_forecaster.operation_range.planned_operation import PlannedOperation
from budget_forecaster.time_range import (
    DailyTimeRange,
    PeriodicDailyTimeRange,
    PeriodicTimeRange,
    TimeRange,
)
from budget_forecaster.types import Category


@pytest.fixture
def account() -> Account:
    """Fixture with an account with one executed operation."""
    return Account(
        name="Test Account",
        balance=1000.0,
        currency="EUR",
        balance_date=datetime(2023, 1, 1),
        operations=(
            HistoricOperation(
                unique_id=1,
                description="Executed Operation",
                amount=Amount(50.0, "EUR"),
                category=Category.GROCERIES,
                date=datetime(2023, 1, 1),
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

    def test_one_time_past_operation_without_links_is_removed(
        self, account: Account
    ) -> None:
        """
        A one-time planned operation in the past/present without links is removed
        because there's no next period.
        """
        forecast = Forecast(
            operations=(
                PlannedOperation(
                    record_id=1,
                    description="Past Operation",
                    amount=Amount(50.0, "EUR"),
                    category=Category.GROCERIES,
                    time_range=DailyTimeRange(datetime(2023, 1, 1)),
                ),
            ),
            budgets=(),
        )
        actualizer = ForecastActualizer(account)
        actualized_forecast = actualizer(forecast)
        # One-time operation with no next period is removed
        assert not actualized_forecast.operations

    def test_periodic_past_operation_without_links_advances_to_next_period(
        self, account: Account
    ) -> None:
        """
        A periodic planned operation in the past without links advances to the
        next period after the balance date.
        """
        forecast = Forecast(
            operations=(
                PlannedOperation(
                    record_id=1,
                    description="Periodic Operation",
                    amount=Amount(100.0, "EUR"),
                    category=Category.OTHER,
                    time_range=PeriodicDailyTimeRange(
                        datetime(2022, 12, 1), relativedelta(days=1)
                    ),
                ),
            ),
            budgets=(),
        )
        actualizer = ForecastActualizer(account)
        actualized_forecast = actualizer(forecast)
        # Without links, operation advances to next period after balance_date
        assert len(actualized_forecast.operations) == 1
        op = actualized_forecast.operations[0]
        assert op.time_range.initial_date == datetime(2023, 1, 2)

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
                    time_range=DailyTimeRange(datetime(2023, 1, 5)),
                ),
            ),
            budgets=(),
        )
        actualizer = ForecastActualizer(account)
        actualized_forecast = actualizer(forecast)
        assert len(actualized_forecast.operations) == 1
        op = actualized_forecast.operations[0]
        assert op.time_range.initial_date == datetime(2023, 1, 5)

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
                    time_range=TimeRange(datetime(2023, 1, 1), relativedelta(months=1)),
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
        assert budget.time_range.initial_date == datetime(2023, 1, 2)

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
                    time_range=TimeRange(datetime(2022, 12, 31), relativedelta(days=1)),
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
                    time_range=TimeRange(datetime(2023, 2, 1), relativedelta(months=1)),
                ),
            ),
        )
        actualizer = ForecastActualizer(account)
        actualized_forecast = actualizer(forecast)
        assert len(actualized_forecast.budgets) == 1
        budget = actualized_forecast.budgets[0]
        assert budget.amount == 100.0
        assert budget.time_range.initial_date == datetime(2023, 2, 1)


class TestForecastActualizerWithLinks:
    """Tests for ForecastActualizer using operation links as source of truth."""

    def test_planned_operation_with_linked_iterations(self, account: Account) -> None:
        """
        When operation links exist for a planned operation, the linked iterations
        determine which iterations are considered executed.
        """
        planned_op = PlannedOperation(
            record_id=1,
            description="Linked Operation",
            amount=Amount(50.0, "EUR"),
            category=Category.GROCERIES,
            time_range=PeriodicDailyTimeRange(
                datetime(2022, 12, 1), relativedelta(days=1)
            ),
        )

        # Create links for 3 iterations (Dec 28, 29, 30)
        links = (
            OperationLink(
                operation_unique_id=1,
                target_type=LinkType.PLANNED_OPERATION,
                target_id=1,
                iteration_date=datetime(2022, 12, 28),
                is_manual=False,
            ),
            OperationLink(
                operation_unique_id=2,
                target_type=LinkType.PLANNED_OPERATION,
                target_id=1,
                iteration_date=datetime(2022, 12, 29),
                is_manual=False,
            ),
            OperationLink(
                operation_unique_id=3,
                target_type=LinkType.PLANNED_OPERATION,
                target_id=1,
                iteration_date=datetime(2022, 12, 30),
                is_manual=False,
            ),
        )

        forecast = Forecast(operations=(planned_op,), budgets=())
        actualizer = ForecastActualizer(account, operation_links=links)
        actualized_forecast = actualizer(forecast)

        # The planned operation should start after the last linked iteration (Dec 30)
        assert len(actualized_forecast.operations) == 1
        op = actualized_forecast.operations[0]
        assert op.time_range.initial_date == datetime(2022, 12, 31)

    def test_only_linked_iterations_are_marked_as_executed(
        self, account: Account
    ) -> None:
        """
        Only iterations explicitly linked to an operation are considered executed.
        The planned operation advances to the iteration after the last linked one.
        """
        # Create an operation linked to a specific iteration
        account_with_linked_op = account._replace(
            operations=(
                HistoricOperation(
                    unique_id=10,
                    description="Matching Operation",
                    amount=Amount(100.0, "EUR"),
                    category=Category.OTHER,
                    date=datetime(2023, 1, 1),
                ),
            )
        )

        planned_op = PlannedOperation(
            record_id=2,
            description="Matching Operation",
            amount=Amount(100.0, "EUR"),
            category=Category.OTHER,
            time_range=PeriodicDailyTimeRange(
                datetime(2022, 12, 25), relativedelta(days=1)
            ),
        )

        # Link only specifies Dec 28, so next iteration is Dec 29
        # Link only Dec 28 iteration, so next iteration is Dec 29
        links = (
            OperationLink(
                operation_unique_id=10,
                target_type=LinkType.PLANNED_OPERATION,
                target_id=2,
                iteration_date=datetime(2022, 12, 28),
                is_manual=True,
            ),
        )

        forecast = Forecast(operations=(planned_op,), budgets=())
        actualizer = ForecastActualizer(account_with_linked_op, operation_links=links)
        actualized_forecast = actualizer(forecast)

        # With links, only the linked iteration counts as executed
        assert len(actualized_forecast.operations) == 1
        op = actualized_forecast.operations[0]
        # Next iteration after Dec 28 is Dec 29
        assert op.time_range.initial_date == datetime(2022, 12, 29)

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
                    date=datetime(2023, 1, 1),
                ),
                HistoricOperation(
                    unique_id=2,
                    description="Unlinked Expense",
                    amount=Amount(40.0, "EUR"),
                    category=Category.GROCERIES,
                    date=datetime(2023, 1, 1),
                ),
            )
        )

        budget = Budget(
            record_id=1,
            description="Groceries Budget",
            amount=Amount(100.0, "EUR"),
            category=Category.GROCERIES,
            time_range=TimeRange(datetime(2023, 1, 1), relativedelta(months=1)),
        )

        # Only link operation 1 to the budget
        links = (
            OperationLink(
                operation_unique_id=1,
                target_type=LinkType.BUDGET,
                target_id=1,
                iteration_date=datetime(2023, 1, 1),
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
            time_range=PeriodicDailyTimeRange(
                datetime(2023, 1, 1), relativedelta(days=1)
            ),
        )

        # Link operation 1 (which happened Jan 1) to future iteration Jan 5
        # Since the operation already happened, the iteration is actualized
        links = (
            OperationLink(
                operation_unique_id=1,  # Operation date is Jan 1 (from fixture)
                target_type=LinkType.PLANNED_OPERATION,
                target_id=1,
                iteration_date=datetime(2023, 1, 5),
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
        assert op.time_range.initial_date == datetime(2023, 1, 6)

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
            time_range=DailyTimeRange(datetime(2023, 1, 2)),
        )

        # Links for a different planned operation ID
        links = (
            OperationLink(
                operation_unique_id=1,
                target_type=LinkType.PLANNED_OPERATION,
                target_id=999,  # Different ID
                iteration_date=datetime(2023, 1, 1),
                is_manual=False,
            ),
        )

        forecast = Forecast(operations=(planned_op,), budgets=())
        actualizer = ForecastActualizer(account, operation_links=links)
        actualized_forecast = actualizer(forecast)

        # The planned operation is future, so it's kept as-is
        assert len(actualized_forecast.operations) == 1
        assert actualized_forecast.operations[0].description == "Unrelated Operation"
        assert actualized_forecast.operations[0].time_range.initial_date == datetime(
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
            balance_date=datetime(2023, 1, 15),
            operations=(
                # Operation from December, linked to December's budget iteration
                HistoricOperation(
                    unique_id=1,
                    description="December Groceries",
                    amount=Amount(-200.0, "EUR"),
                    category=Category.GROCERIES,
                    date=datetime(2022, 12, 15),
                ),
                # Operation from January, linked to January's budget iteration
                HistoricOperation(
                    unique_id=2,
                    description="January Groceries",
                    amount=Amount(-30.0, "EUR"),
                    category=Category.GROCERIES,
                    date=datetime(2023, 1, 10),
                ),
            ),
        )

        # Monthly budget: -100 EUR per month
        budget = Budget(
            record_id=1,
            description="Groceries Budget",
            amount=Amount(-100.0, "EUR"),
            category=Category.GROCERIES,
            time_range=PeriodicTimeRange(
                TimeRange(datetime(2022, 12, 1), relativedelta(months=1)),
                relativedelta(months=1),
            ),
        )

        # Links for both operations to the same budget, but different iterations
        links = (
            OperationLink(
                operation_unique_id=1,
                target_type=LinkType.BUDGET,
                target_id=1,
                iteration_date=datetime(2022, 12, 1),  # December iteration
                is_manual=False,
            ),
            OperationLink(
                operation_unique_id=2,
                target_type=LinkType.BUDGET,
                target_id=1,
                iteration_date=datetime(2023, 1, 1),  # January iteration
                is_manual=False,
            ),
        )

        forecast = Forecast(operations=(), budgets=(budget,))
        actualizer = ForecastActualizer(account_jan, operation_links=links)
        actualized_forecast = actualizer(forecast)

        # January's budget should only be consumed by January's operation (-30)
        # leaving -70 EUR remaining, NOT -100 + 200 + 30 = +130 (if all ops consumed)
        january_budgets = [
            b
            for b in actualized_forecast.budgets
            if b.time_range.initial_date.month == 1
        ]
        assert len(january_budgets) == 1
        assert january_budgets[0].amount == -70.0  # -100 - (-30) = -70
