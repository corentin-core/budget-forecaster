"""Tests for SplitOperationModal TUI component."""

from datetime import datetime

import pytest
from dateutil.relativedelta import relativedelta
from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import Button, Input, Select, Static

from budget_forecaster.amount import Amount
from budget_forecaster.operation_range.budget import Budget
from budget_forecaster.operation_range.planned_operation import PlannedOperation
from budget_forecaster.time_range import (
    DailyTimeRange,
    PeriodicDailyTimeRange,
    PeriodicTimeRange,
    TimeRange,
)
from budget_forecaster.tui.modals.split_operation import (
    SplitOperationModal,
    SplitResult,
)
from budget_forecaster.types import Category


def make_periodic_planned_operation(
    record_id: int = 1,
    description: str = "Salary",
    amount: float = 2500.0,
    initial_date: datetime | None = None,
) -> PlannedOperation:
    """Create a test periodic PlannedOperation."""
    if initial_date is None:
        initial_date = datetime(2025, 1, 1)
    return PlannedOperation(
        record_id=record_id,
        description=description,
        amount=Amount(amount, "EUR"),
        category=Category.SALARY,
        time_range=PeriodicDailyTimeRange(
            initial_date,
            relativedelta(months=1),
        ),
    )


def make_non_periodic_planned_operation() -> PlannedOperation:
    """Create a non-periodic PlannedOperation."""
    return PlannedOperation(
        record_id=2,
        description="One-time payment",
        amount=Amount(-500.0, "EUR"),
        category=Category.OTHER,
        time_range=DailyTimeRange(datetime(2025, 3, 15)),
    )


def make_periodic_budget(
    record_id: int = 1,
    description: str = "Monthly groceries",
    amount: float = -400.0,
    initial_date: datetime | None = None,
) -> Budget:
    """Create a test periodic Budget."""
    if initial_date is None:
        initial_date = datetime(2025, 1, 1)
    return Budget(
        record_id=record_id,
        description=description,
        amount=Amount(amount, "EUR"),
        category=Category.GROCERIES,
        time_range=PeriodicTimeRange(
            TimeRange(initial_date, relativedelta(months=1)),
            period=relativedelta(months=1),
        ),
    )


# Terminal size for tests - large enough to display modal
TEST_SIZE = (100, 50)


class SplitModalTestApp(App[None]):
    """Test app for SplitOperationModal."""

    def __init__(
        self,
        target: PlannedOperation | Budget,
        default_date: datetime | None = None,
    ) -> None:
        super().__init__()
        self._target = target
        self._default_date = default_date
        self.modal_result: SplitResult | None = None
        self.modal_dismissed = False

    def compose(self) -> ComposeResult:
        yield Container()

    def open_modal(self) -> None:
        """Open the split modal."""
        self.push_screen(
            SplitOperationModal(self._target, self._default_date),
            self._on_modal_closed,
        )

    def _on_modal_closed(self, result: SplitResult | None) -> None:
        """Track modal result."""
        self.modal_result = result
        self.modal_dismissed = True


class TestSplitOperationModalDisplay:
    """Tests for modal display and initialization."""

    @pytest.mark.asyncio
    async def test_displays_planned_operation_info(self) -> None:
        """Verify modal shows PlannedOperation description and details."""
        operation = make_periodic_planned_operation()
        app = SplitModalTestApp(operation)
        async with app.run_test(size=TEST_SIZE) as pilot:
            app.open_modal()
            await pilot.pause()

            modal = app.screen
            assert isinstance(modal, SplitOperationModal)
            # Access the Static widget's update value
            info_desc = modal.query_one("#info-description", Static)
            # The renderable is the text content
            assert "Salary" in str(info_desc.content)

    @pytest.mark.asyncio
    async def test_displays_budget_info(self) -> None:
        """Verify modal shows Budget description and details."""
        budget = make_periodic_budget()
        app = SplitModalTestApp(budget)
        async with app.run_test(size=TEST_SIZE) as pilot:
            app.open_modal()
            await pilot.pause()

            modal = app.screen
            assert isinstance(modal, SplitOperationModal)
            info_desc = modal.query_one("#info-description", Static)
            assert "Monthly groceries" in str(info_desc.content)

    @pytest.mark.asyncio
    async def test_duration_field_visible_for_budget(self) -> None:
        """Verify duration field is visible for Budget."""
        budget = make_periodic_budget()
        app = SplitModalTestApp(budget)
        async with app.run_test(size=TEST_SIZE) as pilot:
            app.open_modal()
            await pilot.pause()

            modal = app.screen
            duration_input = modal.query_one("#input-duration", Input)
            # Parent should not have hidden class
            parent = duration_input.parent
            assert parent is not None
            assert "hidden" not in parent.classes

    @pytest.mark.asyncio
    async def test_duration_field_hidden_for_planned_operation(self) -> None:
        """Verify duration field is hidden for PlannedOperation."""
        operation = make_periodic_planned_operation()
        app = SplitModalTestApp(operation)
        async with app.run_test(size=TEST_SIZE) as pilot:
            app.open_modal()
            await pilot.pause()

            modal = app.screen
            duration_input = modal.query_one("#input-duration", Input)
            parent = duration_input.parent
            assert parent is not None
            assert "hidden" in parent.classes

    @pytest.mark.asyncio
    async def test_default_date_populated(self) -> None:
        """Verify default date is populated in the input."""
        operation = make_periodic_planned_operation()
        default_date = datetime(2025, 6, 1)
        app = SplitModalTestApp(operation, default_date)
        async with app.run_test(size=TEST_SIZE) as pilot:
            app.open_modal()
            await pilot.pause()

            modal = app.screen
            date_input = modal.query_one("#input-split-date", Input)
            assert date_input.value == "2025-06-01"


