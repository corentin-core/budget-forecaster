"""Use case for syncing a bank account from an API source."""

import logging
from datetime import date

from budget_forecaster.core.types import ImportStats
from budget_forecaster.infrastructure.persistence.persistent_account import (
    PersistentAccount,
)
from budget_forecaster.services.bank_sync_service import BankSyncService
from budget_forecaster.services.operation.operation_link_service import (
    OperationLinkService,
)
from budget_forecaster.services.use_cases.matcher_cache import MatcherCache

logger = logging.getLogger(__name__)


class SyncUseCase:  # pylint: disable=too-few-public-methods
    """Sync an account from an API source and create heuristic links."""

    def __init__(
        self,
        sync_service: BankSyncService,
        persistent_account: PersistentAccount,
        operation_link_service: OperationLinkService,
        matcher_cache: MatcherCache,
    ) -> None:
        self._sync_service = sync_service
        self._persistent_account = persistent_account
        self._operation_link_service = operation_link_service
        self._matcher_cache = matcher_cache

    def sync(self, account_uid: str, date_from: date | None = None) -> ImportStats:
        """Sync the account, then link the resulting operations to targets."""
        stats = self._sync_service.sync(account_uid, date_from)

        operations = self._persistent_account.account.operations
        if matchers := self._matcher_cache.get_matchers():
            created_links = self._operation_link_service.create_heuristic_links(
                operations, matchers
            )
            logger.info("Created %d heuristic links after sync", len(created_links))

        return stats
