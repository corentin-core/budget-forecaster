"""Module for the planned operation class."""

from datetime import timedelta
from typing import Any

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
        assert isinstance(
            time_range, (DailyTimeRange, PeriodicDailyTimeRange)
        ), "Only daily time ranges are supported."
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

    def replace(self, **kwargs: Any) -> "PlannedOperation":
        """Return a new instance of the planned operation with the given parameters replaced."""
        new_id = kwargs.get("record_id", self.id)
        assert new_id is None or isinstance(
            new_id, int
        ), "record_id should be an int or None"
        new_description = kwargs.get("description", self.description)
        assert isinstance(new_description, str), "description should be a string"
        new_amount = kwargs.get("amount", Amount(self.amount, self.currency))
        assert isinstance(new_amount, Amount), "amount should be an Amount"
        new_category = kwargs.get("category", self.category)
        assert isinstance(new_category, Category), "category should be a Category"
        new_time_range = kwargs.get("time_range", self.time_range)
        assert isinstance(
            new_time_range, (DailyTimeRange, PeriodicDailyTimeRange)
        ), "Only daily time ranges are supported."
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
