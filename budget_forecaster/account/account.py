"""This module contains the Account class."""
from datetime import datetime
from typing import NamedTuple

from budget_forecaster.operation_range.historic_operation import HistoricOperation


class AccountParameters(NamedTuple):
    """Parameters to create an account."""

    name: str
    balance: float | None
    currency: str
    balance_date: datetime | None
    operations: tuple[HistoricOperation, ...]


class Account(NamedTuple):
    """An account with its properties."""

    name: str
    balance: float
    currency: str
    balance_date: datetime
    operations: tuple[HistoricOperation, ...]
