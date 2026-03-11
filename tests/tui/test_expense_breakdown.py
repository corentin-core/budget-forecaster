"""Tests for expense breakdown widget rendering logic."""

import pytest

from budget_forecaster.core.types import Category
from budget_forecaster.tui.screens.expense_breakdown import ExpenseBreakdownWidget


class TestRenderBars:
    """Test the bar rendering logic (pure function, no TUI needed)."""

    @pytest.fixture()
    def widget(self) -> ExpenseBreakdownWidget:
        """Create a widget instance for testing render_bars."""
        inst = ExpenseBreakdownWidget.__new__(ExpenseBreakdownWidget)
        inst._period_months = 3  # pylint: disable=protected-access
        return inst

    def _render(
        self, widget: ExpenseBreakdownWidget, totals: dict, threshold: float = 0
    ) -> list[str]:
        # pylint: disable=protected-access
        return widget._render_bars(totals, threshold)

    @staticmethod
    def _data_lines(lines: list[str]) -> list[str]:
        """Return only data lines (skip the header)."""
        return lines[1:]

    def test_header_present(self, widget: ExpenseBreakdownWidget) -> None:
        """First line is a header with column labels."""
        totals = {Category.GROCERIES: -900.0}
        lines = self._render(widget, totals)

        assert "Avg/mo" in lines[0]
        assert "Total" in lines[0]

    def test_basic_rendering(self, widget: ExpenseBreakdownWidget) -> None:
        """Bars are rendered with correct percentages, averages, and totals."""
        totals = {
            Category.GROCERIES: -900.0,  # 300/month avg, 900 total
            Category.ELECTRICITY: -300.0,  # 100/month avg, 300 total
        }
        lines = self._data_lines(self._render(widget, totals))

        assert len(lines) == 2
        assert "Groceries" in lines[0]
        assert "75%" in lines[0]
        assert "300.00" in lines[0]  # monthly average
        assert "900.00" in lines[0]  # cumulative total
        assert "Electricity" in lines[1]
        assert "25%" in lines[1]
        assert "100.00" in lines[1]
        assert "300.00" in lines[1]

    def test_threshold_groups_small_categories(
        self, widget: ExpenseBreakdownWidget
    ) -> None:
        """Categories below threshold are grouped into Other."""
        totals = {
            Category.GROCERIES: -900.0,
            Category.ELECTRICITY: -90.0,
            Category.WATER: -9.0,  # < 1% of total
        }
        lines = self._data_lines(self._render(widget, totals, threshold=2))

        names = [line.split()[0] for line in lines]
        assert "Groceries" in names
        assert "Electricity" in names
        assert "Other" in names
        assert "Water" not in names

    def test_other_category_merged_with_threshold_bucket(
        self, widget: ExpenseBreakdownWidget
    ) -> None:
        """The real OTHER category is merged into the threshold bucket."""
        totals = {
            Category.GROCERIES: -900.0,
            Category.OTHER: -50.0,
            Category.WATER: -9.0,
        }
        lines = self._data_lines(self._render(widget, totals, threshold=2))

        names = [line.split()[0] for line in lines]
        assert names.count("Other") == 1

    def test_sorted_by_amount_descending(self, widget: ExpenseBreakdownWidget) -> None:
        """Categories are sorted by amount, largest first."""
        totals = {
            Category.ELECTRICITY: -100.0,
            Category.GROCERIES: -500.0,
            Category.CAR_FUEL: -300.0,
        }
        lines = self._data_lines(self._render(widget, totals))

        assert "Groceries" in lines[0]
        assert "Car Fuel" in lines[1]
        assert "Electricity" in lines[2]

    def test_empty_totals(self, widget: ExpenseBreakdownWidget) -> None:
        """Returns 'no data' message when all amounts are zero."""
        totals = {Category.GROCERIES: 0.0}
        lines = self._render(widget, totals)
        assert len(lines) == 1

    def test_single_category(self, widget: ExpenseBreakdownWidget) -> None:
        """Single category renders at 100%."""
        totals = {Category.GROCERIES: -600.0}
        lines = self._data_lines(self._render(widget, totals))

        assert len(lines) == 1
        assert "100%" in lines[0]
        assert "200.00" in lines[0]  # 600/3 months = 200 avg
        assert "600.00" in lines[0]  # cumulative total

    @pytest.mark.parametrize(
        "period_months",
        [1, 3, 6, 12],
        ids=["1M", "3M", "6M", "1Y"],
    )
    def test_monthly_average_scales_with_period(
        self, widget: ExpenseBreakdownWidget, period_months: int
    ) -> None:
        """Monthly average divides total by period length."""
        widget._period_months = period_months  # pylint: disable=protected-access
        totals = {Category.GROCERIES: -1200.0}
        lines = self._data_lines(self._render(widget, totals))

        expected_avg = 1200.0 / period_months
        assert f"{expected_avg:,.2f}" in lines[0]
        # Cumulative total is always the full amount
        assert "1,200.00" in lines[0]
