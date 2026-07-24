"""Run a bank sync and record its outcome.

Single entrypoint shared by the CLI (`main._run_sync`) and the web "Sync now"
button, so both wire the SyncUseCase the same way and record one SyncRun. Lives
in the infrastructure edge because it instantiates the Enable Banking client and
source; the services layer stays free of that wiring.
"""

import logging
from datetime import datetime, timezone

from budget_forecaster.core.types import SyncRun, SyncRunStatus
from budget_forecaster.domain.account.account_registry import AccountRegistry
from budget_forecaster.infrastructure.bank_sources.enable_banking.client import (
    EnableBankingClient,
)
from budget_forecaster.infrastructure.bank_sources.enable_banking.consent_service import (
    ConsentService,
    NoConsentError,
)
from budget_forecaster.infrastructure.bank_sources.enable_banking.source import (
    EnableBankingSource,
)
from budget_forecaster.infrastructure.config import EnableBankingConfig
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


def perform_sync(
    repository: RepositoryInterface,
    consent_service: ConsentService,
    enable_banking: EnableBankingConfig,
    accounts: AccountRegistry,
) -> SyncRun:
    """Sync the consented account, record the outcome, and return it.

    Any failure is recorded as a FAILED run and returned; the exception does not
    propagate, so callers branch on the returned status.
    """
    ran_at = datetime.now(timezone.utc)
    try:
        run = _sync(repository, consent_service, enable_banking, accounts, ran_at)
    except NoConsentError as error:
        logger.warning("Sync skipped: %s", error)
        run = SyncRun(ran_at, SyncRunStatus.FAILED, error=_describe(error))
    except Exception as error:  # pylint: disable=broad-except
        logger.exception("Sync failed")
        run = SyncRun(ran_at, SyncRunStatus.FAILED, error=_describe(error))
    repository.add_sync_run(run)
    return run


def _sync(
    repository: RepositoryInterface,
    consent_service: ConsentService,
    enable_banking: EnableBankingConfig,
    accounts: AccountRegistry,
    ran_at: datetime,
) -> SyncRun:
    """Build the use case, run it, and build the success SyncRun."""
    account_uid = consent_service.resolve_account_uid(enable_banking.account_uid)
    persistent_account = PersistentAccount(repository)
    client = EnableBankingClient(
        enable_banking.application_id,
        enable_banking.private_key_path,
        enable_banking.redirect_url,
    )
    source = EnableBankingSource(client, name=enable_banking.local_account_name)
    sync_use_case = SyncUseCase(
        BankSyncService(persistent_account, source, accounts),
        persistent_account,
        OperationLinkService(repository),
        MatcherCache(ForecastService(persistent_account, repository)),
    )
    stats = sync_use_case.sync(account_uid)
    return SyncRun(
        ran_at,
        SyncRunStatus.OK,
        new_count=stats.new_operations,
        duplicate_count=stats.duplicates_skipped,
        balance=persistent_account.account.balance,
    )


def _describe(error: Exception) -> str:
    """Format an exception as "ClassName: message" for the sync-run record."""
    return f"{type(error).__name__}: {error}"
