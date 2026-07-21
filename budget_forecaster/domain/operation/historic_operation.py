"""Historic operation module."""
from datetime import date
from functools import total_ordering
from typing import Any

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.date_range import SingleDay
from budget_forecaster.core.types import Category, OperationId
from budget_forecaster.domain.operation.content_ref import content_ref
from budget_forecaster.domain.operation.operation_range import OperationRange


@total_ordering
class HistoricOperation(OperationRange):
    """
    A historic operation is a financial operation that has already been executed.
    A negative amount means an expense, a positive amount means an income.
    """

    def __init__(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        unique_id: OperationId,
        description: str,
        amount: Amount,
        category: Category,
        operation_date: date,
        source_ref: str | None = None,
    ):
        self._unique_id = unique_id
        self._source_ref = source_ref
        super().__init__(description, amount, category, SingleDay(operation_date))

    @property
    def unique_id(self) -> OperationId:
        """The unique identifier of the operation."""
        return self._unique_id

    @property
    def operation_date(self) -> date:
        """The date of the operation."""
        return self.date_range.start_date

    @property
    def source_ref(self) -> str | None:
        """External dedup reference (API entry_reference), None for file imports."""
        return self._source_ref

    @property
    def content_ref(self) -> str:
        """Stable dedup key derived from the operation's content."""
        return content_ref(self.description, self.amount, self.operation_date)

    def replace(self, **kwargs: Any) -> "HistoricOperation":
        """Return a new instance of the historic operation with the given parameters replaced."""
        return HistoricOperation(
            unique_id=kwargs.get("unique_id", self._unique_id),
            description=kwargs.get("description", self.description),
            amount=kwargs.get("amount", Amount(self.amount, self.currency)),
            category=kwargs.get("category", self.category),
            operation_date=kwargs.get("operation_date", self.operation_date),
            source_ref=kwargs.get("source_ref", self._source_ref),
        )

    def __repr__(self) -> str:
        return f"{self._unique_id} - {super().__repr__()}"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, HistoricOperation):
            return NotImplemented
        return self._unique_id == other.unique_id and super().__eq__(other)

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, HistoricOperation):
            return NotImplemented
        return super().__lt__(other)

    def __hash__(self) -> int:
        return hash((self._unique_id, super().__hash__()))
