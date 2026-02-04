"""Module for the ForecastOperationRange class."""

from budget_forecaster.amount import Amount
from budget_forecaster.operation_range.operation_matcher import OperationMatcher
from budget_forecaster.operation_range.operation_range import OperationRange
from budget_forecaster.time_range import TimeRangeInterface
from budget_forecaster.types import Category


class ForecastOperationRange(OperationRange):
    """Expected operation range with a matcher to find the actual operation."""

    def __init__(
        self,
        record_id: int | None,
        description: str,
        amount: Amount,
        category: Category,
        time_range: TimeRangeInterface,
    ):
        super().__init__(
            description=description,
            amount=amount,
            category=category,
            time_range=time_range,
        )
        self._id = record_id
        self._operation_matcher = OperationMatcher(
            operation_range=self,
        )

    @property
    def id(self) -> int | None:
        """The database ID of the operation range. None if not persisted yet."""
        return self._id

    @property
    def matcher(self) -> OperationMatcher:
        """The operation matcher of the operation."""
        return self._operation_matcher
