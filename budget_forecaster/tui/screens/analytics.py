"""Analytics tab — balance evolution + expense breakdown."""

from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import ContentSwitcher, RadioButton, RadioSet

from budget_forecaster.i18n import _
from budget_forecaster.services.application_service import ApplicationService
from budget_forecaster.tui.screens.balance import BalanceWidget
from budget_forecaster.tui.screens.expense_breakdown import ExpenseBreakdownWidget


class AnalyticsWidget(Vertical):
    """Analytics tab with sub-views: balance evolution and expense breakdown."""

    BINDINGS = [
        Binding("e", "edit_threshold", _("Edit threshold")),
    ]

    DEFAULT_CSS = """
    AnalyticsWidget {
        height: 1fr;
    }

    AnalyticsWidget #analytics-nav {
        height: 3;
        margin: 0 1;
    }

    AnalyticsWidget #analytics-nav RadioSet {
        layout: horizontal;
        height: 3;
    }

    AnalyticsWidget #analytics-content {
        height: 1fr;
    }
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._app_service: ApplicationService | None = None
        self._active_view: str = "balance"

    def compose(self) -> ComposeResult:
        with Vertical(id="analytics-nav"):
            with RadioSet(id="analytics-radio"):
                yield RadioButton(
                    _("Balance evolution"), value=True, id="radio-balance"
                )
                yield RadioButton(_("Expense breakdown"), id="radio-breakdown")
        with ContentSwitcher(id="analytics-content", initial="balance"):
            yield BalanceWidget(id="balance")
            yield ExpenseBreakdownWidget(id="breakdown")

    def set_app_service(self, service: ApplicationService) -> None:
        """Set the application service on both sub-widgets."""
        self._app_service = service
        self.query_one("#balance", BalanceWidget).set_app_service(service)
        self.query_one("#breakdown", ExpenseBreakdownWidget).set_app_service(service)

    def refresh_data(self) -> None:
        """Refresh data for the active sub-view."""
        self.query_one("#balance", BalanceWidget).refresh_data()

    def compute_and_display(self) -> None:
        """Compute and display the active sub-view."""
        if self._active_view == "balance":
            self.query_one("#balance", BalanceWidget).compute_and_display()
        else:
            self.query_one("#breakdown", ExpenseBreakdownWidget).compute_and_display()

    def action_edit_threshold(self) -> None:
        """Delegate threshold edit to the breakdown widget."""
        if self._active_view == "breakdown":
            self.query_one("#breakdown", ExpenseBreakdownWidget).edit_threshold()

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        """Switch between sub-views when radio selection changes."""
        switcher = self.query_one("#analytics-content", ContentSwitcher)
        if event.pressed.id == "radio-balance":
            switcher.current = "balance"
            self._active_view = "balance"
            self.query_one("#balance", BalanceWidget).compute_and_display()
        elif event.pressed.id == "radio-breakdown":
            switcher.current = "breakdown"
            self._active_view = "breakdown"
            self.query_one("#breakdown", ExpenseBreakdownWidget).compute_and_display()