class TestSplitOperationModalValidation:
    """Tests for form validation."""

    @pytest.mark.asyncio
    async def test_invalid_date_format_shows_error(self) -> None:
        """Verify error is shown for invalid date format."""
        operation = make_periodic_planned_operation()
        app = SplitModalTestApp(operation)
        async with app.run_test(size=TEST_SIZE) as pilot:
            app.open_modal()
            await pilot.pause()

            modal = app.screen
            date_input = modal.query_one("#input-split-date", Input)
            date_input.value = "invalid-date"
            await pilot.pause()

            # Focus apply button and press enter
            apply_btn = modal.query_one("#btn-apply", Button)
            apply_btn.focus()
            await pilot.press("enter")
            await pilot.pause()

            # Modal should still be open and show error
            assert not app.modal_dismissed
            error_msg = modal.query_one("#error-message", Static)
            assert "YYYY-MM-DD" in str(error_msg.content)

    @pytest.mark.asyncio
    async def test_date_before_start_shows_error(self) -> None:
        """Verify error is shown when split date is before operation start."""
        operation = make_periodic_planned_operation(initial_date=datetime(2025, 1, 1))
        app = SplitModalTestApp(operation)
        async with app.run_test(size=TEST_SIZE) as pilot:
            app.open_modal()
            await pilot.pause()

            modal = app.screen
            date_input = modal.query_one("#input-split-date", Input)
            date_input.value = "2024-12-01"  # Before initial date
            await pilot.pause()

            apply_btn = modal.query_one("#btn-apply", Button)
            apply_btn.focus()
            await pilot.press("enter")
            await pilot.pause()

            assert not app.modal_dismissed
            error_msg = modal.query_one("#error-message", Static)
            assert "après" in str(error_msg.content)

    @pytest.mark.asyncio
    async def test_invalid_amount_shows_error(self) -> None:
        """Verify error is shown for invalid amount."""
        operation = make_periodic_planned_operation()
        app = SplitModalTestApp(operation)
        async with app.run_test(size=TEST_SIZE) as pilot:
            app.open_modal()
            await pilot.pause()

            modal = app.screen
            amount_input = modal.query_one("#input-amount", Input)
            amount_input.value = "not-a-number"
            await pilot.pause()

            apply_btn = modal.query_one("#btn-apply", Button)
            apply_btn.focus()
            await pilot.press("enter")
            await pilot.pause()

            assert not app.modal_dismissed
            error_msg = modal.query_one("#error-message", Static)
            assert "nombre" in str(error_msg.content)

    @pytest.mark.asyncio
    async def test_invalid_duration_shows_error_for_budget(self) -> None:
        """Verify error is shown for invalid duration in budget."""
        budget = make_periodic_budget()
        app = SplitModalTestApp(budget)
        async with app.run_test(size=TEST_SIZE) as pilot:
            app.open_modal()
            await pilot.pause()

            modal = app.screen
            # Set valid date and amount first
            date_input = modal.query_one("#input-split-date", Input)
            date_input.value = "2025-06-01"

            duration_input = modal.query_one("#input-duration", Input)
            duration_input.value = "-5"  # Invalid: negative
            await pilot.pause()

            apply_btn = modal.query_one("#btn-apply", Button)
            apply_btn.focus()
            await pilot.press("enter")
            await pilot.pause()

            assert not app.modal_dismissed
            error_msg = modal.query_one("#error-message", Static)
            assert "durée" in str(error_msg.content).lower()


