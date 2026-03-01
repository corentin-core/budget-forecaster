"""Module to analyze account data for budget forecasting."""
import itertools
import logging
from collections import defaultdict
from datetime import date, timedelta
from typing import NamedTuple

import pandas as pd
from dateutil.relativedelta import relativedelta

from budget_forecaster.core.date_range import RecurringDateRange
from budget_forecaster.core.types import (
    BudgetColumn,
    BudgetId,
    Category,
    LinkType,
    OperationId,
    PlannedOperationId,
)
from budget_forecaster.domain.account.account import Account
from budget_forecaster.domain.forecast.forecast import Forecast
from budget_forecaster.domain.operation.operation_link import OperationLink
from budget_forecaster.services.account.account_analysis_report import (
    AccountAnalysisReport,
)
from budget_forecaster.services.account.account_forecaster import AccountForecaster
from budget_forecaster.services.forecast.forecast_actualizer import ForecastActualizer
from budget_forecaster.services.operation.operations_categorizer import (
    categorize_operations,
)

logger = logging.getLogger(__name__)

# Type aliases for the budget data accumulator
_MonthColumns = dict[BudgetColumn, float]
_CategoryMonths = dict[date, _MonthColumns]
_BudgetData = dict[Category, _CategoryMonths]


class _LinkIndexes(NamedTuple):
    """Indexes built from operation links for link-aware attribution."""

    op_to_linked_month: dict[OperationId, date]
    realized_iterations: dict[PlannedOperationId, set[date]]
    budget_linked_amounts: defaultdict[tuple[BudgetId, date], float]


def _increment(
    budget_data: _BudgetData,
    category: Category,
    month: date,
    column: BudgetColumn,
    amount: float,
) -> None:
    """Increment a value in the budget data accumulator."""
    budget_data.setdefault(category, {}).setdefault(month, {}).setdefault(column, 0.0)
    budget_data[category][month][column] += amount


