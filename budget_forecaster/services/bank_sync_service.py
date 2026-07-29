"""Service for syncing a bank account from an API source.

Fetches operations and balance from an API bank source and merges them into
the local account through the same path as file import, so the existing
source_ref dedup makes re-runs idempotent and reconciles overlapping file/API
operations.
"""

import logging
from datetime import date

from budget_forecaster.core.types import ImportStats
from budget_forecaster.domain.account.account import AccountParameters
from budget_forecaster.domain.account.account_registry import AccountRegistry
from budget_forecaster.infrastructure.bank_sources.bank_source import ApiBankSource
from budget_forecaster.infrastructure.persistence.persistent_account import (
    PersistentAccount,
)

logger = logging.getLogger(__name__)


class BankSyncService:  # pylint: disable=too-few-public-methods
    """Sync a single account from a remote API source into the local DB."""

    def __init__(
        self,
        persistent_account: PersistentAccount,
        api_source: ApiBankSource,
        account_registry: AccountRegistry | None = None,
    ) -> None:
        self._persistent_account = persistent_account
        self._api_source = api_source
        self._account_registry = account_registry or AccountRegistry()

    def sync(self, account_uid: str, date_from: date | None = None) -> ImportStats:
        """Fetch the account from the API source and merge it locally.

        Args:
            account_uid: The source-side account identifier to fetch.
            date_from: Optional lower bound on the fetched transactions. When
                omitted, the full available history is fetched; dedup keeps the
                merge idempotent either way.

        Returns:
            ImportStats with the number of new and duplicate operations.
        """
        operation_factory = self._persistent_account.next_operation_factory()
        self._api_source.fetch(account_uid, operation_factory, date_from)

        if self._api_source.balance is None:
            logger.warning(
                "No closing booked (CLBD) balance returned for %s",
                self._api_source.name,
            )

        account_params = AccountParameters(
            name=self._api_source.name,
            balance=self._api_source.balance,
            currency="EUR",
            balance_date=self._api_source.export_date or date.today(),
            operations=self._api_source.operations,
            external_id=self._account_registry.external_id_for(self._api_source.name),
            authoritative=True,
        )

        stats = self._persistent_account.upsert_account(account_params)
        self._persistent_account.save()
        self._persistent_account.reload()

        logger.info(
            "Synced %s: %d new, %d duplicates skipped",
            self._api_source.name,
            stats.new_operations,
            stats.duplicates_skipped,
        )
        return stats
