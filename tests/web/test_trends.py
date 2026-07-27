"""Tests for the trends chart helpers and the breakdown threshold route."""

from datetime import date, timedelta
from unittest.mock import Mock

from dateutil.relativedelta import relativedelta
from fastapi.testclient import TestClient

from budget_forecaster.core.types import Category
from budget_forecaster.web.routes.trends import (
    _DEFAULT_PERIOD,
    _OTHER_COLOR,
    _PALETTE,
    _PIE_CIRCUMFERENCE,
    GroupedExpense,
    _breakdown,
    _grouped_expenses,
    _period_from,
    _slices,
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
        app.expense_breakdown_threshold = 2.0
        app.get_category_totals.return_value = {Category.GROCERIES: -300.0}
        breakdown = _breakdown(app, 3)
        assert breakdown.total == 300.0
        assert breakdown.slices[0].average == 100.0


class TestGroupedExpenses:
    """Threshold-driven folding for the donut."""

    def test_sorted_desc_above_threshold(self) -> None:
        """Categories above the threshold are returned largest-first, unfolded."""
        amounts = {Category.GROCERIES: 100.0, Category.RENT: 300.0}
        entries = _grouped_expenses(amounts, 2.0)
        assert [entry.amount for entry in entries] == [300.0, 100.0]
        assert all(entry.members == () for entry in entries)

    def test_sub_threshold_categories_folded(self) -> None:
        """Categories below the threshold percent collapse into one 'Other' entry."""
        # RENT is 96% of the total; the two 2% tails (< 3% threshold) fold together.
        amounts = {
            Category.RENT: 960.0,
            Category.GROCERIES: 20.0,
            Category.CLOTHING: 20.0,
        }
        entries = _grouped_expenses(amounts, 3.0)
        assert len(entries) == 2
        other = entries[-1]
        assert other.amount == 40.0
        assert len(other.members) == 2  # the two folded tails, carried for the legend

    def test_lonely_sub_threshold_stays_itself(self) -> None:
        """A single sub-threshold category is drawn as itself, not as 'Other'."""
        amounts = {Category.RENT: 980.0, Category.GROCERIES: 20.0}
        entries = _grouped_expenses(amounts, 3.0)
        assert [entry.amount for entry in entries] == [980.0, 20.0]
        assert all(entry.members == () for entry in entries)

    def test_real_other_always_folded(self) -> None:
        """The real OTHER category folds into 'Other', even above the threshold."""
        amounts = {Category.RENT: 500.0, Category.OTHER: 500.0}
        entries = _grouped_expenses(amounts, 2.0)
        assert len(entries) == 2
        assert entries[-1].amount == 500.0
        assert len(entries[-1].members) == 1

    def test_empty_when_no_expenses(self) -> None:
        """No expenses yields no entries."""
        assert not _grouped_expenses({}, 2.0)


class TestSlices:
    """Donut geometry: the folded 'Other' slice is grey, last, and off-palette."""

    def test_other_slice_is_grey_and_palette_not_wasted(self) -> None:
        """The folded slice takes the neutral grey; kept slices keep the palette order."""
        entries = (
            GroupedExpense("Rent", 600.0),
            GroupedExpense("Other categories", 400.0, (("A", 200.0), ("B", 200.0))),
        )
        slices = _slices(entries, total=1000.0, months=2)
        assert len(slices) == 2
        rent, other = slices[0], slices[1]
        assert rent.color == _PALETTE[0]
        assert (rent.fraction, rent.offset) == (0.6, 0.0)
        assert other.color == _OTHER_COLOR
        assert other.average == 200.0  # 400 over 2 months
        assert other.members == (("A", 200.0), ("B", 200.0))
        # The Other slice starts where Rent ends: offset is minus the accumulated arc.
        assert other.offset == round(-0.6 * _PIE_CIRCUMFERENCE, 2)

    def test_sequential_categories_walk_the_palette(self) -> None:
        """Plain (unfolded) categories take palette colors in order."""
        entries = (
            GroupedExpense("A", 300.0),
            GroupedExpense("B", 200.0),
            GroupedExpense("C", 100.0),
        )
        slices = _slices(entries, total=600.0, months=1)
        assert [s.color for s in slices] == list(_PALETTE[:3])


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


class TestThresholdRoute:
    """The POST /trends/threshold persists the value and re-renders the donut.

    Persistence is checked through a follow-up request rather than app.state, because
    the shared SQLite connection is bound to the TestClient's worker thread.
    """

    def _rendered_threshold(self, client: TestClient) -> str:
        """The slider value the Trends page renders (12m: a period with demo data)."""
        html = client.get("/trends?months=12").text
        marker = 'name="threshold"'
        segment = html[html.index(marker) : html.index(">", html.index(marker))]
        value = segment.split('value="', 1)[1]
        return value.split('"', 1)[0]

    def test_change_persists_and_returns_fragment(self, client: TestClient) -> None:
        """A posted threshold is stored and read back; the card fragment comes back."""
        body = client.post(
            "/trends/threshold", data={"threshold": "4.5", "months": "6"}
        ).text
        assert 'id="breakdown"' in body
        assert "<html" not in body  # only the fragment, not the whole page
        assert self._rendered_threshold(client) == "4.5"

    def test_out_of_range_is_clamped(self, client: TestClient) -> None:
        """Values outside [0, 10] are clamped before being stored."""
        client.post("/trends/threshold", data={"threshold": "42", "months": "3"})
        assert self._rendered_threshold(client) == "10.0"
        client.post("/trends/threshold", data={"threshold": "-5", "months": "3"})
        assert self._rendered_threshold(client) == "0.0"

    def test_invalid_keeps_current(self, client: TestClient) -> None:
        """An unparseable value leaves the stored threshold untouched."""
        client.post("/trends/threshold", data={"threshold": "3", "months": "3"})
        client.post("/trends/threshold", data={"threshold": "abc", "months": "3"})
        assert self._rendered_threshold(client) == "3.0"

    def test_comma_decimal_accepted(self, client: TestClient) -> None:
        """A French comma-decimal threshold is parsed like a dot-decimal one."""
        client.post("/trends/threshold", data={"threshold": "4,5", "months": "6"})
        assert self._rendered_threshold(client) == "4.5"


class TestPeriodFrom:
    """Month coercion for the threshold route form field."""

    def test_valid_period_kept(self) -> None:
        """An offered period passes through unchanged."""
        assert _period_from("6") == 6

    def test_invalid_or_unknown_falls_back(self) -> None:
        """Unknown, unparseable or missing month falls back to the default period."""
        assert _period_from("7") == _DEFAULT_PERIOD  # not one of the offered periods
        assert _period_from("abc") == _DEFAULT_PERIOD
        assert _period_from(None) == _DEFAULT_PERIOD
