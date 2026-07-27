"""Swile OAuth2 API source."""

import logging
from datetime import date

from budget_forecaster.infrastructure.bank_sources.bank_source import ApiBankSource
from budget_forecaster.infrastructure.bank_sources.swile.swile_parser import (
    parse_balance,
    parse_operations,
)
from budget_forecaster.infrastructure.bank_sources.swile_oauth.client import SwileClient
from budget_forecaster.services.operation.historic_operation_factory import (
    HistoricOperationFactory,
)

logger = logging.getLogger(__name__)


class SwileApiSource(ApiBankSource):
    """Bank source fetching meal-voucher operations and balance from Swile.

    Swile returns the whole user account in one call, so account_uid and
    date_from are ignored; dedup keeps re-runs idempotent.
    """

    def __init__(self, client: SwileClient, access_token: str, name: str) -> None:
        super().__init__(name)
        self._client = client
        self._access_token = access_token

    def fetch(
        self,
        account_uid: str,
        operation_factory: HistoricOperationFactory,
        date_from: date | None = None,
    ) -> None:
        operations_payload = self._client.get_operations(self._access_token)
        wallets_payload = self._client.get_wallets(self._access_token)
        if operations_payload.get("has_more"):
            logger.warning(
                "Swile returned more operations than one page; only the first "
                "page is synced (older operations arrive on later syncs)"
            )
        self._operations = list(parse_operations(operations_payload, operation_factory))
        self._balance = parse_balance(wallets_payload)
        self._export_date = date.today()
