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
from budget_forecaster.tui.widgets.filter_bar import FilterBar, StatusFilter


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
            date(2030, 12, 31),
        ),
    )


SAMPLE_OPERATIONS = (
    _make_planned_operation(1, "Loyer mensuel", -900.00, Category.RENT),
    _make_planned_operation(2, "Electricite EDF", -80.00, Category.ELECTRICITY),
    _make_planned_operation(3, "Abonnement metro", -75.00, Category.PUBLIC_TRANSPORT),
    _make_planned_operation(4, "Salaire net", 2500.00, Category.SALARY),
    _make_planned_operation(5, "Loyer parking", -60.00, Category.RENT),
)


def _make_expired_operation(
    record_id: int,
    description: str,
    amount: float,
    category: Category,
) -> PlannedOperation:
    """Create a test planned operation that is already expired."""
    return PlannedOperation(
        record_id=record_id,
        description=description,
        amount=Amount(amount, "EUR"),
        category=category,
        date_range=RecurringDay(
            date(2023, 1, 1),
            relativedelta(months=1),
            date(2024, 12, 31),
        ),
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
        async with app.run_test(size=(160, 48)):
            table = app.query_one("#planned-ops-table", DataTable)
            assert table.row_count == 5

    async def test_filter_by_search_text(self) -> None:
        """Filtering by search text shows only matching operations."""
        app = PlannedOpsWidgetTestApp()
        async with app.run_test(size=(160, 48)) as pilot:
            app.query_one("#filter-search", Input).value = "loyer"
            await pilot.click("#filter-apply")

            widget = app.query_one(PlannedOperationsWidget)
            descriptions = {op.description for op in widget.planned_operations}
            assert descriptions == {"Loyer mensuel", "Loyer parking"}

    async def test_filter_by_category(self) -> None:
        """Filtering by category shows only matching operations."""
        app = PlannedOpsWidgetTestApp()
        async with app.run_test(size=(160, 48)) as pilot:
            app.query_one("#filter-category", Select).value = Category.RENT.name
            await pilot.click("#filter-apply")

            widget = app.query_one(PlannedOperationsWidget)
            descriptions = {op.description for op in widget.planned_operations}
            assert descriptions == {"Loyer mensuel", "Loyer parking"}

    async def test_combined_filters(self) -> None:
        """Combining search text and category narrows results further."""
        app = PlannedOpsWidgetTestApp()
        async with app.run_test(size=(160, 48)) as pilot:
            app.query_one("#filter-search", Input).value = "parking"
            app.query_one("#filter-category", Select).value = Category.RENT.name
            await pilot.click("#filter-apply")

            widget = app.query_one(PlannedOperationsWidget)
            descriptions = {op.description for op in widget.planned_operations}
            assert descriptions == {"Loyer parking"}

    async def test_reset_restores_all_operations(self) -> None:
        """Resetting filters shows all operations again."""
        app = PlannedOpsWidgetTestApp()
        async with app.run_test(size=(160, 48)) as pilot:
            app.query_one("#filter-search", Input).value = "loyer"
            await pilot.click("#filter-apply")

            widget = app.query_one(PlannedOperationsWidget)
            assert len(widget.planned_operations) == 2

            await pilot.click("#filter-reset")
            assert len(widget.planned_operations) == 5

    async def test_status_shows_count(self) -> None:
        """Status bar shows the number of planned operations."""
        app = PlannedOpsWidgetTestApp()
        async with app.run_test(size=(160, 48)):
            status = app.query_one("#planned-ops-status", Static)
            assert str(status.render()) == "5 planned operation(s)"

    async def test_filter_bar_shows_filtered_count(self) -> None:
        """Filter bar status shows filtered vs total count."""
        app = PlannedOpsWidgetTestApp()
        async with app.run_test(size=(160, 48)) as pilot:
            app.query_one("#filter-search", Input).value = "loyer"
            await pilot.click("#filter-apply")

            status = app.query_one("#filter-status", Static)
            assert str(status.render()) == "2 / 5"

    async def test_no_date_or_amount_range_inputs(self) -> None:
        """FilterBar in planned ops does not show date/amount range inputs."""
        app = PlannedOpsWidgetTestApp()
        async with app.run_test(size=(160, 48)):
            filter_bar = app.query_one(FilterBar)
            assert filter_bar.date_from is None
            assert filter_bar.date_to is None
            assert filter_bar.min_amount is None
            assert filter_bar.max_amount is None

    async def test_search_case_insensitive(self) -> None:
        """Search text is case-insensitive."""
        app = PlannedOpsWidgetTestApp()
        async with app.run_test(size=(160, 48)) as pilot:
            app.query_one("#filter-search", Input).value = "EDF"
            await pilot.click("#filter-apply")

            widget = app.query_one(PlannedOperationsWidget)
            descriptions = {op.description for op in widget.planned_operations}
            assert descriptions == {"Electricite EDF"}

    async def test_no_match_shows_empty_table(self) -> None:
        """A search with no matches shows an empty table."""
        app = PlannedOpsWidgetTestApp()
        async with app.run_test(size=(160, 48)) as pilot:
            app.query_one("#filter-search", Input).value = "zzz-no-match"
            await pilot.click("#filter-apply")

            table = app.query_one("#planned-ops-table", DataTable)
            assert table.row_count == 0

    async def test_expired_filter_shows_only_expired(self) -> None:
        """Expired status filter shows only expired operations."""
        mixed_ops = (
            _make_planned_operation(1, "Active op", -100.0, Category.RENT),
            _make_expired_operation(2, "Expired op", -200.0, Category.ELECTRICITY),
        )
        app = PlannedOpsWidgetTestApp(operations=mixed_ops)
        async with app.run_test(size=(160, 48)) as pilot:
            app.query_one(
                "#filter-status-select", Select
            ).value = StatusFilter.EXPIRED.value
            await pilot.click("#filter-apply")

            widget = app.query_one(PlannedOperationsWidget)
            descriptions = {op.description for op in widget.planned_operations}
            assert descriptions == {"Expired op"}
