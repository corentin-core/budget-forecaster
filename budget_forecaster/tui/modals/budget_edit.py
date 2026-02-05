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
from budget_forecaster.core.time_range import PeriodicTimeRange, TimeRange
from budget_forecaster.core.types import Category
from budget_forecaster.domain.operation.budget import Budget


class BudgetEditModal(ModalScreen[Budget | None]):
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

    BINDINGS = [("escape", "cancel", "Annuler")]

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
        title = "Nouveau budget" if self._is_new else "Modifier le budget"

        with Vertical(id="modal-container"):
            yield Static(title, id="modal-title")

            with VerticalScroll(id="form-scroll"):
                # Description
                with Horizontal(classes="form-row"):
                    yield Label("Description:", classes="form-label")
                    yield Input(
                        value=self._budget.description if self._budget else "",
                        id="input-description",
                        classes="form-input",
                    )

                # Amount
                with Horizontal(classes="form-row"):
                    yield Label("Montant:", classes="form-label")
                    yield Input(
                        value=str(self._budget.amount) if self._budget else "-100",
                        id="input-amount",
                        classes="form-input",
                    )

                # Category
                with Horizontal(classes="form-row"):
                    yield Label("Catégorie:", classes="form-label")
                    categories = [
                        (cat.value, cat.name)
                        for cat in sorted(Category, key=lambda c: c.value)
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
                    yield Label("Date début:", classes="form-label")
                    start = (
                        self._budget.time_range.initial_date
                        if self._budget
                        else date.today()
                    )
                    yield Input(
                        value=start.strftime("%Y-%m-%d"),
                        id="input-start-date",
                        placeholder="YYYY-MM-DD",
                        classes="form-input",
                    )

                # Duration (months)
                with Horizontal(classes="form-row"):
                    yield Label("Durée (mois):", classes="form-label")
                    duration = self._get_duration_months()
                    yield Input(
                        value=str(duration),
                        id="input-duration",
                        classes="form-input",
                    )

                # Periodic checkbox and period
                with Horizontal(classes="form-row"):
                    yield Label("Récurrent:", classes="form-label")
                    is_periodic = self._budget and isinstance(
                        self._budget.time_range, PeriodicTimeRange
                    )
                    yield Select(
                        [("Non", "no"), ("Oui", "yes")],
                        value="yes" if is_periodic else "no",
                        id="select-periodic",
                        classes="form-input",
                    )

                with Horizontal(classes="form-row"):
                    yield Label("Période (mois):", classes="form-label")
                    period = self._get_period_months()
                    yield Input(
                        value=str(period) if period else "",
                        id="input-period",
                        placeholder="Laisser vide si non récurrent",
                        classes="form-input",
                    )

                # End date (for periodic)
                with Horizontal(classes="form-row"):
                    yield Label("Date fin:", classes="form-label")
                    end_date = self._get_end_date()
                    yield Input(
                        value=end_date.strftime("%Y-%m-%d") if end_date else "",
                        id="input-end-date",
                        placeholder="Laisser vide pour indéfini",
                        classes="form-input",
                    )

            yield Static("", id="error-message")

            # Buttons
            with Horizontal(id="buttons-row"):
                yield Button("Annuler", id="btn-cancel", variant="default")
                yield Button("Enregistrer", id="btn-save", variant="primary")

    def _get_duration_months(self) -> int:
        """Get the duration in months from the current budget."""
        if not self._budget:
            return 1
        tr = self._budget.time_range
        rd = tr.duration
        return rd.months if rd.months else 1

    def _get_period_months(self) -> int | None:
        """Get the period in months from the current budget."""
        if not self._budget:
            return None
        tr = self._budget.time_range
        if isinstance(tr, PeriodicTimeRange):
            return tr.period.months if tr.period.months else 1
        return None

    def _get_end_date(self) -> date | None:
        """Get the end date from the current budget."""
        if not self._budget:
            return None
        tr = self._budget.time_range
        if isinstance(tr, PeriodicTimeRange):
            if tr.last_date != date.max:
                return tr.last_date
        return None

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-cancel":
            self.dismiss(None)
        elif event.button.id == "btn-save":
            self._save()

    def _save(self) -> None:
        """Validate and save the budget."""
        error_widget = self.query_one("#error-message", Static)
        error_widget.update("")

        try:
            # Get values
            description = self.query_one("#input-description", Input).value.strip()
            if not description:
                raise ValueError("La description est requise")

            amount_str = self.query_one("#input-amount", Input).value.strip()
            try:
                amount_val = float(amount_str)
            except ValueError:
                raise ValueError("Le montant doit être un nombre")

            category_select = self.query_one("#select-category", Select)
            if category_select.value == Select.BLANK:
                raise ValueError("La catégorie est requise")
            try:
                category = Category[str(category_select.value)]
            except KeyError:
                raise ValueError("Catégorie invalide")

            start_str = self.query_one("#input-start-date", Input).value.strip()
            try:
                start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
            except ValueError:
                raise ValueError("La date de début doit être au format YYYY-MM-DD")

            duration_str = self.query_one("#input-duration", Input).value.strip()
            try:
                duration_months = int(duration_str)
                if duration_months <= 0:
                    raise ValueError()
            except ValueError:
                raise ValueError("La durée doit être un nombre entier positif")

            is_periodic = self.query_one("#select-periodic", Select).value == "yes"

            period_str = self.query_one("#input-period", Input).value.strip()
            period_months = None
            if period_str:
                try:
                    period_months = int(period_str)
                    if period_months <= 0:
                        raise ValueError()
                except ValueError:
                    raise ValueError("La période doit être un nombre entier positif")

            end_str = self.query_one("#input-end-date", Input).value.strip()
            end_date = None
            if end_str:
                try:
                    end_date = datetime.strptime(end_str, "%Y-%m-%d").date()
                except ValueError:
                    raise ValueError("La date de fin doit être au format YYYY-MM-DD")

            # Build time range
            inner_range = TimeRange(start_date, relativedelta(months=duration_months))

            time_range: TimeRange | PeriodicTimeRange
            if is_periodic and period_months:
                time_range = PeriodicTimeRange(
                    inner_range,
                    relativedelta(months=period_months),
                    end_date,
                )
            else:
                time_range = inner_range

            # Create budget
            budget_id = self._budget.id if self._budget else None
            budget = Budget(
                record_id=budget_id,
                description=description,
                amount=Amount(amount_val, "EUR"),
                category=category,
                time_range=time_range,
            )

            self.dismiss(budget)

        except ValueError as e:
            error_widget.update(str(e))

    def action_cancel(self) -> None:
        """Cancel editing."""
        self.dismiss(None)
