"""Modal for splitting a PlannedOperation or Budget at a date."""

from datetime import date, datetime
from typing import Any, NamedTuple

from dateutil.relativedelta import relativedelta
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.date_range import RecurringDateRange
from budget_forecaster.domain.operation.budget import Budget
from budget_forecaster.domain.operation.planned_operation import PlannedOperation
from budget_forecaster.i18n import _, ngettext
from budget_forecaster.tui.modals.duration_input import DurationInput
from budget_forecaster.tui.symbols import DisplaySymbol


def _format_relativedelta(rd: relativedelta) -> str:
    """Format a relativedelta for user-facing display."""
    if rd.years and rd.years > 0:
        return ngettext("{} year", "{} years", rd.years).format(rd.years)
    if rd.months and rd.months > 0:
        return ngettext("{} month", "{} months", rd.months).format(rd.months)
    if not rd.days or rd.days <= 0:
        return ngettext("{} month", "{} months", 1).format(1)
    if rd.days % 7 != 0:
        return ngettext("{} day", "{} days", rd.days).format(rd.days)
    weeks = rd.days // 7
    return ngettext("{} week", "{} weeks", weeks).format(weeks)


class SplitResult(NamedTuple):
    """Result of a split operation modal."""

    split_date: date
    new_amount: Amount
    new_period: relativedelta
    new_duration: relativedelta | None = None  # Only for budgets


