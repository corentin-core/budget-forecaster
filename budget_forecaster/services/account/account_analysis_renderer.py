"""Module to render account analysis data."""
from __future__ import annotations

import abc
import tempfile
from datetime import date
from pathlib import Path
from types import TracebackType

import pandas as pd
from matplotlib import pyplot as plt

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

    def _add_operations(self, operations: pd.DataFrame) -> None:
        sheet_name = "Opérations"

        # hack: we can't set multiple date formats in the same workbook
        # convert datetime to date to avoid the datetime format
        operations_reformatted = operations.copy()
        idx = operations_reformatted.index
        operations_reformatted.index = idx.date  # type: ignore[attr-defined]
        operations_reformatted.index.name = "Date"
        operations_reformatted = operations_reformatted.sort_index(ascending=False)

        operations_reformatted.to_excel(self._writer, sheet_name=sheet_name, index=True)
        worksheet = self._writer.sheets[sheet_name]
        worksheet.autofit()
        worksheet.set_column(0, 0, 20)
        worksheet.set_column(2, 2, 100)
        worksheet.set_column(3, 3, 12, self._money_format)
        worksheet.autofilter("A1:D1")
        worksheet.freeze_panes(1, 0)

    def _add_forecast(self, forecast: pd.DataFrame) -> None:
        sheet_name = "Source prévisions"
        forecast_reformatted = forecast.copy()
        # Dates are already date objects, no conversion needed

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
        balance_evolution_with_margin["Marge"] = (
            balance_evolution["Solde"].iloc[::-1].expanding().min().iloc[::-1]
        )
        # remove margin values before balance date as they are not relevant
        balance_evolution_with_margin.loc[
            balance_evolution_with_margin.index < balance_date.strftime("%Y-%m-%d"),
            "Marge",
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
        balance_evolution_per_month["Solde Min."] = balance_evolution.resample(
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
        ax.set_yticks(range(0, int(balance_evolution_with_stats["Solde"].max()), 250))
        ax.set_xticks(
            [date for date in balance_evolution_with_stats.index if date.day == 1]
        )
        plt.legend(["Solde", "Marge"])
        plt.grid()
        plt.title("Evolution du solde du compte")
        saved_path = self._temp_dir / "balance_evolution.png"
        plt.savefig(saved_path)
        return saved_path

    def _add_balance_evolution(
        self, balance_date: date, balance_evolution: pd.DataFrame
    ) -> None:
        sheet_name = "Evolution du solde"

        balance_evolution_per_month = self._get_balance_evolution_per_month(
            balance_date, balance_evolution
        )
        balance_evolution_per_month.to_excel(
            self._writer, sheet_name=sheet_name, index=True
        )
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
        sheet_name = "Prévisions des dépenses"

        expenses_forecast = expenses_forecast.mask(expenses_forecast.eq(0))
        expenses_forecast.to_excel(self._writer, sheet_name=sheet_name, index=True)
        worksheet = self._writer.sheets[sheet_name]
        worksheet.autofit()
        worksheet.set_column(1, 21, 12, self._money_format)

        # compare "Prévu" and "Réel" columns
        # and highlight the cells where the "Réel" value is lower than the "Prévu" value
        date_to_header_column: dict[str, dict[str, int]] = {}
        for i, col_tuple in enumerate(expenses_forecast.columns):
            col_date, header = col_tuple[0], col_tuple[1]
            date_to_header_column.setdefault(col_date, {}).setdefault(header, i)

        for _, header_to_column in date_to_header_column.items():
            if "Prévu" not in header_to_column or "Réel" not in header_to_column:
                continue

            real_column_letter = chr(ord("B") + header_to_column["Réel"])
            forecast_column_letter = chr(ord("B") + header_to_column["Prévu"])
            worksheet.conditional_format(
                f"{real_column_letter}2:{real_column_letter}{len(expenses_forecast)}",
                {
                    "type": "formula",
                    "criteria": f"={real_column_letter}2<{forecast_column_letter}2",
                    "format": self._writer.book.add_format(  # type: ignore[union-attr]
                        {"bg_color": "red"}
                    ),
                },
            )

        worksheet.freeze_panes(0, 1)

    def _add_expenses_statistics(self, expenses_statistics: pd.DataFrame) -> None:
        sheet_name = "Statistiques des dépenses"

        expenses_statistics = expenses_statistics.sort_index()
        expenses_statistics.to_excel(self._writer, sheet_name=sheet_name, index=True)
        worksheet = self._writer.sheets[sheet_name]
        worksheet.autofit()
        worksheet.set_column(1, 2, 25, self._money_format)

        # create a pie plot for the total expenses
        # filter only negative values corresponding to expenses and get their absolute value
        filtered_expenses = expenses_statistics[expenses_statistics["Total"] < 0].abs()
        plt.figure(figsize=(15, 10))
        plt.pie(
            filtered_expenses["Total"],
            labels=list(filtered_expenses.index),
            autopct="%1.1f%%",
        )
        plt.title("Répartition des dépenses")
        plot_path = self._temp_dir / "expenses_pie.png"
        plt.savefig(plot_path)
        worksheet.insert_image("E1", plot_path)
