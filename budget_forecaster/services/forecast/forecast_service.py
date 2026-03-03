"""Service for forecast operations."""

import enum
import logging
from datetime import date, timedelta
from typing import Any, NamedTuple, SupportsFloat, TypedDict, cast

import pandas as pd
from dateutil.relativedelta import relativedelta

from budget_forecaster.core.date_range import (
    DateRangeInterface,
    RecurringDateRange,
)
from budget_forecaster.core.types import (
    BudgetColumn,
    BudgetId,
    Category,
    OperationId,
    PlannedOperationId,
)
from budget_forecaster.domain.account.account_interface import AccountInterface
from budget_forecaster.domain.forecast.forecast import Forecast
from budget_forecaster.domain.operation.budget import Budget
from budget_forecaster.domain.operation.operation_link import OperationLink
from budget_forecaster.domain.operation.planned_operation import PlannedOperation
from budget_forecaster.i18n import _
from budget_forecaster.infrastructure.persistence.repository_interface import (
    RepositoryInterface,
)
from budget_forecaster.services.account.account_analysis_report import (
    AccountAnalysisReport,
)
from budget_forecaster.services.account.account_analyzer import AccountAnalyzer

logger = logging.getLogger(__name__)


class ForecastSourceType(enum.Enum):
    """Type of forecast source: budget envelope or planned operation."""

    BUDGET = enum.auto()
    PLANNED_OPERATION = enum.auto()


class CategoryBudget(TypedDict):
    """Budget values for a category in a given month."""

    planned: float
    actual: float
    forecast: float
    is_income: bool


class MonthlySummary(TypedDict):
    """Monthly budget summary."""

    month: Any  # pandas Timestamp
    categories: dict[str, CategoryBudget]


class PlannedSourceDetail(TypedDict):
    """A single planned source for a category in a month."""

    forecast_source_type: ForecastSourceType
    description: str
    periodicity: str
    amount: float
    iteration_day: int  # for budgets: period start day (used for sorting)


class AttributedOperationDetail(TypedDict):
    """An operation attributed to a category in a month (link-aware)."""

    operation_date: date
    description: str
    amount: float
    cross_month_annotation: str  # empty if same month


class CategoryDetail(TypedDict):
    """Full detail for a category in a given month."""

    category: Category
    month: date
    planned_sources: tuple[PlannedSourceDetail, ...]
    operations: tuple[AttributedOperationDetail, ...]
    total_planned: float
    total_actual: float
    forecast: float
    remaining: float
    is_income: bool


class _PeriodicityInfo(NamedTuple):
    """Display period information extracted from a date range."""

    label: str  # "monthly", "yearly", "one-time"
    unit: str  # "month", "year", "" (empty for one-time)


def _df_value(
    df: pd.DataFrame, month: Any, category: str, column: BudgetColumn
) -> float:
    """Get a value from the budget forecast DataFrame, defaulting to 0."""
    if (month, column) in df.columns:
        return float(cast(SupportsFloat, df.loc[category, (month, column)]))
    return 0.0


def _ordinal(day: int) -> str:
    """Return the ordinal for a day number (translatable)."""
    if 11 <= day <= 13:
        return _("{n}th").format(n=day)
    match day % 10:
        case 1:
            return _("{n}st").format(n=day)
        case 2:
            return _("{n}nd").format(n=day)
        case 3:
            return _("{n}rd").format(n=day)
        case _:
            return _("{n}th").format(n=day)


def _periodicity_info(date_range: DateRangeInterface) -> _PeriodicityInfo:
    """Extract display period label and unit from a date range."""
    if isinstance(date_range, RecurringDateRange):
        period = date_range.period
        if period == relativedelta(months=1):
            return _PeriodicityInfo(label=_("monthly"), unit=_("month"))
        if period == relativedelta(years=1):
            return _PeriodicityInfo(label=_("yearly"), unit=_("year"))
        return _PeriodicityInfo(label=str(period), unit=str(period))
    return _PeriodicityInfo(label=_("one-time"), unit="")


