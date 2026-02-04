"""Module to create historic operations"""
from datetime import datetime

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.types import Category
from budget_forecaster.domain.operation.historic_operation import HistoricOperation


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
