"""Use case for importing bank export files."""

import logging
from pathlib import Path

from budget_forecaster.core.types import ImportProgressCallback
from budget_forecaster.infrastructure.persistence.persistent_account import (
    PersistentAccount,
)
from budget_forecaster.services.import_service import (
    ImportResult,
    ImportService,
    ImportSummary,
)
from budget_forecaster.services.operation.operation_link_service import (
    OperationLinkService,
)
from budget_forecaster.services.use_cases.matcher_cache import MatcherCache

logger = logging.getLogger(__name__)


class ImportUseCase:
    """Import bank export files and create heuristic links."""

    def __init__(
        self,
        import_service: ImportService,
        persistent_account: PersistentAccount,
        operation_link_service: OperationLinkService,
        matcher_cache: MatcherCache,
    ) -> None:
        self._import_service = import_service
        self._persistent_account = persistent_account
        self._operation_link_service = operation_link_service
        self._matcher_cache = matcher_cache

    def import_file(self, path: Path, move_to_processed: bool = False) -> ImportResult:
        """Import a bank export file and create heuristic links.

        Args:
            path: Path to the export file.
            move_to_processed: If True, move file to processed/ after import.

        Returns:
            ImportResult with the outcome.
        """
        result = self._import_service.import_file(path, move_to_processed)

        if result.success:
            operations = self._persistent_account.account.operations
            if matchers := self._matcher_cache.get_matchers():
                created_links = self._operation_link_service.create_heuristic_links(
                    operations, matchers
                )
                logger.info(
                    "Created %d heuristic links after import", len(created_links)
                )

        return result

    def import_from_inbox(
        self,
        on_progress: ImportProgressCallback | None = None,
    ) -> ImportSummary:
        """Import all bank exports from the inbox folder.

        Args:
            on_progress: Optional callback for progress updates.

        Returns:
            ImportSummary with the results.
        """
        summary = self._import_service.import_from_inbox(on_progress)

        if summary.successful_imports > 0:
            operations = self._persistent_account.account.operations
            if matchers := self._matcher_cache.get_matchers():
                created_links = self._operation_link_service.create_heuristic_links(
                    operations, matchers
                )
                logger.info(
                    "Created %d heuristic links after inbox import",
                    len(created_links),
                )

        return summary
