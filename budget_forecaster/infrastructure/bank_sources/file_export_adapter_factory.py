"""Module for the FileExportAdapterFactory class."""
# pylint: disable=unused-import
import inspect
import pathlib
from typing import Generator

from budget_forecaster.exceptions import UnsupportedExportError
from budget_forecaster.infrastructure.bank_sources.bnp_paribas.bnp_paribas_bank_adapter import (
    BnpParibasBankAdapter,  # noqa: F401
)
from budget_forecaster.infrastructure.bank_sources.file_export_adapter import (
    FileExportAdapter,
)
from budget_forecaster.infrastructure.bank_sources.swile.swile_bank_adapter import (
    SwileBankAdapter,  # noqa: F401
)


class FileExportAdapterFactory:  # pylint: disable=too-few-public-methods
    """A class to create a file-export adapter for a given export file."""

    @staticmethod
    def __get_concrete_adapters_recursive(
        adapter_cls: type[FileExportAdapter],
    ) -> Generator[type[FileExportAdapter], None, None]:
        """Yield all concrete file-export adapters recursively."""
        for subclass in adapter_cls.__subclasses__():
            yield from FileExportAdapterFactory.__get_concrete_adapters_recursive(
                subclass
            )
            if not inspect.isabstract(subclass):
                yield subclass

    @staticmethod
    def create_adapter(bank_export: pathlib.Path) -> FileExportAdapter:
        """Create a file-export adapter matching the given export file."""
        for adapter in FileExportAdapterFactory.__get_concrete_adapters_recursive(
            FileExportAdapter  # type: ignore
        ):
            if adapter.match(bank_export):
                return adapter()

        raise UnsupportedExportError(bank_export)
