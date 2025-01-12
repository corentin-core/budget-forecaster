"""Module to render account analysis data."""
import abc
import pathlib
from datetime import datetime
from pathlib import Path

import pandas as pd
from matplotlib import pyplot as plt

from budget_forecaster.account.account_analysis_report import AccountAnalysisReport


class AccountAnalysisRenderer(abc.ABC):  # pylint: disable=too-few-public-methods
    """
    A class to render account analysis data.
    """

    @abc.abstractmethod
    def render_report(self, report: AccountAnalysisReport) -> None:
        """
        Render an account analysis report.
        """


class AccountAnalysisRendererExcel(AccountAnalysisRenderer):
    """
    Exports account analysis data to an Excel file.
    """

    def __init__(self, path: Path) -> None:
        self.__writer = pd.ExcelWriter(
            path,
            engine="xlsxwriter",
            datetime_format="mmm yy",
            date_format="dd/mm/yyyy",
        )
        workbook = self.__writer.book
        self.__money_format = workbook.add_format({"num_format": "#,##0.00 €"})
        self.__saved_plots: list[pathlib.Path] = []

    def render_report(self, report: AccountAnalysisReport) -> None:
        self.__add_balance_evolution(
            report.balance_date, report.balance_evolution_per_day
        )
        self.__add_expenses_forecast(report.budget_forecast)
        self.__add_expenses_statistics(report.budget_statistics)
        self.__add_operations(report.operations)
        self.__add_forecast(report.forecast)
        self.__do_export()

    def __add_operations(self, operations: pd.DataFrame) -> None:
        sheet_name = "Opérations"

        # hack: we can't set multiple date formats in the same workbook
        # convert datetime to date to avoid the datetime format
        operations_reformatted = operations.copy()
        operations_reformatted.index = operations_reformatted.index.date
        operations_reformatted.index.name = "Date"
        operations_reformatted = operations_reformatted.sort_index(ascending=False)

        operations_reformatted.to_excel(
            self.__writer, sheet_name=sheet_name, index=True
        )
        worksheet = self.__writer.sheets[sheet_name]
        worksheet.autofit()
        worksheet.set_column(0, 0, 20)
        worksheet.set_column(2, 2, 100)
        worksheet.set_column(3, 3, 12, self.__money_format)
        worksheet.autofilter("A1:D1")
        worksheet.freeze_panes(1, 0)

    def __add_forecast(self, forecast: pd.DataFrame) -> None:
        sheet_name = "Source prévisions"
        forecast_reformatted = forecast.copy()
        # convert datetime to date to avoid the datetime format only on non-empty cells
        forecast_reformatted["Date de début"] = forecast_reformatted[
            "Date de début"
        ].apply(lambda x: x.date() if not pd.isnull(x) else x)
        forecast_reformatted["Date de fin"] = forecast_reformatted["Date de fin"].apply(
            lambda x: x.date() if not pd.isnull(x) else x
        )

        forecast_reformatted.to_excel(self.__writer, sheet_name=sheet_name, index=True)
        worksheet = self.__writer.sheets[sheet_name]
        worksheet.autofit()
        worksheet.set_column(2, 5, 20)
        worksheet.set_column(2, 2, 20, self.__money_format)
        worksheet.autofilter("A1:F1")
        worksheet.freeze_panes(1, 0)

    @staticmethod
    def __add_safe_margin(
        balance_date: datetime, balance_evolution: pd.DataFrame
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
    def __get_balance_evolution_per_month(
        balance_date: datetime,
        balance_evolution: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Compute the balance of the account per month,
        the minimum balance per month and the safe margin.
        """
        balance_evolution_per_month = AccountAnalysisRendererExcel.__add_safe_margin(
            balance_date, balance_evolution
        )
        balance_evolution_per_month = balance_evolution_per_month.resample("MS").first()
        balance_evolution_per_month["Solde Min."] = balance_evolution.resample(
            "MS"
        ).min()
        balance_evolution_per_month = balance_evolution_per_month.round(2)

        return balance_evolution_per_month

    @staticmethod
    def __make_random_temp_path(file_name: str) -> pathlib.Path:
        path = Path(f"/tmp/{round(datetime.now().timestamp(), 0)}/{file_name}")
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def plot_balance_evolution(
        self, balance_date: datetime, balance_evolution: pd.DataFrame
    ) -> pathlib.Path:
        """
        Plot the balance evolution with a safe margin.
        Return the path of the saved plot.
        """

        balance_evolution_with_stats = self.__add_safe_margin(
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
        saved_path = self.__make_random_temp_path("balance_evolution.png")
        plt.savefig(saved_path)
        return saved_path

    def __add_balance_evolution(
        self, balance_date: datetime, balance_evolution: pd.DataFrame
    ) -> None:
        sheet_name = "Evolution du solde"

        balance_evolution_per_month = self.__get_balance_evolution_per_month(
            balance_date, balance_evolution
        )
        balance_evolution_per_month.to_excel(
            self.__writer, sheet_name=sheet_name, index=True
        )
        worksheet = self.__writer.sheets[sheet_name]
        worksheet.autofit()
        worksheet.set_column(1, 3, 12, self.__money_format)

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
        self.__saved_plots.append(plot_path)

    def __add_expenses_forecast(self, expenses_forecast: pd.DataFrame) -> None:
        sheet_name = "Prévisions des dépenses"

        expenses_forecast = expenses_forecast.mask(expenses_forecast.eq(0))
        expenses_forecast.to_excel(self.__writer, sheet_name=sheet_name, index=True)
        worksheet = self.__writer.sheets[sheet_name]
        worksheet.autofit()
        worksheet.set_column(1, 21, 12, self.__money_format)

        # compare "Prévu" and "Réel" columns
        # and highlight the cells where the "Réel" value is lower than the "Prévu" value
        date_to_header_column: dict[str, dict[str, int]] = {}
        for i, (date, header_to_column) in enumerate(expenses_forecast.columns):
            date_to_header_column.setdefault(date, {}).setdefault(header_to_column, i)

        for date, header_to_column in date_to_header_column.items():
            if "Prévu" not in header_to_column or "Réel" not in header_to_column:
                continue

            real_column_letter = chr(ord("B") + header_to_column["Réel"])
            forecast_column_letter = chr(ord("B") + header_to_column["Prévu"])
            worksheet.conditional_format(
                f"{real_column_letter}2:{real_column_letter}{len(expenses_forecast)}",
                {
                    "type": "formula",
                    "criteria": f"={real_column_letter}2<{forecast_column_letter}2",
                    "format": self.__writer.book.add_format({"bg_color": "red"}),
                },
            )

        worksheet.freeze_panes(0, 1)

    def __add_expenses_statistics(self, expenses_statistics: pd.DataFrame) -> None:
        sheet_name = "Statistiques des dépenses"

        expenses_statistics = expenses_statistics.sort_index()
        expenses_statistics.to_excel(self.__writer, sheet_name=sheet_name, index=True)
        worksheet = self.__writer.sheets[sheet_name]
        worksheet.autofit()
        worksheet.set_column(1, 2, 25, self.__money_format)

        # create a pie plot for the total expenses
        # filter only negative values corresponding to expenses and get their absolute value
        filtered_expenses = expenses_statistics[expenses_statistics["Total"] < 0].abs()
        plt.figure(figsize=(15, 10))
        plt.pie(
            filtered_expenses["Total"],
            labels=filtered_expenses.index,
            autopct="%1.1f%%",
        )
        plt.title("Répartition des dépenses")
        plot_path = self.__make_random_temp_path("expenses_pie.png")
        plt.savefig(plot_path)
        worksheet.insert_image("E1", plot_path)
        self.__saved_plots.append(plot_path)

    def __do_export(self) -> None:
        self.__writer.close()
        # remove the saved plots files
        for plot_path in self.__saved_plots:
            plot_path.unlink()
        self.__saved_plots = []
