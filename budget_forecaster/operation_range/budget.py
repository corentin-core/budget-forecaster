"""Module for the budget class."""

import math
from datetime import datetime, timedelta
from typing import Any

from dateutil.relativedelta import relativedelta

from budget_forecaster.amount import Amount
from budget_forecaster.operation_range.operation_matcher import OperationMatcher
from budget_forecaster.operation_range.operation_range import OperationRange
from budget_forecaster.time_range import PeriodicTimeRange, TimeRangeInterface
from budget_forecaster.types import Category


class Budget(OperationRange):
    """
    A budget is an amount of money allocated to a category over a period of time.
    It can be periodic or not.
    """

    def __init__(
        self,
        record_id: int | None,
        description: str,
        amount: Amount,
        category: Category,
        time_range: TimeRangeInterface,
    ):
        super().__init__(description, amount, category, time_range)
        self._id = record_id
        self._operation_matcher = OperationMatcher(operation_range=self)
        # Only operations strictly in the budget time range will be considered
        # However they can have any amount
        self.set_matcher_params(
            approximation_date_range=timedelta(), approximation_amount_ratio=math.inf
        )

    @property
    def id(self) -> int | None:
        """The database ID of the budget. None if not persisted yet."""
        return self._id

    @property
    def matcher(self) -> OperationMatcher:
        """The operation matcher of the budget."""
        return self._operation_matcher

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

    def split_at(
        self,
        date: datetime,
        new_amount: Amount | None = None,
        new_period: relativedelta | None = None,
        new_duration: relativedelta | None = None,
    ) -> tuple["Budget", "Budget"]:
        """Split this budget at the given date.

        Args:
            date: Date from which the new values apply.
            new_amount: New amount for continuation (if None, keeps original).
            new_period: New period for continuation (if None, keeps original).
            new_duration: New duration for continuation (if None, keeps original).

        Returns:
            Tuple of (terminated, continuation) Budgets.

        Raises:
            ValueError: If this budget is not periodic.
        """
        if not isinstance(self.time_range, PeriodicTimeRange):
            raise ValueError("Cannot split a non-periodic budget")

        terminated_range, continuation_range = self.time_range.split_at(date)

        terminated = self.replace(time_range=terminated_range)

        amount = new_amount or Amount(self.amount, self.currency)
        time_range = continuation_range
        if new_period:
            time_range = time_range.replace(period=new_period)
        if new_duration:
            base_tr = time_range.base_time_range.replace(duration=new_duration)
            time_range = time_range.replace(initial_date=base_tr.initial_date)
            # Rebuild with new base time range
            time_range = PeriodicTimeRange(
                base_tr,
                time_range.period,
                time_range.last_date if time_range.last_date < datetime.max else None,
            )

        continuation = Budget(
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

    def replace(self, **kwargs: Any) -> "Budget":
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
        if not isinstance(new_time_range, TimeRangeInterface):
            raise TypeError(
                f"time_range must be TimeRangeInterface, got {type(new_time_range)}"
            )
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
