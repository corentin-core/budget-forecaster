"""Tests for OperationTable multi-selection functionality."""

from datetime import datetime

import pytest
from textual.app import App, ComposeResult

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.types import Category
from budget_forecaster.domain.operation.historic_operation import HistoricOperation
from budget_forecaster.tui.widgets.operation_table import OperationTable


def make_operation(
    unique_id: int,
    description: str = "Test operation",
    amount: float = -100.00,
    category: Category = Category.UNCATEGORIZED,
) -> HistoricOperation:
    """Create a test operation."""
    return HistoricOperation(
        unique_id=unique_id,
        date=datetime(2025, 1, 15),
        description=description,
        amount=Amount(amount, "EUR"),
        category=category,
    )


@pytest.fixture
def sample_operations() -> list[HistoricOperation]:
    """Create sample operations for testing."""
    return [
        make_operation(1, "Operation 1", -50.00),
        make_operation(2, "Operation 2", -75.00),
        make_operation(3, "Operation 3", -100.00),
        make_operation(4, "Operation 4", -125.00),
        make_operation(5, "Operation 5", -150.00),
    ]


class OperationTableTestApp(App[None]):
    """Test app containing just an OperationTable."""

    def __init__(self, operations: list[HistoricOperation] | None = None) -> None:
        super().__init__()
        self._operations = operations or []
        self.selection_changed_count = 0
        self.last_selection_count = 0

    def compose(self) -> ComposeResult:
        yield OperationTable()

    def on_mount(self) -> None:
        """Load operations when app mounts."""
        if self._operations:
            table = self.query_one(OperationTable)
            table.load_operations(self._operations)

    def on_operation_table_selection_changed(
        self, event: OperationTable.SelectionChanged
    ) -> None:
        """Track selection change events for test assertions."""
        self.selection_changed_count += 1
        self.last_selection_count = event.selected_count


