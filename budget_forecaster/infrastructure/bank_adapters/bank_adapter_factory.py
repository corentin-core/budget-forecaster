"""Module for the BankAdapterFactory class."""
# pylint: disable=unused-import
import inspect
import pathlib
from typing import Generator

from budget_forecaster.exceptions import UnsupportedExportError
from budget_forecaster.infrastructure.bank_adapters.bank_adapter import (
    BankAdapterInterface,
)
from budget_forecaster.infrastructure.bank_adapters.bnp_paribas.bnp_paribas_bank_adapter import (
    BnpParibasBankAdapter,  # noqa: F401
)
from budget_forecaster.infrastructure.bank_adapters.swile.swile_bank_adapter import (
    SwileBankAdapter,  # noqa: F401
)


class BankAdapterFactory:  # pylint: disable=too-few-public-methods
    """A class to create a bank adapter."""

    @staticmethod
    def __get_concrete_bank_adapters_recursive(
        adapter_cls: type[BankAdapterInterface],
    ) -> Generator[type[BankAdapterInterface], None, None]:
        """Get all concrete bank adapters recursively."""
        for subclass in adapter_cls.__subclasses__():
            yield from BankAdapterFactory.__get_concrete_bank_adapters_recursive(
                subclass
            )
            if not inspect.isabstract(subclass):
                yield subclass

    @staticmethod
    def create_bank_adapter(bank_export: pathlib.Path) -> BankAdapterInterface:
        """Create a bank adapter."""
        for adapter in BankAdapterFactory.__get_concrete_bank_adapters_recursive(
            BankAdapterInterface  # type: ignore
        ):
            if adapter.match(bank_export):
                return adapter()

        raise UnsupportedExportError(bank_export)