class SplitOperationModal(ModalScreen[SplitResult | None]):
    """Modal for splitting a PlannedOperation or Budget at a date.

    This modal allows users to specify:
    - The date from which the new values apply
    - New amount
    - New period
    - New duration (for budgets only)
    """

    DEFAULT_CSS = """
    SplitOperationModal {
        align: center middle;
    }

    SplitOperationModal #modal-container {
        width: 70;
        height: auto;
        max-height: 45;
        border: solid $primary;
        background: $surface;
        padding: 1 2;
    }

    SplitOperationModal #modal-title {
        text-style: bold;
        margin-bottom: 1;
        height: 2;
    }

    SplitOperationModal #current-info {
        border: dashed $primary-darken-2;
        padding: 1;
        margin-bottom: 1;
        height: auto;
    }

    SplitOperationModal #current-info Static {
        height: 1;
    }

    SplitOperationModal #form-scroll {
        height: auto;
        max-height: 20;
    }

    SplitOperationModal .form-row {
        height: 3;
        margin-bottom: 1;
    }

    SplitOperationModal .form-label {
        width: 20;
        padding: 0 1;
    }

    SplitOperationModal .form-input {
        width: 1fr;
    }

    SplitOperationModal .info-hint {
        color: $text-muted;
        height: 1;
        margin-left: 21;
        margin-bottom: 1;
    }

    SplitOperationModal #separator {
        margin: 1 0;
        height: 1;
        color: $text-muted;
    }

    SplitOperationModal #buttons-row {
        height: 3;
        margin-top: 1;
    }

    SplitOperationModal Button {
        margin-left: 1;
    }

    SplitOperationModal #error-message {
        color: $error;
        height: 2;
        margin-top: 1;
    }

    SplitOperationModal .hidden {
        display: none;
    }
    """

    BINDINGS = [("escape", "cancel", _("Cancel"))]

    def __init__(
        self,
        target: PlannedOperation | Budget,
        default_date: date | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the modal.

        Args:
            target: The PlannedOperation or Budget to split.
            default_date: Default split date (if None, uses next non-actualized).
        """
        super().__init__(**kwargs)
        self._target = target
        self._default_date = default_date
        self._is_budget = isinstance(target, Budget)

    def compose(self) -> ComposeResult:
        """Create the modal layout."""
        with Vertical(id="modal-container"):
            yield Static(_("Split from a date"), id="modal-title")

            # Current info box
            with Vertical(id="current-info"):
                yield Static(self._target.description, id="info-description")
                yield Static(self._format_current_state(), id="info-state")
                yield Static(
                    _("Since: {}").format(
                        self._target.date_range.start_date.strftime("%d/%m/%Y")
                    ),
                    id="info-since",
                )

            with VerticalScroll(id="form-scroll"):
                # Split date
                with Horizontal(classes="form-row"):
                    yield Label(_("First iteration:"), classes="form-label")
                    default_date = self._default_date or date.today()
                    yield Input(
                        value=default_date.strftime("%Y-%m-%d"),
                        id="input-split-date",
                        placeholder="YYYY-MM-DD",
                        classes="form-input",
                    )
                yield Static(
                    _("ⓘ Next unadjusted iteration"),
                    classes="info-hint",
                )

                yield Static(DisplaySymbol.SEPARATOR * 40, id="separator")

                # New amount
                with Horizontal(classes="form-row"):
                    yield Label(_("Amount:"), classes="form-label")
                    yield Input(
                        value=str(self._target.amount),
                        id="input-amount",
                        classes="form-input",
                    )

                # New period
                with Horizontal(classes="form-row"):
                    yield Label(_("Period:"), classes="form-label")
                    yield DurationInput(
                        self._get_period(),
                        id="input-period",
                        classes="form-input",
                    )

                # Duration (only for budgets)
                hidden_class = "" if self._is_budget else "hidden"
                with Horizontal(classes=f"form-row {hidden_class}"):
                    yield Label(_("Duration:"), classes="form-label")
                    duration = self._get_duration() if self._is_budget else None
                    yield DurationInput(
                        duration,
                        id="input-duration",
                        classes="form-input",
                    )

            yield Static("", id="error-message")

            # Buttons
            with Horizontal(id="buttons-row"):
                yield Button(_("Cancel"), id="btn-cancel", variant="default")
                yield Button(_("Apply"), id="btn-apply", variant="primary")

    def _format_current_state(self) -> str:
        """Format the current state for display."""
        amount = f"{self._target.amount:+.2f} {DisplaySymbol.EURO}"
        period = self._format_period()

        if self._is_budget:
            duration = self._format_duration()
            return _("Currently: {} / {}, {}").format(amount, duration, period)
        return _("Currently: {} {}").format(amount, period)

    def _format_period(self) -> str:
        """Format the period for display."""
        tr = self._target.date_range
        if isinstance(tr, RecurringDateRange):
            return _format_relativedelta(tr.period)
        return _format_relativedelta(relativedelta(months=1))

    def _format_duration(self) -> str:
        """Format the duration for display (budgets only)."""
        tr = self._target.date_range
        return _format_relativedelta(tr.duration)

    def _get_period(self) -> relativedelta | None:
        """Get the period from the current target."""
        tr = self._target.date_range
        if isinstance(tr, RecurringDateRange):
            return tr.period
        return None

    def _get_duration(self) -> relativedelta | None:
        """Get the duration from the current target (budgets only)."""
        tr = self._target.date_range
        return tr.duration

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-cancel":
            self.dismiss(None)
        elif event.button.id == "btn-apply":
            self._apply()

    def _apply(self) -> None:
        """Validate and return the split result."""
        error_widget = self.query_one("#error-message", Static)
        error_widget.update("")

        try:
            # Validate split date
            date_str = self.query_one("#input-split-date", Input).value.strip()
            try:
                split_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError as exc:
                raise ValueError(_("Date must be in YYYY-MM-DD format")) from exc

            # Validate split date is after initial date
            if split_date <= self._target.date_range.start_date:
                raise ValueError(_("Date must be after first iteration"))

            # Validate amount
            amount_str = self.query_one("#input-amount", Input).value.strip()
            try:
                amount_val = float(amount_str)
            except ValueError as exc:
                raise ValueError(_("Amount must be a number")) from exc

            # Get period
            new_period = self.query_one("#input-period", DurationInput).duration

            # Get duration (for budgets)
            new_duration: relativedelta | None = None
            if self._is_budget:
                new_duration = self.query_one("#input-duration", DurationInput).duration

            result = SplitResult(
                split_date=split_date,
                new_amount=Amount(amount_val, self._target.currency),
                new_period=new_period,
                new_duration=new_duration,
            )
            self.dismiss(result)

        except ValueError as e:
            error_widget.update(str(e))

    def action_cancel(self) -> None:
        """Cancel the operation."""
        self.dismiss(None)
