"""Tests for BudgetEditModal validation."""


from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import Button, Input, Select, Static

from budget_forecaster.domain.operation.budget import Budget
from budget_forecaster.tui.modals.budget_edit import BudgetEditModal
from budget_forecaster.tui.modals.duration_input import DurationInput

# Terminal size for tests - large enough to display modal
TEST_SIZE = (100, 50)


def _set_duration_input(modal: object, widget_id: str, value: str, unit: str) -> None:
    """Set value and unit on a DurationInput widget."""
    duration_widget = modal.query_one(f"#{widget_id}", DurationInput)
    duration_widget.query_one(".duration-value", Input).value = value
    duration_widget.query_one(".duration-unit", Select).value = unit


class BudgetEditTestApp(App[None]):
    """Test app for BudgetEditModal."""

    def __init__(self) -> None:
        super().__init__()
        self.modal_result: Budget | None = None
        self.modal_dismissed = False

    def compose(self) -> ComposeResult:
        yield Container()

    def open_modal(self, budget: Budget | None = None) -> None:
        """Open the budget edit modal."""
        self.push_screen(
            BudgetEditModal(budget),
            self._on_modal_closed,
        )

    def _on_modal_closed(self, result: Budget | None) -> None:
        """Track modal result."""
        self.modal_result = result
        self.modal_dismissed = True


async def _fill_and_save_periodic_budget(
    app: App[None],
    pilot: object,
    *,
    start_date: str = "2025-01-01",
    duration: str = "1",
    period: str = "12",
    end_date: str = "",
) -> None:
    """Fill the budget edit form and press save."""
    modal = app.screen
    assert isinstance(modal, BudgetEditModal)

    modal.query_one("#input-description", Input).value = "Test budget"
    modal.query_one("#input-amount", Input).value = "-100"
    modal.query_one("#input-start-date", Input).value = start_date
    _set_duration_input(modal, "input-duration", duration, "months")
    modal.query_one("#select-periodic", Select).value = "yes"
    _set_duration_input(modal, "input-period", period, "months")
    modal.query_one("#input-end-date", Input).value = end_date
    await pilot.pause()

    save_btn = modal.query_one("#btn-save", Button)
    save_btn.focus()
    await pilot.press("enter")
    await pilot.pause()


class TestBudgetEditEndDateValidation:
    """Tests for end date validation on recurring budgets."""

    async def test_accepts_end_date_capturing_single_iteration(self) -> None:
        """A recurring budget ending within its first period keeps one occurrence."""
        app = BudgetEditTestApp()
        async with app.run_test(size=TEST_SIZE) as pilot:
            app.open_modal()
            await pilot.pause()

            await _fill_and_save_periodic_budget(
                app,
                pilot,
                start_date="2025-01-01",
                period="12",
                end_date="2025-06-01",
            )

            assert app.modal_dismissed
            assert app.modal_result is not None

    async def test_rejects_end_date_before_start(self) -> None:
        """End date earlier than the start date is invalid."""
        app = BudgetEditTestApp()
        async with app.run_test(size=TEST_SIZE) as pilot:
            app.open_modal()
            await pilot.pause()

            await _fill_and_save_periodic_budget(
                app,
                pilot,
                start_date="2025-02-09",
                period="12",
                end_date="2025-02-08",
            )

            assert not app.modal_dismissed
            modal = app.screen
            assert isinstance(modal, BudgetEditModal)
            error = modal.query_one("#error-message", Static)
            assert str(error.content) == "End date cannot be before the start date"

    async def test_accepts_end_date_after_second_iteration(self) -> None:
        """End date allowing two iterations is valid."""
        app = BudgetEditTestApp()
        async with app.run_test(size=TEST_SIZE) as pilot:
            app.open_modal()
            await pilot.pause()

            await _fill_and_save_periodic_budget(
                app,
                pilot,
                start_date="2025-01-01",
                period="12",
                end_date="2026-02-01",
            )

            assert app.modal_dismissed
            assert app.modal_result is not None

    async def test_accepts_no_end_date(self) -> None:
        """No end date (indefinite) is always valid."""
        app = BudgetEditTestApp()
        async with app.run_test(size=TEST_SIZE) as pilot:
            app.open_modal()
            await pilot.pause()

            await _fill_and_save_periodic_budget(
                app,
                pilot,
                start_date="2025-01-01",
                period="12",
                end_date="",
            )

            assert app.modal_dismissed
            assert app.modal_result is not None

    async def test_rejects_end_date_on_non_recurring_budget(self) -> None:
        """An end date on a one-time budget is rejected instead of dropped."""
        app = BudgetEditTestApp()
        async with app.run_test(size=TEST_SIZE) as pilot:
            app.open_modal()
            await pilot.pause()

            modal = app.screen
            assert isinstance(modal, BudgetEditModal)
            modal.query_one("#input-description", Input).value = "Test budget"
            modal.query_one("#input-amount", Input).value = "-100"
            modal.query_one("#input-start-date", Input).value = "2025-01-01"
            _set_duration_input(modal, "input-duration", "1", "months")
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
