"""
Module forecasting the future state of an account and
reconstructing the past state of an account.
"""
import itertools
from datetime import date, timedelta
from typing import Final, Iterator

from budget_forecaster.core.amount import Amount
from budget_forecaster.domain.account.account import Account
from budget_forecaster.domain.forecast.forecast import Forecast
from budget_forecaster.domain.operation.historic_operation import HistoricOperation
from budget_forecaster.domain.operation.operation_range import OperationRangeInterface


class AccountForecaster:  # pylint: disable=too-few-public-methods
    """Forecasts the future state or reconstructs the past state of an account."""

    def __init__(self, account: Account, forecast: Forecast) -> None:
        self._account: Final = account
        self._forecast: Final = forecast
        self._last_historic_identifier = max(
            (operation.unique_id for operation in self._account.operations), default=0
        )

    def _get_new_historic_identifier(self) -> int:
        """Get a new unique identifier for historic operations."""
        self._last_historic_identifier += 1
        return self._last_historic_identifier

    def _get_past_state(self, target_date: date) -> Account:
        """Get the past state of the account at a certain date."""
        balance_date = self._account.balance_date
        if target_date > balance_date:  # pragma: no cover
            raise ValueError(
                f"target_date must be <= balance_date, got {target_date} > {balance_date}"
            )

        past_balance = self._account.balance
        past_operations: list[HistoricOperation] = []
        for operation in self._account.operations:
            if target_date < operation.operation_date <= balance_date:
                past_balance -= operation.amount
                continue

            past_operations.append(operation)

        return self._account._replace(
            balance=past_balance,
            balance_date=target_date,
            operations=tuple(past_operations),
        )

    def _compute_operations(
        self, operation_range: OperationRangeInterface, target_date: date
    ) -> Iterator[HistoricOperation]:
        balance_date = self._account.balance_date
        for dr in operation_range.date_range.iterate_over_date_ranges(balance_date):
            if dr.is_future(target_date):
                break

            if dr.is_expired(balance_date):
                continue

            amount_per_day = operation_range.amount / dr.total_duration.days
            budget_start_date = max(dr.start_date, balance_date + timedelta(days=1))
            budget_end_date = min(dr.last_date, target_date)
            budget_current_date = budget_start_date
            while budget_current_date <= budget_end_date:
                yield HistoricOperation(
                    unique_id=self._get_new_historic_identifier(),
                    description=operation_range.description,
                    amount=Amount(amount_per_day, operation_range.currency),
                    category=operation_range.category,
                    operation_date=budget_current_date,
                )
                budget_current_date += timedelta(days=1)

    def _get_future_state(self, target_date: date) -> "Account":
        """Get the future state of the account at a certain date."""
        balance_date = self._account.balance_date
        if target_date < balance_date:  # pragma: no cover
            raise ValueError(
                f"target_date must be >= balance_date, got {target_date} < {balance_date}"
            )
        # update balance and historic operations
        future_balance = self._account.balance
        future_historic_operations: list[HistoricOperation] = list(
            self._account.operations
        )

        for operation_range in itertools.chain(
            self._forecast.operations, self._forecast.budgets
        ):
            for future_operation in self._compute_operations(
                operation_range, target_date
            ):
                future_historic_operations.append(future_operation)
                future_balance += future_operation.amount

        return self._account._replace(
            balance=future_balance,
            balance_date=target_date,
            operations=tuple(future_historic_operations),
        )

    def __call__(self, target_date: date) -> Account:
        """Get the state of the account at a certain date."""
        balance_date = self._account.balance_date
        if target_date == balance_date:
            return self._account
        if target_date < balance_date:
            return self._get_past_state(target_date)
        return self._get_future_state(target_date)
