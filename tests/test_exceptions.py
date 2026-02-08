"""Tests for the custom exception hierarchy."""

from pathlib import Path

import pytest

from budget_forecaster.exceptions import (
    AccountNotLoadedError,
    BudgetForecasterError,
    InvalidExportDataError,
    PersistenceError,
    UnsupportedExportError,
)


@pytest.mark.parametrize(
    "exception",
    [
        UnsupportedExportError(Path("/tmp/file.csv")),
        InvalidExportDataError("bad data"),
        AccountNotLoadedError(),
        PersistenceError("insert failed"),
    ],
    ids=[
        "UnsupportedExportError",
        "InvalidExportDataError",
        "AccountNotLoadedError",
        "PersistenceError",
    ],
)
def test_all_inherit_from_base(exception: BudgetForecasterError) -> None:
    """Every custom exception is a BudgetForecasterError."""
    assert isinstance(exception, BudgetForecasterError)


class TestUnsupportedExportError:
    """Tests for UnsupportedExportError."""

    def test_message_includes_path(self) -> None:
        """Error message contains the file path."""
        path = Path("/home/user/exports/statement.csv")
        error = UnsupportedExportError(path)
        assert str(path) in str(error)

    def test_path_attribute(self) -> None:
        """The path attribute stores the original path."""
        path = Path("/home/user/exports/statement.csv")
        error = UnsupportedExportError(path)
        assert error.path == path


class TestInvalidExportDataError:
    """Tests for InvalidExportDataError."""

    def test_message(self) -> None:
        """Error message is the provided string."""
        error = InvalidExportDataError("The balance field should be a float")
        assert str(error) == "The balance field should be a float"

    def test_path_attribute_when_provided(self) -> None:
        """The path attribute is set when provided."""
        path = Path("/exports/swile")
        error = InvalidExportDataError("bad data", path=path)
        assert error.path == path

    def test_path_attribute_defaults_to_none(self) -> None:
        """The path attribute defaults to None."""
        error = InvalidExportDataError("bad data")
        assert error.path is None


def test_account_not_loaded_error_has_user_friendly_message() -> None:
    """Error message guides the user to import first."""
    error = AccountNotLoadedError()
    assert "Import a bank export first" in str(error)


def test_persistence_error_message() -> None:
    """Error message is the provided string."""
    error = PersistenceError("Failed to insert budget")
    assert str(error) == "Failed to insert budget"
