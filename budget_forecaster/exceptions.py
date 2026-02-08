"""Custom exception hierarchy for budget forecaster."""

from pathlib import Path


class BudgetForecasterError(Exception):
    """Base exception for all budget forecaster errors."""


class UnsupportedExportError(BudgetForecasterError):
    """No bank adapter can handle this export file."""

    def __init__(self, path: Path) -> None:
        super().__init__(f"Unsupported export format: {path}")
        self.path = path


class InvalidExportDataError(BudgetForecasterError):
    """Export file matched an adapter but contains invalid or missing data."""

    def __init__(self, message: str, *, path: Path | None = None) -> None:
        super().__init__(message)
        self.path = path


class AccountNotLoadedError(BudgetForecasterError):
    """No account data has been loaded yet."""

    def __init__(self) -> None:
        super().__init__("No account loaded. Import a bank export first.")


class PersistenceError(BudgetForecasterError):
    """A database operation failed unexpectedly."""
