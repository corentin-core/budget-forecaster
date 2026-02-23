"""Tests for BudgetEditModal validation."""


from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import Button, Input, Select, Static

from budget_forecaster.domain.operation.budget import Budget
from budget_forecaster.tui.modals.budget_edit import BudgetEditModal

# Terminal size for tests - large enough to display modal
TEST_SIZE = (100, 50)


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
    modal.query_one("#input-duration", Input).value = duration
    modal.query_one("#select-periodic", Select).value = "yes"
    modal.query_one("#input-period", Input).value = period
    modal.query_one("#input-end-date", Input).value = end_date
    await pilot.pause()

    save_btn = modal.query_one("#btn-save", Button)
    save_btn.focus()
    await pilot.press("enter")
    await pilot.pause()


class TestBudgetEditEndDateValidation:
    """Tests for end date validation on recurring budgets."""

    async def test_rejects_end_date_equal_to_start(self) -> None:
        """End date equal to start date prevents recurrence."""
        app = BudgetEditTestApp()
        async with app.run_test(size=TEST_SIZE) as pilot:
            app.open_modal()
            await pilot.pause()

            await _fill_and_save_periodic_budget(
                app,
                pilot,
                start_date="2025-02-09",
                period="12",
                end_date="2025-02-09",
            )

            assert not app.modal_dismissed
            modal = app.screen
            assert isinstance(modal, BudgetEditModal)
            error = modal.query_one("#error-message", Static)
            assert str(error.content) == "End date must allow at least two iterations"

    async def test_rejects_end_date_within_first_period(self) -> None:
        """End date before start + period prevents meaningful recurrence."""
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

            assert not app.modal_dismissed
            modal = app.screen
            assert isinstance(modal, BudgetEditModal)
            error = modal.query_one("#error-message", Static)
            assert str(error.content) == "End date must allow at least two iterations"

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
