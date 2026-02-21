"""Tests for OperationsScreen with FilterBar integration."""

from datetime import date
from unittest.mock import Mock

from textual.app import App, ComposeResult
from textual.widgets import Input, Select, Static

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.types import Category
from budget_forecaster.domain.operation.historic_operation import HistoricOperation
from budget_forecaster.services.application_service import ApplicationService
from budget_forecaster.services.operation.operation_service import OperationFilter
from budget_forecaster.tui.screens.operations import OperationsScreen
from budget_forecaster.tui.widgets.operation_table import OperationTable


def _make_operation(
    unique_id: int,
    description: str = "Test operation",
    amount: float = -100.00,
    category: Category = Category.UNCATEGORIZED,
    op_date: date | None = None,
) -> HistoricOperation:
    """Create a test operation."""
    return HistoricOperation(
        unique_id=unique_id,
        operation_date=op_date or date(2025, 1, 15),
        description=description,
        amount=Amount(amount, "EUR"),
        category=category,
    )


SAMPLE_OPERATIONS = (
    _make_operation(
        1, "CARREFOUR MARKET", -85.20, Category.GROCERIES, date(2025, 1, 10)
    ),
    _make_operation(
        2, "SNCF VOYAGE", -45.00, Category.PUBLIC_TRANSPORT, date(2025, 2, 5)
    ),
    _make_operation(
        3, "CARREFOUR EXPRESS", -12.50, Category.GROCERIES, date(2025, 3, 20)
    ),
    _make_operation(4, "EDF FACTURE", -95.00, Category.ELECTRICITY, date(2025, 1, 25)),
    _make_operation(
        5, "RESTAURANT LE BISTRO", -32.00, Category.LEISURE, date(2025, 4, 1)
    ),
)


def _make_app_service(operations: tuple[HistoricOperation, ...]) -> Mock:
    """Create a mock ApplicationService returning given operations."""
    service = Mock(spec=ApplicationService)

    def get_operations(
        filter_: OperationFilter | None = None,
    ) -> tuple[HistoricOperation, ...]:
        if filter_ is None:
            return operations
        return tuple(op for op in operations if filter_.matches(op))

    service.get_operations = Mock(side_effect=get_operations)
    service.get_all_links = Mock(return_value=())
    service.get_all_planned_operations = Mock(return_value=())
    service.get_all_budgets = Mock(return_value=())
    return service


class OperationsScreenTestApp(App[None]):
    """Test app wrapping OperationsScreen."""

    def __init__(
        self, operations: tuple[HistoricOperation, ...] = SAMPLE_OPERATIONS
    ) -> None:
        super().__init__()
        self._operations = operations
        self._service = _make_app_service(operations)

    def compose(self) -> ComposeResult:
        yield OperationsScreen(id="ops-screen")

    def on_mount(self) -> None:
        """Inject the mock service."""
        screen = self.query_one(OperationsScreen)
        screen.set_app_service(self._service)


