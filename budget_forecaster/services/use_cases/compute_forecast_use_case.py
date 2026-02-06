"""Use case for computing forecast reports."""

from datetime import date

from budget_forecaster.services.account.account_analysis_report import (
    AccountAnalysisReport,
)
from budget_forecaster.services.forecast.forecast_service import ForecastService
from budget_forecaster.services.operation.operation_link_service import (
    OperationLinkService,
)


class ComputeForecastUseCase:  # pylint: disable=too-few-public-methods
    """Compute forecast reports by combining links and forecast data."""

    def __init__(
        self,
        forecast_service: ForecastService,
        operation_link_service: OperationLinkService,
    ) -> None:
        self._forecast_service = forecast_service
        self._operation_link_service = operation_link_service

    def compute_report(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> AccountAnalysisReport:
        """Compute the forecast report.

        Args:
            start_date: Start date for the report (default: today).
            end_date: End date for the report (default: 1 year from start).

        Returns:
            The computed analysis report.
        """
        links = self._operation_link_service.get_all_links()
        return self._forecast_service.compute_report(start_date, end_date, links)
