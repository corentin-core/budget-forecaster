"""Run a Swile sync and record its outcome.

Mirrors the Enable Banking sync runner: builds the SyncUseCase, records exactly
one SyncRun (tagged source=swile), and never raises so callers branch on the
returned status. A missing enrollment records a FAILED run pointing the user at
re-enrollment.
"""

import logging
from datetime import datetime, timezone

from budget_forecaster.core.types import SyncRun, SyncRunStatus, SyncSource
from budget_forecaster.domain.account.account_registry import AccountRegistry
from budget_forecaster.infrastructure.bank_sources.swile_oauth.client import SwileClient
from budget_forecaster.infrastructure.bank_sources.swile_oauth.consent_service import (
    NotEnrolledError,
    SwileConsentService,
)
from budget_forecaster.infrastructure.bank_sources.swile_oauth.source import (
    SwileApiSource,
)
from budget_forecaster.infrastructure.bank_sources.swile_oauth.token_store import (
    SwileTokenStore,
)
from budget_forecaster.infrastructure.persistence.persistent_account import (
    PersistentAccount,
)
from budget_forecaster.infrastructure.persistence.repository_interface import (
    RepositoryInterface,
)
from budget_forecaster.services.bank_sync_service import BankSyncService
from budget_forecaster.services.forecast.forecast_service import ForecastService
from budget_forecaster.services.operation.operation_link_service import (
    OperationLinkService,
)
from budget_forecaster.services.use_cases import MatcherCache, SyncUseCase

logger = logging.getLogger(__name__)

_ACCOUNT_NAME = "swile"
# Swile fetches the whole account; the source ignores this uid.
_ACCOUNT_UID = "swile"


def perform_sync(
    repository: RepositoryInterface,
    token_store: SwileTokenStore,
    accounts: AccountRegistry,
    client: SwileClient | None = None,
) -> SyncRun:
    """Sync the enrolled Swile account, record the outcome, and return it.

    Any failure is recorded as a FAILED run and returned; the exception does not
    propagate.
    """
    ran_at = datetime.now(timezone.utc)
    swile_client = client or SwileClient()
    consent_service = SwileConsentService(swile_client, token_store)
    try:
        run = _sync(repository, consent_service, swile_client, accounts, ran_at)
    except NotEnrolledError as error:
        logger.warning("Swile sync skipped: %s", error)
        run = SyncRun(
            ran_at,
            SyncRunStatus.FAILED,
            error=_describe(error),
            source=SyncSource.SWILE,
        )
    except Exception as error:  # pylint: disable=broad-except
        logger.exception("Swile sync failed")
        run = SyncRun(
            ran_at,
            SyncRunStatus.FAILED,
            error=_describe(error),
            source=SyncSource.SWILE,
        )
    repository.add_sync_run(run)
    return run


def _sync(
    repository: RepositoryInterface,
    consent_service: SwileConsentService,
    client: SwileClient,
    accounts: AccountRegistry,
    ran_at: datetime,
) -> SyncRun:
    """Build the use case, run it, and build the success SyncRun."""
    access_token = consent_service.authenticate()
    persistent_account = PersistentAccount(repository)
    source = SwileApiSource(client, access_token, name=_ACCOUNT_NAME)
    sync_use_case = SyncUseCase(
        BankSyncService(persistent_account, source, accounts),
        persistent_account,
        OperationLinkService(repository),
        MatcherCache(ForecastService(persistent_account, repository)),
    )
    stats = sync_use_case.sync(_ACCOUNT_UID)
    return SyncRun(
        ran_at,
        SyncRunStatus.OK,
        new_count=stats.new_operations,
        duplicate_count=stats.duplicates_skipped,
        balance=persistent_account.account.balance,
        source=SyncSource.SWILE,
    )


def _describe(error: Exception) -> str:
    """Format an exception as "ClassName: message" for the sync-run record."""
    return f"{type(error).__name__}: {error}"
