"""Planned operation edit modal for creating/editing planned operations."""

# pylint: disable=too-many-locals,too-many-branches,too-many-statements
# pylint: disable=raise-missing-from,no-else-return
# pylint: disable=consider-using-assignment-expr

from datetime import date, datetime, timedelta
from typing import Any

from dateutil.relativedelta import relativedelta
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.time_range import DailyTimeRange, PeriodicDailyTimeRange
from budget_forecaster.core.types import Category
from budget_forecaster.domain.operation.planned_operation import PlannedOperation


class PlannedOperationEditModal(ModalScreen[PlannedOperation | None]):
    """Modal for creating or editing a planned operation."""

    DEFAULT_CSS = """
    PlannedOperationEditModal {
        align: center middle;
    }

    PlannedOperationEditModal #modal-container {
        width: 80;
        height: 45;
        border: solid $primary;
        background: $surface;
        padding: 1 2;
    }

    PlannedOperationEditModal #modal-title {
        text-style: bold;
        margin-bottom: 1;
        height: 2;
    }

    PlannedOperationEditModal #form-scroll {
        height: 1fr;
    }

    PlannedOperationEditModal .form-row {
        height: 3;
        margin-bottom: 1;
    }

    PlannedOperationEditModal .form-label {
        width: 18;
        padding: 0 1;
    }

    PlannedOperationEditModal .form-input {
        width: 1fr;
    }

    PlannedOperationEditModal #buttons-row {
        height: 3;
        margin-top: 1;
        dock: bottom;
    }

    PlannedOperationEditModal Button {
        margin-left: 1;
    }

    PlannedOperationEditModal #error-message {
        color: $error;
        height: 2;
        margin-top: 1;
        dock: bottom;
    }
    """

    BINDINGS = [("escape", "cancel", "Annuler")]

    def __init__(
        self, operation: PlannedOperation | None = None, **kwargs: Any
    ) -> None:
        """Initialize the modal.

        Args:
            operation: Planned operation to edit, or None to create a new one.
        """
        super().__init__(**kwargs)
        self._operation = operation
        self._is_new = operation is None

    def compose(self) -> ComposeResult:
        """Create the modal layout."""
        title = "Nouvelle opération" if self._is_new else "Modifier l'opération"

        with Vertical(id="modal-container"):
            yield Static(title, id="modal-title")

            with VerticalScroll(id="form-scroll"):
                # Description
                with Horizontal(classes="form-row"):
                    yield Label("Description:", classes="form-label")
                    yield Input(
                        value=self._operation.description if self._operation else "",
                        id="input-description",
                        classes="form-input",
                    )

                # Amount
                with Horizontal(classes="form-row"):
                    yield Label("Montant:", classes="form-label")
                    yield Input(
                        value=str(self._operation.amount) if self._operation else "100",
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
                        self._operation.category.name
                        if self._operation
                        else Category.OTHER.name
                    )
                    yield Select(
                        categories,
                        value=current,
                        id="select-category",
                        classes="form-input",
                    )

                # Date
                with Horizontal(classes="form-row"):
                    yield Label("Date:", classes="form-label")
                    start = (
                        self._operation.time_range.initial_date
                        if self._operation
                        else date.today()
                    )
                    yield Input(
                        value=start.strftime("%Y-%m-%d"),
                        id="input-date",
                        placeholder="YYYY-MM-DD",
                        classes="form-input",
                    )

                # Periodic
                with Horizontal(classes="form-row"):
                    yield Label("Récurrent:", classes="form-label")
                    is_periodic = self._operation and isinstance(
                        self._operation.time_range, PeriodicDailyTimeRange
                    )
                    yield Select(
                        [("Non", "no"), ("Oui", "yes")],
                        value="yes" if is_periodic else "no",
                        id="select-periodic",
                        classes="form-input",
                    )

                # Period (months)
                with Horizontal(classes="form-row"):
                    yield Label("Période (mois):", classes="form-label")
                    period = self._get_period_months()
                    yield Input(
                        value=str(period) if period else "",
                        id="input-period",
                        placeholder="Laisser vide si non récurrent",
                        classes="form-input",
                    )

                # End date
                with Horizontal(classes="form-row"):
                    yield Label("Date fin:", classes="form-label")
                    end_date = self._get_end_date()
                    yield Input(
                        value=end_date.strftime("%Y-%m-%d") if end_date else "",
                        id="input-end-date",
                        placeholder="Laisser vide pour indéfini",
                        classes="form-input",
                    )

                # Description hints
                with Horizontal(classes="form-row"):
                    yield Label("Mots-clés:", classes="form-label")
                    hints = self._get_hints()
                    yield Input(
                        value=hints,
                        id="input-hints",
                        placeholder="Séparés par des virgules",
                        classes="form-input",
                    )

                # Approximation days
                with Horizontal(classes="form-row"):
                    yield Label("Tolérance date (j):", classes="form-label")
                    approx_days = self._get_approx_days()
                    yield Input(
                        value=str(approx_days),
                        id="input-approx-days",
                        classes="form-input",
                    )

                # Approximation ratio
                with Horizontal(classes="form-row"):
                    yield Label("Tolérance montant:", classes="form-label")
                    approx_ratio = self._get_approx_ratio()
                    yield Input(
                        value=str(approx_ratio),
                        id="input-approx-ratio",
                        placeholder="Ex: 0.05 pour 5%",
                        classes="form-input",
                    )

            yield Static("", id="error-message")

            # Buttons
            with Horizontal(id="buttons-row"):
                yield Button("Annuler", id="btn-cancel", variant="default")
                yield Button("Enregistrer", id="btn-save", variant="primary")

    def _get_period_months(self) -> int | None:
        """Get the period in months from the current operation."""
        if not self._operation:
            return None
        tr = self._operation.time_range
        if isinstance(tr, PeriodicDailyTimeRange):
            p = tr.period
            if p.months:
                return p.months
            elif p.days:
                return None  # Days, not months
        return None

    def _get_end_date(self) -> date | None:
        """Get the end date from the current operation."""
        if not self._operation:
            return None
        tr = self._operation.time_range
        if isinstance(tr, PeriodicDailyTimeRange):
            if tr.last_date != date.max:
                return tr.last_date
        return None

    def _get_hints(self) -> str:
        """Get description hints as comma-separated string."""
        if not self._operation:
            return ""
        hints = self._operation.matcher.description_hints
        return ", ".join(sorted(hints)) if hints else ""

    def _get_approx_days(self) -> int:
        """Get approximation days from the current operation."""
        if not self._operation:
            return 5
        return int(
            self._operation.matcher.approximation_date_range.total_seconds() / 86400
        )

    def _get_approx_ratio(self) -> float:
        """Get approximation ratio from the current operation."""
        if not self._operation:
            return 0.05
        return self._operation.matcher.approximation_amount_ratio

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-cancel":
            self.dismiss(None)
        elif event.button.id == "btn-save":
            self._save()

    def _save(self) -> None:
        """Validate and save the planned operation."""
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

            date_str = self.query_one("#input-date", Input).value.strip()
            try:
                op_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                raise ValueError("La date doit être au format YYYY-MM-DD")

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

            hints_str = self.query_one("#input-hints", Input).value.strip()
            hints = (
                {h.strip() for h in hints_str.split(",") if h.strip()}
                if hints_str
                else set()
            )

            approx_days_str = self.query_one("#input-approx-days", Input).value.strip()
            try:
                approx_days = int(approx_days_str)
                if approx_days < 0:
                    raise ValueError()
            except ValueError:
                raise ValueError("La tolérance date doit être un nombre entier positif")

            approx_ratio_str = self.query_one(
                "#input-approx-ratio", Input
            ).value.strip()
            try:
                approx_ratio = float(approx_ratio_str)
                if approx_ratio < 0:
                    raise ValueError()
            except ValueError:
                raise ValueError("La tolérance montant doit être un nombre positif")

            # Build time range
            time_range: DailyTimeRange | PeriodicDailyTimeRange
            if is_periodic and period_months:
                time_range = PeriodicDailyTimeRange(
                    op_date,
                    relativedelta(months=period_months),
                    end_date,
                )
            else:
                time_range = DailyTimeRange(op_date)

            # Create operation
            op_id = self._operation.id if self._operation else None
            operation = PlannedOperation(
                record_id=op_id,
                description=description,
                amount=Amount(amount_val, "EUR"),
                category=category,
                time_range=time_range,
            )

            # Set matcher params
            operation.set_matcher_params(
                description_hints=hints,
                approximation_date_range=timedelta(days=approx_days),
                approximation_amount_ratio=approx_ratio,
            )

            self.dismiss(operation)

        except ValueError as e:
            error_widget.update(str(e))

    def action_cancel(self) -> None:
        """Cancel editing."""
        self.dismiss(None)
