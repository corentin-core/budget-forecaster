"""Modal for splitting a PlannedOperation or Budget at a date."""

from datetime import datetime
from typing import Any, NamedTuple

from dateutil.relativedelta import relativedelta
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.time_range import PeriodicTimeRange
from budget_forecaster.domain.operation.budget import Budget
from budget_forecaster.domain.operation.planned_operation import PlannedOperation


class SplitResult(NamedTuple):
    """Result of a split operation modal."""

    split_date: datetime
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

    BINDINGS = [("escape", "cancel", "Annuler")]

    def __init__(
        self,
        target: PlannedOperation | Budget,
        default_date: datetime | None = None,
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
            yield Static("Scinder à partir d'une date", id="modal-title")

            # Current info box
            with Vertical(id="current-info"):
                yield Static(self._target.description, id="info-description")
                yield Static(self._format_current_state(), id="info-state")
                yield Static(
                    f"Depuis: {self._target.time_range.initial_date.strftime('%d/%m/%Y')}",
                    id="info-since",
                )

            with VerticalScroll(id="form-scroll"):
                # Split date
                with Horizontal(classes="form-row"):
                    yield Label("Première itération:", classes="form-label")
                    default_date = self._default_date or datetime.now()
                    yield Input(
                        value=default_date.strftime("%Y-%m-%d"),
                        id="input-split-date",
                        placeholder="YYYY-MM-DD",
                        classes="form-input",
                    )
                yield Static(
                    "ⓘ Prochaine itération non actualisée",
                    classes="info-hint",
                )

                yield Static("─" * 40, id="separator")

                # New amount
                with Horizontal(classes="form-row"):
                    yield Label("Montant:", classes="form-label")
                    yield Input(
                        value=str(self._target.amount),
                        id="input-amount",
                        classes="form-input",
                    )

                # New period
                with Horizontal(classes="form-row"):
                    yield Label("Période:", classes="form-label")
                    period_options = [
                        ("Mensuel", "1"),
                        ("Bimestriel", "2"),
                        ("Trimestriel", "3"),
                        ("Semestriel", "6"),
                        ("Annuel", "12"),
                    ]
                    current_period = self._get_period_months()
                    yield Select(
                        period_options,
                        value=str(current_period),
                        id="select-period",
                        classes="form-input",
                    )

                # Duration (only for budgets)
                hidden_class = "" if self._is_budget else "hidden"
                with Horizontal(classes=f"form-row {hidden_class}"):
                    yield Label("Durée (mois):", classes="form-label")
                    duration = self._get_duration_months() if self._is_budget else 1
                    yield Input(
                        value=str(duration),
                        id="input-duration",
                        classes="form-input",
                    )

            yield Static("", id="error-message")

            # Buttons
            with Horizontal(id="buttons-row"):
                yield Button("Annuler", id="btn-cancel", variant="default")
                yield Button("Appliquer", id="btn-apply", variant="primary")

    def _format_current_state(self) -> str:
        """Format the current state for display."""
        amount = f"{self._target.amount:+.2f} €"
        period = self._format_period()

        if self._is_budget:
            duration = self._get_duration_months()
            return f"Actuellement: {amount} / {duration} mois, {period}"
        return f"Actuellement: {amount} {period}"

    def _format_period(self) -> str:
        """Format the period for display."""
        months = self._get_period_months()
        period_names = {
            1: "mensuel",
            2: "bimestriel",
            3: "trimestriel",
            6: "semestriel",
            12: "annuel",
        }
        return period_names.get(months, f"tous les {months} mois")

    def _get_period_months(self) -> int:
        """Get the period in months from the current target."""
        tr = self._target.time_range
        if isinstance(tr, PeriodicTimeRange):
            p = tr.period
            if p.months:
                return p.months
            if p.years:
                return p.years * 12
        return 1

    def _get_duration_months(self) -> int:
        """Get the duration in months (for budgets)."""
        tr = self._target.time_range
        if isinstance(tr, PeriodicTimeRange):
            d = tr.duration
            if d.months:
                return d.months
            if d.years:
                return d.years * 12
        return 1

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
                split_date = datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError as exc:
                raise ValueError("La date doit être au format YYYY-MM-DD") from exc

            # Validate split date is after initial date
            if split_date <= self._target.time_range.initial_date:
                raise ValueError("La date doit être après la première itération")

            # Validate amount
            amount_str = self.query_one("#input-amount", Input).value.strip()
            try:
                amount_val = float(amount_str)
            except ValueError as exc:
                raise ValueError("Le montant doit être un nombre") from exc

            # Get period
            period_select = self.query_one("#select-period", Select)
            if period_select.value == Select.BLANK:
                raise ValueError("La période est requise")
            period_months = int(str(period_select.value))
            new_period = relativedelta(months=period_months)

            # Get duration (for budgets)
            new_duration: relativedelta | None = None
            if self._is_budget:
                duration_str = self.query_one("#input-duration", Input).value.strip()
                try:
                    if (duration_months := int(duration_str)) <= 0:
                        raise ValueError("must be positive")
                    new_duration = relativedelta(months=duration_months)
                except ValueError as exc:
                    raise ValueError(
                        "La durée doit être un nombre entier positif"
                    ) from exc

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
