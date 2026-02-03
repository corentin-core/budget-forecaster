"""Module for the planned operation class."""

from datetime import datetime, timedelta
from typing import Any

from dateutil.relativedelta import relativedelta

from budget_forecaster.amount import Amount
from budget_forecaster.operation_range.forecast_operation_range import (
    ForecastOperationRange,
)
from budget_forecaster.time_range import (
    DailyTimeRange,
    PeriodicDailyTimeRange,
    TimeRangeInterface,
)
from budget_forecaster.types import Category


class PlannedOperation(ForecastOperationRange):
    """
    A planned operation is a financial operation that is expected to happen.
    It can be a recurring or a one-time operation.
    A negative amount means an expense, a positive amount means an income.
    """

    def __init__(
        self,
        record_id: int | None,
        description: str,
        amount: Amount,
        category: Category,
        time_range: TimeRangeInterface,
    ):
        if not isinstance(time_range, (DailyTimeRange, PeriodicDailyTimeRange)):
            raise TypeError(
                f"time_range must be DailyTimeRange or PeriodicDailyTimeRange, "
                f"got {type(time_range)}"
            )
        super().__init__(
            record_id=record_id,
            description=description,
            amount=amount,
            category=category,
            time_range=time_range,
        )

    def set_matcher_params(
        self,
        description_hints: set[str] | None = None,
        approximation_date_range: timedelta = timedelta(days=5),
        approximation_amount_ratio: float = 0.05,
    ) -> "PlannedOperation":
        """Set the parameters used to match operations to the planned operation."""
        self.matcher.update_params(
            description_hints, approximation_date_range, approximation_amount_ratio
        )
        return self

    def split_at(
        self,
        date: datetime,
        new_amount: Amount | None = None,
        new_period: relativedelta | None = None,
    ) -> tuple["PlannedOperation", "PlannedOperation"]:
        """Split this planned operation at the given date.

        Args:
            date: Date from which the new values apply.
            new_amount: New amount for continuation (if None, keeps original).
            new_period: New period for continuation (if None, keeps original).

        Returns:
            Tuple of (terminated, continuation) PlannedOperations.

        Raises:
            ValueError: If this operation is not periodic.
        """
        if not isinstance(self.time_range, PeriodicDailyTimeRange):
            raise ValueError("Cannot split a non-periodic planned operation")

        terminated_range, continuation_range = self.time_range.split_at(date)

        terminated = self.replace(time_range=terminated_range)

        amount = new_amount or Amount(self.amount, self.currency)
        time_range = (
            continuation_range.replace(period=new_period)
            if new_period
            else continuation_range
        )
        continuation = PlannedOperation(
            record_id=None,
            description=self.description,
            amount=amount,
            category=self.category,
            time_range=time_range,
        ).set_matcher_params(
            description_hints=self.matcher.description_hints,
            approximation_date_range=self.matcher.approximation_date_range,
            approximation_amount_ratio=self.matcher.approximation_amount_ratio,
        )

        return terminated, continuation

    def replace(self, **kwargs: Any) -> "PlannedOperation":
        """Return a new instance of the planned operation with the given parameters replaced."""
        new_id = kwargs.get("record_id", self.id)
        if new_id is not None and not isinstance(new_id, int):
            raise TypeError(f"record_id must be int or None, got {type(new_id)}")
        new_description = kwargs.get("description", self.description)
        if not isinstance(new_description, str):
            raise TypeError(f"description must be str, got {type(new_description)}")
        new_amount = kwargs.get("amount", Amount(self.amount, self.currency))
        if not isinstance(new_amount, Amount):
            raise TypeError(f"amount must be Amount, got {type(new_amount)}")
        new_category = kwargs.get("category", self.category)
        if not isinstance(new_category, Category):
            raise TypeError(f"category must be Category, got {type(new_category)}")
        new_time_range = kwargs.get("time_range", self.time_range)
        if not isinstance(new_time_range, (DailyTimeRange, PeriodicDailyTimeRange)):
            raise TypeError(
                f"time_range must be DailyTimeRange or PeriodicDailyTimeRange, "
                f"got {type(new_time_range)}"
            )
        return PlannedOperation(
            record_id=new_id,
            description=new_description,
            amount=new_amount,
            category=new_category,
            time_range=new_time_range,
        ).set_matcher_params(
            description_hints=self.matcher.description_hints,
            approximation_date_range=self.matcher.approximation_date_range,
            approximation_amount_ratio=self.matcher.approximation_amount_ratio,
        )