class AccountAnalyzer:
    """Analyze account data for budget forecasting."""

    def __init__(
        self,
        account: Account,
        forecast: Forecast,
        operation_links: tuple[OperationLink, ...] = (),
    ) -> None:
        self._account = account._replace(
            operations=categorize_operations(account.operations, forecast)
        )
        self._forecast = forecast
        self._operation_links = operation_links

    def compute_report(self, start_date: date, end_date: date) -> AccountAnalysisReport:
        """
        Compute an account analysis report between two dates.
        """
        return AccountAnalysisReport(
            balance_date=self._account.balance_date,
            start_date=start_date,
            end_date=end_date,
            operations=self.compute_operations(start_date, end_date),
            forecast=self.compute_forecast(start_date, end_date),
            balance_evolution_per_day=self.compute_balance_evolution_per_day(
                start_date, end_date
            ),
            budget_forecast=self.compute_budget_forecast(start_date, end_date),
            budget_statistics=self.compute_budget_statistics(start_date, end_date),
        )

    def compute_operations(self, start_date: date, end_date: date) -> pd.DataFrame:
        """Compute the operations of the account."""
        operations: dict[str, list] = {
            "Date": [],
            "Category": [],
            "Description": [],
            "Amount": [],
        }
        for operation in self._account.operations:
            if start_date <= operation.operation_date <= end_date:
                operations["Date"].append(operation.operation_date)
                operations["Category"].append(operation.category)
                operations["Description"].append(operation.description)
                operations["Amount"].append(operation.amount)

        df = pd.DataFrame(operations)
        df.set_index("Date", inplace=True)
        return df

    @staticmethod
    def _relative_delta_to_str(delta: relativedelta | None) -> str:
        """Convert a relativedelta to a string."""
        if delta is None:
            return ""

        years_str = ""
        months_str = ""
        days_str = ""
        if delta.years:
            years_str = (
                f"{delta.years} Year" if delta.years == 1 else f"{delta.years} Years"
            )
        if delta.months:
            months_str = (
                f"{delta.months} Month"
                if delta.months == 1
                else f"{delta.months} Months"
            )
        if delta.days:
            days_str = f"{delta.days} Day" if delta.days == 1 else f"{delta.days} Days"
        return " ".join(filter(None, [years_str, months_str, days_str]))

    def compute_forecast(self, start_date: date, end_date: date) -> pd.DataFrame:
        """Compute the budget forecast of the account."""
        budget_forecast: dict[str, list] = {
            "Category": [],
            "Description": [],
            "Amount": [],
            "Start date": [],
            "End date": [],
            "Frequency": [],
        }
        for operation_range in itertools.chain(
            self._forecast.operations, self._forecast.budgets
        ):
            time_range = operation_range.date_range
            if time_range.is_future(end_date):
                continue

            if time_range.is_expired(start_date):
                continue

            budget_forecast["Category"].append(operation_range.category)
            budget_forecast["Description"].append(operation_range.description)
            budget_forecast["Amount"].append(operation_range.amount)
            budget_forecast["Start date"].append(time_range.start_date)
            budget_forecast["End date"].append(
                time_range.last_date if time_range.last_date < date.max else None
            )
            period = (
                time_range.period
                if isinstance(time_range, RecurringDateRange)
                else None
            )
            budget_forecast["Frequency"].append(self._relative_delta_to_str(period))

        df = pd.DataFrame(budget_forecast)
        df.set_index("Category", inplace=True)
        df.sort_index(inplace=True)
        return df

    def compute_balance_evolution_per_day(
        self, start_date: date, end_date: date
    ) -> pd.DataFrame:
        """Compute the balance of the account between two dates."""
        if start_date > end_date:
            raise ValueError(
                f"start_date must be <= end_date, got {start_date} > {end_date}"
            )

        actualized_forecast = ForecastActualizer(self._account, self._operation_links)(
            self._forecast
        )
        account_forecaster = AccountForecaster(self._account, actualized_forecast)

        initial_state = account_forecaster(start_date)
        final_state = account_forecaster(end_date)

        current_balance = initial_state.balance
        balance_evolution: list[float] = [current_balance]
        dates = pd.date_range(start_date, end_date, freq="D")
        for ts in dates[1:]:
            current_date = ts.date()
            for operation in final_state.operations:
                if operation.operation_date == current_date:
                    current_balance += operation.amount
            balance_evolution.append(current_balance)

        df = pd.DataFrame({"Date": dates, "Balance": balance_evolution})
        df.set_index("Date", inplace=True)
        return df

    def compute_budget_forecast(self, start_date: date, end_date: date) -> pd.DataFrame:
        """Compute per-category monthly budget forecast with link-aware attribution.

        Produces a MultiIndex DataFrame with columns (month, column_name) where
        column_name is a BudgetColumn value: TotalPlanned, PlannedFromOps,
        PlannedFromBudgets, Actual, Forecast.
        """
        budget_data: _BudgetData = {}
        months = pd.date_range(
            start_date.replace(day=1), end_date.replace(day=1), freq="MS"
        )
        link_indexes = self._build_link_indexes()
        self._fill_actual(
            budget_data, start_date, end_date, link_indexes.op_to_linked_month
        )
        self._fill_planned_operations(budget_data, months)
        self._fill_planned_budgets(budget_data, months)
        self._fill_unrealized_operations(budget_data, months, link_indexes)
        self._fill_unrealized_budgets(budget_data, months, link_indexes)
        self._finalize_projected(budget_data)
        return self._build_budget_forecast_df(budget_data)

    def _build_link_indexes(self) -> _LinkIndexes:
        """Build indexes from operation links for link-aware attribution."""
        op_to_linked_month: dict[OperationId, date] = {}
        realized_iterations: dict[PlannedOperationId, set[date]] = {}
        budget_linked_amounts: defaultdict[tuple[BudgetId, date], float] = defaultdict(
            float
        )
        op_amounts = {op.unique_id: op.amount for op in self._account.operations}

        for link in self._operation_links:
            linked_month = link.iteration_date.replace(day=1)
            op_to_linked_month[link.operation_unique_id] = linked_month

            match link.target_type:
                case LinkType.PLANNED_OPERATION:
                    realized_iterations.setdefault(link.target_id, set()).add(
                        link.iteration_date
                    )
                case LinkType.BUDGET:
                    op_amount = op_amounts.get(link.operation_unique_id, 0.0)
                    budget_linked_amounts[link.target_id, linked_month] += op_amount

        return _LinkIndexes(
            op_to_linked_month, realized_iterations, budget_linked_amounts
        )

    def _fill_actual(
        self,
        budget_data: _BudgetData,
        start_date: date,
        end_date: date,
        op_to_linked_month: dict[OperationId, date],
    ) -> None:
        """Fill the Actual column with link-aware attribution."""
        for operation in self._account.operations:
            if (
                operation.operation_date < start_date
                or operation.operation_date > end_date
            ):
                continue
            month = op_to_linked_month.get(
                operation.unique_id, operation.operation_date.replace(day=1)
            )
            _increment(
                budget_data,
                operation.category,
                month,
                BudgetColumn.ACTUAL,
                operation.amount,
            )

    def _fill_planned_operations(
        self, budget_data: _BudgetData, months: pd.DatetimeIndex
    ) -> None:
        """Fill TotalPlanned and PlannedFromOps for planned operations."""
        for ts in months:
            month_start = ts.date()
            month_end = month_start + relativedelta(months=1) - timedelta(days=1)

            for planned_op in self._forecast.operations:
                if amount := planned_op.amount_on_period(month_start, month_end):
                    _increment(
                        budget_data,
                        planned_op.category,
                        month_start,
                        BudgetColumn.TOTAL_PLANNED,
                        amount,
                    )
                    _increment(
                        budget_data,
                        planned_op.category,
                        month_start,
                        BudgetColumn.PLANNED_FROM_OPS,
                        amount,
                    )

    def _fill_planned_budgets(
        self, budget_data: _BudgetData, months: pd.DatetimeIndex
    ) -> None:
        """Fill TotalPlanned and PlannedFromBudgets for budgets."""
        for ts in months:
            month_start = ts.date()
            month_end = month_start + relativedelta(months=1) - timedelta(days=1)

            for budget in self._forecast.budgets:
                if amount := budget.amount_on_period(month_start, month_end):
                    _increment(
                        budget_data,
                        budget.category,
                        month_start,
                        BudgetColumn.TOTAL_PLANNED,
                        amount,
                    )
                    _increment(
                        budget_data,
                        budget.category,
                        month_start,
                        BudgetColumn.PLANNED_FROM_BUDGETS,
                        amount,
                    )

    def _fill_unrealized_operations(
        self,
        budget_data: _BudgetData,
        months: pd.DatetimeIndex,
        link_indexes: _LinkIndexes,
    ) -> None:
        """Fill _UNREALIZED with not-yet-realized planned operation amounts."""
        for ts in months:
            month_start = ts.date()
            month_end = month_start + relativedelta(months=1) - timedelta(days=1)

            for planned_op in self._forecast.operations:
                if planned_op.id is None:
                    logger.warning(
                        "Skipping planned operation '%s' with no database id",
                        planned_op.description,
                    )
                    continue
                realized = link_indexes.realized_iterations.get(planned_op.id, set())
                for date_range in planned_op.date_range.iterate_over_date_ranges():
                    if date_range.is_expired(month_start):
                        continue
                    if date_range.is_future(month_end):
                        break
                    if date_range.start_date not in realized:
                        _increment(
                            budget_data,
                            planned_op.category,
                            month_start,
                            BudgetColumn.UNREALIZED_INTERNAL,
                            planned_op.amount,
                        )

    def _fill_unrealized_budgets(
        self,
        budget_data: _BudgetData,
        months: pd.DatetimeIndex,
        link_indexes: _LinkIndexes,
    ) -> None:
        """Fill _UNREALIZED with not-yet-realized budget amounts."""
        for ts in months:
            month_start = ts.date()
            month_end = month_start + relativedelta(months=1) - timedelta(days=1)

            for budget in self._forecast.budgets:
                budget_amount = budget.amount_on_period(month_start, month_end)
                if not budget_amount or budget.id is None:
                    continue
                consumed = abs(
                    link_indexes.budget_linked_amounts[budget.id, month_start]
                )
                remaining = max(0.0, abs(budget_amount) - consumed)
                # Preserve the sign: expenses are negative, income is positive
                if unrealized := -remaining if budget_amount < 0 else remaining:
                    _increment(
                        budget_data,
                        budget.category,
                        month_start,
                        BudgetColumn.UNREALIZED_INTERNAL,
                        unrealized,
                    )

    @staticmethod
    def _finalize_projected(budget_data: _BudgetData) -> None:
        """Compute Forecast = Actual + _UNREALIZED, then drop _UNREALIZED."""
        for category_months in budget_data.values():
            for month_columns in category_months.values():
                actual = month_columns.get(BudgetColumn.ACTUAL, 0.0)
                unrealized = month_columns.pop(BudgetColumn.UNREALIZED_INTERNAL, 0.0)
                month_columns[BudgetColumn.FORECAST] = actual + unrealized

    @staticmethod
    def _build_budget_forecast_df(budget_data: _BudgetData) -> pd.DataFrame:
        """Build the final MultiIndex DataFrame from accumulated data."""
        df = pd.DataFrame.from_dict(
            {
                (category, month): month_columns
                for category, category_months in budget_data.items()
                for month, month_columns in category_months.items()
            },
            orient="index",
        )

        column_order = [
            BudgetColumn.TOTAL_PLANNED,
            BudgetColumn.PLANNED_FROM_OPS,
            BudgetColumn.PLANNED_FROM_BUDGETS,
            BudgetColumn.ACTUAL,
            BudgetColumn.FORECAST,
        ]

        df.index = pd.MultiIndex.from_tuples(df.index, names=["Category", "Month"])
        df = df.reindex(columns=column_order, fill_value=0)
        df = df.unstack(level=-1).fillna(0)  # type: ignore[assignment]
        df.columns = df.columns.swaplevel(0, 1)  # type: ignore[attr-defined]
        df.sort_index(axis=1, level=0, inplace=True)

        # Convert month strings to Timestamps and sort
        new_columns = [
            (pd.to_datetime(col[0], format="%Y-%m-%d"), col[1]) for col in df.columns
        ]
        new_columns = sorted(new_columns, key=lambda x: (x[0], x[1]))
        df.columns = pd.MultiIndex.from_tuples(new_columns)

        df = df.sort_index()
        df.loc["Total"] = df.sum(numeric_only=True, axis=0)
        df = df.round(0).astype(int)

        return df

    def compute_budget_statistics(
        self, start_date: date, end_date: date
    ) -> pd.DataFrame:
        """Compute the expenses statistics per category."""
        if not self._account.operations:
            return pd.DataFrame(
                columns=["Category", "Total", "Monthly average"]
            ).set_index("Category")

        expenses_per_category_dict: dict[Category, list[tuple[date, float]]] = {}
        analysis_start = max(
            min(operation.operation_date for operation in self._account.operations),
            start_date,
        )
        analysis_end = min(
            max(operation.operation_date for operation in self._account.operations),
            end_date,
        )

        # start period is the first day of the first complete month
        analysis_start = (
            analysis_start.replace(day=1) + relativedelta(months=1)
            if analysis_start.day != 1
            else analysis_start
        )
        # end period is the last day of the last complete month
        analysis_end = (
            analysis_end.replace(day=1) - timedelta(days=1)
            if analysis_end.day != 1
            else analysis_end
        )

        all_months = pd.date_range(analysis_start, analysis_end, freq="MS")

        for operation in self._account.operations:
            if analysis_start <= operation.operation_date <= analysis_end:
                expenses_per_category_dict.setdefault(operation.category, []).append(
                    (operation.operation_date, operation.amount)
                )
        expenses_per_category = {}
        for category, expenses in expenses_per_category_dict.items():
            df = pd.DataFrame(expenses, columns=["Date", "Amount"])
            df["Date"] = pd.to_datetime(df["Date"])
            expenses_per_category[category] = df.set_index("Date")

        df = pd.DataFrame(
            {
                "Category": list(expenses_per_category),
                "Total": [df["Amount"].sum() for df in expenses_per_category.values()],
                "Monthly average": [
                    df.resample("MS")["Amount"]
                    .sum()
                    .reindex(all_months, fill_value=0.0)
                    .mean()
                    for df in expenses_per_category.values()
                ],
            }
        )
        df.set_index("Category", inplace=True)
        df = df.round(2)
        return df
