"""Module to create historic operations"""
from datetime import datetime

from budget_forecaster.amount import Amount
from budget_forecaster.operation_range.historic_operation import HistoricOperation
from budget_forecaster.types import Category


class HistoricOperationFactory:  # pylint: disable=too-few-public-methods
    """Factory to create historic operations"""

    def __init__(self, last_operation_id: int) -> None:
        self._operation_id = last_operation_id

    def create_operation(
        self,
        description: str,
        amount: Amount,
        category: Category,
        date: datetime,
    ) -> HistoricOperation:
        """Create a historic operation"""
        self._operation_id += 1
        return HistoricOperation(
            unique_id=self._operation_id,
            description=description,
            amount=amount,
            category=category,
            date=date,
        )
