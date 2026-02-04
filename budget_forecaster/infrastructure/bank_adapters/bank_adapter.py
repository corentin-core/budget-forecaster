"""Module for the BankAdapter interface class."""
import abc
from datetime import datetime
from pathlib import Path
from typing import Final

from budget_forecaster.domain.operation.historic_operation import HistoricOperation
from budget_forecaster.services.operation.historic_operation_factory import (
    HistoricOperationFactory,
)


class BankAdapterInterface(abc.ABC):
    """Adapter for the bank export transactions."""

    @abc.abstractmethod
    def __init__(self) -> None:
        """Initialize the bank adapter."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Return the bank adapter name."""

    @abc.abstractmethod
    def load_bank_export(
        self, bank_export: Path, operation_factory: HistoricOperationFactory
    ) -> None:
        """Load the bank export."""

    @classmethod
    @abc.abstractmethod
    def match(cls, bank_export: Path) -> bool:
        """Return True if the bank export is supported."""

    @property
    @abc.abstractmethod
    def operations(self) -> tuple[HistoricOperation, ...]:
        """Return the operations."""

    @property
    @abc.abstractmethod
    def balance(self) -> float | None:
        """Return the balance."""

    @property
    @abc.abstractmethod
    def export_date(self) -> datetime | None:
        """Return the export date."""


class BankAdapterBase(BankAdapterInterface, abc.ABC):
    """Base class for bank adapters."""

    def __init__(self, name: str) -> None:
        self._name: Final[str] = name
        self._operations: list[HistoricOperation] = []
        self._balance: float | None = None
        self._export_date: datetime | None = None

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
    def export_date(self) -> datetime | None:
        return self._export_date
