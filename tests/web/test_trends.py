"""Unit tests for the trends chart helpers (pure logic, no app/DB)."""

from datetime import date, timedelta
from unittest.mock import Mock

from dateutil.relativedelta import relativedelta

from budget_forecaster.core.types import Category
from budget_forecaster.web.routes.trends import (
    _breakdown,
    _grouped_expenses,
    _sparkline,
)


class TestBreakdownWindow:
    """The breakdown uses a true rolling N-month window ending today."""

    def test_window_is_rolling_n_months(self) -> None:
        """date_from/date_to span exactly N months ending today."""
        app = Mock()
        app.get_category_totals.return_value = {}
        _breakdown(app, 3)
        criteria = app.get_category_totals.call_args.args[0]
        today = date.today()
        assert criteria.date_to == today
        assert criteria.date_from == today + timedelta(days=1) - relativedelta(months=3)
        assert criteria.max_amount == 0

    def test_average_is_total_over_months(self) -> None:
        """Per-slice average divides the window total by the month count."""
        app = Mock()
        app.get_category_totals.return_value = {Category.GROCERIES: -300.0}
        breakdown = _breakdown(app, 3)
        assert breakdown.total == 300.0
        assert breakdown.slices[0].average == 100.0


class TestGroupedExpenses:
    """Ordering and long-tail folding for the donut."""

    def test_sorted_desc_when_few(self) -> None:
        """Up to the slice cap, categories are returned largest-first."""
        amounts = {Category.GROCERIES: 100.0, Category.RENT: 300.0}
        assert [amount for _label, amount in _grouped_expenses(amounts)] == [
            300.0,
            100.0,
        ]

    def test_long_tail_folded_into_other(self) -> None:
        """Beyond the cap, the smallest categories collapse into one entry."""
        amounts = {c: float(i + 1) for i, c in enumerate(list(Category)[:12])}
        entries = _grouped_expenses(amounts)
        assert len(entries) == 8
        assert entries[-1][1] == 1 + 2 + 3 + 4 + 5  # folded smallest five

    def test_empty_when_no_expenses(self) -> None:
        """No expenses yields no entries."""
        assert _grouped_expenses({}) == []


class TestSparkline:
    """Balance sparkline geometry and axis references."""

    def test_marks_and_points(self) -> None:
        """Zero and threshold are on-scale and every sample maps to a point."""
        samples = [(date(2026, 1, 1), -100.0), (date(2026, 1, 2), 200.0)]
        spark = _sparkline(samples, "EUR", 50.0)
        assert spark is not None
        assert len(spark.points) == 2
        assert spark.zero is not None  # range spans below and above 0
        assert spark.threshold.text.startswith("50")
        assert spark.threshold.text.endswith("EUR")
        assert spark.x_labels[0] == "01/01/2026"
        assert spark.x_labels[-1] == "02/01/2026"

    def test_none_below_two_points(self) -> None:
        """A single sample yields no sparkline."""
        assert _sparkline([(date(2026, 1, 1), 10.0)], "EUR", 0.0) is None
