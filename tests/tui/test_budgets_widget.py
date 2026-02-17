"""Tests for BudgetsWidget with FilterBar integration."""

from datetime import date
from unittest.mock import Mock

from dateutil.relativedelta import relativedelta
from textual.app import App, ComposeResult
from textual.widgets import DataTable, Input, Select, Static

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.date_range import DateRange, RecurringDateRange
from budget_forecaster.core.types import Category
from budget_forecaster.domain.operation.budget import Budget
from budget_forecaster.services.application_service import ApplicationService
from budget_forecaster.tui.screens.budgets import BudgetsWidget
from budget_forecaster.tui.widgets.filter_bar import FilterBar


def _make_budget(
    record_id: int,
    description: str,
    amount: float,
    category: Category,
) -> Budget:
    """Create a test budget with a simple recurring date range."""
    return Budget(
        record_id=record_id,
        description=description,
        amount=Amount(amount, "EUR"),
        category=category,
        date_range=RecurringDateRange(
            DateRange(date(2025, 1, 1), relativedelta(months=1)),
            relativedelta(months=1),
            date(2025, 12, 31),
        ),
    )


SAMPLE_BUDGETS = (
    _make_budget(1, "Courses alimentaires", -500.00, Category.GROCERIES),
    _make_budget(2, "Electricite EDF", -80.00, Category.ELECTRICITY),
    _make_budget(3, "Abonnement transport", -75.00, Category.PUBLIC_TRANSPORT),
    _make_budget(4, "Restaurants et sorties", -200.00, Category.LEISURE),
    _make_budget(5, "Courses marche bio", -150.00, Category.GROCERIES),
)


def _make_app_service(budgets: tuple[Budget, ...]) -> Mock:
    """Create a mock ApplicationService returning given budgets."""
    service = Mock(spec=ApplicationService)
    service.get_all_budgets = Mock(return_value=budgets)
    return service


class BudgetsWidgetTestApp(App[None]):
    """Test app wrapping BudgetsWidget."""

    def __init__(self, budgets: tuple[Budget, ...] = SAMPLE_BUDGETS) -> None:
        super().__init__()
        self._service = _make_app_service(budgets)

    def compose(self) -> ComposeResult:
        yield BudgetsWidget(id="budgets-widget")

    def on_mount(self) -> None:
        """Inject the mock service."""
        widget = self.query_one(BudgetsWidget)
        widget.set_app_service(self._service)


class TestBudgetsWidgetFiltering:
    """Integration tests for BudgetsWidget filtering."""

    async def test_all_budgets_shown_initially(self) -> None:
        """All budgets are displayed when no filter is applied."""
        app = BudgetsWidgetTestApp()
        async with app.run_test():
            table = app.query_one("#budgets-table", DataTable)
            assert table.row_count == 5

    async def test_filter_by_search_text(self) -> None:
        """Filtering by search text shows only matching budgets."""
        app = BudgetsWidgetTestApp()
        async with app.run_test() as pilot:
            app.query_one("#filter-search", Input).value = "courses"
            await pilot.click("#filter-apply")

            table = app.query_one("#budgets-table", DataTable)
            # "Courses alimentaires" and "Courses marche bio"
            assert table.row_count == 2

    async def test_filter_by_category(self) -> None:
        """Filtering by category shows only matching budgets."""
        app = BudgetsWidgetTestApp()
        async with app.run_test() as pilot:
            app.query_one("#filter-category", Select).value = Category.GROCERIES.name
            await pilot.click("#filter-apply")

            table = app.query_one("#budgets-table", DataTable)
            assert table.row_count == 2

    async def test_combined_filters(self) -> None:
        """Combining search text and category narrows results further."""
        app = BudgetsWidgetTestApp()
        async with app.run_test() as pilot:
            app.query_one("#filter-search", Input).value = "bio"
            app.query_one("#filter-category", Select).value = Category.GROCERIES.name
            await pilot.click("#filter-apply")

            table = app.query_one("#budgets-table", DataTable)
            assert table.row_count == 1

    async def test_reset_restores_all_budgets(self) -> None:
        """Resetting filters shows all budgets again."""
        app = BudgetsWidgetTestApp()
        async with app.run_test() as pilot:
            app.query_one("#filter-search", Input).value = "courses"
            await pilot.click("#filter-apply")

            table = app.query_one("#budgets-table", DataTable)
            assert table.row_count == 2

            await pilot.click("#filter-reset")
            assert table.row_count == 5

    async def test_status_shows_count(self) -> None:
        """Status bar shows the number of budgets."""
        app = BudgetsWidgetTestApp()
        async with app.run_test():
            status = app.query_one("#budgets-status", Static)
            assert "5" in str(status.render())

    async def test_filter_bar_shows_filtered_count(self) -> None:
        """Filter bar status shows filtered vs total count."""
        app = BudgetsWidgetTestApp()
        async with app.run_test() as pilot:
            app.query_one("#filter-search", Input).value = "courses"
            await pilot.click("#filter-apply")

            status = app.query_one("#filter-status", Static)
            rendered = str(status.render())
            assert "2" in rendered
            assert "5" in rendered

    async def test_no_date_or_amount_range_inputs(self) -> None:
        """FilterBar in budgets does not show date/amount range inputs."""
        app = BudgetsWidgetTestApp()
        async with app.run_test():
            filter_bar = app.query_one(FilterBar)
            assert filter_bar.date_from is None
            assert filter_bar.date_to is None
            assert filter_bar.min_amount is None
            assert filter_bar.max_amount is None

    async def test_search_case_insensitive(self) -> None:
        """Search text is case-insensitive."""
        app = BudgetsWidgetTestApp()
        async with app.run_test() as pilot:
            app.query_one("#filter-search", Input).value = "EDF"
            await pilot.click("#filter-apply")

            table = app.query_one("#budgets-table", DataTable)
            assert table.row_count == 1

    async def test_no_match_shows_empty_table(self) -> None:
        """A search with no matches shows an empty table."""
        app = BudgetsWidgetTestApp()
        async with app.run_test() as pilot:
            app.query_one("#filter-search", Input).value = "zzz-no-match"
            await pilot.click("#filter-apply")

            table = app.query_one("#budgets-table", DataTable)
            assert table.row_count == 0
