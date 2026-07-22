"""This module contains the Account class."""
from datetime import date
from typing import NamedTuple

from budget_forecaster.domain.operation.historic_operation import HistoricOperation


class AccountParameters(NamedTuple):
    """Parameters to create an account."""

    name: str
    balance: float | None
    currency: str
    balance_date: date | None
    operations: tuple[HistoricOperation, ...]
    external_id: str | None = None
    """Source-scoped external id (IBAN, Swile id); None for undeclared accounts."""


class Account(NamedTuple):
    """An account with its properties."""

    name: str
    balance: float
    currency: str
    balance_date: date
    operations: tuple[HistoricOperation, ...]
    external_id: str | None = None
    """Source-scoped external id (IBAN, Swile id); None for undeclared accounts."""
