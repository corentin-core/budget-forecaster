"""Module for the budget class."""

import math
from datetime import timedelta
from typing import Any

from budget_forecaster.amount import Amount
from budget_forecaster.operation_range.forecast_operation_range import (
    ForecastOperationRange,
)
from budget_forecaster.time_range import TimeRangeInterface
from budget_forecaster.types import Category


class Budget(ForecastOperationRange):
    """
    A budget is an amount of money allocated to a category over a period of time.
    It can be periodic or not.
    """

    def __init__(
        self,
        record_id: int,
        description: str,
        amount: Amount,
        category: Category,
        time_range: TimeRangeInterface,
    ):
        super().__init__(record_id, description, amount, category, time_range)
        # Only operations strictly in the budget time range will be considered
        # However they can have any amount
        self.set_matcher_params(
            approximation_date_range=timedelta(), approximation_amount_ratio=math.inf
        )

    def set_matcher_params(
        self,
        description_hints: set[str] | None = None,
        approximation_date_range: timedelta = timedelta(),
        approximation_amount_ratio: float = math.inf,
    ) -> "Budget":
        """Set the parameters used to match operations to the budget."""
        self.matcher.update_params(
            description_hints, approximation_date_range, approximation_amount_ratio
        )
        return self

    def replace(self, **kwargs: Any) -> "Budget":
        """Return a new instance of the planned operation with the given parameters replaced."""
        new_id = kwargs.get("record_id", self.id)
        assert isinstance(new_id, int), "record_id should be an int"
        new_description = kwargs.get("description", self.description)
        assert isinstance(new_description, str), "description should be a string"
        new_amount = kwargs.get("amount", Amount(self.amount, self.currency))
        assert isinstance(new_amount, Amount), "amount should be an Amount"
        new_category = kwargs.get("category", self.category)
        assert isinstance(new_category, Category), "category should be a Category"
        new_time_range = kwargs.get("time_range", self.time_range)
        assert isinstance(
            new_time_range, TimeRangeInterface
        ), "time_range should be a TimeRangeInterface"
        return Budget(
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
