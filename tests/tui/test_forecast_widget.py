"""Tests for ForecastWidget budget table display."""

from unittest.mock import MagicMock

import pandas as pd
import pytest
from textual.app import App, ComposeResult
from textual.widgets import DataTable

from budget_forecaster.core.types import Category
from budget_forecaster.tui.screens.forecast import ForecastWidget


class ForecastTestApp(App[None]):
    """Test app containing a ForecastWidget."""

    def __init__(self, app_service: MagicMock) -> None:
        super().__init__()
        self._app_service = app_service

    def compose(self) -> ComposeResult:
        yield ForecastWidget()

    def on_mount(self) -> None:
        """Inject app_service into the widget."""
        widget = self.query_one(ForecastWidget)
        widget.set_app_service(self._app_service)


def _make_budget_dataframe(
    categories: tuple[Category, ...],
) -> pd.DataFrame:
    """Build a minimal budget_forecast DataFrame with the given categories."""
    month = pd.Timestamp("2025-01-01")
    columns = pd.MultiIndex.from_tuples([(month, "Actual")])
    data = {cat: [100] for cat in categories}
    df = pd.DataFrame.from_dict(data, orient="index", columns=columns)
    df.loc["Total"] = df.sum(numeric_only=True, axis=0)
    return df.astype(int)


def _make_app_service(
    budget_forecast: pd.DataFrame,
) -> MagicMock:
    """Create a mock ApplicationService with the given budget forecast."""
    app_service = MagicMock()
    app_service.report = None

    def set_report_after_compute(*_args: object, **_kwargs: object) -> None:
        report = MagicMock()
        report.budget_forecast = budget_forecast
        app_service.report = report

    app_service.compute_report.side_effect = set_report_after_compute
    app_service.get_balance_evolution_summary.return_value = []
    return app_service


@pytest.mark.asyncio
async def test_budget_table_shows_translated_category_names() -> None:
    """Clicking Calculate populates the budget table with display names, not raw enums."""
    categories = (Category.BANK_FEES, Category.GROCERIES)
    df = _make_budget_dataframe(categories)
    app_service = _make_app_service(df)

    app = ForecastTestApp(app_service)
    async with app.run_test() as pilot:
        await pilot.click("#btn-compute")
        await pilot.pause()

        table = app.query_one("#budget-table", DataTable)

        # Verify category column shows display names, not raw enum values
        displayed_categories = [table.get_row(row_key)[0] for row_key in table.rows]
        expected = [cat.display_name for cat in categories] + ["Total"]
        assert displayed_categories == expected