class TestSplitOperationModalSubmission:
    """Tests for successful form submission."""

    @pytest.mark.asyncio
    async def test_cancel_returns_none(self) -> None:
        """Verify cancel button returns None."""
        operation = make_periodic_planned_operation()
        app = SplitModalTestApp(operation)
        async with app.run_test(size=TEST_SIZE) as pilot:
            app.open_modal()
            await pilot.pause()

            modal = app.screen
            cancel_btn = modal.query_one("#btn-cancel", Button)
            cancel_btn.focus()
            await pilot.press("enter")
            await pilot.pause()

            assert app.modal_dismissed
            assert app.modal_result is None

    @pytest.mark.asyncio
    async def test_escape_returns_none(self) -> None:
        """Verify escape key returns None."""
        operation = make_periodic_planned_operation()
        app = SplitModalTestApp(operation)
        async with app.run_test(size=TEST_SIZE) as pilot:
            app.open_modal()
            await pilot.pause()

            await pilot.press("escape")
            await pilot.pause()

            assert app.modal_dismissed
            assert app.modal_result is None

    @pytest.mark.asyncio
    async def test_successful_planned_operation_split(self) -> None:
        """Verify successful split returns correct SplitResult for PlannedOperation."""
        operation = make_periodic_planned_operation(
            initial_date=datetime(2025, 1, 1),
            amount=2500.0,
        )
        app = SplitModalTestApp(operation)
        async with app.run_test(size=TEST_SIZE) as pilot:
            app.open_modal()
            await pilot.pause()

            modal = app.screen
            # Set split date
            date_input = modal.query_one("#input-split-date", Input)
            date_input.value = "2025-06-01"

            # Set new amount
            amount_input = modal.query_one("#input-amount", Input)
            amount_input.value = "3000.0"

            # Period is already set to default (1 month)
            await pilot.pause()

            apply_btn = modal.query_one("#btn-apply", Button)
            apply_btn.focus()
            await pilot.press("enter")
            await pilot.pause()

            assert app.modal_dismissed
            assert app.modal_result is not None
            assert app.modal_result.split_date == datetime(2025, 6, 1)
            assert app.modal_result.new_amount.value == 3000.0
            assert app.modal_result.new_amount.currency == "EUR"
            assert app.modal_result.new_period == relativedelta(months=1)
            assert app.modal_result.new_duration is None  # Not a budget

    @pytest.mark.asyncio
    async def test_successful_budget_split_with_duration(self) -> None:
        """Verify successful split returns correct SplitResult for Budget."""
        budget = make_periodic_budget(
            initial_date=datetime(2025, 1, 1),
            amount=-400.0,
        )
        app = SplitModalTestApp(budget)
        async with app.run_test(size=TEST_SIZE) as pilot:
            app.open_modal()
            await pilot.pause()

            modal = app.screen
            # Set split date
            date_input = modal.query_one("#input-split-date", Input)
            date_input.value = "2025-06-01"

            # Set new amount
            amount_input = modal.query_one("#input-amount", Input)
            amount_input.value = "-500.0"

            # Set new duration
            duration_input = modal.query_one("#input-duration", Input)
            duration_input.value = "2"  # 2 months
            await pilot.pause()

            apply_btn = modal.query_one("#btn-apply", Button)
            apply_btn.focus()
            await pilot.press("enter")
            await pilot.pause()

            assert app.modal_dismissed
            assert app.modal_result is not None
            assert app.modal_result.split_date == datetime(2025, 6, 1)
            assert app.modal_result.new_amount.value == -500.0
            assert app.modal_result.new_duration == relativedelta(months=2)

    @pytest.mark.asyncio
    async def test_period_selection(self) -> None:
        """Verify period selection works correctly."""
        operation = make_periodic_planned_operation()
        app = SplitModalTestApp(operation)
        async with app.run_test(size=TEST_SIZE) as pilot:
            app.open_modal()
            await pilot.pause()

            modal = app.screen
            # Set valid date
            date_input = modal.query_one("#input-split-date", Input)
            date_input.value = "2025-06-01"

            # Change period to quarterly (3 months)
            period_select = modal.query_one("#select-period", Select)
            period_select.value = "3"  # Trimestriel
            await pilot.pause()

            apply_btn = modal.query_one("#btn-apply", Button)
            apply_btn.focus()
            await pilot.press("enter")
            await pilot.pause()

            assert app.modal_dismissed
            assert app.modal_result is not None
            assert app.modal_result.new_period == relativedelta(months=3)
