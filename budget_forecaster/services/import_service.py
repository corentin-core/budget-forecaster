"""Service for importing bank exports.

This service provides a UI-agnostic API for importing bank statements.
"""

import fnmatch
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import NamedTuple

from budget_forecaster.account.account import AccountParameters
from budget_forecaster.account.persistent_account import PersistentAccount
from budget_forecaster.bank_adapter.bank_adapter_factory import BankAdapterFactory
from budget_forecaster.operation_range.historic_operation_factory import (
    HistoricOperationFactory,
)
from budget_forecaster.types import ImportProgressCallback, ImportStats

logger = logging.getLogger(__name__)


class ImportResult(NamedTuple):
    """Result of an import operation."""

    path: Path
    success: bool
    stats: ImportStats | None
    """Import statistics (None if import failed)."""
    error_message: str | None = None


class ImportSummary(NamedTuple):
    """Summary of import operations."""

    total_files: int
    successful_imports: int
    failed_imports: int
    total_new_operations: int
    total_duplicates_skipped: int
    results: tuple[ImportResult, ...]


class ImportService:
    """Service for importing bank exports.

    This service provides methods to import bank statements from files or
    the inbox folder. It only handles import logic; link creation is
    orchestrated by ApplicationService.
    """

    def __init__(
        self,
        persistent_account: PersistentAccount,
        inbox_path: Path,
        exclude_patterns: list[str] | None = None,
        include_patterns: list[str] | None = None,
    ) -> None:
        """Initialize the service.

        Args:
            persistent_account: The persistent account to import to.
            inbox_path: Path to the inbox folder.
            exclude_patterns: List of glob patterns to exclude from inbox.
            include_patterns: List of glob patterns to include in inbox.
                If specified, only files matching at least one pattern are included.
        """
        self._persistent_account = persistent_account
        self._inbox_path = inbox_path
        self._exclude_patterns = exclude_patterns or []
        self._include_patterns = include_patterns or []
        self._bank_adapter_factory = BankAdapterFactory()

    def _is_excluded(self, path: Path) -> bool:
        """Check if a path matches any exclusion pattern.

        Args:
            path: Path to check.

        Returns:
            True if the path should be excluded.
        """
        name = path.name
        for pattern in self._exclude_patterns:
            if fnmatch.fnmatch(name, pattern):
                return True
        return False

    def _should_include(self, path: Path) -> bool:
        """Check if a file should be included in inbox processing.

        Args:
            path: Path to check.

        Returns:
            True if the file should be included.
        """
        name = path.name

        # If include patterns exist, file must match at least one
        if self._include_patterns:
            if not any(fnmatch.fnmatch(name, p) for p in self._include_patterns):
                return False

        # File must not match any exclude pattern
        if self._is_excluded(path):
            return False

        return True

    def _get_last_operation_id(self) -> int:
        """Get the last operation id."""
        if not (operations := self._persistent_account.account.operations):
            return 0
        return max(op.unique_id for op in operations)

    def _create_operation_factory(self) -> HistoricOperationFactory:
        """Create an operation factory with the next available ID."""
        return HistoricOperationFactory(self._get_last_operation_id())

    def get_supported_exports_in_inbox(self) -> list[Path]:
        """Get all supported bank exports in the inbox folder.

        Returns:
            List of paths to supported export files/folders.
        """
        if not self._inbox_path.exists():
            return []

        exports: list[Path] = []
        for item in sorted(self._inbox_path.iterdir()):
            if item.name == "processed":
                continue
            if not self._should_include(item):
                continue
            if self.is_supported_export(item):
                exports.append(item)

        return exports

    def is_supported_export(self, path: Path) -> bool:
        """Check if a path is a supported bank export.

        Args:
            path: Path to check.

        Returns:
            True if the path is a supported export.
        """
        try:
            self._bank_adapter_factory.create_bank_adapter(path)
            return True
        except RuntimeError:
            return False

    def import_file(
        self,
        path: Path,
        move_to_processed: bool = False,
    ) -> ImportResult:
        """Import a single bank export file.

        Args:
            path: Path to the export file or folder.
            move_to_processed: If True, move the file to processed/ after import.

        Returns:
            ImportResult with the outcome and import statistics.
        """
        operation_factory = self._create_operation_factory()

        try:
            bank_adapter = self._bank_adapter_factory.create_bank_adapter(path)
            bank_adapter.load_bank_export(path, operation_factory)

            account_params = AccountParameters(
                name=bank_adapter.name,
                balance=bank_adapter.balance,
                currency="EUR",
                balance_date=bank_adapter.export_date or datetime.now(),
                operations=bank_adapter.operations,
            )

            stats = self._persistent_account.upsert_account(account_params)
            self._persistent_account.save()

            # Reload to get updated operations with unique_ids
            self._persistent_account.load()

            if move_to_processed:
                self._move_to_processed(path)

            return ImportResult(
                path=path,
                success=True,
                stats=stats,
            )

        except Exception as e:  # pylint: disable=broad-except
            logger.exception("Import failed for %s", path)
            return ImportResult(
                path=path,
                success=False,
                stats=None,
                error_message=str(e),
            )

    def _move_to_processed(self, path: Path) -> None:
        """Move a file/folder to the processed directory."""
        processed_path = self._inbox_path / "processed"
        processed_path.mkdir(exist_ok=True)
        dest = processed_path / path.name
        shutil.move(str(path), str(dest))

    def import_from_inbox(
        self,
        on_progress: ImportProgressCallback | None = None,
    ) -> ImportSummary:
        """Import all supported exports from the inbox folder.

        Args:
            on_progress: Optional callback called for each file.
                        Args: (current_index, total_count, filename)

        Returns:
            ImportSummary with the results of all imports.
        """
        # Ensure inbox exists
        if not self._inbox_path.exists():
            self._inbox_path.mkdir(parents=True)

        if not (exports := self.get_supported_exports_in_inbox()):
            return ImportSummary(
                total_files=0,
                successful_imports=0,
                failed_imports=0,
                total_new_operations=0,
                total_duplicates_skipped=0,
                results=(),
            )

        results: list[ImportResult] = []
        total_new_operations = 0
        total_duplicates_skipped = 0

        for i, export_path in enumerate(exports):
            if on_progress:
                on_progress(i + 1, len(exports), export_path.name)

            result = self.import_file(export_path, move_to_processed=True)
            results.append(result)

            if result.success and result.stats:
                total_new_operations += result.stats.new_operations
                total_duplicates_skipped += result.stats.duplicates_skipped

        successful = sum(1 for r in results if r.success)

        return ImportSummary(
            total_files=len(exports),
            successful_imports=successful,
            failed_imports=len(exports) - successful,
            total_new_operations=total_new_operations,
            total_duplicates_skipped=total_duplicates_skipped,
            results=tuple(results),
        )

    @property
    def inbox_path(self) -> Path:
        """Get the inbox path."""
        return self._inbox_path

    @property
    def has_pending_imports(self) -> bool:
        """Check if there are pending imports in the inbox."""
        return len(self.get_supported_exports_in_inbox()) > 0

    @property
    def pending_import_count(self) -> int:
        """Get the number of pending imports."""
        return len(self.get_supported_exports_in_inbox())
