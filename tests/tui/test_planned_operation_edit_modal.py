"""Tests for PlannedOperationEditModal validation."""


from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import Button, Input, Select, Static

from budget_forecaster.domain.operation.planned_operation import PlannedOperation
from budget_forecaster.tui.modals.duration_input import DurationInput
from budget_forecaster.tui.modals.planned_operation_edit import (
    PlannedOperationEditModal,
)

# Terminal size for tests - large enough to display modal
TEST_SIZE = (100, 50)


def _set_duration_input(modal: object, widget_id: str, value: str, unit: str) -> None:
    """Set value and unit on a DurationInput widget."""
    duration_widget = modal.query_one(f"#{widget_id}", DurationInput)
    duration_widget.query_one(".duration-value", Input).value = value
    duration_widget.query_one(".duration-unit", Select).value = unit


class PlannedOpEditTestApp(App[None]):
    """Test app for PlannedOperationEditModal."""

    def __init__(self) -> None:
        super().__init__()
        self.modal_result: PlannedOperation | None = None
        self.modal_dismissed = False

    def compose(self) -> ComposeResult:
        yield Container()

    def open_modal(self) -> None:
        """Open the planned operation edit modal."""
        self.push_screen(
            PlannedOperationEditModal(),
            self._on_modal_closed,
        )

    def _on_modal_closed(self, result: PlannedOperation | None) -> None:
        """Track modal result."""
        self.modal_result = result
        self.modal_dismissed = True


async def _fill_and_save_periodic_op(
    app: App[None],
    pilot: object,
    *,
    op_date: str = "2025-01-01",
    period: str = "12",
    period_unit: str = "months",
    end_date: str = "",
) -> None:
    """Fill the planned operation edit form and press save."""
    modal = app.screen
    assert isinstance(modal, PlannedOperationEditModal)

    modal.query_one("#input-description", Input).value = "Test op"
    modal.query_one("#input-amount", Input).value = "-100"
    modal.query_one("#input-date", Input).value = op_date
    modal.query_one("#select-periodic", Select).value = "yes"
    _set_duration_input(modal, "input-period", period, period_unit)
    modal.query_one("#input-end-date", Input).value = end_date
    await pilot.pause()

    save_btn = modal.query_one("#btn-save", Button)
    save_btn.focus()
    await pilot.press("enter")
    await pilot.pause()


class TestPlannedOpEditEndDateValidation:
    """Tests for end date validation on recurring planned operations."""

    async def test_accepts_end_date_capturing_single_iteration(self) -> None:
        """A yearly op ending before its second iteration keeps one occurrence."""
        app = PlannedOpEditTestApp()
        async with app.run_test(size=TEST_SIZE) as pilot:
            app.open_modal()
            await pilot.pause()

            await _fill_and_save_periodic_op(
                app,
                pilot,
                op_date="2026-01-19",
                period="1",
                period_unit="years",
                end_date="2027-01-18",
            )

            assert app.modal_dismissed
            assert app.modal_result is not None

    async def test_rejects_end_date_before_start(self) -> None:
        """End date earlier than the start date is invalid."""
        app = PlannedOpEditTestApp()
        async with app.run_test(size=TEST_SIZE) as pilot:
            app.open_modal()
            await pilot.pause()

            await _fill_and_save_periodic_op(
                app,
                pilot,
                op_date="2025-02-09",
                period="12",
                end_date="2025-02-08",
            )

            assert not app.modal_dismissed
            modal = app.screen
            assert isinstance(modal, PlannedOperationEditModal)
            error = modal.query_one("#error-message", Static)
            assert str(error.content) == "End date cannot be before the start date"

    async def test_accepts_end_date_after_second_iteration(self) -> None:
        """End date allowing two iterations is valid."""
        app = PlannedOpEditTestApp()
        async with app.run_test(size=TEST_SIZE) as pilot:
            app.open_modal()
            await pilot.pause()

            await _fill_and_save_periodic_op(
                app,
                pilot,
                op_date="2025-01-01",
                period="12",
                end_date="2026-02-01",
            )

            assert app.modal_dismissed
            assert app.modal_result is not None

    async def test_rejects_end_date_on_non_recurring_op(self) -> None:
        """An end date on a one-time op is rejected instead of silently dropped."""
        app = PlannedOpEditTestApp()
        async with app.run_test(size=TEST_SIZE) as pilot:
            app.open_modal()
            await pilot.pause()

            modal = app.screen
            assert isinstance(modal, PlannedOperationEditModal)
            modal.query_one("#input-description", Input).value = "Test op"
            modal.query_one("#input-amount", Input).value = "-100"
            modal.query_one("#input-date", Input).value = "2025-01-01"
            modal.query_one("#select-periodic", Select).value = "no"
            modal.query_one("#input-end-date", Input).value = "2026-01-01"
            await pilot.pause()

            save_btn = modal.query_one("#btn-save", Button)
            save_btn.focus()
            await pilot.press("enter")
            await pilot.pause()

            assert not app.modal_dismissed
            error = modal.query_one("#error-message", Static)
            assert str(error.content) == "End date only applies to recurring operations"
