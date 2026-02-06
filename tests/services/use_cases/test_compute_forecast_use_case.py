"""Tests for the ComputeForecastUseCase."""

# pylint: disable=redefined-outer-name

from datetime import date
from unittest.mock import MagicMock

import pytest

from budget_forecaster.services.forecast.forecast_service import ForecastService
from budget_forecaster.services.operation.operation_link_service import (
    OperationLinkService,
)
from budget_forecaster.services.use_cases.compute_forecast_use_case import (
    ComputeForecastUseCase,
)


@pytest.fixture
def mock_forecast_service() -> MagicMock:
    """Create a mock forecast service."""
    return MagicMock(spec=ForecastService)


@pytest.fixture
def mock_operation_link_service() -> MagicMock:
    """Create a mock operation link service."""
    return MagicMock(spec=OperationLinkService)


@pytest.fixture
def use_case(
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
