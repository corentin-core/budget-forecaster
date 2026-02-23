"""Module for the planned operation class."""

from datetime import date, timedelta
from typing import Any

from dateutil.relativedelta import relativedelta

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.date_range import (
    DateRangeInterface,
    RecurringDay,
    SingleDay,
)
from budget_forecaster.core.types import Category, PlannedOperationId
from budget_forecaster.domain.operation.operation_range import OperationRange
from budget_forecaster.services.operation.operation_matcher import OperationMatcher


class PlannedOperation(OperationRange):
    """
    A planned operation is a financial operation that is expected to happen.
    It can be a recurring or a one-time operation.
    A negative amount means an expense, a positive amount means an income.
    """

    def __init__(
        self,
        record_id: PlannedOperationId | None,
        description: str,
        amount: Amount,
        category: Category,
        date_range: DateRangeInterface,
        *,
        is_archived: bool = False,
    ):
        if not isinstance(date_range, (SingleDay, RecurringDay)):
            raise TypeError(
                f"date_range must be SingleDay or RecurringDay, "
                f"got {type(date_range)}"
            )
        super().__init__(
            description=description,
            amount=amount,
            category=category,
            date_range=date_range,
        )
        self._id = record_id
        self._is_archived = is_archived
        self._operation_matcher = OperationMatcher(operation_range=self)

    @property
    def id(self) -> PlannedOperationId | None:
        """The database ID of the planned operation. None if not persisted yet."""
        return self._id

    @property
    def is_archived(self) -> bool:
        """Whether this planned operation is archived."""
        return self._is_archived

    @property
    def matcher(self) -> OperationMatcher:
        """The operation matcher of the planned operation."""
        return self._operation_matcher

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
        split_date: date,
        new_amount: Amount | None = None,
        new_period: relativedelta | None = None,
    ) -> tuple["PlannedOperation", "PlannedOperation"]:
        """Split this planned operation at the given date.

        Args:
            split_date: Date from which the new values apply.
            new_amount: New amount for continuation (if None, keeps original).
            new_period: New period for continuation (if None, keeps original).

        Returns:
            Tuple of (terminated, continuation) PlannedOperations.

        Raises:
            ValueError: If this operation is not periodic.
        """
        if not isinstance(self.date_range, RecurringDay):
            raise ValueError("Cannot split a non-periodic planned operation")

        terminated_range, continuation_range = self.date_range.split_at(split_date)

        terminated = self.replace(date_range=terminated_range)

        amount = new_amount or Amount(self.amount, self.currency)
        dr = (
            continuation_range.replace(period=new_period)
            if new_period
            else continuation_range
        )
        continuation = PlannedOperation(
            record_id=None,
            description=self.description,
            amount=amount,
            category=self.category,
            date_range=dr,
        ).set_matcher_params(
            description_hints=self.matcher.description_hints,
            approximation_date_range=self.matcher.approximation_date_range,
            approximation_amount_ratio=self.matcher.approximation_amount_ratio,
        )

        return terminated, continuation

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PlannedOperation):
            return NotImplemented
        return (
            self._id == other._id
            and self._is_archived == other._is_archived
            and super().__eq__(other)
        )

    def __hash__(self) -> int:
        return hash((self._id, self._is_archived, super().__hash__()))

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
        new_date_range = kwargs.get("date_range", self.date_range)
        if not isinstance(new_date_range, (SingleDay, RecurringDay)):
            raise TypeError(
                f"date_range must be SingleDay or RecurringDay, "
                f"got {type(new_date_range)}"
            )
        new_is_archived = kwargs.get("is_archived", self.is_archived)
        if not isinstance(new_is_archived, bool):
            raise TypeError(f"is_archived must be bool, got {type(new_is_archived)}")
        return PlannedOperation(
            record_id=new_id,
            description=new_description,
            amount=new_amount,
            category=new_category,
            date_range=new_date_range,
            is_archived=new_is_archived,
        ).set_matcher_params(
            description_hints=self.matcher.description_hints,
            approximation_date_range=self.matcher.approximation_date_range,
            approximation_amount_ratio=self.matcher.approximation_amount_ratio,
        )
