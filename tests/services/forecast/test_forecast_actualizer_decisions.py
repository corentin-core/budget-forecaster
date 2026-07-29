"""How the user's decisions and the advance floor shape the actualized forecast."""
# pylint: disable=too-few-public-methods
from datetime import date

import pytest
from dateutil.relativedelta import relativedelta

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.date_range import RecurringDay, SingleDay
from budget_forecaster.core.types import Category, IterationAction, LinkType
from budget_forecaster.domain.account.account import Account
from budget_forecaster.domain.forecast.forecast import Forecast
from budget_forecaster.domain.operation.historic_operation import HistoricOperation
from budget_forecaster.domain.operation.iteration_resolution import IterationResolution
from budget_forecaster.domain.operation.operation_link import OperationLink
from budget_forecaster.domain.operation.planned_operation import PlannedOperation
from budget_forecaster.services.forecast.forecast_actualizer import ForecastActualizer


@pytest.fixture(name="account")
def account_fixture() -> Account:
    """An account whose balance stops on 2023-01-01."""
    return Account(
        name="Test Account",
        balance=1000.0,
        currency="EUR",
        balance_date=date(2023, 1, 1),
        operations=(),
    )


class TestForecastActualizerWithResolutions:
    """The user's decisions on late iterations drive the forecast."""

    @staticmethod
    def _monthly_op() -> PlannedOperation:
        """A monthly expense whose December iteration is late on Jan 1."""
        return PlannedOperation(
            record_id=1,
            description="Subscription",
            amount=Amount(-20.0, "EUR"),
            category=Category.OTHER,
            date_range=RecurringDay(date(2022, 12, 20), relativedelta(months=1)),
        )

    def test_skipped_iteration_is_not_counted(self, account: Account) -> None:
        """Only the recurrence carries on; the missed period is gone."""
        forecast = Forecast(operations=(self._monthly_op(),), budgets=())
        actualizer = ForecastActualizer(
            account,
            iteration_resolutions=(
                IterationResolution(
                    planned_operation_id=1,
                    iteration_date=date(2022, 12, 20),
                    action=IterationAction.SKIP,
                ),
            ),
        )
        actualized_forecast = actualizer(forecast)
        (periodic_op,) = actualized_forecast.operations
        assert periodic_op.date_range.start_date == date(2023, 1, 20)

    def test_postponed_iteration_lands_on_the_chosen_date(
        self, account: Account
    ) -> None:
        """The forecast counts the amount where the user moved it."""
        forecast = Forecast(operations=(self._monthly_op(),), budgets=())
        actualizer = ForecastActualizer(
            account,
            iteration_resolutions=(
                IterationResolution(
                    planned_operation_id=1,
                    iteration_date=date(2022, 12, 20),
                    action=IterationAction.POSTPONE,
                    postponed_to=date(2023, 1, 10),
                ),
            ),
        )
        actualized_forecast = actualizer(forecast)
        postponed_op, periodic_op = actualized_forecast.operations
        assert isinstance(postponed_op.date_range, SingleDay)
        assert postponed_op.date_range.start_date == date(2023, 1, 10)
        assert periodic_op.date_range.start_date == date(2023, 1, 20)

    def test_a_link_overrides_a_decision(self, account: Account) -> None:
        """An operation turned up, so the iteration is settled, not skipped."""
        forecast = Forecast(operations=(self._monthly_op(),), budgets=())
        links = (
            OperationLink(
                operation_unique_id=1,
                target_type=LinkType.PLANNED_OPERATION,
                target_id=1,
                iteration_date=date(2022, 12, 20),
            ),
        )
        actualizer = ForecastActualizer(
            account,
            operation_links=links,
            iteration_resolutions=(
                IterationResolution(
                    planned_operation_id=1,
                    iteration_date=date(2022, 12, 20),
                    action=IterationAction.POSTPONE,
                    postponed_to=date(2023, 1, 10),
                ),
            ),
        )
        actualized_forecast = actualizer(forecast)
        (periodic_op,) = actualized_forecast.operations
        assert periodic_op.date_range.start_date == date(2023, 1, 20)

    def test_skipping_the_only_iteration_of_a_one_time_operation_removes_it(
        self, account: Account
    ) -> None:
        """Nothing is left to forecast."""
        forecast = Forecast(
            operations=(
                PlannedOperation(
                    record_id=1,
                    description="Cancelled repair",
                    amount=Amount(-300.0, "EUR"),
                    category=Category.HOUSE_WORKS,
                    date_range=SingleDay(date(2022, 12, 15)),
                ),
            ),
            budgets=(),
        )
        actualizer = ForecastActualizer(
            account,
            iteration_resolutions=(
                IterationResolution(
                    planned_operation_id=1,
                    iteration_date=date(2022, 12, 15),
                    action=IterationAction.SKIP,
                ),
            ),
        )
        assert not actualizer(forecast).operations


