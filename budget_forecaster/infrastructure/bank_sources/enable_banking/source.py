"""Enable Banking API source."""

from datetime import date

from budget_forecaster.infrastructure.bank_sources.bank_source import ApiBankSource
from budget_forecaster.infrastructure.bank_sources.enable_banking.client import (
    EnableBankingClient,
)
from budget_forecaster.infrastructure.bank_sources.enable_banking.mapper import (
    map_transaction,
    select_closing_booked_balance,
)
from budget_forecaster.services.operation.historic_operation_factory import (
    HistoricOperationFactory,
)


class EnableBankingSource(ApiBankSource):
    """Bank source fetching booked operations and balance via Enable Banking."""

    def __init__(self, client: EnableBankingClient, name: str) -> None:
        super().__init__(name)
        self._client = client

    def fetch(
        self,
        account_uid: str,
        operation_factory: HistoricOperationFactory,
        date_from: date | None = None,
    ) -> None:
        raw_transactions = self._client.get_transactions(account_uid, date_from)
        self._operations = [
            operation
            for raw in raw_transactions
            if (operation := map_transaction(raw, operation_factory)) is not None
        ]
        closing = select_closing_booked_balance(self._client.get_balances(account_uid))
        if closing is not None:
            self._balance = closing.amount
            self._export_date = closing.reference_date or date.today()
        else:
            self._balance = None
            self._export_date = date.today()
