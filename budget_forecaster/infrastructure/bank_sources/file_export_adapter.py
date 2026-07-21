"""File-export bank adapter.

A file-export adapter reads operations and balance from a downloaded bank
export file (xls, zip, ...).
"""
import abc
from pathlib import Path

from budget_forecaster.infrastructure.bank_sources.bank_source import (
    BankSource,
    BankSourceBase,
)
from budget_forecaster.services.operation.historic_operation_factory import (
    HistoricOperationFactory,
)


class FileExportAdapter(BankSource, abc.ABC):
    """A bank source backed by a downloaded export file."""

    @abc.abstractmethod
    def load_bank_export(
        self, bank_export: Path, operation_factory: HistoricOperationFactory
    ) -> None:
        """Load the bank export."""

    @classmethod
    @abc.abstractmethod
    def match(cls, bank_export: Path) -> bool:
        """Return True if the bank export is supported."""


class FileExportAdapterBase(BankSourceBase, FileExportAdapter, abc.ABC):
    """Base class for file-export adapters."""
