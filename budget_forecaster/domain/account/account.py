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
    authoritative: bool = False
    """Whether balance and balance_date are a fresh snapshot that always wins.

    True for live API syncs: the fetched balance is the current truth, so it
    overwrites the stored value unconditionally. False for file imports, where a
    re-imported older export must not regress a newer stored balance.
    """


class Account(NamedTuple):
    """An account with its properties."""

    name: str
    balance: float
    currency: str
    balance_date: date
    operations: tuple[HistoricOperation, ...]
    external_id: str | None = None
    """Source-scoped external id (IBAN, Swile id); None for undeclared accounts."""