def _format_periodicity(planned_op: PlannedOperation) -> str:
    """Format the periodicity of a planned operation for display."""
    info = _periodicity_info(planned_op.date_range)
    ordinal = _ordinal(planned_op.date_range.start_date.day)
    return f"{info.label}, {ordinal}"


def _format_budget_periodicity(
    budget: Budget, month_start: date, month_end: date
) -> str:
    """Format the periodicity of a budget for display, including iteration dates."""
    info = _periodicity_info(budget.date_range)
    amount_str = f"{abs(budget.amount):,.0f}"
    dates = f"{month_start.strftime('%d/%m')}→{month_end.strftime('%d/%m')}"
    if info.unit:
        return f"{amount_str}/{info.unit} ({dates})"
    return f"{amount_str} ({dates})"


def _cross_month_annotation(
    operation_date: date, month_start: date, month_end: date
) -> str:
    """Build a cross-month annotation if the operation is from another month."""
    if month_start <= operation_date <= month_end:
        return ""
    date_str = operation_date.strftime("%b %d")
    if operation_date < month_start:
        return _("paid early (operation dated {})").format(date_str)
    return _("paid late (operation dated {})").format(date_str)


def _collect_operation_sources(
    operations: tuple[PlannedOperation, ...],
    category: Category,
    month_start: date,
    month_end: date,
) -> tuple[PlannedSourceDetail, ...]:
    """Collect planned operation sources for a category/month."""
    sources: list[PlannedSourceDetail] = []
    for planned_op in operations:
        if planned_op.category != category:
            continue
        if not (amount := planned_op.amount_on_period(month_start, month_end)):
            continue
        sources.append(
            PlannedSourceDetail(
                forecast_source_type=ForecastSourceType.PLANNED_OPERATION,
                description=planned_op.description,
                periodicity=_format_periodicity(planned_op),
                amount=amount,
                iteration_day=planned_op.date_range.start_date.day,
            )
        )
    return tuple(sources)


def _collect_budget_sources(
    budgets: tuple[Budget, ...],
    category: Category,
    month_start: date,
    month_end: date,
) -> tuple[PlannedSourceDetail, ...]:
    """Collect budget sources for a category/month."""
    sources: list[PlannedSourceDetail] = []
    for budget in budgets:
        if budget.category != category:
            continue
        if not (amount := budget.amount_on_period(month_start, month_end)):
            continue
        sources.append(
            PlannedSourceDetail(
                forecast_source_type=ForecastSourceType.BUDGET,
                description=budget.description,
                periodicity=_format_budget_periodicity(budget, month_start, month_end),
                amount=amount,
                iteration_day=month_start.day,
            )
        )
    return tuple(sources)


