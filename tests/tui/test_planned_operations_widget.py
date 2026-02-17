"""Tests for PlannedOperationsWidget with FilterBar integration."""

from datetime import date
from unittest.mock import Mock

from dateutil.relativedelta import relativedelta
from textual.app import App, ComposeResult
from textual.widgets import DataTable, Input, Select, Static

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.date_range import RecurringDay
from budget_forecaster.core.types import Category
from budget_forecaster.domain.operation.planned_operation import PlannedOperation
from budget_forecaster.services.application_service import ApplicationService
from budget_forecaster.tui.screens.planned_operations import PlannedOperationsWidget
from budget_forecaster.tui.widgets.filter_bar import FilterBar


def _make_planned_operation(
    record_id: int,
    description: str,
    amount: float,
    category: Category,
) -> PlannedOperation:
    """Create a test planned operation with a simple recurring date range."""
    return PlannedOperation(
        record_id=record_id,
        description=description,
        amount=Amount(amount, "EUR"),
        category=category,
        date_range=RecurringDay(
            date(2025, 1, 1),
            relativedelta(months=1),
            date(2025, 12, 31),
        ),
    )


SAMPLE_OPERATIONS = (
    _make_planned_operation(1, "Loyer mensuel", -900.00, Category.RENT),
    _make_planned_operation(2, "Electricite EDF", -80.00, Category.ELECTRICITY),
    _make_planned_operation(3, "Abonnement metro", -75.00, Category.PUBLIC_TRANSPORT),
    _make_planned_operation(4, "Salaire net", 2500.00, Category.SALARY),
    _make_planned_operation(5, "Loyer parking", -60.00, Category.RENT),
)


def _make_app_service(
    operations: tuple[PlannedOperation, ...],
) -> Mock:
    """Create a mock ApplicationService returning given planned operations."""
    service = Mock(spec=ApplicationService)
    service.get_all_planned_operations = Mock(return_value=operations)
    return service


class PlannedOpsWidgetTestApp(App[None]):
    """Test app wrapping PlannedOperationsWidget."""

    def __init__(
        self, operations: tuple[PlannedOperation, ...] = SAMPLE_OPERATIONS
    ) -> None:
        super().__init__()
        self._service = _make_app_service(operations)

    def compose(self) -> ComposeResult:
        yield PlannedOperationsWidget(id="planned-ops-widget")

    def on_mount(self) -> None:
        """Inject the mock service."""
        widget = self.query_one(PlannedOperationsWidget)
        widget.set_app_service(self._service)


class TestPlannedOperationsWidgetFiltering:
    """Integration tests for PlannedOperationsWidget filtering."""

    async def test_all_operations_shown_initially(self) -> None:
        """All planned operations are displayed when no filter is applied."""
        app = PlannedOpsWidgetTestApp()
        async with app.run_test():
            table = app.query_one("#planned-ops-table", DataTable)
            assert table.row_count == 5

    async def test_filter_by_search_text(self) -> None:
        """Filtering by search text shows only matching operations."""
        app = PlannedOpsWidgetTestApp()
        async with app.run_test() as pilot:
            app.query_one("#filter-search", Input).value = "loyer"
            await pilot.click("#filter-apply")

            table = app.query_one("#planned-ops-table", DataTable)
            # "Loyer mensuel" and "Loyer parking"
            assert table.row_count == 2

    async def test_filter_by_category(self) -> None:
        """Filtering by category shows only matching operations."""
        app = PlannedOpsWidgetTestApp()
        async with app.run_test() as pilot:
            app.query_one("#filter-category", Select).value = Category.RENT.name
            await pilot.click("#filter-apply")

            table = app.query_one("#planned-ops-table", DataTable)
            assert table.row_count == 2

    async def test_combined_filters(self) -> None:
        """Combining search text and category narrows results further."""
        app = PlannedOpsWidgetTestApp()
        async with app.run_test() as pilot:
            app.query_one("#filter-search", Input).value = "parking"
            app.query_one("#filter-category", Select).value = Category.RENT.name
            await pilot.click("#filter-apply")

            table = app.query_one("#planned-ops-table", DataTable)
            assert table.row_count == 1

    async def test_reset_restores_all_operations(self) -> None:
        """Resetting filters shows all operations again."""
        app = PlannedOpsWidgetTestApp()
        async with app.run_test() as pilot:
            app.query_one("#filter-search", Input).value = "loyer"
            await pilot.click("#filter-apply")

            table = app.query_one("#planned-ops-table", DataTable)
            assert table.row_count == 2

            await pilot.click("#filter-reset")
            assert table.row_count == 5

    async def test_status_shows_count(self) -> None:
        """Status bar shows the number of planned operations."""
        app = PlannedOpsWidgetTestApp()
        async with app.run_test():
            status = app.query_one("#planned-ops-status", Static)
            assert "5" in str(status.render())

    async def test_filter_bar_shows_filtered_count(self) -> None:
        """Filter bar status shows filtered vs total count."""
        app = PlannedOpsWidgetTestApp()
        async with app.run_test() as pilot:
            app.query_one("#filter-search", Input).value = "loyer"
            await pilot.click("#filter-apply")

            status = app.query_one("#filter-status", Static)
            rendered = str(status.render())
            assert "2" in rendered
            assert "5" in rendered

    async def test_no_date_or_amount_range_inputs(self) -> None:
        """FilterBar in planned ops does not show date/amount range inputs."""
        app = PlannedOpsWidgetTestApp()
        async with app.run_test():
            filter_bar = app.query_one(FilterBar)
            assert filter_bar.date_from is None
            assert filter_bar.date_to is None
            assert filter_bar.min_amount is None
            assert filter_bar.max_amount is None

    async def test_search_case_insensitive(self) -> None:
        """Search text is case-insensitive."""
        app = PlannedOpsWidgetTestApp()
        async with app.run_test() as pilot:
            app.query_one("#filter-search", Input).value = "EDF"
            await pilot.click("#filter-apply")

            table = app.query_one("#planned-ops-table", DataTable)
            assert table.row_count == 1

    async def test_no_match_shows_empty_table(self) -> None:
        """A search with no matches shows an empty table."""
        app = PlannedOpsWidgetTestApp()
        async with app.run_test() as pilot:
            app.query_one("#filter-search", Input).value = "zzz-no-match"
            await pilot.click("#filter-apply")

            table = app.query_one("#planned-ops-table", DataTable)
            assert table.row_count == 0
