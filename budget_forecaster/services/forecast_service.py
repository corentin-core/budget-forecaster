"""Service for forecast operations."""

import logging
from datetime import date, datetime, time
from pathlib import Path

from dateutil.relativedelta import relativedelta

from budget_forecaster.account.account import Account
from budget_forecaster.account.account_analysis_report import AccountAnalysisReport
from budget_forecaster.account.account_analyzer import AccountAnalyzer
from budget_forecaster.forecast.forecast import Forecast
from budget_forecaster.forecast.forecast_reader import ForecastReader

logger = logging.getLogger(__name__)


class ForecastService:
    """Service for generating and managing forecasts."""

    def __init__(
        self,
        account: Account,
        planned_operations_path: Path,
        budgets_path: Path,
    ) -> None:
        """Initialize the forecast service.

        Args:
            account: The account to forecast.
            planned_operations_path: Path to the planned operations CSV file.
            budgets_path: Path to the budgets CSV file.
        """
        self._account = account
        self._planned_operations_path = planned_operations_path
        self._budgets_path = budgets_path
        self._forecast: Forecast | None = None
        self._report: AccountAnalysisReport | None = None

    @property
    def has_forecast_files(self) -> bool:
        """Check if forecast files exist."""
        return self._planned_operations_path.exists() and self._budgets_path.exists()

    @property
    def planned_operations_path(self) -> Path:
        """Get the planned operations file path."""
        return self._planned_operations_path

    @property
    def budgets_path(self) -> Path:
        """Get the budgets file path."""
        return self._budgets_path

    def load_forecast(self) -> Forecast:
        """Load forecast data from CSV files.

        Returns:
            The loaded Forecast object.

        Raises:
            FileNotFoundError: If the forecast files don't exist.
        """
        if not self._planned_operations_path.exists():
            raise FileNotFoundError(
                f"Planned operations file not found: {self._planned_operations_path}"
            )
        if not self._budgets_path.exists():
            raise FileNotFoundError(f"Budgets file not found: {self._budgets_path}")

        logger.info(
            "Loading forecast from %s and %s",
            self._planned_operations_path,
            self._budgets_path,
        )

        reader = ForecastReader()
        planned_operations = reader.read_planned_operations(
            self._planned_operations_path
        )
        budgets = reader.read_budgets(self._budgets_path)

        self._forecast = Forecast(planned_operations, budgets)
        logger.info(
            "Loaded %d planned operations and %d budgets",
            len(planned_operations),
            len(budgets),
        )

        return self._forecast

    def compute_report(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> AccountAnalysisReport:
        """Compute the forecast report.

        Args:
            start_date: Start date for the report (default: 4 months ago).
            end_date: End date for the report (default: 12 months from now).

        Returns:
            The computed AccountAnalysisReport.
        """
        if self._forecast is None:
            self.load_forecast()

        if start_date is None:
            start_date = date.today() - relativedelta(months=4)
        if end_date is None:
            end_date = date.today() + relativedelta(months=12)

        logger.info("Computing forecast report from %s to %s", start_date, end_date)

        analyzer = AccountAnalyzer(self._account, self._forecast)  # type: ignore[arg-type]
        self._report = analyzer.compute_report(
            datetime.combine(start_date, time()),
            datetime.combine(end_date, time()),
        )

        return self._report

    @property
    def report(self) -> AccountAnalysisReport | None:
        """Get the last computed report."""
        return self._report

    def get_balance_evolution_summary(self) -> list[tuple[date, float]]:
        """Get a summary of balance evolution for display.

        Returns:
            List of (date, balance) tuples sampled for display.
        """
        if self._report is None:
            return []

        df = self._report.balance_evolution_per_day
        # Sample to reduce data points for display (weekly)
        sampled = df.resample("W").last()

        return [
            (d.to_pydatetime().date(), float(row["Solde"]))  # type: ignore[attr-defined]
            for d, row in sampled.iterrows()
        ]

    def get_monthly_summary(self) -> list[dict]:
        """Get monthly budget summary.

        Returns:
            List of monthly summaries with category breakdowns.
        """
        if self._report is None:
            return []

        df = self._report.budget_forecast
        summaries: list[dict] = []

        # Get unique months from columns
        months = sorted({col[0] for col in df.columns})

        for month in months:
            categories: dict = {}
            for category in df.index:
                if category == "Total":
                    continue
                try:
                    real = df.loc[category, (month, "Réel")]
                except KeyError:
                    real = 0
                try:
                    predicted = df.loc[category, (month, "Prévu")]
                except KeyError:
                    predicted = 0
                try:
                    actualized = df.loc[category, (month, "Actualisé")]
                except KeyError:
                    actualized = 0

                if real != 0 or predicted != 0 or actualized != 0:
                    categories[category] = {
                        "real": float(real),
                        "predicted": float(predicted),
                        "actualized": float(actualized),
                    }
            summaries.append({"month": month, "categories": categories})

        return summaries

    def get_category_statistics(self) -> list[tuple[str, float, float]]:
        """Get category statistics (total, monthly average).

        Returns:
            List of (category, total, monthly_average) tuples.
        """
        if self._report is None:
            return []

        df = self._report.budget_statistics
        return [
            (str(cat), float(row["Total"]), float(row["Moyenne mensuelle"]))
            for cat, row in df.iterrows()
        ]
