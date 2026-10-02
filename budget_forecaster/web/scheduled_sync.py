"""Sync every connected source from the web app: on demand, at startup, daily.

The web app is the only process writing the database while it runs, so the
daily sync runs here rather than on a separate timer.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from starlette.datastructures import State

from budget_forecaster.core.types import SyncRun, SyncRunStatus
from budget_forecaster.infrastructure.bank_sources.sync_all import (
    connected_sources,
    sync_all_sources,
)
from budget_forecaster.web.dependencies import refresh_forecast

logger = logging.getLogger(__name__)

SYNC_INTERVAL = timedelta(days=1)
_CHECK_INTERVAL_SECONDS = 3600


def sync_and_refresh(state: State) -> tuple[SyncRun, ...]:
    """Sync every connected source, then refresh the cached account and forecast.

    The sync does blocking network I/O on the event-loop thread (the shared SQLite
    connection is bound to it, so it can't be offloaded), stalling other requests
    for its duration. Reloads only when a source succeeded, so an empty database
    is tolerated.
    """
    runs = sync_all_sources(
        state.repository,
        state.config,
        state.consent_service,
        state.swile_token_store,
        state.swile_client,
    )
    if any(run.status is SyncRunStatus.OK for run in runs):
        state.app_service.reload_account()
        refresh_forecast(state.app_service)
    return runs


def is_sync_due(state: State, now: datetime) -> bool:
    """Whether a connected source's latest run, failed or not, is a day old or more.

    A failed run counts, so a broken source waits for the next day or the Sync
    button instead of failing again every hour. Per source, so a run of one
    source (a Swile enrollment, say) does not postpone the others.
    """
    for source in connected_sources(
        state.config, state.consent_service, state.swile_token_store
    ):
        latest = state.repository.get_recent_sync_runs(limit=1, source=source)
        if not latest or now - latest[0].ran_at >= SYNC_INTERVAL:
            return True
    return False


def sync_if_due(state: State) -> None:
    """Run the sync when it is due; log and swallow any error.

    Called before the app serves, so an error here must not stop it booting.
    """
    try:
        if is_sync_due(state, datetime.now(timezone.utc)):
            logger.info("Daily sync due; syncing every connected source")
            sync_and_refresh(state)
    except Exception:  # pylint: disable=broad-except
        logger.exception("Scheduled sync failed")


async def sync_daily(state: State) -> None:
    """Check every hour whether the daily sync is due, until cancelled."""
    while True:
        await asyncio.sleep(_CHECK_INTERVAL_SECONDS)
        sync_if_due(state)
