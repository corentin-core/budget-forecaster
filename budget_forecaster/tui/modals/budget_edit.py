"""Budget edit modal for creating/editing budgets."""

# pylint: disable=too-many-locals,too-many-branches,too-many-statements
# pylint: disable=raise-missing-from,consider-using-assignment-expr

from datetime import date, datetime
from typing import Any

from dateutil.relativedelta import relativedelta
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.date_range import DateRange, RecurringDateRange
from budget_forecaster.core.types import Category
from budget_forecaster.domain.operation.budget import Budget
from budget_forecaster.i18n import _
from budget_forecaster.tui.modals.duration_input import DurationInput
from budget_forecaster.tui.modals.edit_actions import EditAction


class BudgetEditModal(ModalScreen[Budget | EditAction | None]):
    """Modal for creating or editing a budget."""

    DEFAULT_CSS = """
    BudgetEditModal {
        align: center middle;
    }

    BudgetEditModal #modal-container {
        width: 80;
        height: 40;
        border: solid $primary;
        background: $surface;
        padding: 1 2;
    }

    BudgetEditModal #modal-title {
        text-style: bold;
        margin-bottom: 1;
        height: 2;
    }

    BudgetEditModal #form-scroll {
        height: 1fr;
    }

    BudgetEditModal .form-row {
        height: 3;
        margin-bottom: 1;
    }

    BudgetEditModal .form-label {
        width: 15;
        padding: 0 1;
    }

    BudgetEditModal .form-input {
        width: 1fr;
    }

    BudgetEditModal #buttons-row {
        height: 3;
        margin-top: 1;
        dock: bottom;
    }

    BudgetEditModal Button {
        margin-left: 1;
    }

    BudgetEditModal #error-message {
        color: $error;
        height: 2;
        margin-top: 1;
        dock: bottom;
    }
    """

    BINDINGS = [("escape", "cancel", _("Cancel"))]

    def __init__(self, budget: Budget | None = None, **kwargs: Any) -> None:
        """Initialize the modal.

        Args:
            budget: Budget to edit, or None to create a new one.
        """
        super().__init__(**kwargs)
        self._budget = budget
        self._is_new = budget is None

    def compose(self) -> ComposeResult:
        """Create the modal layout."""
        title = _("New budget") if self._is_new else _("Edit budget")

        with Vertical(id="modal-container"):
            yield Static(title, id="modal-title")

            with VerticalScroll(id="form-scroll"):
                # Description
                with Horizontal(classes="form-row"):
                    yield Label(_("Description:"), classes="form-label")
                    yield Input(
                        value=self._budget.description if self._budget else "",
                        id="input-description",
                        classes="form-input",
                    )

                # Amount
                with Horizontal(classes="form-row"):
                    yield Label(_("Amount:"), classes="form-label")
                    yield Input(
                        value=str(self._budget.amount) if self._budget else "-100",
                        id="input-amount",
                        classes="form-input",
                    )

                # Category
                with Horizontal(classes="form-row"):
                    yield Label(_("Category:"), classes="form-label")
                    categories = [
                        (cat.display_name, cat.name)
                        for cat in sorted(Category, key=lambda c: c.display_name)
                    ]
                    current = (
                        self._budget.category.name
                        if self._budget
                        else Category.OTHER.name
                    )
                    yield Select(
                        categories,
                        value=current,
                        id="select-category",
                        classes="form-input",
                    )

                # Start date
                with Horizontal(classes="form-row"):
                    yield Label(_("Start date:"), classes="form-label")
                    start = (
                        self._budget.date_range.start_date
                        if self._budget
                        else date.today()
                    )
                    yield Input(
                        value=start.strftime("%Y-%m-%d"),
                        id="input-start-date",
                        placeholder="YYYY-MM-DD",
                        classes="form-input",
                    )

                # Duration
                with Horizontal(classes="form-row"):
                    yield Label(_("Duration:"), classes="form-label")
                    duration = self._get_duration()
                    yield DurationInput(
                        duration,
                        id="input-duration",
                        classes="form-input",
                    )

                # Periodic checkbox and period
                with Horizontal(classes="form-row"):
                    yield Label(_("Recurring:"), classes="form-label")
                    is_periodic = self._budget and isinstance(
                        self._budget.date_range, RecurringDateRange
                    )
                    yield Select(
                        [(_("No"), "no"), (_("Yes"), "yes")],
                        value="yes" if is_periodic else "no",
                        id="select-periodic",
                        classes="form-input",
                    )

                with Horizontal(classes="form-row"):
                    yield Label(_("Period:"), classes="form-label")
                    period = self._get_period()
                    yield DurationInput(
                        period,
                        id="input-period",
                        classes="form-input",
                    )

                # End date (for periodic)
                with Horizontal(classes="form-row"):
                    yield Label(_("End date:"), classes="form-label")
                    end_date = self._get_end_date()
                    yield Input(
                        value=end_date.strftime("%Y-%m-%d") if end_date else "",
                        id="input-end-date",
                        placeholder=_("Leave empty for indefinite"),
                        classes="form-input",
                    )

            yield Static("", id="error-message")

            # Buttons
            with Horizontal(id="buttons-row"):
                yield Button(_("Cancel"), id="btn-cancel", variant="default")
                if not self._is_new:
                    yield Button(
                        _("Delete"),
                        id="btn-delete",
                        variant="error",
                    )
                    yield Button(
                        _("Split"),
                        id="btn-split",
                        variant="warning",
                        disabled=not self._can_split,
                    )
                yield Button(_("Save"), id="btn-save", variant="primary")

    @property
    def _can_split(self) -> bool:
        """Check if the budget can be split (existing + periodic)."""
        return (
            self._budget is not None
            and self._budget.id is not None
            and isinstance(self._budget.date_range, RecurringDateRange)
        )

    def _get_duration(self) -> relativedelta | None:
        """Get the duration from the current budget."""
        if not self._budget:
            return None
        return self._budget.date_range.duration

    def _get_period(self) -> relativedelta | None:
        """Get the period from the current budget."""
        if not self._budget:
            return None
        tr = self._budget.date_range
        if isinstance(tr, RecurringDateRange):
            return tr.period
        return None

    def _get_end_date(self) -> date | None:
        """Get the end date from the current budget."""
        if not self._budget:
            return None
        tr = self._budget.date_range
        if isinstance(tr, RecurringDateRange):
            if tr.last_date != date.max:
                return tr.last_date
        return None

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-cancel":
            self.dismiss(None)
        elif event.button.id == "btn-save":
            self._save()
        elif event.button.id == "btn-split":
            self.dismiss(EditAction.SPLIT)
        elif event.button.id == "btn-delete":
            self.dismiss(EditAction.DELETE)

    def _save(self) -> None:
        """Validate and save the budget."""
        error_widget = self.query_one("#error-message", Static)
        error_widget.update("")

        try:
            # Get values
            description = self.query_one("#input-description", Input).value.strip()
            if not description:
                raise ValueError(_("Description is required"))

            amount_str = self.query_one("#input-amount", Input).value.strip()
            try:
                amount_val = float(amount_str)
            except ValueError:
                raise ValueError(_("Amount must be a number"))

            category_select = self.query_one("#select-category", Select)
            if category_select.value == Select.BLANK:
                raise ValueError(_("Category is required"))
            try:
                category = Category[str(category_select.value)]
            except KeyError:
                raise ValueError(_("Invalid category"))

            start_str = self.query_one("#input-start-date", Input).value.strip()
            try:
                start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
            except ValueError:
                raise ValueError(_("Start date must be in YYYY-MM-DD format"))

            duration_rd = self.query_one("#input-duration", DurationInput).duration

            is_periodic = self.query_one("#select-periodic", Select).value == "yes"

            period_rd: relativedelta | None = None
            if is_periodic:
                period_rd = self.query_one("#input-period", DurationInput).duration

            end_str = self.query_one("#input-end-date", Input).value.strip()
            end_date = None
            if end_str:
                try:
                    end_date = datetime.strptime(end_str, "%Y-%m-%d").date()
                except ValueError:
                    raise ValueError(_("End date must be in YYYY-MM-DD format"))

            # Build date range
            inner_range = DateRange(start_date, duration_rd)

            dr: DateRange | RecurringDateRange
            if is_periodic and period_rd:
                if end_date is not None and end_date < start_date + period_rd:
                    raise ValueError(_("End date must allow at least two iterations"))
                dr = RecurringDateRange(
                    inner_range,
                    period_rd,
                    end_date,
                )
            else:
                dr = inner_range

            # Create budget
            budget_id = self._budget.id if self._budget else None
            budget = Budget(
                record_id=budget_id,
                description=description,
                amount=Amount(amount_val, "EUR"),
                category=category,
                date_range=dr,
            )

            self.dismiss(budget)

        except ValueError as e:
            error_widget.update(str(e))

    def action_cancel(self) -> None:
        """Cancel editing."""
        self.dismiss(None)
