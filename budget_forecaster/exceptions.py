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


class BackupError(BudgetForecasterError):
    """A backup operation failed."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class AccountNotFoundError(BudgetForecasterError):
    """No account with the given name exists."""

    def __init__(self, name: str) -> None:
        super().__init__(f"Account not found: {name!r}")
        self.name = name


class BudgetNotFoundError(BudgetForecasterError):
    """No budget with the given ID exists."""

    def __init__(self, budget_id: int) -> None:
        super().__init__(f"Budget not found: {budget_id}")
        self.budget_id = budget_id


class PlannedOperationNotFoundError(BudgetForecasterError):
    """No planned operation with the given ID exists."""

    def __init__(self, operation_id: int) -> None:
        super().__init__(f"Planned operation not found: {operation_id}")
        self.operation_id = operation_id


class OperationNotFoundError(BudgetForecasterError):
    """No historic operation with the given ID exists."""

    def __init__(self, operation_id: int) -> None:
        super().__init__(f"Operation not found: {operation_id}")
        self.operation_id = operation_id