class ForecastService:
    """Service for generating and managing forecasts.

    This service handles forecast computation and CRUD operations for
    planned operations and budgets. Link management is orchestrated by
    ApplicationService.
    """

    def __init__(
        self,
        account_provider: AccountInterface,
        repository: RepositoryInterface,
    ) -> None:
        """Initialize the forecast service.

        Args:
            account_provider: Provider for the account to forecast.
            repository: Repository for data persistence.
        """
        self._account_provider = account_provider
        self._repository = repository
        self._forecast: Forecast | None = None
        self._report: AccountAnalysisReport | None = None

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

    def get_all_budgets(self) -> tuple[Budget, ...]:
        """Get all budgets from the database."""
        return self._repository.get_all_budgets()

    def get_budget_by_id(self, budget_id: BudgetId) -> Budget:
        """Get a budget by ID."""
        return self._repository.get_budget_by_id(budget_id)

    def add_budget(self, budget: Budget) -> Budget:
        """Add a new budget.

        Args:
            budget: Budget to add (id should be None).

        Returns:
            The newly created budget with its assigned ID.
        """
        budget_id = self._repository.upsert_budget(budget)
        self._invalidate_cache()
        return budget.replace(record_id=budget_id)

    def update_budget(self, budget: Budget) -> Budget:
        """Update an existing budget.

        Args:
            budget: Budget with updated values (id must not be None).

        Returns:
            The updated budget.
        """
        if budget.id is None:
            raise ValueError("Budget must have a valid ID for update")
        self._repository.upsert_budget(budget)
        self._invalidate_cache()
        return budget

    def delete_budget(self, budget_id: BudgetId) -> None:
        """Delete a budget.

        Args:
            budget_id: ID of the budget to delete.
        """
        self._repository.delete_budget(budget_id)
        self._invalidate_cache()

    # Planned Operation CRUD methods

    def get_all_planned_operations(self) -> tuple[PlannedOperation, ...]:
        """Get all planned operations from the database."""
        return self._repository.get_all_planned_operations()

    def get_planned_operation_by_id(
        self, op_id: PlannedOperationId
    ) -> PlannedOperation:
        """Get a planned operation by ID."""
        return self._repository.get_planned_operation_by_id(op_id)

    def add_planned_operation(self, op: PlannedOperation) -> PlannedOperation:
        """Add a new planned operation.

        Args:
            op: Planned operation to add (id should be None).

        Returns:
            The newly created planned operation with its assigned ID.
        """
        op_id = self._repository.upsert_planned_operation(op)
        self._invalidate_cache()
        return op.replace(record_id=op_id)

    def update_planned_operation(self, op: PlannedOperation) -> PlannedOperation:
        """Update an existing planned operation.

        Args:
            op: Planned operation with updated values (id must not be None).

        Returns:
            The updated planned operation.
        """
        if op.id is None:
            raise ValueError("Planned operation must have a valid ID for update")
        self._repository.upsert_planned_operation(op)
        self._invalidate_cache()
        return op

    def delete_planned_operation(self, op_id: PlannedOperationId) -> None:
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
        operation_links: tuple[OperationLink, ...] = (),
    ) -> AccountAnalysisReport:
        """Compute the forecast report.

        Args:
            start_date: Start date for the report (default: 4 months ago).
            end_date: End date for the report (default: 12 months from now).
            operation_links: Tuple of operation links to use for actualization.

        Returns:
            The computed AccountAnalysisReport.
        """
        forecast = self._forecast or self.load_forecast()

        if start_date is None:
            start_date = date.today() - relativedelta(months=4)
        if end_date is None:
            end_date = date.today() + relativedelta(months=12)

        logger.info("Computing forecast report from %s to %s", start_date, end_date)

        analyzer = AccountAnalyzer(
            self._account_provider.account, forecast, operation_links
        )
        self._report = analyzer.compute_report(start_date, end_date)

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
            (d.to_pydatetime().date(), float(row["Balance"]))  # type: ignore[attr-defined]
            for d, row in sampled.iterrows()
        ]

    def get_monthly_summary(self) -> list[MonthlySummary]:
        """Get monthly budget summary with link-aware attribution.

        Returns:
            List of monthly summaries with category breakdowns.
        """
        if self._report is None:
            return []

        df = self._report.budget_forecast
        summaries: list[MonthlySummary] = []

        months = sorted({col[0] for col in df.columns})

        for month in months:
            categories: dict[str, CategoryBudget] = {}
            for category in df.index:
                if category == "Total":
                    continue

                planned = _df_value(df, month, category, BudgetColumn.TOTAL_PLANNED)
                actual = _df_value(df, month, category, BudgetColumn.ACTUAL)
                projected = _df_value(df, month, category, BudgetColumn.FORECAST)

                if any((planned != 0, actual != 0, projected != 0)):
                    # Determine income vs expense from the first non-zero value.
                    # Priority matters: planned is user-defined (most reliable),
                    # actual may include partial refunds, projected is derived.
                    ref = planned or actual or projected
                    categories[str(category)] = CategoryBudget(
                        planned=planned,
                        actual=actual,
                        forecast=projected,
                        is_income=ref > 0,
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
            (str(cat), float(row["Total"]), float(row["Monthly average"]))
            for cat, row in df.iterrows()
        ]

    def get_category_detail(
        self,
        category: str,
        month: date,
        operation_links: tuple[OperationLink, ...] = (),
    ) -> CategoryDetail:
        """Get detailed breakdown for a category in a given month.

        Returns planned sources (budgets + planned operations) and attributed
        operations (link-aware) for the category in the given month.

        Args:
            category: Category name.
            month: First day of the month.
            operation_links: Links for link-aware attribution.

        Returns:
            Full category detail for the modal drill-down.
        """
        forecast = self._forecast or self.load_forecast()
        month_start = month.replace(day=1)
        month_end = month_start + relativedelta(months=1) - timedelta(days=1)

        cat = Category(category)
        planned_sources = self._collect_planned_sources(
            forecast, cat, month_start, month_end
        )
        operations = self._collect_attributed_operations(
            cat, month_start, month_end, operation_links
        )

        total_planned = sum(s["amount"] for s in planned_sources)
        total_actual = sum(op["amount"] for op in operations)

        # Read forecast from the cached report if available
        forecast_value = total_actual
        if self._report is not None:
            forecast_value = _df_value(
                self._report.budget_forecast,
                pd.Timestamp(month_start),
                cat,
                BudgetColumn.FORECAST,
            )
            if forecast_value == 0.0 and total_actual != 0.0:
                forecast_value = total_actual

        ref = total_planned or total_actual or forecast_value
        return CategoryDetail(
            category=cat,
            month=month_start,
            planned_sources=planned_sources,
            operations=operations,
            total_planned=total_planned,
            total_actual=total_actual,
            forecast=forecast_value,
            remaining=abs(forecast_value) - abs(total_actual),
            is_income=ref > 0,
        )

    def _collect_planned_sources(
        self,
        forecast: Forecast,
        category: Category,
        month_start: date,
        month_end: date,
    ) -> tuple[PlannedSourceDetail, ...]:
        """Collect planned operation and budget sources for a category/month."""
        op_sources = _collect_operation_sources(
            forecast.operations, category, month_start, month_end
        )
        budget_sources = _collect_budget_sources(
            forecast.budgets, category, month_start, month_end
        )
        sources = sorted(
            (*op_sources, *budget_sources),
            key=lambda s: (s["iteration_day"], s["description"]),
        )
        return tuple(sources)

    def _collect_attributed_operations(
        self,
        category: Category,
        month_start: date,
        month_end: date,
        operation_links: tuple[OperationLink, ...],
    ) -> tuple[AttributedOperationDetail, ...]:
        """Collect operations attributed to a category/month (link-aware)."""
        account = self._account_provider.account

        # Build link index: operation_unique_id → linked month (first day)
        op_to_linked_month: dict[OperationId, date] = {}
        for link in operation_links:
            op_to_linked_month[link.operation_unique_id] = link.iteration_date.replace(
                day=1
            )

        operations: list[AttributedOperationDetail] = []
        for op in account.operations:
            if op.category != category:
                continue

            linked_month = op_to_linked_month.get(op.unique_id)

            if linked_month is not None and linked_month != month_start:
                continue
            if linked_month is None and not (
                month_start <= op.operation_date <= month_end
            ):
                continue

            annotation = (
                _cross_month_annotation(op.operation_date, month_start, month_end)
                if linked_month is not None
                else ""
            )
            operations.append(
                AttributedOperationDetail(
                    operation_date=op.operation_date,
                    description=op.description,
                    amount=op.amount,
                    cross_month_annotation=annotation,
                )
            )

        operations.sort(key=lambda o: (o["operation_date"], o["description"]))
        return tuple(operations)
