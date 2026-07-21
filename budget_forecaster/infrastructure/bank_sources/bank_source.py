"""Common bank source abstraction.

A bank source produces historic operations and a balance for an account,
whatever the origin: a downloaded export file or a remote API.
"""
import abc
from datetime import date
from typing import Final

from budget_forecaster.domain.operation.historic_operation import HistoricOperation
from budget_forecaster.services.operation.historic_operation_factory import (
    HistoricOperationFactory,
)


class BankSource(abc.ABC):
    """A source of bank operations and balance for an account."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Return the source name."""

    @property
    @abc.abstractmethod
    def operations(self) -> tuple[HistoricOperation, ...]:
        """Return the loaded operations."""

    @property
    @abc.abstractmethod
    def balance(self) -> float | None:
        """Return the account balance."""

    @property
    @abc.abstractmethod
    def export_date(self) -> date | None:
        """Return the date the balance is valid at."""


class BankSourceBase(BankSource, abc.ABC):
    """Base class storing the loaded operations, balance and date."""

    def __init__(self, name: str) -> None:
        self._name: Final[str] = name
        self._operations: list[HistoricOperation] = []
        self._balance: float | None = None
        self._export_date: date | None = None

    @property
    def name(self) -> str:
        return self._name

    @property
    def operations(self) -> tuple[HistoricOperation, ...]:
        return tuple(self._operations)

    @property
    def balance(self) -> float | None:
        return self._balance

    @property
    def export_date(self) -> date | None:
        return self._export_date


class ApiBankSource(BankSourceBase, abc.ABC):
    """A bank source that fetches operations and balance from a remote API."""

    @abc.abstractmethod
    def fetch(
        self,
        account_uid: str,
        operation_factory: HistoricOperationFactory,
        date_from: date | None = None,
    ) -> None:
        """Fetch operations and balance for an account into this source."""
