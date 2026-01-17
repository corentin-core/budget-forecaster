"""
Module forecasting the future state of an account and
reconstructing the past state of an account.
"""
import itertools
from datetime import datetime, timedelta
from typing import Final, Iterator

from budget_forecaster.account.account import Account
from budget_forecaster.amount import Amount
from budget_forecaster.forecast.forecast import Forecast
from budget_forecaster.operation_range.historic_operation import HistoricOperation
from budget_forecaster.operation_range.operation_range import OperationRangeInterface


class AccountForecaster:  # pylint: disable=too-few-public-methods
    """Forecasts the future state or reconstructs the past state of an account."""

    def __init__(self, account: Account, forecast: Forecast) -> None:
        self.__account: Final = account
        self.__forecast: Final = forecast
        self.__last_historic_identifier = max(
            (operation.unique_id for operation in self.__account.operations), default=0
        )

    def __get_new_historic_identifier(self) -> int:
        """Get a new unique identifier for historic operations."""
        self.__last_historic_identifier += 1
        return self.__last_historic_identifier

    def __get_past_state(self, target_date: datetime) -> Account:
        """Get the past state of the account at a certain date."""
        balance_date = self.__account.balance_date
        assert target_date <= balance_date

        past_balance = self.__account.balance
        past_operations: list[HistoricOperation] = []
        for operation in self.__account.operations:
            if target_date < operation.date <= balance_date:
                past_balance -= operation.amount
                continue

            past_operations.append(operation)

        return self.__account._replace(
            balance=past_balance,
            balance_date=target_date,
            operations=tuple(past_operations),
        )

    def __compute_operations(
        self, operation_range: OperationRangeInterface, target_date: datetime
    ) -> Iterator[HistoricOperation]:
        balance_date = self.__account.balance_date
        for time_range in operation_range.time_range.iterate_over_time_ranges(
            balance_date
        ):
            if time_range.is_future(target_date):
                break

            if time_range.is_expired(balance_date):
                continue

            amount_per_day = operation_range.amount / time_range.total_duration.days
            budget_start_date = max(
                time_range.initial_date, balance_date + timedelta(days=1)
            )
            budget_end_date = min(time_range.last_date, target_date)
            budget_current_date = budget_start_date
            while budget_current_date <= budget_end_date:
                yield HistoricOperation(
                    unique_id=self.__get_new_historic_identifier(),
                    description=operation_range.description,
                    amount=Amount(amount_per_day, operation_range.currency),
                    category=operation_range.category,
                    date=budget_current_date,
                )
                budget_current_date += timedelta(days=1)

    def __get_future_state(self, target_date: datetime) -> "Account":
        """Get the future state of the account at a certain date."""
        balance_date = self.__account.balance_date
        assert target_date >= balance_date
        # update balance and historic operations
        future_balance = self.__account.balance
        future_historic_operations: list[HistoricOperation] = list(
            self.__account.operations
        )

        for operation_range in itertools.chain(
            self.__forecast.operations, self.__forecast.budgets
        ):
            for future_operation in self.__compute_operations(
                operation_range, target_date
            ):
                future_historic_operations.append(future_operation)
                future_balance += future_operation.amount

        return self.__account._replace(
            balance=future_balance,
            balance_date=target_date,
            operations=tuple(future_historic_operations),
        )

    def __call__(self, target_date: datetime) -> Account:
        """Get the state of the account at a certain date."""
        balance_date = self.__account.balance_date
        if target_date == balance_date:
            return self.__account
        if target_date < balance_date:
            return self.__get_past_state(target_date)
        return self.__get_future_state(target_date)
