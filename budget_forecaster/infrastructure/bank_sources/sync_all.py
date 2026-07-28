"""Sync every connected source in one pass.

One orchestrator behind both the CLI sync command and the web "Sync now" button,
so Swile rides the daily timer alongside Enable Banking.
"""

import logging

from budget_forecaster.core.types import SyncRun
from budget_forecaster.infrastructure.bank_sources.enable_banking.consent_service import (
    ConsentService,
)
from budget_forecaster.infrastructure.bank_sources.enable_banking.sync_runner import (
    perform_sync as perform_enable_banking_sync,
)
from budget_forecaster.infrastructure.bank_sources.swile_oauth.client import SwileClient
from budget_forecaster.infrastructure.bank_sources.swile_oauth.sync_runner import (
    perform_sync as perform_swile_sync,
)
from budget_forecaster.infrastructure.bank_sources.swile_oauth.token_store import (
    SwileTokenStore,
)
from budget_forecaster.infrastructure.config import Config
from budget_forecaster.infrastructure.persistence.repository_interface import (
    RepositoryInterface,
)

logger = logging.getLogger(__name__)


def sync_all_sources(
    repository: RepositoryInterface,
    config: Config,
    consent_service: ConsentService | None,
    swile_token_store: SwileTokenStore | None,
    swile_client: SwileClient | None = None,
) -> tuple[SyncRun, ...]:
    """Sync every connected source and return one SyncRun per attempted source.

    A source is attempted only when connected: Enable Banking needs a stored
    consent, Swile needs a stored token. Unconnected sources are skipped with no
    run recorded. Neither runner raises, so one failing source never stops the
    others. The caller reloads the account and refreshes the forecast once, after
    all sources.
    """
    runs: list[SyncRun] = []

    if (
        consent_service is not None
        and config.enable_banking is not None
        and consent_service.current_consent() is not None
    ):
        runs.append(
            perform_enable_banking_sync(
                repository, consent_service, config.enable_banking, config.accounts
            )
        )

    if swile_token_store is not None and swile_token_store.load() is not None:
        runs.append(
            perform_swile_sync(
                repository, swile_token_store, config.accounts, client=swile_client
            )
        )

    return tuple(runs)
