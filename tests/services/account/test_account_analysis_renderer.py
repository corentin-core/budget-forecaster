"""Tests for the AccountAnalysisRendererExcel."""

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from budget_forecaster.core.types import Category
from budget_forecaster.services.account.account_analysis_renderer import (
    AccountAnalysisRendererExcel,
)
from budget_forecaster.services.account.account_analysis_report import (
    AccountAnalysisReport,
)


@pytest.fixture
def sample_report() -> AccountAnalysisReport:
    """Create a minimal AccountAnalysisReport with realistic data."""
    balance_date = date(2025, 1, 15)
    start_date = date(2025, 1, 1)
    end_date = date(2025, 3, 31)

    # Operations DataFrame: indexed by date, with Category, Description, Amount
    operations = pd.DataFrame(
        {
            "Category": [Category.GROCERIES, Category.SALARY, Category.ENTERTAINMENT],
            "Description": ["CARREFOUR", "VIREMENT SALAIRE", "CINEMA"],
            "Amount": [-85.20, 2500.00, -15.00],
        },
        index=pd.Index(
            [date(2025, 1, 10), date(2025, 1, 11), date(2025, 1, 12)],
            name="Date",
        ),
    )

    # Forecast DataFrame: indexed by Category, columns for forecast data
    forecast = pd.DataFrame(
        {
            "Description": ["Monthly rent", "Monthly salary"],
            "Amount": [-800.0, 2500.0],
            "Start date": [date(2025, 1, 1), date(2025, 1, 1)],
            "End date": [date(2025, 3, 31), date(2025, 3, 31)],
            "Frequency": ["1 Month", "1 Month"],
        },
        index=pd.Index([Category.RENT, Category.SALARY], name="Category"),
    )

    # Balance evolution per day: DatetimeIndex with "Balance" column
    date_range = pd.date_range(start_date, end_date, freq="D")
    balance_values = [1000.0 + i * 10 for i in range(len(date_range))]
    balance_evolution = pd.DataFrame(
        {"Balance": balance_values},
        index=date_range,
    )

    # Budget forecast: MultiIndex columns (date, Planned/Actual/Projected)
    budget_forecast = pd.DataFrame(
        {
            ("Jan 25", "Planned"): [-800.0, -100.0],
            ("Jan 25", "PlannedOps"): [-800.0, 0.0],
            ("Jan 25", "PlannedBudgets"): [0.0, -100.0],
            ("Jan 25", "Actual"): [-800.0, -85.20],
            ("Jan 25", "Projected"): [-800.0, -100.0],
        },
        index=[Category.RENT, Category.GROCERIES],
    )
    budget_forecast.columns = pd.MultiIndex.from_tuples(budget_forecast.columns)

    # Budget statistics: indexed by category
    budget_statistics = pd.DataFrame(
        {
            "Total": [-800.0, -100.0, 2500.0],
            "Monthly average": [-800.0, -100.0, 2500.0],
        },
        index=[Category.RENT, Category.GROCERIES, Category.SALARY],
    )

    return AccountAnalysisReport(
        balance_date=balance_date,
        start_date=start_date,
        end_date=end_date,
        operations=operations,
        forecast=forecast,
        balance_evolution_per_day=balance_evolution,
        budget_forecast=budget_forecast,
        budget_statistics=budget_statistics,
    )


