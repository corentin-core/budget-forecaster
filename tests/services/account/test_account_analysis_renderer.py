"""Tests for the AccountAnalysisRendererExcel."""

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

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
            "Catégorie": ["Courses", "Salaire", "Loisirs"],
            "Description": ["CARREFOUR", "VIREMENT SALAIRE", "CINEMA"],
            "Montant": [-85.20, 2500.00, -15.00],
        },
        index=pd.DatetimeIndex(
            [date(2025, 1, 10), date(2025, 1, 11), date(2025, 1, 12)],
            name="Date",
        ),
    )

    # Forecast DataFrame: indexed by description, columns for forecast data
    forecast = pd.DataFrame(
        {
            "Description": ["Loyer", "Salaire"],
            "Montant": [-800.0, 2500.0],
            "Date début": [date(2025, 1, 1), date(2025, 1, 1)],
            "Date fin": [date(2025, 3, 31), date(2025, 3, 31)],
        }
    ).set_index("Description")

    # Balance evolution per day: DatetimeIndex with "Solde" column
    date_range = pd.date_range(start_date, end_date, freq="D")
    balance_values = [1000.0 + i * 10 for i in range(len(date_range))]
    balance_evolution = pd.DataFrame(
        {"Solde": balance_values},
        index=date_range,
    )

    # Budget forecast: MultiIndex columns (date, Prévu/Réel)
    budget_forecast = pd.DataFrame(
        {
            ("Jan 25", "Prévu"): [-800.0, -100.0],
            ("Jan 25", "Réel"): [-800.0, -85.20],
        },
        index=["Loyer", "Courses"],
    )
    budget_forecast.columns = pd.MultiIndex.from_tuples(budget_forecast.columns)

    # Budget statistics: indexed by category
    budget_statistics = pd.DataFrame(
        {"Total": [-800.0, -100.0, 2500.0], "Moyenne": [-800.0, -100.0, 2500.0]},
        index=["Loyer", "Courses", "Salaire"],
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
            "Evolution du solde",
            "Prévisions des dépenses",
            "Statistiques des dépenses",
            "Opérations",
            "Source prévisions",
        }

    def test_operations_sheet_data(
        self, sample_report: AccountAnalysisReport, tmp_path: Path
    ) -> None:
        """Test that operations sheet contains correct data."""
        output_path = tmp_path / "report.xlsx"
        with AccountAnalysisRendererExcel(output_path) as renderer:
            renderer(sample_report)

        ops_df = pd.read_excel(output_path, sheet_name="Opérations", index_col=0)
        assert len(ops_df) == 3
        assert "Description" in ops_df.columns
        assert "Montant" in ops_df.columns
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
            output_path, sheet_name="Source prévisions", index_col=0
        )
        assert len(forecast_df) == 2
        assert "Loyer" in forecast_df.index
        assert "Salaire" in forecast_df.index

    def test_balance_evolution_sheet_data(
        self, sample_report: AccountAnalysisReport, tmp_path: Path
    ) -> None:
        """Test that balance evolution sheet is resampled to monthly."""
        output_path = tmp_path / "report.xlsx"
        with AccountAnalysisRendererExcel(output_path) as renderer:
            renderer(sample_report)

        balance_df = pd.read_excel(
            output_path, sheet_name="Evolution du solde", index_col=0
        )
        # Jan, Feb, Mar = 3 months
        assert len(balance_df) == 3
        assert "Solde" in balance_df.columns
        assert "Solde Min." in balance_df.columns
        assert "Marge" in balance_df.columns

    def test_budget_statistics_sheet_data(
        self, sample_report: AccountAnalysisReport, tmp_path: Path
    ) -> None:
        """Test that budget statistics sheet contains categories."""
        output_path = tmp_path / "report.xlsx"
        with AccountAnalysisRendererExcel(output_path) as renderer:
            renderer(sample_report)

        stats_df = pd.read_excel(
            output_path, sheet_name="Statistiques des dépenses", index_col=0
        )
        assert "Total" in stats_df.columns
        assert "Loyer" in stats_df.index

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
            sheet_name="Prévisions des dépenses",
            index_col=0,
            header=[0, 1],
        )
        assert len(forecast_df) == 2
        assert "Loyer" in forecast_df.index
        assert "Courses" in forecast_df.index

    def test_render_with_empty_operations(self, tmp_path: Path) -> None:
        """Test rendering with empty DataFrames doesn't crash."""
        empty_report = AccountAnalysisReport(
            balance_date=date(2025, 1, 15),
            start_date=date(2025, 1, 1),
            end_date=date(2025, 3, 31),
            operations=pd.DataFrame(
                columns=["Catégorie", "Description", "Montant"],
                index=pd.DatetimeIndex([], name="Date"),
            ),
            forecast=pd.DataFrame(
                columns=["Montant", "Date début", "Date fin"],
            ).rename_axis("Description"),
            balance_evolution_per_day=pd.DataFrame(
                {"Solde": [1000.0]},
                index=pd.date_range("2025-01-01", periods=1, freq="D"),
            ),
            budget_forecast=pd.DataFrame(),
            budget_statistics=pd.DataFrame(columns=["Total", "Moyenne"]),
        )

        output_path = tmp_path / "empty_report.xlsx"
        with AccountAnalysisRendererExcel(output_path) as renderer:
            renderer(empty_report)

        assert output_path.exists()
