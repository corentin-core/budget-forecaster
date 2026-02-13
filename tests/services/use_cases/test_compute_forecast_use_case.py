"""Tests for the ComputeForecastUseCase."""
# pylint: disable=too-few-public-methods

from datetime import date
from unittest.mock import MagicMock

import pytest
from dateutil.relativedelta import relativedelta

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.date_range import (
    DateRange,
    RecurringDateRange,
    RecurringDay,
)
from budget_forecaster.core.types import Category, LinkType
from budget_forecaster.domain.account.account import Account
from budget_forecaster.domain.operation.budget import Budget
from budget_forecaster.domain.operation.historic_operation import HistoricOperation
from budget_forecaster.domain.operation.operation_link import OperationLink
from budget_forecaster.domain.operation.planned_operation import PlannedOperation
from budget_forecaster.services.forecast.forecast_service import ForecastService
from budget_forecaster.services.operation.operation_link_service import (
    OperationLinkService,
)
from budget_forecaster.services.use_cases.compute_forecast_use_case import (
    ComputeForecastUseCase,
)


@pytest.fixture(name="mock_forecast_service")
def mock_forecast_service_fixture() -> MagicMock:
    """Create a mock forecast service."""
    return MagicMock(spec=ForecastService)


@pytest.fixture(name="mock_operation_link_service")
def mock_operation_link_service_fixture() -> MagicMock:
    """Create a mock operation link service."""
    return MagicMock(spec=OperationLinkService)


@pytest.fixture(name="use_case")
def use_case_fixture(
    mock_forecast_service: MagicMock,
    mock_operation_link_service: MagicMock,
) -> ComputeForecastUseCase:
    """Create a ComputeForecastUseCase with mock dependencies."""
    return ComputeForecastUseCase(mock_forecast_service, mock_operation_link_service)


class TestComputeReport:
    """Tests for compute_report."""

    def test_fetches_links_and_delegates(
        self,
        use_case: ComputeForecastUseCase,
        mock_forecast_service: MagicMock,
        mock_operation_link_service: MagicMock,
    ) -> None:
        """compute_report fetches all links then delegates to forecast service."""
        links = (MagicMock(), MagicMock())
        mock_operation_link_service.get_all_links.return_value = links
        mock_forecast_service.compute_report.return_value = MagicMock()

        use_case.compute_report()

        mock_operation_link_service.get_all_links.assert_called_once()
        mock_forecast_service.compute_report.assert_called_once_with(None, None, links)

    def test_passes_date_range(
        self,
        use_case: ComputeForecastUseCase,
        mock_forecast_service: MagicMock,
        mock_operation_link_service: MagicMock,
    ) -> None:
        """Date parameters are forwarded to forecast service."""
        mock_operation_link_service.get_all_links.return_value = ()
        mock_forecast_service.compute_report.return_value = MagicMock()

        start = date(2025, 1, 1)
        end = date(2025, 12, 31)
        use_case.compute_report(start, end)

        mock_forecast_service.compute_report.assert_called_once_with(start, end, ())


class TestComputeReportIntegration:
    """Integration test exercising the full chain with real domain objects."""

    def test_report_with_operation_links(self) -> None:
        """Linked operations affect actualized forecast values.

        Setup:
        - Account with balance_date=2025-03-01, one historic op on 2025-03-05
        - A recurring planned operation (-100/month from 2025-03-01)
        - An operation link tying the historic op to the March iteration

        Expected:
        - The March planned op iteration is marked as actualized (linked)
        - The "Adjusted" column for March reflects only the remaining
          unlinked planned operations (none here), not the linked one
        """
        historic_op = HistoricOperation(
            unique_id=1,
            description="Monthly subscription",
            amount=Amount(-95.0),
            category=Category.OTHER,
            operation_date=date(2025, 3, 5),
        )
        account = Account(
            name="Integration Test",
            balance=5000.0,
            currency="EUR",
            balance_date=date(2025, 3, 10),
            operations=(historic_op,),
        )

        planned_op = PlannedOperation(
            record_id=1,
            description="Monthly subscription",
            amount=Amount(-100.0),
            category=Category.OTHER,
            date_range=RecurringDay(
                date(2025, 3, 1),
                period=relativedelta(months=1),
            ),
        )
        budget = Budget(
            record_id=1,
            description="Monthly groceries",
            amount=Amount(-400.0),
            category=Category.GROCERIES,
            date_range=RecurringDateRange(
                DateRange(date(2025, 3, 1), relativedelta(months=1)),
                period=relativedelta(months=1),
            ),
        )

        link = OperationLink(
            operation_unique_id=1,
            target_type=LinkType.PLANNED_OPERATION,
            target_id=1,
            iteration_date=date(2025, 3, 1),
        )

        # Wire real services with stub repositories
        mock_repo = MagicMock()
        mock_repo.get_all_planned_operations.return_value = (planned_op,)
        mock_repo.get_all_budgets.return_value = (budget,)

        mock_link_repo = MagicMock()
        mock_link_repo.get_all_links.return_value = (link,)

        forecast_service = ForecastService(account, mock_repo)
        link_service = OperationLinkService(mock_link_repo)
        use_case = ComputeForecastUseCase(forecast_service, link_service)

        report = use_case.compute_report(
            start_date=date(2025, 3, 1),
            end_date=date(2025, 5, 31),
        )

        # Report is properly structured
        assert report.balance_date == date(2025, 3, 10)
        assert report.start_date == date(2025, 3, 1)
        assert report.end_date == date(2025, 5, 31)

        # Balance evolution covers the full range
        assert report.balance_evolution_per_day.index[0].date() == date(2025, 3, 1)
        assert report.balance_evolution_per_day.index[-1].date() == date(2025, 5, 31)

        # Budget forecast includes both categories
        budget_forecast = report.budget_forecast
        assert str(Category.OTHER) in budget_forecast.index
        assert str(Category.GROCERIES) in budget_forecast.index

        # The historic operation appears as "Actual" for March
        assert budget_forecast.loc[str(Category.OTHER)]["2025-03-01"]["Actual"] == -95.0

        # The linked planned op is actualized: the March iteration is consumed
        # by the link, so "Adjusted" reflects the actual amount from the link
        march_actualized = budget_forecast.loc[str(Category.OTHER)]["2025-03-01"][
            "Adjusted"
        ]
        # Without link, March planned op would be advanced (not executed).
        # With link, it's recognized as actualized: the forecast shows the linked
        # operation's actual amount (-95) instead of the planned amount (-100).
        assert march_actualized == -95.0