class TestForecastActualizerAdvance:
    """Where the recurrence resumes after unmatched past iterations."""

    def test_iteration_due_the_day_after_the_balance_date_is_kept(
        self, account: Account
    ) -> None:
        """The late one lands there too, but the natural one is a separate amount.

        Resuming strictly after balance_date + 1 used to swallow it, so recovering
        the late iteration cost the next one and the forecast was unchanged.
        """
        rent = PlannedOperation(
            record_id=1,
            description="Rent",
            amount=Amount(-850.0, "EUR"),
            category=Category.RENT,
            date_range=RecurringDay(date(2022, 12, 2), relativedelta(months=1)),
        )
        # Balance date Jan 1, so the January iteration falls on Jan 2
        actualizer = ForecastActualizer(account)
        actualized_forecast = actualizer(Forecast(operations=(rent,), budgets=()))

        late_op, periodic_op = actualized_forecast.operations
        assert isinstance(late_op.date_range, SingleDay)
        assert late_op.date_range.start_date == date(2023, 1, 2)
        assert periodic_op.date_range.start_date == date(2023, 1, 2)
        total = sum(
            op.amount_on_period(date(2023, 1, 1), date(2023, 2, 28))
            for op in actualized_forecast.operations
        )
        assert total == pytest.approx(-2550.0)

    def test_a_future_iteration_paid_early_is_not_forecast_again(
        self, account: Account
    ) -> None:
        """An operation posted before its planned date settles that iteration.

        The late branch must not advance blindly past the balance date, or the
        already-received amount is projected a second time.
        """
        salary_paid_early = HistoricOperation(
            unique_id=10,
            description="SALARY",
            amount=Amount(3000.0, "EUR"),
            category=Category.SALARY,
            operation_date=date(2022, 12, 30),
        )
        account_with_early_pay = account._replace(
            operations=(salary_paid_early,), balance_date=date(2023, 1, 1)
        )
        salary = PlannedOperation(
            record_id=1,
            description="Monthly Salary",
            amount=Amount(3000.0, "EUR"),
            category=Category.SALARY,
            date_range=RecurringDay(date(2022, 12, 5), relativedelta(months=1)),
        )
        links = (
            OperationLink(
                operation_unique_id=10,
                target_type=LinkType.PLANNED_OPERATION,
                target_id=1,
                iteration_date=date(2023, 1, 5),
                is_manual=True,
            ),
        )
        actualizer = ForecastActualizer(account_with_early_pay, operation_links=links)
        actualized_forecast = actualizer(Forecast(operations=(salary,), budgets=()))

        # December is late (counted Jan 2); January was paid early, so the
        # recurrence resumes in February
        late_op, periodic_op = actualized_forecast.operations
        assert late_op.date_range.start_date == date(2023, 1, 2)
        assert periodic_op.date_range.start_date == date(2023, 2, 5)

    def test_iterations_older_than_the_horizon_are_left_out_of_the_walk(
        self, account: Account
    ) -> None:
        """The actualizer only needs what it may still count.

        Walking an operation's whole history would cost more the longer it has
        existed, and those iterations are not counted either way.
        """
        old_op = PlannedOperation(
            record_id=1,
            description="Old subscription",
            amount=Amount(-9.99, "EUR"),
            category=Category.ENTERTAINMENT,
            date_range=RecurringDay(date(2015, 1, 1), relativedelta(months=1)),
        )
        actualizer = ForecastActualizer(account)
        actualized_forecast = actualizer(Forecast(operations=(old_op,), budgets=()))

        # Only Dec 1 and Jan 1 fall inside the 31-day horizon, not the 96 monthly
        # iterations since 2015
        late_ops = [
            op
            for op in actualized_forecast.operations
            if isinstance(op.date_range, SingleDay)
        ]
        assert len(late_ops) == 2

    def test_a_decision_older_than_the_horizon_is_still_honoured(
        self, account: Account
    ) -> None:
        """The window bounds the search, never the user's decisions."""
        old_op = PlannedOperation(
            record_id=1,
            description="Deposit",
            amount=Amount(-300.0, "EUR"),
            category=Category.HOUSE_WORKS,
            date_range=SingleDay(date(2022, 6, 15)),
        )
        actualizer = ForecastActualizer(
            account,
            iteration_resolutions=(
                IterationResolution(
                    planned_operation_id=1,
                    iteration_date=date(2022, 6, 15),
                    action=IterationAction.POSTPONE,
                    postponed_to=date(2023, 2, 1),
                ),
            ),
        )
        actualized_forecast = actualizer(Forecast(operations=(old_op,), budgets=()))

        (postponed_op,) = actualized_forecast.operations
        assert postponed_op.date_range.start_date == date(2023, 2, 1)
