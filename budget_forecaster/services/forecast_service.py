"""Service for forecast operations."""

import logging
from datetime import date, datetime, time
from typing import Any, TypedDict

from dateutil.relativedelta import relativedelta

from budget_forecaster.account.account import Account
from budget_forecaster.account.account_analysis_report import AccountAnalysisReport
from budget_forecaster.account.account_analyzer import AccountAnalyzer
from budget_forecaster.account.repository_interface import RepositoryInterface
from budget_forecaster.forecast.forecast import Forecast
from budget_forecaster.operation_range.budget import Budget
from budget_forecaster.operation_range.operation_link import LinkType
from budget_forecaster.operation_range.operation_matcher import OperationMatcher
from budget_forecaster.operation_range.planned_operation import PlannedOperation
from budget_forecaster.services.operation_link_service import OperationLinkService

logger = logging.getLogger(__name__)


class CategoryBudget(TypedDict):
    """Budget values for a category."""

    real: float
    predicted: float
    actualized: float


class MonthlySummary(TypedDict):
    """Monthly budget summary."""

    month: Any  # pandas Timestamp
    categories: dict[str, CategoryBudget]


class ForecastService:
    """Service for generating and managing forecasts.

    Automatically recalculates heuristic operation links when planned
    operations or budgets are added or modified.
    """

    def __init__(
        self,
        account: Account,
        repository: RepositoryInterface,
        auto_link: bool = True,
    ) -> None:
        """Initialize the forecast service.

        Args:
            account: The account to forecast.
            repository: Repository for data persistence.
            auto_link: If True, automatically recalculate links on changes.
        """
        self._account = account
        self._repository = repository
        self._forecast: Forecast | None = None
        self._report: AccountAnalysisReport | None = None
        self._auto_link = auto_link
        self._link_service: OperationLinkService | None = None

    @property
    def _operation_link_service(self) -> OperationLinkService:
        """Get or create the operation link service."""
        if self._link_service is None:
            self._link_service = OperationLinkService(self._repository)
        return self._link_service

    def set_account(self, account: Account) -> None:
        """Update the account reference.

        Used when the account is reloaded from the database.

        Args:
            account: The new account reference.
        """
        self._account = account
        self._invalidate_cache()

    def load_forecast(self) -> Forecast:
        """Load forecast data from the database.

        Returns:
            The loaded Forecast object.
        """
        logger.info("Loading forecast from database")

        planned_operations = tuple(self._repository.get_all_planned_operations())
        budgets = tuple(self._repository.get_all_budgets())

        self._forecast = Forecast(planned_operations, budgets)
        logger.info(
            "Loaded %d planned operations and %d budgets",
            len(planned_operations),
            len(budgets),
        )

        return self._forecast

    def reload_forecast(self) -> Forecast:
        """Force reload forecast data from the database.

        Returns:
            The reloaded Forecast object.
        """
        self._invalidate_cache()
        return self.load_forecast()

    def _invalidate_cache(self) -> None:
        """Invalidate cached forecast and report data."""
        self._forecast = None
        self._report = None

    # Budget CRUD methods

    def get_all_budgets(self) -> list[Budget]:
        """Get all budgets from the database."""
        return self._repository.get_all_budgets()

    def get_budget_by_id(self, budget_id: int) -> Budget | None:
        """Get a budget by ID."""
        return self._repository.get_budget_by_id(budget_id)

    def add_budget(self, budget: Budget) -> int:
        """Add a new budget.

        Args:
            budget: Budget to add (id should be -1).

        Returns:
            The ID of the newly created budget.
        """
        budget_id = self._repository.upsert_budget(budget)
        self._invalidate_cache()

        # Recalculate heuristic links for the new budget
        if self._auto_link:
            self._recalculate_budget_links(budget_id)

        return budget_id

    def update_budget(self, budget: Budget) -> None:
        """Update an existing budget.

        Args:
            budget: Budget with updated values (id must not be None).
        """
        if budget.id is None:
            raise ValueError("Budget must have a valid ID for update")
        self._repository.upsert_budget(budget)
        self._invalidate_cache()

        # Recalculate heuristic links for the modified budget
        if self._auto_link:
            self._recalculate_budget_links(budget.id)

    def delete_budget(self, budget_id: int) -> None:
        """Delete a budget.

        Args:
            budget_id: ID of the budget to delete.
        """
        self._repository.delete_budget(budget_id)
        self._invalidate_cache()

    # Planned Operation CRUD methods

    def get_all_planned_operations(self) -> list[PlannedOperation]:
        """Get all planned operations from the database."""
        return self._repository.get_all_planned_operations()

    def get_planned_operation_by_id(self, op_id: int) -> PlannedOperation | None:
        """Get a planned operation by ID."""
        return self._repository.get_planned_operation_by_id(op_id)

    def add_planned_operation(self, op: PlannedOperation) -> int:
        """Add a new planned operation.

        Args:
            op: Planned operation to add (id should be None).

        Returns:
            The ID of the newly created planned operation.
        """
        op_id = self._repository.upsert_planned_operation(op)
        self._invalidate_cache()

        # Recalculate heuristic links for the new planned operation
        if self._auto_link:
            self._recalculate_planned_operation_links(op_id)

        return op_id

    def update_planned_operation(self, op: PlannedOperation) -> None:
        """Update an existing planned operation.

        Args:
            op: Planned operation with updated values (id must not be None).
        """
        if op.id is None:
            raise ValueError("Planned operation must have a valid ID for update")
        self._repository.upsert_planned_operation(op)
        self._invalidate_cache()

        # Recalculate heuristic links for the modified planned operation
        if self._auto_link:
            self._recalculate_planned_operation_links(op.id)

    def delete_planned_operation(self, op_id: int) -> None:
        """Delete a planned operation.

        Args:
            op_id: ID of the planned operation to delete.
        """
        self._repository.delete_planned_operation(op_id)
        self._invalidate_cache()

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

        # After load_forecast(), _forecast is guaranteed to be set
        assert self._forecast is not None

        if start_date is None:
            start_date = date.today() - relativedelta(months=4)
        if end_date is None:
            end_date = date.today() + relativedelta(months=12)

        logger.info("Computing forecast report from %s to %s", start_date, end_date)

        analyzer = AccountAnalyzer(self._account, self._forecast)
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

    def get_monthly_summary(self) -> list[MonthlySummary]:
        """Get monthly budget summary.

        Returns:
            List of monthly summaries with category breakdowns.
        """
        if self._report is None:
            return []

        df = self._report.budget_forecast
        summaries: list[MonthlySummary] = []

        # Get unique months from columns
        months = sorted({col[0] for col in df.columns})

        for month in months:
            categories: dict[str, CategoryBudget] = {}
            for category in df.index:
                if category == "Total":
                    continue

                real = (
                    df.loc[category, (month, "Réel")]
                    if (month, "Réel") in df.columns
                    else 0
                )
                predicted = (
                    df.loc[category, (month, "Prévu")]
                    if (month, "Prévu") in df.columns
                    else 0
                )
                actualized = (
                    df.loc[category, (month, "Actualisé")]
                    if (month, "Actualisé") in df.columns
                    else 0
                )

                if any((real != 0, predicted != 0, actualized != 0)):
                    categories[str(category)] = CategoryBudget(
                        real=float(real),
                        predicted=float(predicted),
                        actualized=float(actualized),
                    )
            summaries.append(MonthlySummary(month=month, categories=categories))

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

    # Link recalculation methods

    def _recalculate_planned_operation_links(self, op_id: int) -> None:
        """Recalculate heuristic links for a planned operation.

        Args:
            op_id: The ID of the planned operation.
        """
        if (planned_op := self._repository.get_planned_operation_by_id(op_id)) is None:
            return

        operations = self._account.operations
        self._operation_link_service.recalculate_links_for_target(
            LinkType.PLANNED_OPERATION,
            op_id,
            operations,
            planned_op.matcher,
        )
        logger.debug("Recalculated links for planned operation %d", op_id)

    def _recalculate_budget_links(self, budget_id: int) -> None:
        """Recalculate heuristic links for a budget.

        Args:
            budget_id: The ID of the budget.
        """
        if (budget := self._repository.get_budget_by_id(budget_id)) is None:
            return

        operations = self._account.operations
        # Create a basic matcher for the budget
        matcher = OperationMatcher(operation_range=budget)
        self._operation_link_service.recalculate_links_for_target(
            LinkType.BUDGET,
            budget_id,
            operations,
            matcher,
        )
        logger.debug("Recalculated links for budget %d", budget_id)