class TestAccountAnalysisRendererExcel:
    """Tests for the Excel renderer public API."""

    def test_render_creates_file(
        self, sample_report: AccountAnalysisReport, tmp_path: Path
    ) -> None:
        """Test that rendering produces an Excel file."""
        output_path = tmp_path / "report.xlsx"
        with AccountAnalysisRendererExcel(output_path) as renderer:
            renderer(sample_report)
        assert output_path.exists()
        assert output_path.stat().st_size > 0

    def test_render_creates_expected_sheets(
        self, sample_report: AccountAnalysisReport, tmp_path: Path
    ) -> None:
        """Test that the output contains all expected sheet names."""
        output_path = tmp_path / "report.xlsx"
        with AccountAnalysisRendererExcel(output_path) as renderer:
            renderer(sample_report)

        xls = pd.ExcelFile(output_path)
        assert set(xls.sheet_names) == {
            "Balance evolution",
            "Expense forecast",
            "Expense statistics",
            "Operations",
            "Forecast source",
        }

    def test_operations_sheet_data(
        self, sample_report: AccountAnalysisReport, tmp_path: Path
    ) -> None:
        """Test that operations sheet contains correct data."""
        output_path = tmp_path / "report.xlsx"
        with AccountAnalysisRendererExcel(output_path) as renderer:
            renderer(sample_report)

        ops_df = pd.read_excel(output_path, sheet_name="Operations", index_col=0)
        assert len(ops_df) == 3
        assert "Description" in ops_df.columns
        assert "Amount" in ops_df.columns
        assert set(ops_df["Description"]) == {
            "CARREFOUR",
            "VIREMENT SALAIRE",
            "CINEMA",
        }

    def test_forecast_sheet_data(
        self, sample_report: AccountAnalysisReport, tmp_path: Path
    ) -> None:
        """Test that forecast sheet contains correct data."""
        output_path = tmp_path / "report.xlsx"
        with AccountAnalysisRendererExcel(output_path) as renderer:
            renderer(sample_report)

        forecast_df = pd.read_excel(
            output_path, sheet_name="Forecast source", index_col=0
        )
        assert len(forecast_df) == 2
        assert "Rent" in forecast_df.index
        assert "Salary" in forecast_df.index

    def test_balance_evolution_sheet_data(
        self, sample_report: AccountAnalysisReport, tmp_path: Path
    ) -> None:
        """Test that balance evolution sheet is resampled to monthly."""
        output_path = tmp_path / "report.xlsx"
        with AccountAnalysisRendererExcel(output_path) as renderer:
            renderer(sample_report)

        balance_df = pd.read_excel(
            output_path, sheet_name="Balance evolution", index_col=0
        )
        # Jan, Feb, Mar = 3 months
        assert len(balance_df) == 3
        assert "Balance" in balance_df.columns
        assert "Min. Balance" in balance_df.columns
        assert "Margin" in balance_df.columns

    def test_budget_statistics_sheet_data(
        self, sample_report: AccountAnalysisReport, tmp_path: Path
    ) -> None:
        """Test that budget statistics sheet contains categories."""
        output_path = tmp_path / "report.xlsx"
        with AccountAnalysisRendererExcel(output_path) as renderer:
            renderer(sample_report)

        stats_df = pd.read_excel(
            output_path, sheet_name="Expense statistics", index_col=0
        )
        assert "Total" in stats_df.columns
        assert "Rent" in stats_df.index

    def test_budget_forecast_sheet_data(
        self, sample_report: AccountAnalysisReport, tmp_path: Path
    ) -> None:
        """Test that budget forecast sheet contains expected data."""
        output_path = tmp_path / "report.xlsx"
        with AccountAnalysisRendererExcel(output_path) as renderer:
            renderer(sample_report)

        # MultiIndex columns produce extra header rows in Excel;
        # read with header=[0,1] to reconstruct them properly
        forecast_df = pd.read_excel(
            output_path,
            sheet_name="Expense forecast",
            index_col=0,
            header=[0, 1],
        )
        assert len(forecast_df) == 2
        assert "Rent" in forecast_df.index
        assert "Groceries" in forecast_df.index

    def test_render_with_empty_operations(self, tmp_path: Path) -> None:
        """Test rendering with empty DataFrames doesn't crash."""
        empty_report = AccountAnalysisReport(
            balance_date=date(2025, 1, 15),
            start_date=date(2025, 1, 1),
            end_date=date(2025, 3, 31),
            operations=pd.DataFrame(
                columns=["Category", "Description", "Amount"],
                index=pd.Index([], dtype="object", name="Date"),
            ),
            forecast=pd.DataFrame(
                columns=[
                    "Description",
                    "Amount",
                    "Start date",
                    "End date",
                    "Frequency",
                ],
            ).rename_axis("Category"),
            balance_evolution_per_day=pd.DataFrame(
                {"Balance": [1000.0]},
                index=pd.date_range("2025-01-01", periods=1, freq="D"),
            ),
            budget_forecast=pd.DataFrame(),
            budget_statistics=pd.DataFrame(columns=["Total", "Monthly average"]),
        )

        output_path = tmp_path / "empty_report.xlsx"
        with AccountAnalysisRendererExcel(output_path) as renderer:
            renderer(empty_report)

        assert output_path.exists()
