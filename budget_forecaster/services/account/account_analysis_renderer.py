"""Module to render account analysis data."""
from __future__ import annotations

import abc
import tempfile
from datetime import date
from pathlib import Path
from types import TracebackType
from typing import Any

import pandas as pd
from matplotlib import pyplot as plt

from budget_forecaster.core.types import BudgetColumn, Category
from budget_forecaster.i18n import _
from budget_forecaster.services.account.account_analysis_report import (
    AccountAnalysisReport,
)


class AccountAnalysisRenderer(abc.ABC):
    """
    Abstract base class for account analysis renderers.

    Must be used as a context manager.
    """

    @abc.abstractmethod
    def __enter__(self) -> AccountAnalysisRenderer:
        """Enter context manager and initialize resources."""

    @abc.abstractmethod
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit context manager and cleanup resources."""

    @abc.abstractmethod
    def __call__(self, report: AccountAnalysisReport) -> None:
        """Render an account analysis report."""


class AccountAnalysisRendererExcel(AccountAnalysisRenderer):
    """
    Exports account analysis data to an Excel file.

    Must be used as a context manager:
        with AccountAnalysisRendererExcel(path) as renderer:
            renderer(report)
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._writer_impl: pd.ExcelWriter | None = None
        self._money_format: object = None
        self._temp_dir_impl: tempfile.TemporaryDirectory[str] | None = None

    @property
    def _writer(self) -> pd.ExcelWriter:
        """Return the writer, raising if not in context manager."""
        if self._writer_impl is None:
            raise RuntimeError("Renderer must be used as a context manager")
        return self._writer_impl

    @property
    def _temp_dir(self) -> Path:
        """Return the temp directory path, raising if not in context manager."""
        if self._temp_dir_impl is None:
            raise RuntimeError("Renderer must be used as a context manager")
        return Path(self._temp_dir_impl.name)

    def __enter__(self) -> AccountAnalysisRendererExcel:
        self._temp_dir_impl = tempfile.TemporaryDirectory(prefix="budget_forecaster_")
        self._writer_impl = pd.ExcelWriter(
            self._path,
            engine="xlsxwriter",
            datetime_format="mmm yy",
            date_format="dd/mm/yyyy",
        )
        workbook = self._writer_impl.book
        money_fmt = {"num_format": "#,##0.00 €"}
        self._money_format = workbook.add_format(money_fmt)  # type: ignore[union-attr]
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self._writer_impl is not None:
            self._writer_impl.close()
        if self._temp_dir_impl is not None:
            self._temp_dir_impl.cleanup()

    def __call__(self, report: AccountAnalysisReport) -> None:
        self._add_balance_evolution(
            report.balance_date, report.balance_evolution_per_day
        )
        self._add_expenses_forecast(report.budget_forecast)
        self._add_expenses_statistics(report.budget_statistics)
        self._add_operations(report.operations)
        self._add_forecast(report.forecast)

    @staticmethod
    def _translate_category_index(df: pd.DataFrame) -> pd.DataFrame:
        """Translate Category enum values in the index to display names."""
        translated = df.copy()
        translated.index = [
            cat.display_name if isinstance(cat, Category) else _(str(cat))
            for cat in translated.index
        ]
        return translated

    def _add_operations(self, operations: pd.DataFrame) -> None:
        sheet_name = _("Operations")

        operations_reformatted = operations.copy()
        operations_reformatted = operations_reformatted.sort_index(ascending=False)
        # Translate for export
        operations_reformatted.index.name = _("Date")
        operations_reformatted.columns = [
            _("Category"),
            _("Description"),
            _("Amount"),
        ]
        # Translate category values
        cat_col = operations_reformatted.columns[0]
        operations_reformatted[cat_col] = [
            cat.display_name if isinstance(cat, Category) else str(cat)
            for cat in operations_reformatted[cat_col]
        ]

        operations_reformatted.to_excel(self._writer, sheet_name=sheet_name, index=True)
        worksheet = self._writer.sheets[sheet_name]
        worksheet.autofit()
        worksheet.set_column(0, 0, 20)
        worksheet.set_column(2, 2, 100)
        worksheet.set_column(3, 3, 12, self._money_format)
        worksheet.autofilter("A1:D1")
        worksheet.freeze_panes(1, 0)

    def _add_forecast(self, forecast: pd.DataFrame) -> None:
        sheet_name = _("Forecast source")
        forecast_reformatted = self._translate_category_index(forecast)
        forecast_reformatted.index.name = _("Category")
        forecast_reformatted.columns = [
            _("Description"),
            _("Amount"),
            _("Start date"),
            _("End date"),
            _("Frequency"),
        ]
        forecast_reformatted.to_excel(self._writer, sheet_name=sheet_name, index=True)
        worksheet = self._writer.sheets[sheet_name]
        worksheet.autofit()
        worksheet.set_column(2, 5, 20)
        worksheet.set_column(2, 2, 20, self._money_format)
        worksheet.autofilter("A1:F1")
        worksheet.freeze_panes(1, 0)

    @staticmethod
    def _add_safe_margin(
        balance_date: date, balance_evolution: pd.DataFrame
    ) -> pd.DataFrame:
        balance_evolution_with_margin = balance_evolution.copy()
        # add the minimum balance of the subsequent months
        # to do so, we reverse the dataframe, compute the cumulative minimum and reverse it back
        balance_evolution_with_margin["Margin"] = (
            balance_evolution["Balance"].iloc[::-1].expanding().min().iloc[::-1]
        )
        # remove margin values before balance date as they are not relevant
        balance_evolution_with_margin.loc[
            balance_evolution_with_margin.index < balance_date.strftime("%Y-%m-%d"),
            "Margin",
        ] = None
        return balance_evolution_with_margin

    @staticmethod
    def _get_balance_evolution_per_month(
        balance_date: date,
        balance_evolution: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Compute the balance of the account per month,
        the minimum balance per month and the safe margin.
        """
        balance_evolution_per_month = AccountAnalysisRendererExcel._add_safe_margin(
            balance_date, balance_evolution
        )
        balance_evolution_per_month = balance_evolution_per_month.resample("MS").first()
        balance_evolution_per_month["Min. Balance"] = balance_evolution.resample(
            "MS"
        ).min()
        balance_evolution_per_month = balance_evolution_per_month.round(2)

        return balance_evolution_per_month

    def plot_balance_evolution(
        self, balance_date: date, balance_evolution: pd.DataFrame
    ) -> Path:
        """
        Plot the balance evolution with a safe margin.
        Return the path of the saved plot.
        """

        balance_evolution_with_stats = self._add_safe_margin(
            balance_date, balance_evolution
        )
        ax = balance_evolution_with_stats.plot(figsize=(15, 10))
        ax.set_yticks(range(0, int(balance_evolution_with_stats["Balance"].max()), 250))
        ax.set_xticks(
            [date for date in balance_evolution_with_stats.index if date.day == 1]
        )
        plt.legend([_("Balance"), _("Margin")])
        plt.grid()
        plt.title(_("Account balance evolution"))
        saved_path = self._temp_dir / "balance_evolution.png"
        plt.savefig(saved_path)
        return saved_path

    def _add_balance_evolution(
        self, balance_date: date, balance_evolution: pd.DataFrame
    ) -> None:
        sheet_name = _("Balance evolution")

        balance_evolution_per_month = self._get_balance_evolution_per_month(
            balance_date, balance_evolution
        )
        # Translate column headers for export
        export_balance = balance_evolution_per_month.rename(
            columns={
                "Balance": _("Balance"),
                "Margin": _("Margin"),
                "Min. Balance": _("Min. Balance"),
            }
        )
        export_balance.index.name = _("Date")
        export_balance.to_excel(self._writer, sheet_name=sheet_name, index=True)
        worksheet = self._writer.sheets[sheet_name]
        worksheet.autofit()
        worksheet.set_column(1, 3, 12, self._money_format)

        # add conditional formatting
        last_row = len(balance_evolution_per_month) + 1
        worksheet.conditional_format(
            f"B2:D{last_row}",
            {
                "type": "3_color_scale",
                "min_color": "red",
                "mid_color": "yellow",
                "max_color": "green",
                "min_value": "0",
                "max_value": "10000",
            },
        )

        plot_path = self.plot_balance_evolution(balance_date, balance_evolution)
        worksheet.insert_image("F1", plot_path)

    def _add_expenses_forecast(self, expenses_forecast: pd.DataFrame) -> None:
        sheet_name = _("Expense forecast")

        # Filter to main columns only (exclude source-breakdown detail)
        main_columns = {
            BudgetColumn.TOTAL_PLANNED,
            BudgetColumn.ACTUAL,
            BudgetColumn.PROJECTED,
        }
        export_columns = [
            col for col in expenses_forecast.columns if col[1] in main_columns
        ]
        expenses_forecast = expenses_forecast[export_columns]

        expenses_forecast = expenses_forecast.mask(expenses_forecast.eq(0))
        # Translate for export: column sub-headers and category index
        if not expenses_forecast.empty:
            col_tr: dict[str, str] = {
                BudgetColumn.ACTUAL: _("Actual"),
                BudgetColumn.TOTAL_PLANNED: _("Planned"),
                BudgetColumn.PROJECTED: _("Projected"),
            }
            export_df = self._translate_category_index(expenses_forecast)
            export_df.columns = pd.MultiIndex.from_tuples(
                [(col[0], col_tr.get(col[1], col[1])) for col in export_df.columns]
            )
        else:
            export_df = expenses_forecast
        export_df.to_excel(self._writer, sheet_name=sheet_name, index=True)
        worksheet = self._writer.sheets[sheet_name]
        worksheet.autofit()
        worksheet.set_column(1, 21, 12, self._money_format)

        self._highlight_overspend(expenses_forecast, worksheet)
        worksheet.freeze_panes(0, 1)

    def _highlight_overspend(
        self, expenses_forecast: pd.DataFrame, worksheet: Any
    ) -> None:
        """Add conditional formatting to highlight Actual < Planned (overspend)."""
        month_to_column_index: dict[str, dict[str, int]] = {}
        for i, col in enumerate(expenses_forecast.columns):
            month_label, col_name = col[0], col[1]
            month_to_column_index.setdefault(month_label, {}).setdefault(col_name, i)

        for _month, column_index in month_to_column_index.items():
            if (
                BudgetColumn.TOTAL_PLANNED not in column_index
                or BudgetColumn.ACTUAL not in column_index
            ):
                continue

            actual_letter = chr(ord("B") + column_index[BudgetColumn.ACTUAL])
            planned_letter = chr(ord("B") + column_index[BudgetColumn.TOTAL_PLANNED])
            worksheet.conditional_format(
                f"{actual_letter}2:{actual_letter}{len(expenses_forecast)}",
                {
                    "type": "formula",
                    "criteria": f"={actual_letter}2<{planned_letter}2",
                    "format": self._writer.book.add_format(  # type: ignore[union-attr]
                        {"bg_color": "red"}
                    ),
                },
            )

    def _add_expenses_statistics(self, expenses_statistics: pd.DataFrame) -> None:
        sheet_name = _("Expense statistics")

        expenses_statistics = expenses_statistics.sort_index()
        # Translate for export
        export_stats = self._translate_category_index(expenses_statistics)
        export_stats.index.name = _("Category")
        export_stats.columns = [_("Total"), _("Monthly average")]
        export_stats.to_excel(self._writer, sheet_name=sheet_name, index=True)
        worksheet = self._writer.sheets[sheet_name]
        worksheet.autofit()
        worksheet.set_column(1, 2, 25, self._money_format)

        # create a pie plot for the total expenses
        # filter only negative values corresponding to expenses and get their absolute value
        filtered_expenses = expenses_statistics[expenses_statistics["Total"] < 0].abs()
        pie_labels = [
            cat.display_name if isinstance(cat, Category) else str(cat)
            for cat in filtered_expenses.index
        ]
        plt.figure(figsize=(15, 10))
        plt.pie(
            filtered_expenses["Total"],
            labels=pie_labels,
            autopct="%1.1f%%",
        )
        plt.title(_("Expense breakdown"))
        plot_path = self._temp_dir / "expenses_pie.png"
        plt.savefig(plot_path)
        worksheet.insert_image("E1", plot_path)