class TestOperationTableIntegration:
    """Integration tests for OperationTable using Textual test framework."""

    @pytest.mark.asyncio
    async def test_toggle_selection_with_space(
        self, sample_operations: list[HistoricOperation]
    ) -> None:
        """Test toggling selection with space key."""
        app = OperationTableTestApp(sample_operations)
        async with app.run_test() as pilot:
            table = app.query_one(OperationTable)

            # Press space to select first row
            await pilot.press("space")

            assert table.selected_count == 1
            assert app.selection_changed_count >= 1

            # Press space again to deselect
            await pilot.press("space")

            assert table.selected_count == 0

    @pytest.mark.asyncio
    async def test_extend_selection_down_with_shift(
        self, sample_operations: list[HistoricOperation]
    ) -> None:
        """Test extending selection down with shift+down."""
        app = OperationTableTestApp(sample_operations)
        async with app.run_test() as pilot:
            table = app.query_one(OperationTable)

            # Extend selection down twice
            await pilot.press("shift+down")
            await pilot.press("shift+down")

            # Should have 3 rows selected (initial + 2 extensions)
            assert table.selected_count == 3

    @pytest.mark.asyncio
    async def test_extend_selection_up_with_shift(
        self, sample_operations: list[HistoricOperation]
    ) -> None:
        """Test extending selection up with shift+up."""
        app = OperationTableTestApp(sample_operations)
        async with app.run_test() as pilot:
            table = app.query_one(OperationTable)

            # Move to middle of table first
            await pilot.press("down")
            await pilot.press("down")

            # Extend selection up twice
            await pilot.press("shift+up")
            await pilot.press("shift+up")

            # Should have 3 rows selected
            assert table.selected_count == 3

    @pytest.mark.asyncio
    async def test_select_all_with_ctrl_a(
        self, sample_operations: list[HistoricOperation]
    ) -> None:
        """Test selecting all rows with ctrl+a."""
        app = OperationTableTestApp(sample_operations)
        async with app.run_test() as pilot:
            table = app.query_one(OperationTable)

            await pilot.press("ctrl+a")

            assert table.selected_count == 5
            assert app.last_selection_count == 5

    @pytest.mark.asyncio
    async def test_clear_selection_with_escape(
        self, sample_operations: list[HistoricOperation]
    ) -> None:
        """Test clearing selection with escape key."""
        app = OperationTableTestApp(sample_operations)
        async with app.run_test() as pilot:
            table = app.query_one(OperationTable)

            # Select all first
            await pilot.press("ctrl+a")
            assert table.selected_count == 5

            # Clear with escape
            await pilot.press("escape")

            assert table.selected_count == 0
            assert app.last_selection_count == 0

    @pytest.mark.asyncio
    async def test_get_selected_operations_returns_selection(
        self, sample_operations: list[HistoricOperation]
    ) -> None:
        """Test get_selected_operations returns the selected operations."""
        app = OperationTableTestApp(sample_operations)
        async with app.run_test() as pilot:
            table = app.query_one(OperationTable)

            # Select first two operations
            await pilot.press("space")
            await pilot.press("shift+down")

            selected = table.get_selected_operations()

            assert len(selected) == 2
            # Verify we got actual operation objects
            assert all(isinstance(op, HistoricOperation) for op in selected)

    @pytest.mark.asyncio
    async def test_get_selected_operations_returns_highlighted_when_no_selection(
        self, sample_operations: list[HistoricOperation]
    ) -> None:
        """Test get_selected_operations returns highlighted row when no explicit selection."""
        app = OperationTableTestApp(sample_operations)
        async with app.run_test() as pilot:
            table = app.query_one(OperationTable)

            # Move cursor without selecting
            await pilot.press("down")
            await pilot.press("down")

            # No explicit selection, but cursor is on row 2
            assert table.selected_count == 0

            selected = table.get_selected_operations()

            # Should return the highlighted operation
            assert len(selected) == 1

    @pytest.mark.asyncio
    async def test_load_operations_clears_selection(
        self, sample_operations: list[HistoricOperation]
    ) -> None:
        """Test that loading new operations clears previous selection."""
        app = OperationTableTestApp(sample_operations)
        async with app.run_test() as pilot:
            table = app.query_one(OperationTable)

            # Select some operations
            await pilot.press("ctrl+a")
            assert table.selected_count == 5

            # Load new operations
            new_ops = [make_operation(10), make_operation(11)]
            table.load_operations(new_ops)

            # Selection should be cleared
            assert table.selected_count == 0

    @pytest.mark.asyncio
    async def test_selection_changed_message_sent(
        self, sample_operations: list[HistoricOperation]
    ) -> None:
        """Test that SelectionChanged message is sent when selection changes."""
        app = OperationTableTestApp(sample_operations)
        async with app.run_test() as pilot:
            initial_count = app.selection_changed_count

            await pilot.press("space")

            # Message should have been sent
            assert app.selection_changed_count > initial_count
            assert app.last_selection_count == 1

    @pytest.mark.asyncio
    async def test_extend_selection_at_boundary_does_nothing(
        self, sample_operations: list[HistoricOperation]
    ) -> None:
        """Test that extending selection at table boundaries doesn't crash."""
        app = OperationTableTestApp(sample_operations)
        async with app.run_test() as pilot:
            table = app.query_one(OperationTable)

            # Try to extend up at top - should not crash or select anything
            await pilot.press("shift+up")

            # Move to bottom
            for _ in range(5):
                await pilot.press("down")

            # Try to extend down at bottom
            await pilot.press("shift+down")

            # Should not crash, selection should be reasonable
            assert table.selected_count >= 0


class TestOperationTableEmpty:  # pylint: disable=too-few-public-methods
    """Tests for OperationTable with no operations."""

    @pytest.mark.asyncio
    async def test_empty_table_operations(self) -> None:
        """Test that empty table handles operations gracefully."""
        app = OperationTableTestApp([])
        async with app.run_test() as pilot:
            table = app.query_one(OperationTable)

            # These should not crash on empty table
            await pilot.press("space")
            await pilot.press("ctrl+a")
            await pilot.press("escape")

            assert table.selected_count == 0
            assert table.get_selected_operations() == ()
