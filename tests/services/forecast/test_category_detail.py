"""Tests for ForecastService.get_category_detail."""

# pylint: disable=too-few-public-methods

from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest
from dateutil.relativedelta import relativedelta

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.date_range import RecurringDay, SingleDay
from budget_forecaster.core.types import Category, LinkType
from budget_forecaster.domain.account.account import Account
from budget_forecaster.domain.operation.budget import Budget
from budget_forecaster.domain.operation.historic_operation import HistoricOperation
from budget_forecaster.domain.operation.operation_link import OperationLink
from budget_forecaster.domain.operation.planned_operation import PlannedOperation
from budget_forecaster.infrastructure.persistence.repository_interface import (
    RepositoryInterface,
)
from budget_forecaster.infrastructure.persistence.sqlite_repository import (
    SqliteRepository,
)
from budget_forecaster.services.forecast.forecast_service import (
    ForecastService,
    _cross_month_annotation,
    _format_budget_periodicity,
    _format_periodicity,
    _ordinal,
)


class _AccountStub:
    """Mutable AccountInterface stub for unit tests."""

    def __init__(self, account: Account) -> None:
        self._account = account

    @property
    def account(self) -> Account:
        """Return the current account."""
        return self._account

    @account.setter
    def account(self, value: Account) -> None:
        self._account = value


@pytest.fixture(name="temp_db_path")
def temp_db_path_fixture(tmp_path: Path) -> Path:
    """Return a temporary database path."""
    return tmp_path / "test.db"


@pytest.fixture(name="repository")
def repository_fixture(temp_db_path: Path) -> Iterator[RepositoryInterface]:
    """Create a fresh SQLite repository for each test."""
    with SqliteRepository(temp_db_path) as repo:
        yield repo


def _make_service(account: Account, repository: RepositoryInterface) -> ForecastService:
    """Create a ForecastService from an account and repository."""
    return ForecastService(
        account_provider=_AccountStub(account),
        repository=repository,
    )


class TestFormatHelpers:
    """Tests for formatting helper functions."""

    def test_ordinal_1st(self) -> None:
        """Ordinal of 1 is 1st."""
        assert _ordinal(1) == "1st"

    def test_ordinal_2nd(self) -> None:
        """Ordinal of 2 is 2nd."""
        assert _ordinal(2) == "2nd"

    def test_ordinal_3rd(self) -> None:
        """Ordinal of 3 is 3rd."""
        assert _ordinal(3) == "3rd"

    def test_ordinal_11th(self) -> None:
        """Ordinal of 11 is 11th (special case)."""
        assert _ordinal(11) == "11th"

    def test_ordinal_21st(self) -> None:
        """Ordinal of 21 is 21st."""
        assert _ordinal(21) == "21st"

    def test_ordinal_15th(self) -> None:
        """Ordinal of 15 is 15th."""
        assert _ordinal(15) == "15th"

    def test_format_periodicity_monthly(self) -> None:
        """Monthly recurring operation formats as 'monthly, Nth'."""
        op = PlannedOperation(
            record_id=1,
            description="Rent",
            amount=Amount(-800.0, "EUR"),
            category=Category.RENT,
            date_range=RecurringDay(date(2025, 1, 1), relativedelta(months=1)),
        )
        assert _format_periodicity(op) == "monthly, 1st"

    def test_format_periodicity_yearly(self) -> None:
        """Yearly recurring operation formats as 'yearly, Nth'."""
        op = PlannedOperation(
            record_id=2,
            description="Insurance",
            amount=Amount(-1200.0, "EUR"),
            category=Category.OTHER,
            date_range=RecurringDay(date(2025, 3, 15), relativedelta(years=1)),
        )
        assert _format_periodicity(op) == "yearly, 15th"

    def test_format_periodicity_one_time(self) -> None:
        """Single-day operation formats as 'one-time, Nth'."""
        op = PlannedOperation(
            record_id=3,
            description="Plumber",
            amount=Amount(-100.0, "EUR"),
            category=Category.HOUSE_WORKS,
            date_range=SingleDay(date(2025, 2, 15)),
        )
        assert _format_periodicity(op) == "one-time, 15th"

    def test_format_budget_periodicity_monthly(self) -> None:
        """Monthly budget formats as 'amount/month (dates)'."""
        budget = Budget(
            record_id=1,
            description="Groceries",
            amount=Amount(-500.0, "EUR"),
            category=Category.GROCERIES,
            date_range=RecurringDay(date(2025, 1, 1), relativedelta(months=1)),
        )
        result = _format_budget_periodicity(budget, date(2025, 2, 1), date(2025, 2, 28))
        assert result == "500/month (01/02→28/02)"

    def test_format_budget_periodicity_yearly(self) -> None:
        """Yearly budget formats as 'amount/year (dates)'."""
        budget = Budget(
            record_id=2,
            description="Insurance",
            amount=Amount(-1200.0, "EUR"),
            category=Category.OTHER,
            date_range=RecurringDay(date(2025, 1, 1), relativedelta(years=1)),
        )
        result = _format_budget_periodicity(
            budget, date(2025, 1, 1), date(2025, 12, 31)
        )
        assert result == "1,200/year (01/01→31/12)"


