"""Module to define the AccountAnalysisReport class."""
from datetime import date
from typing import NamedTuple

import pandas as pd


class BudgetStatistics(NamedTuple):
    """Budget statistics with the effective analysis period.

    The analysis period may differ from the requested period because
    incomplete months are trimmed.
    """

    data: pd.DataFrame
    analysis_start: date
    analysis_end: date


class AccountAnalysisReport(NamedTuple):
    """
    A class to represent an account analysis report.
    """

    balance_date: date
    start_date: date
    end_date: date
    operations: pd.DataFrame
    forecast: pd.DataFrame
    balance_evolution_per_day: pd.DataFrame
    budget_forecast: pd.DataFrame
    budget_statistics: BudgetStatistics
