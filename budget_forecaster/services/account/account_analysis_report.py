"""Module to define the AccountAnalysisReport class."""
from datetime import datetime
from typing import NamedTuple

import pandas as pd


class AccountAnalysisReport(NamedTuple):
    """
    A class to represent an account analysis report.
    """

    balance_date: datetime
    start_date: datetime
    end_date: datetime
    operations: pd.DataFrame
    forecast: pd.DataFrame
    balance_evolution_per_day: pd.DataFrame
    budget_forecast: pd.DataFrame
    budget_statistics: pd.DataFrame