class TestOperationsScreenIntegration:
    """Integration tests for OperationsScreen filtering."""

    async def test_all_operations_shown_initially(self) -> None:
        """All operations are displayed when no filter is applied."""
        app = OperationsScreenTestApp()
        async with app.run_test():
            table = app.query_one(OperationTable)
            assert table.operation_count == 5

    async def test_filter_by_search_text(self) -> None:
        """Filtering by search text shows only matching operations."""
        app = OperationsScreenTestApp()
        async with app.run_test() as pilot:
            app.query_one("#filter-search", Input).value = "carrefour"
            await pilot.click("#filter-apply")

            table = app.query_one(OperationTable)
            descriptions = {op.description for op in table.operations}
            assert descriptions == {"CARREFOUR MARKET", "CARREFOUR EXPRESS"}

    async def test_filter_by_category(self) -> None:
        """Filtering by category shows only matching operations."""
        app = OperationsScreenTestApp()
        async with app.run_test() as pilot:
            app.query_one("#filter-category", Select).value = Category.GROCERIES.name
            await pilot.click("#filter-apply")

            table = app.query_one(OperationTable)
            descriptions = {op.description for op in table.operations}
            assert descriptions == {"CARREFOUR MARKET", "CARREFOUR EXPRESS"}

    async def test_combined_filters(self) -> None:
        """Combining search text and category narrows results further."""
        app = OperationsScreenTestApp()
        async with app.run_test() as pilot:
            app.query_one("#filter-search", Input).value = "express"
            app.query_one("#filter-category", Select).value = Category.GROCERIES.name
            await pilot.click("#filter-apply")

            table = app.query_one(OperationTable)
            descriptions = {op.description for op in table.operations}
            assert descriptions == {"CARREFOUR EXPRESS"}

    async def test_reset_restores_all_operations(self) -> None:
        """Resetting filters shows all operations again."""
        app = OperationsScreenTestApp()
        async with app.run_test() as pilot:
            # Apply a filter first
            app.query_one("#filter-search", Input).value = "carrefour"
            await pilot.click("#filter-apply")

            table = app.query_one(OperationTable)
            assert table.operation_count == 2

            # Reset
            await pilot.click("#filter-reset")
            assert table.operation_count == 5

    async def test_status_bar_shows_count(self) -> None:
        """Status bar shows the number of operations."""
        app = OperationsScreenTestApp()
        async with app.run_test():
            status = app.query_one("#status-bar", Static)
            assert "5" in str(status.render())

    async def test_filter_bar_shows_filtered_count(self) -> None:
        """Filter bar status shows filtered vs total count."""
        app = OperationsScreenTestApp()
        async with app.run_test() as pilot:
            app.query_one("#filter-search", Input).value = "carrefour"
            await pilot.click("#filter-apply")

            status = app.query_one("#filter-status", Static)
            assert str(status.render()) == "2 / 5"

    async def test_filter_by_date_from(self) -> None:
        """Filtering by date_from excludes earlier operations."""
        app = OperationsScreenTestApp()
        async with app.run_test() as pilot:
            app.query_one("#filter-date-from", Input).value = "2025-02-01"
            await pilot.click("#filter-apply")

            table = app.query_one(OperationTable)
            descriptions = {op.description for op in table.operations}
            assert descriptions == {
                "SNCF VOYAGE",
                "CARREFOUR EXPRESS",
                "RESTAURANT LE BISTRO",
            }

    async def test_filter_by_date_to(self) -> None:
        """Filtering by date_to excludes later operations."""
        app = OperationsScreenTestApp()
        async with app.run_test() as pilot:
            app.query_one("#filter-date-to", Input).value = "2025-01-31"
            await pilot.click("#filter-apply")

            table = app.query_one(OperationTable)
            descriptions = {op.description for op in table.operations}
            assert descriptions == {"CARREFOUR MARKET", "EDF FACTURE"}

    async def test_filter_by_date_range(self) -> None:
        """Filtering by date range shows operations within the range."""
        app = OperationsScreenTestApp()
        async with app.run_test() as pilot:
            app.query_one("#filter-date-from", Input).value = "2025-02-01"
            app.query_one("#filter-date-to", Input).value = "2025-03-31"
            await pilot.click("#filter-apply")

            table = app.query_one(OperationTable)
            descriptions = {op.description for op in table.operations}
            assert descriptions == {"SNCF VOYAGE", "CARREFOUR EXPRESS"}

    async def test_filter_by_min_amount(self) -> None:
        """Filtering by min_amount excludes smaller amounts."""
        app = OperationsScreenTestApp()
        async with app.run_test() as pilot:
            app.query_one("#filter-amount-min", Input).value = "-50"
            await pilot.click("#filter-apply")

            table = app.query_one(OperationTable)
            descriptions = {op.description for op in table.operations}
            assert descriptions == {
                "SNCF VOYAGE",
                "CARREFOUR EXPRESS",
                "RESTAURANT LE BISTRO",
            }

    async def test_filter_by_max_amount(self) -> None:
        """Filtering by max_amount excludes larger amounts."""
        app = OperationsScreenTestApp()
        async with app.run_test() as pilot:
            app.query_one("#filter-amount-max", Input).value = "-80"
            await pilot.click("#filter-apply")

            table = app.query_one(OperationTable)
            descriptions = {op.description for op in table.operations}
            assert descriptions == {"CARREFOUR MARKET", "EDF FACTURE"}

    async def test_filter_by_amount_range(self) -> None:
        """Filtering by amount range narrows results."""
        app = OperationsScreenTestApp()
        async with app.run_test() as pilot:
            app.query_one("#filter-amount-min", Input).value = "-90"
            app.query_one("#filter-amount-max", Input).value = "-40"
            await pilot.click("#filter-apply")

            table = app.query_one(OperationTable)
            descriptions = {op.description for op in table.operations}
            assert descriptions == {"CARREFOUR MARKET", "SNCF VOYAGE"}

    async def test_combined_all_filters(self) -> None:
        """Combining search, category, date, and amount filters."""
        app = OperationsScreenTestApp()
        async with app.run_test() as pilot:
            app.query_one("#filter-search", Input).value = "carrefour"
            app.query_one("#filter-category", Select).value = Category.GROCERIES.name
            app.query_one("#filter-date-from", Input).value = "2025-03-01"
            await pilot.click("#filter-apply")

            table = app.query_one(OperationTable)
            descriptions = {op.description for op in table.operations}
            assert descriptions == {"CARREFOUR EXPRESS"}

    async def test_invalid_date_ignored(self) -> None:
        """Invalid date values are ignored (treated as no filter)."""
        app = OperationsScreenTestApp()
        async with app.run_test() as pilot:
            app.query_one("#filter-date-from", Input).value = "invalid"
            await pilot.click("#filter-apply")

            table = app.query_one(OperationTable)
            assert table.operation_count == 5

    async def test_invalid_amount_ignored(self) -> None:
        """Invalid amount values are ignored (treated as no filter)."""
        app = OperationsScreenTestApp()
        async with app.run_test() as pilot:
            app.query_one("#filter-amount-min", Input).value = "abc"
            await pilot.click("#filter-apply")

            table = app.query_one(OperationTable)
            assert table.operation_count == 5
