"""Module to analyze account data for budget forecasting."""
import itertools
from datetime import datetime, timedelta

import pandas as pd
from dateutil.relativedelta import relativedelta

from budget_forecaster.account.account import Account
from budget_forecaster.account.account_analysis_report import AccountAnalysisReport
from budget_forecaster.account.account_forecaster import AccountForecaster
from budget_forecaster.forecast.forecast import Forecast
from budget_forecaster.forecast.forecast_actualizer import ForecastActualizer
from budget_forecaster.operation_range.operation_link import OperationLink
from budget_forecaster.operation_range.operations_categorizer import (
    OperationsCategorizer,
)
from budget_forecaster.time_range import PeriodicTimeRange
from budget_forecaster.types import Category


class AccountAnalyzer:
    """Analyze account data for budget forecasting."""

    def __init__(
        self,
        account: Account,
        forecast: Forecast,
        operation_links: tuple[OperationLink, ...] = (),
    ) -> None:
        self.__account = account._replace(
            operations=OperationsCategorizer(forecast)(account.operations)
        )
        self.__forecast = forecast
        self.__operation_links = operation_links

    def compute_report(
        self, start_date: datetime, end_date: datetime
    ) -> AccountAnalysisReport:
        """
        Compute an account analysis report between two dates.
        """
        return AccountAnalysisReport(
            balance_date=self.__account.balance_date,
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

    def compute_operations(
        self, start_date: datetime, end_date: datetime
    ) -> pd.DataFrame:
        """Compute the operations of the account."""
        operations: dict[str, list] = {
            "Date": [],
            "Catégorie": [],
            "Description": [],
            "Montant": [],
        }
        for operation in self.__account.operations:
            if start_date <= operation.date <= end_date:
                operations["Date"].append(operation.date)
                operations["Catégorie"].append(operation.category)
                operations["Description"].append(operation.description)
                operations["Montant"].append(operation.amount)

        df = pd.DataFrame(operations)
        df.set_index("Date", inplace=True)
        return df

    @staticmethod
    def __relative_delta_to_str(delta: relativedelta | None) -> str:
        """Convert a relativedelta to a string."""
        if delta is None:
            return ""

        years_str = ""
        months_str = ""
        days_str = ""
        if delta.years:
            years_str = f"{delta.years} Ans"
        if delta.months:
            months_str = f"{delta.months} Mois"
        if delta.days:
            days_str = f"{delta.days} Jours"
        return " ".join(filter(None, [years_str, months_str, days_str]))

    def compute_forecast(
        self, start_date: datetime, end_date: datetime
    ) -> pd.DataFrame:
        """Compute the budget forecast of the account."""
        budget_forecast: dict[str, list] = {
            "Catégorie": [],
            "Description": [],
            "Montant": [],
            "Date de début": [],
            "Date de fin": [],
            "Périodicité": [],
        }
        for operation_range in itertools.chain(
            self.__forecast.operations, self.__forecast.budgets
        ):
            time_range = operation_range.time_range
            if time_range.is_future(end_date):
                continue

            if time_range.is_expired(start_date):
                continue

            budget_forecast["Catégorie"].append(operation_range.category)
            budget_forecast["Description"].append(operation_range.description)
            budget_forecast["Montant"].append(operation_range.amount)
            budget_forecast["Date de début"].append(time_range.initial_date)
            budget_forecast["Date de fin"].append(
                time_range.last_date if time_range.last_date < datetime.max else None
            )
            period = (
                time_range.period if isinstance(time_range, PeriodicTimeRange) else None
            )
            budget_forecast["Périodicité"].append(self.__relative_delta_to_str(period))

        df = pd.DataFrame(budget_forecast)
        df.set_index("Catégorie", inplace=True)
        df.sort_index(inplace=True)
        return df

    def compute_balance_evolution_per_day(
        self, start_date: datetime, end_date: datetime
    ) -> pd.DataFrame:
        """Compute the balance of the account between two dates."""
        assert start_date <= end_date

        actualized_forecast = ForecastActualizer(
            self.__account, self.__operation_links
        )(self.__forecast)
        account_forecaster = AccountForecaster(self.__account, actualized_forecast)

        initial_state = account_forecaster(start_date)
        final_state = account_forecaster(end_date)

        current_balance = initial_state.balance
        balance_evolution: list[float] = [current_balance]
        dates = pd.date_range(start_date, end_date, freq="D")
        for current_date in dates[1:]:
            for operation in final_state.operations:
                if operation.date == current_date:
                    current_balance += operation.amount
            balance_evolution.append(current_balance)

        df = pd.DataFrame({"Date": dates, "Solde": balance_evolution})
        df.set_index("Date", inplace=True)
        return df

    def compute_budget_forecast(
        self, start_date: datetime, end_date: datetime
    ) -> pd.DataFrame:
        """
        Compute the expenses per category and
        month with actual vs forecast as secondary columns.
        """

        expenses_per_month_and_category: dict[
            Category, dict[datetime, dict[str, float]]
        ] = {}

        def increment_expense(
            category: Category, month: datetime, amount_type: str, amount: float
        ) -> None:
            expenses_per_month_and_category.setdefault(category, {}).setdefault(
                month, {}
            ).setdefault(amount_type, 0.0)
            expenses_per_month_and_category[category][month][amount_type] += amount

        actualized_forecast = ForecastActualizer(
            self.__account, self.__operation_links
        )(self.__forecast)
        account_forecaster = AccountForecaster(self.__account, actualized_forecast)

        # Actualized expenses are only computed for the current period
        current_month = self.__account.balance_date.replace(day=1)
        next_month_state = account_forecaster(
            current_month + relativedelta(months=1) - timedelta(days=1)
        )
        for operation in next_month_state.operations:
            if (
                current_month
                <= operation.date
                <= current_month + relativedelta(months=1) - timedelta(days=1)
            ):
                increment_expense(
                    operation.category,
                    operation.date.replace(day=1),
                    "Actualisé",
                    operation.amount,
                )

        for operation in self.__account.operations:
            if start_date <= operation.date <= end_date:
                increment_expense(
                    operation.category,
                    operation.date.replace(day=1),
                    "Réel",
                    operation.amount,
                )

        for month_start_date in pd.date_range(
            start_date.replace(day=1), end_date.replace(day=1), freq="MS"
        ):
            for operation_range in itertools.chain(
                self.__forecast.operations, self.__forecast.budgets
            ):
                increment_expense(
                    operation_range.category,
                    month_start_date,
                    "Prévu",
                    operation_range.amount_on_period(
                        month_start_date,
                        month_start_date + relativedelta(months=1) - timedelta(days=1),
                    ),
                )

        df = pd.DataFrame.from_dict(
            {
                (category, month): expenses
                for category, expenses_per_month in expenses_per_month_and_category.items()
                for month, expenses in expenses_per_month.items()
            },
            orient="index",
        )

        df.index = pd.MultiIndex.from_tuples(df.index, names=["Catégorie", "Mois"])
        df = df.unstack(level=-1).fillna(0)  # type: ignore[assignment]
        df.columns = df.columns.swaplevel(0, 1)  # type: ignore[attr-defined]
        df.sort_index(axis=1, level=0, inplace=True)

        # Filter out "Actualisé" columns for dates before the current balance date
        df = df.loc[
            :,
            (df.columns.get_level_values(0) >= current_month.strftime("%Y-%m-%d"))
            | (df.columns.get_level_values(1) == "Réel")
            | (df.columns.get_level_values(1) == "Prévu"),
        ]

        # Filter out "Réel" and "Actualisé" columns for dates after the current balance date
        df = df.loc[
            :,
            (df.columns.get_level_values(0) <= current_month.strftime("%Y-%m-%d"))
            | (df.columns.get_level_values(1) == "Prévu"),
        ]

        # convert columns and sort dates
        new_index = [
            (pd.to_datetime(col_tuple[0], format="%Y-%m-%d"), col_tuple[1])
            for col_tuple in df.columns
        ]
        new_index = sorted(new_index, key=lambda x: x[0])
        df.columns = pd.MultiIndex.from_tuples(new_index)

        # Sort categories
        df = df.sort_index()

        # # Add total row
        df.loc["Total"] = df.sum(numeric_only=True, axis=0)

        # Round values to no decimal places
        df = df.round(0).astype(int)

        return df

    def compute_budget_statistics(
        self, start_date: datetime, end_date: datetime
    ) -> pd.DataFrame:
        """Compute the expenses statistics per category."""
        expenses_per_category_dict: dict[Category, list[tuple[datetime, float]]] = {}
        analysis_start = max(
            min(operation.date for operation in self.__account.operations), start_date
        )
        analysis_end = min(
            max(operation.date for operation in self.__account.operations), end_date
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

        for operation in self.__account.operations:
            if analysis_start <= operation.date <= analysis_end:
                expenses_per_category_dict.setdefault(operation.category, []).append(
                    (operation.date, operation.amount)
                )
        expenses_per_category = {
            category: pd.DataFrame(expenses, columns=["Date", "Montant"]).set_index(
                "Date"
            )
            for category, expenses in expenses_per_category_dict.items()
        }

        df = pd.DataFrame(
            {
                "Catégorie": list(expenses_per_category),
                "Total": [df["Montant"].sum() for df in expenses_per_category.values()],
                "Moyenne mensuelle": [
                    df.resample("MS")["Montant"].sum().mean()
                    for df in expenses_per_category.values()
                ],
            }
        )
        df.set_index("Catégorie", inplace=True)
        df = df.round(2)
        return df
