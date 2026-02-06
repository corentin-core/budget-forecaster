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
                    date_range=SingleDay(date(2023, 1, 1)),
                ),
            ),
            budgets=(),
        )
        actualizer = ForecastActualizer(account)
        actualized_forecast = actualizer(forecast)
        # One-time operation with no next period is removed
        assert not actualized_forecast.operations

    def test_periodic_past_operation_outside_tolerance_advances_to_next_period(
        self, account: Account
    ) -> None:
        """
        A periodic planned operation in the past, outside the tolerance window
        (more than 5 days before balance_date), advances to the next period.
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
        # Outside tolerance window: operation advances to next period
        assert len(actualized_forecast.operations) == 1
        op = actualized_forecast.operations[0]
        assert op.date_range.start_date == date(2023, 1, 20)

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
            date_range=RecurringDay(date(2022, 12, 1), relativedelta(days=1)),
        )

        # Create links for all iterations in the approximation window (Dec 27-31)
        # With balance_date Jan 1 and default approximation of 5 days
        links = (
            OperationLink(
                operation_unique_id=1,
                target_type=LinkType.PLANNED_OPERATION,
                target_id=1,
                iteration_date=date(2022, 12, 27),
                is_manual=False,
            ),
            OperationLink(
                operation_unique_id=2,
                target_type=LinkType.PLANNED_OPERATION,
                target_id=1,
                iteration_date=date(2022, 12, 28),
                is_manual=False,
            ),
            OperationLink(
                operation_unique_id=3,
                target_type=LinkType.PLANNED_OPERATION,
                target_id=1,
                iteration_date=date(2022, 12, 29),
                is_manual=False,
            ),
            OperationLink(
                operation_unique_id=4,
                target_type=LinkType.PLANNED_OPERATION,
                target_id=1,
                iteration_date=date(2022, 12, 30),
                is_manual=False,
            ),
            OperationLink(
                operation_unique_id=5,
                target_type=LinkType.PLANNED_OPERATION,
                target_id=1,
                iteration_date=date(2022, 12, 31),
                is_manual=False,
            ),
        )

        forecast = Forecast(operations=(planned_op,), budgets=())
        actualizer = ForecastActualizer(account, operation_links=links)
        actualized_forecast = actualizer(forecast)

        # All iterations in window have links, no late iterations
        # Operation advances to Jan 1 (next after last linked Dec 31)
        assert len(actualized_forecast.operations) == 1
        op = actualized_forecast.operations[0]
        assert op.date_range.start_date == date(2023, 1, 1)

    def test_missing_links_in_window_are_late(self, account: Account) -> None:
        """
        When some iterations in the approximation window have no links,
        they are considered late and postponed to balance_date + 1.
        """
        planned_op = PlannedOperation(
            record_id=2,
            description="Partially Linked Operation",
            amount=Amount(100.0, "EUR"),
            category=Category.OTHER,
            date_range=RecurringDay(date(2022, 12, 25), relativedelta(days=1)),
        )

        # Link only Dec 28, leaving Dec 27, 29, 30, 31 as late
        # (within the 5-day approximation window before Jan 1 balance_date)
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

        # Dec 27, 29, 30, 31 are late (4 iterations without links in window)
        # Each gets postponed to Jan 2, plus the periodic continuation from Jan 3
        assert len(actualized_forecast.operations) == 5

        # First 4 are postponed one-time operations
        for i in range(4):
            op = actualized_forecast.operations[i]
            assert op.date_range.start_date == date(2023, 1, 2)

        # Last one is the periodic continuation
        periodic_op = actualized_forecast.operations[4]
        assert periodic_op.date_range.start_date == date(2023, 1, 3)

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
            date_range=RecurringDay(date(2023, 1, 1), relativedelta(days=1)),
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
