"""Historic operation module."""
from datetime import datetime
from functools import total_ordering
from typing import Any, cast

from budget_forecaster.amount import Amount
from budget_forecaster.operation_range.operation_range import OperationRange
from budget_forecaster.time_range import DailyTimeRange
from budget_forecaster.types import Category, OperationId


@total_ordering
class HistoricOperation(OperationRange):
    """
    A historic operation is a financial operation that has already been executed.
    A negative amount means an expense, a positive amount means an income.
    """

    def __init__(
        self,
        unique_id: OperationId,
        description: str,
        amount: Amount,
        category: Category,
        date: datetime,
    ):
        self.__unique_id = unique_id
        super().__init__(description, amount, category, DailyTimeRange(date))

    @property
    def unique_id(self) -> OperationId:
        """The unique identifier of the operation."""
        return self.__unique_id

    @property
    def date(self) -> datetime:
        """The date of the operation."""
        return cast(DailyTimeRange, self.time_range).date

    def replace(self, **kwargs: Any) -> "HistoricOperation":
        """Return a new instance of the historic operation with the given parameters replaced."""
        return HistoricOperation(
            unique_id=kwargs.get("unique_id", self.__unique_id),
            description=kwargs.get("description", self.description),
            amount=kwargs.get("amount", Amount(self.amount, self.currency)),
            category=kwargs.get("category", self.category),
            date=kwargs.get("date", self.date),
        )

    def __repr__(self) -> str:
        return f"{self.__unique_id} - {super().__repr__()}"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, HistoricOperation):
            return NotImplemented
        return self.__unique_id == other.unique_id and super().__eq__(other)

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, HistoricOperation):
            return NotImplemented
        return super().__lt__(other)

    def __hash__(self) -> int:
        return hash((self.__unique_id, super().__hash__()))
