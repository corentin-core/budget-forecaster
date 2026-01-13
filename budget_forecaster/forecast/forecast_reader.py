"""Module to read planned operations and budgets from a CSV file."""
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Mapping

import numpy as np
import pandas as pd
from dateutil.relativedelta import relativedelta

from budget_forecaster.amount import Amount
from budget_forecaster.operation_range.budget import Budget
from budget_forecaster.operation_range.planned_operation import PlannedOperation
from budget_forecaster.time_range import (
    DailyTimeRange,
    PeriodicDailyTimeRange,
    PeriodicTimeRange,
    TimeRange,
    TimeRangeInterface,
)
from budget_forecaster.types import Category

DEFAULT_CATEGORY_MAPPING: dict[str, Category] = {
    "Salaire": Category.SALARY,
    "Prêt maison": Category.HOUSE_LOAN,
    "Prêt travaux": Category.WORKS_LOAN,
    "Crédit auto": Category.CAR_LOAN,
    "Epargne": Category.SAVINGS,
    "Allocations": Category.BENEFITS,
    "Garde d'enfant": Category.CHILDCARE,
    "Assurance prêt": Category.LOAN_INSURANCE,
    "Electricité": Category.ELECTRICITY,
    "Eau": Category.WATER,
    "Pension": Category.CHILD_SUPPORT,
    "Divertissement": Category.ENTERTAINMENT,
    "Internet": Category.INTERNET,
    "Téléphone": Category.PHONE,
    "Frais bancaires": Category.BANK_FEES,
    "Frais professionnels": Category.PROFESSIONAL_EXPENSES,
    "Dons": Category.CHARITY,
    "Assurance auto": Category.CAR_INSURANCE,
    "Assurance habitation": Category.HOUSE_INSURANCE,
    "Autres assurances": Category.OTHER_INSURANCE,
    "Impôts": Category.TAXES,
    "Travaux": Category.HOUSE_WORKS,
    "Enfants": Category.CHILDCARE,
    "Courses": Category.GROCERIES,
    "Loisirs": Category.LEISURE,
    "Habillement": Category.CLOTHING,
    "Soins": Category.CARE,
    "Carburant": Category.CAR_FUEL,
    "Vacances": Category.HOLIDAYS,
    "Entretien automobile": Category.CAR_MAINTENANCE,
    "Santé": Category.HEALTH_CARE,
    "Cadeaux": Category.GIFTS,
    "Autres": Category.OTHER,
    "Ameublement": Category.FURNITURE,
}