class TestCrossMonthAnnotation:
    """Tests for cross-month annotation logic."""

    def test_same_month_no_annotation(self) -> None:
        """Operation in the same month gets no annotation."""
        assert (
            _cross_month_annotation(
                date(2025, 2, 15), date(2025, 2, 1), date(2025, 2, 28)
            )
            == ""
        )

    def test_paid_early(self) -> None:
        """Operation before the month gets 'paid early' annotation."""
        result = _cross_month_annotation(
            date(2025, 1, 28), date(2025, 2, 1), date(2025, 2, 28)
        )
        assert "paid early" in result
        assert "Jan 28" in result

    def test_paid_late(self) -> None:
        """Operation after the month gets 'paid late' annotation."""
        result = _cross_month_annotation(
            date(2025, 3, 2), date(2025, 2, 1), date(2025, 2, 28)
        )
        assert "paid late" in result
        assert "Mar 02" in result


class TestGetCategoryDetail:
    """Tests for ForecastService.get_category_detail."""

    def test_category_with_planned_operations(
        self, repository: RepositoryInterface
    ) -> None:
        """Category with planned operations returns correct sources."""
        op = PlannedOperation(
            record_id=None,
            description="Netflix",
            amount=Amount(-15.0, "EUR"),
            category=Category.INTERNET,
            date_range=RecurringDay(date(2025, 1, 1), relativedelta(months=1)),
        )
        repository.upsert_planned_operation(op)

        account = Account(
            name="Test",
            balance=1000.0,
            currency="EUR",
            balance_date=date(2025, 1, 20),
            operations=(),
        )
        service = _make_service(account, repository)
        service.load_forecast()

        detail = service.get_category_detail("internet", date(2025, 2, 1))

        assert detail["category"] == "internet"
        assert detail["month"] == date(2025, 2, 1)
        assert len(detail["planned_sources"]) == 1

        source = detail["planned_sources"][0]
        assert source["tag"] == "planned"
        assert source["description"] == "Netflix"
        assert source["periodicity"] == "monthly, 1st"
        assert source["amount"] == -15.0

    def test_category_with_budget(self, repository: RepositoryInterface) -> None:
        """Category with budget returns correct source."""
        budget = Budget(
            record_id=None,
            description="House works",
            amount=Amount(-200.0, "EUR"),
            category=Category.HOUSE_WORKS,
            date_range=RecurringDay(date(2025, 1, 1), relativedelta(months=1)),
        )
        repository.upsert_budget(budget)

        account = Account(
            name="Test",
            balance=1000.0,
            currency="EUR",
            balance_date=date(2025, 1, 20),
            operations=(),
        )
        service = _make_service(account, repository)
        service.load_forecast()

        detail = service.get_category_detail("house_works", date(2025, 2, 1))

        assert len(detail["planned_sources"]) == 1
        source = detail["planned_sources"][0]
        assert source["tag"] == "budget"
        assert source["description"] == "House works"
        assert source["periodicity"] == "200/month (01/02→28/02)"

    def test_mixed_budget_and_planned(self, repository: RepositoryInterface) -> None:
        """Category with both budget and planned op returns both sources."""
        budget = Budget(
            record_id=None,
            description="House works",
            amount=Amount(-200.0, "EUR"),
            category=Category.HOUSE_WORKS,
            date_range=RecurringDay(date(2025, 1, 1), relativedelta(months=1)),
        )
        op = PlannedOperation(
            record_id=None,
            description="Plumber visit",
            amount=Amount(-100.0, "EUR"),
            category=Category.HOUSE_WORKS,
            date_range=SingleDay(date(2025, 2, 15)),
        )
        repository.upsert_budget(budget)
        repository.upsert_planned_operation(op)

        account = Account(
            name="Test",
            balance=1000.0,
            currency="EUR",
            balance_date=date(2025, 1, 20),
            operations=(),
        )
        service = _make_service(account, repository)
        service.load_forecast()

        detail = service.get_category_detail("house_works", date(2025, 2, 1))

        assert len(detail["planned_sources"]) == 2
        tags = {s["tag"] for s in detail["planned_sources"]}
        assert tags == {"budget", "planned"}
        assert detail["total_planned"] == -300.0

    def test_operations_attributed_to_month(
        self, repository: RepositoryInterface
    ) -> None:
        """Unlinked operations in the month appear in the detail."""
        operation = HistoricOperation(
            unique_id=1,
            description="LEROY MERLIN",
            amount=Amount(-80.0, "EUR"),
            category=Category.HOUSE_WORKS,
            operation_date=date(2025, 2, 3),
        )

        account = Account(
            name="Test",
            balance=1000.0,
            currency="EUR",
            balance_date=date(2025, 1, 20),
            operations=(operation,),
        )
        service = _make_service(account, repository)
        service.load_forecast()

        detail = service.get_category_detail("house_works", date(2025, 2, 1))

        assert len(detail["operations"]) == 1
        op_detail = detail["operations"][0]
        assert op_detail["description"] == "LEROY MERLIN"
        assert op_detail["amount"] == -80.0
        assert op_detail["cross_month_annotation"] == ""

    def test_cross_month_linked_operation(
        self, repository: RepositoryInterface
    ) -> None:
        """Operation linked to another month is attributed there with annotation."""
        # Operation dated Feb 28, linked to March iteration
        operation = HistoricOperation(
            unique_id=1,
            description="VIREMENT LOYER",
            amount=Amount(-800.0, "EUR"),
            category=Category.RENT,
            operation_date=date(2025, 2, 28),
        )
        op_planned = PlannedOperation(
            record_id=None,
            description="Rent",
            amount=Amount(-800.0, "EUR"),
            category=Category.RENT,
            date_range=RecurringDay(date(2025, 1, 1), relativedelta(months=1)),
        )
        op_id = repository.upsert_planned_operation(op_planned)

        link = OperationLink(
            operation_unique_id=1,
            target_type=LinkType.PLANNED_OPERATION,
            target_id=op_id,
            iteration_date=date(2025, 3, 1),
            is_manual=False,
        )

        account = Account(
            name="Test",
            balance=1000.0,
            currency="EUR",
            balance_date=date(2025, 1, 20),
            operations=(operation,),
        )
        service = _make_service(account, repository)
        service.load_forecast()

        # March detail should show the operation
        march_detail = service.get_category_detail(
            "rent", date(2025, 3, 1), operation_links=(link,)
        )
        assert len(march_detail["operations"]) == 1
        assert "paid early" in march_detail["operations"][0]["cross_month_annotation"]
        assert "Feb 28" in march_detail["operations"][0]["cross_month_annotation"]

        # February detail should NOT show the operation (it was linked elsewhere)
        feb_detail = service.get_category_detail(
            "rent", date(2025, 2, 1), operation_links=(link,)
        )
        assert len(feb_detail["operations"]) == 0

    def test_unforecasted_category(self, repository: RepositoryInterface) -> None:
        """Category with only operations and no forecast sources."""
        operation = HistoricOperation(
            unique_id=1,
            description="RESTAURANT SUSHI",
            amount=Amount(-45.0, "EUR"),
            category=Category.ENTERTAINMENT,
            operation_date=date(2025, 2, 10),
        )

        account = Account(
            name="Test",
            balance=1000.0,
            currency="EUR",
            balance_date=date(2025, 1, 20),
            operations=(operation,),
        )
        service = _make_service(account, repository)
        service.load_forecast()

        detail = service.get_category_detail("entertainment", date(2025, 2, 1))

        assert len(detail["planned_sources"]) == 0
        assert len(detail["operations"]) == 1
        assert detail["total_planned"] == 0.0
        assert detail["total_actual"] == -45.0

    def test_operations_sorted_by_date(self, repository: RepositoryInterface) -> None:
        """Operations are sorted by date ascending."""
        ops = (
            HistoricOperation(
                unique_id=2,
                description="SECOND",
                amount=Amount(-20.0, "EUR"),
                category=Category.GROCERIES,
                operation_date=date(2025, 2, 15),
            ),
            HistoricOperation(
                unique_id=1,
                description="FIRST",
                amount=Amount(-10.0, "EUR"),
                category=Category.GROCERIES,
                operation_date=date(2025, 2, 3),
            ),
        )

        account = Account(
            name="Test",
            balance=1000.0,
            currency="EUR",
            balance_date=date(2025, 1, 20),
            operations=ops,
        )
        service = _make_service(account, repository)
        service.load_forecast()

        detail = service.get_category_detail("groceries", date(2025, 2, 1))

        assert len(detail["operations"]) == 2
        assert detail["operations"][0]["description"] == "FIRST"
        assert detail["operations"][1]["description"] == "SECOND"

    def test_is_income_from_planned(self, repository: RepositoryInterface) -> None:
        """is_income is determined from planned amount when available."""
        op = PlannedOperation(
            record_id=None,
            description="Salary",
            amount=Amount(2500.0, "EUR"),
            category=Category.SALARY,
            date_range=RecurringDay(date(2025, 1, 1), relativedelta(months=1)),
        )
        repository.upsert_planned_operation(op)

        account = Account(
            name="Test",
            balance=1000.0,
            currency="EUR",
            balance_date=date(2025, 1, 20),
            operations=(),
        )
        service = _make_service(account, repository)
        service.load_forecast()

        detail = service.get_category_detail("salary", date(2025, 2, 1))
        assert detail["is_income"] is True

    def test_remaining_computation(self, repository: RepositoryInterface) -> None:
        """Remaining = abs(projected) - abs(actual)."""
        op = PlannedOperation(
            record_id=None,
            description="Groceries Plan",
            amount=Amount(-500.0, "EUR"),
            category=Category.GROCERIES,
            date_range=RecurringDay(date(2025, 1, 1), relativedelta(months=1)),
        )
        repository.upsert_planned_operation(op)

        operation = HistoricOperation(
            unique_id=1,
            description="SUPERMARKET",
            amount=Amount(-320.0, "EUR"),
            category=Category.GROCERIES,
            operation_date=date(2025, 2, 5),
        )

        account = Account(
            name="Test",
            balance=1000.0,
            currency="EUR",
            balance_date=date(2025, 1, 20),
            operations=(operation,),
        )
        service = _make_service(account, repository)
        service.load_forecast()

        detail = service.get_category_detail("groceries", date(2025, 2, 1))

        assert detail["total_actual"] == -320.0
        # Without a cached report, projected = total_actual
        assert detail["remaining"] == abs(detail["forecast"]) - abs(
            detail["total_actual"]
        )
