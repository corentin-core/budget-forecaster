"""Category detail of a budget whose period spans several months."""

from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest
from dateutil.relativedelta import relativedelta

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.date_range import DateRange
from budget_forecaster.core.types import Category, LinkType
from budget_forecaster.domain.account.account import Account
from budget_forecaster.domain.operation.budget import Budget
from budget_forecaster.domain.operation.historic_operation import HistoricOperation
from budget_forecaster.domain.operation.operation_link import OperationLink
from budget_forecaster.infrastructure.persistence.repository_interface import (
    RepositoryInterface,
)
from budget_forecaster.infrastructure.persistence.sqlite_repository import (
    SqliteRepository,
)
from budget_forecaster.services.forecast.forecast_service import ForecastService


class _AccountStub:  # pylint: disable=too-few-public-methods
    """AccountInterface stub for unit tests."""

    def __init__(self, account: Account) -> None:
        self._account = account

    @property
    def account(self) -> Account:
        """Return the account."""
        return self._account


@pytest.fixture(name="repository")
def repository_fixture(tmp_path: Path) -> Iterator[RepositoryInterface]:
    """Create an initialized repository."""
    with SqliteRepository(tmp_path / "test.db") as repo:
        yield repo


def test_operations_listed_in_their_own_month(
    repository: RepositoryInterface,
) -> None:
    """A budget over July and August lists each operation in its own month."""
    budget = Budget(
        record_id=None,
        description="Holidays",
        amount=Amount(-1000.0, "EUR"),
        category=Category.LEISURE,
        date_range=DateRange(date(2025, 7, 1), relativedelta(months=2)),
    )
    budget_id = repository.upsert_budget(budget)
    spending = (
        (date(2025, 6, 28), -100.0),
        (date(2025, 7, 15), -300.0),
        (date(2025, 8, 10), -500.0),
    )
    operations = tuple(
        HistoricOperation(
            unique_id=index,
            description=f"HOLIDAYS {index}",
            amount=Amount(amount, "EUR"),
            category=Category.LEISURE,
            operation_date=day,
        )
        for index, (day, amount) in enumerate(spending, start=1)
    )
    links = tuple(
        OperationLink(
            operation_unique_id=op.unique_id,
            target_type=LinkType.BUDGET,
            target_id=budget_id,
            iteration_date=date(2025, 7, 1),
        )
        for op in operations
    )
    account = Account(
        name="Test",
        balance=1000.0,
        currency="EUR",
        balance_date=date(2025, 8, 10),
        operations=operations,
    )
    service = ForecastService(
        account_provider=_AccountStub(account), repository=repository
    )
    service.load_forecast()
    service.compute_report(date(2025, 6, 1), date(2025, 8, 31), links)

    july = service.get_category_detail("leisure", date(2025, 7, 1), links)
    august = service.get_category_detail("leisure", date(2025, 8, 1), links)

    # The operation paid before the period counts in its first month
    assert [
        (op["operation_date"], op["cross_month_annotation"])
        for op in july["operations"]
    ] == [
        (date(2025, 6, 28), "paid early (operation dated Jun 28)"),
        (date(2025, 7, 15), ""),
    ]
    assert [
        (op["operation_date"], op["cross_month_annotation"])
        for op in august["operations"]
    ] == [(date(2025, 8, 10), "")]
    # 900 of 1000 spent: the 100 left belongs to August, July has none
    assert july["remaining"] == 0.0
    assert august["remaining"] == -100.0