class ForecastReader:
    """Reads planned operations and budgets from a CSV file."""

    def __init__(self, category_mapping: Mapping[str, Category] | None = None) -> None:
        self.__category_mapping = category_mapping or DEFAULT_CATEGORY_MAPPING

    def __read_category(self, row: pd.Series) -> Category:
        if (category := row["Catégorie"]) not in self.__category_mapping:
            raise ValueError(f"Invalid category: {category}")
        return self.__category_mapping[category]

    @staticmethod
    def __read_amount_euros(row: pd.Series) -> float:
        amount_euros = row["Montant"]
        if not isinstance(amount_euros, (int, float)):
            raise ValueError(f"Invalid amount: {amount_euros}")
        return float(amount_euros)

    @staticmethod
    def __read_start_date(row: pd.Series) -> datetime:
        start_date = (
            datetime.strptime(row["Date de début"], "%d/%m/%Y")
            if row["Date de début"]
            else None
        )
        if start_date is None:
            raise ValueError("Date de début is required")
        return start_date

    @staticmethod
    def __read_end_date(row: pd.Series) -> datetime | None:
        date_end_cell = row["Date de fin"]
        return (
            datetime.strptime(date_end_cell, "%d/%m/%Y")
            if isinstance(date_end_cell, str)
            else None
        )

    @staticmethod
    def __extract_timedelta(cell: str) -> relativedelta:
        if (re_match := re.match("(\\d+) (Mois|An|Semaine|Jour)", cell)) is None:
            raise ValueError(f"Invalid duration: {cell}")
        multiplier = int(re_match.group(1))
        match re_match.group(2):
            case "Mois":
                return relativedelta(months=multiplier)
            case "An":
                return relativedelta(years=multiplier)
            case "Semaine":
                return relativedelta(weeks=multiplier)
            case "Jour":
                return relativedelta(days=multiplier)
            case _:
                raise ValueError(f"Invalid duration: {cell}")

    @staticmethod
    def ___read_duration(row: pd.Series) -> relativedelta:
        duration_cell = row["Durée"]
        if not isinstance(duration_cell, str):
            raise ValueError(f"Invalid duration: {duration_cell}")
        return ForecastReader.__extract_timedelta(duration_cell)

    @staticmethod
    def __read_period(row: pd.Series) -> relativedelta | None:
        period_cell = row["Périodicité"]
        if pd.isna(period_cell):
            return None

        if not isinstance(period_cell, str):
            raise ValueError(f"Invalid period: {period_cell}")

        return ForecastReader.__extract_timedelta(period_cell)

    @staticmethod
    def __read_description_hints(row: pd.Series) -> set[str]:
        return (
            set(row["Mots clés libellé"].split(";"))
            if isinstance(row["Mots clés libellé"], str)
            else set()
        )

    @staticmethod
    def __read_approx_date_range(forecast_type: str, row: pd.Series) -> timedelta:
        approx_days = row["Approximation date (jours)"]
        if np.isnan(approx_days):
            return timedelta(days=5)
        if not isinstance(approx_days, (int, float)):
            raise ValueError(f"Invalid approximation days: {approx_days}")
        if forecast_type == "Budget":
            raise ValueError("Approximation date is not supported for budgets")
        return timedelta(days=approx_days)

    @staticmethod
    def __read_approx_amount_ratio(forecast_type: str, row: pd.Series) -> float:
        approx_ratio = row["Approximation montant (%)"]
        if np.isnan(approx_ratio):
            return 0.05
        if not isinstance(approx_ratio, (int, float)):
            raise ValueError(f"Invalid approximation ratio: {approx_ratio}")
        if forecast_type == "Budget":
            raise ValueError("Approximation amount is not supported for budgets")
        return approx_ratio

    @staticmethod
    def __make_time_range(
        start_date: datetime,
        duration: relativedelta | None,
        period: relativedelta | None,
        end_date: datetime | None,
    ) -> TimeRangeInterface:
        if duration is None:
            return (
                DailyTimeRange(start_date)
                if period is None
                else PeriodicDailyTimeRange(start_date, period, end_date)
            )

        if period is not None:
            return PeriodicTimeRange(TimeRange(start_date, duration), period, end_date)

        # duration = relativedelta(days=(end_date - start_date).days + 1)
        return TimeRange(start_date, duration)

    def read_budgets(self, path: Path) -> tuple[Budget, ...]:
        """Read budgets from a CSV file."""
        df = pd.read_csv(path)
        budgets: list[Budget] = []

        for _, row in df.iterrows():
            description = row["Description"]
            amount_euros = self.__read_amount_euros(row)
            category = self.__read_category(row)
            start_date = self.__read_start_date(row)
            end_date = self.__read_end_date(row)
            duration = self.___read_duration(row)
            period = self.__read_period(row)
            time_range = self.__make_time_range(start_date, duration, period, end_date)

            budgets.append(
                Budget(
                    id=-1,
                    description=description,
                    amount=Amount(amount_euros, "EUR"),
                    category=category,
                    time_range=time_range,
                )
            )

        return tuple(budgets)

    def read_planned_operations(self, path: Path) -> tuple[PlannedOperation, ...]:
        """Read planned operations from a CSV file."""
        df = pd.read_csv(path)
        planned_operations: list[PlannedOperation] = []

        for _, row in df.iterrows():
            description = row["Description"]
            amount_euros = self.__read_amount_euros(row)
            category = self.__read_category(row)
            start_date = self.__read_start_date(row)
            end_date = self.__read_end_date(row)
            period = self.__read_period(row)
            time_range = self.__make_time_range(start_date, None, period, end_date)

            planned_operations.append(
                PlannedOperation(
                    id=-1,
                    description=description,
                    amount=Amount(amount_euros, "EUR"),
                    category=category,
                    time_range=time_range,
                ).set_matcher_params(
                    description_hints=self.__read_description_hints(row),
                    approximation_date_range=self.__read_approx_date_range(
                        "Operation", row
                    ),
                    approximation_amount_ratio=self.__read_approx_amount_ratio(
                        "Operation", row
                    ),
                )
            )

        return tuple(planned_operations)
