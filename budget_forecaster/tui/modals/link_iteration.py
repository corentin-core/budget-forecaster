"""Modal for selecting an iteration to link an operation to."""

from datetime import date, timedelta
from typing import Any

from dateutil.relativedelta import relativedelta
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, OptionList, Static
from textual.widgets.option_list import Option

from budget_forecaster.core.date_range import DateRangeInterface
from budget_forecaster.domain.operation.budget import Budget
from budget_forecaster.domain.operation.historic_operation import HistoricOperation
from budget_forecaster.domain.operation.planned_operation import PlannedOperation
from budget_forecaster.services.operation.operation_link_service import (
    compute_match_score,
)


class LinkIterationModal(ModalScreen[date | None]):
    """Modal for selecting an iteration date to link."""

    DEFAULT_CSS = """
    LinkIterationModal {
        align: center middle;
    }

    LinkIterationModal #modal-container {
        width: 70;
        height: 35;
        border: solid $primary;
        background: $surface;
        padding: 1 2;
    }

    LinkIterationModal #modal-title {
        text-style: bold;
        margin-bottom: 1;
        height: 2;
    }

    LinkIterationModal #info-section {
        height: auto;
        margin-bottom: 1;
        padding: 1;
        border: solid $accent;
    }

    LinkIterationModal #op-description {
        height: auto;
        max-height: 2;
    }

    LinkIterationModal #op-details {
        color: $text-muted;
    }

    LinkIterationModal #target-info {
        margin-top: 1;
        text-style: italic;
    }

    LinkIterationModal .amount-positive {
        color: $success;
    }

    LinkIterationModal .amount-negative {
        color: $error;
    }

    LinkIterationModal #nav-row {
        height: 3;
        margin-bottom: 1;
    }

    LinkIterationModal #nav-row Button {
        width: 5;
    }

    LinkIterationModal #date-range {
        width: 1fr;
        text-align: center;
        padding: 0 1;
    }

    LinkIterationModal #list-header {
        height: 1;
        background: $surface-darken-1;
        color: $text-muted;
        text-style: bold;
    }

    LinkIterationModal #iteration-list {
        height: 1fr;
    }

    LinkIterationModal #buttons-row {
        height: 3;
        margin-top: 1;
        dock: bottom;
    }

    LinkIterationModal Button {
        margin-left: 1;
    }
    """

    BINDINGS = [("escape", "cancel", "Annuler")]

    def __init__(
        self,
        operation: HistoricOperation,
        target: PlannedOperation | Budget,
        **kwargs: Any,
    ) -> None:
        """Initialize the modal.

        Args:
            operation: The operation to link.
            target: The target planned operation or budget.
        """
        super().__init__(**kwargs)
        self._operation = operation
        self._target = target
        self._offset_months = 0  # Offset from operation date
        self._selected_date: date | None = None

    @property
    def _window_center(self) -> date:
        """Get the center of the iteration window."""
        return self._operation.operation_date + relativedelta(
            months=self._offset_months
        )

    @property
    def _window_start(self) -> date:
        """Get the start of the iteration window (center - 2 months)."""
        return self._window_center - relativedelta(months=2)

    @property
    def _window_end(self) -> date:
        """Get the end of the iteration window (center + 2 months)."""
        return self._window_center + relativedelta(months=2)

    def compose(self) -> ComposeResult:
        """Create the modal layout."""
        op = self._operation
        amount_class = "amount-negative" if op.amount < 0 else "amount-positive"

        with Vertical(id="modal-container"):
            yield Static("Sélectionner l'itération", id="modal-title")

            # Info section
            with Vertical(id="info-section"):
                yield Static(op.description, id="op-description")
                yield Static(
                    f"{op.operation_date.strftime('%d/%m/%Y')} | {op.amount:+.2f} €",
                    id="op-details",
                    classes=amount_class,
                )
                yield Static(
                    f"→ {self._target.description}",
                    id="target-info",
                )

            # Navigation row
            with Horizontal(id="nav-row"):
                yield Button("<", id="btn-prev")
                yield Static(self._get_date_range_text(), id="date-range")
                yield Button(">", id="btn-next-month")

            # List header
            yield Static("Score  Itération", id="list-header")

            # Iterations list
            yield OptionList(*self._build_iteration_options(), id="iteration-list")

            # Buttons
            with Horizontal(id="buttons-row"):
                yield Button("Annuler", id="btn-cancel", variant="default")
                yield Button("Lier", id="btn-link", variant="primary")

    def _get_date_range_text(self) -> str:
        """Get the display text for the current date range."""
        start = self._window_start
        end = self._window_end
        return f"{start.strftime('%b %Y')} - {end.strftime('%b %Y')}"

    def _build_iteration_options(self) -> list[Option]:
        """Build options for iterations within the current window."""
        options = []

        # Collect iterations within window
        iterations_with_scores: list[tuple[DateRangeInterface, float]] = []

        for iteration in self._target.date_range.iterate_over_date_ranges(
            self._window_start - timedelta(days=31)  # Start a bit earlier
        ):
            iteration_date = iteration.start_date

            # Skip if before window start
            if iteration_date < self._window_start:
                continue

            # Stop if after window end
            if iteration_date > self._window_end:
                break

            score = compute_match_score(
                self._operation,
                self._target,
                iteration_date,
            )
            iterations_with_scores.append((iteration, score))

        # Sort by score descending to highlight best match
        iterations_with_scores.sort(key=lambda x: x[1], reverse=True)

        if not iterations_with_scores:
            # No iterations in window - show message
            options.append(Option("Aucune itération dans cette période", id="empty"))
            return options

        # Pre-select the best match
        best_date = iterations_with_scores[0][0].start_date
        self._selected_date = best_date

        # Sort by date for display
        iterations_with_scores.sort(key=lambda x: x[0].start_date)

        for iteration, score in iterations_with_scores:
            score_str = f"{score:3.0f}%"
            if iteration.start_date == iteration.last_date:
                date_str = iteration.start_date.strftime("%d/%m/%Y")
            else:
                start = iteration.start_date.strftime("%d/%m/%Y")
                end = iteration.last_date.strftime("%d/%m/%Y")
                date_str = f"{start} → {end}"
            label = f"{score_str}  {date_str}"
            option_id = iteration.start_date.strftime("%Y-%m-%d")
            options.append(Option(label, id=option_id))

        return options

    def _refresh_iteration_list(self) -> None:
        """Refresh the iteration list with current window."""
        iteration_list = self.query_one("#iteration-list", OptionList)
        iteration_list.clear_options()
        for option in self._build_iteration_options():
            iteration_list.add_option(option)

        # Update date range display
        date_range = self.query_one("#date-range", Static)
        date_range.update(self._get_date_range_text())

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle iteration selection."""
        if event.option.id is None or event.option.id == "empty":
            return

        try:
            self._selected_date = date.fromisoformat(str(event.option.id))
        except ValueError:
            pass

    def on_option_list_option_highlighted(
        self, event: OptionList.OptionHighlighted
    ) -> None:
        """Handle iteration highlight."""
        if (
            event.option is None
            or event.option.id is None
            or event.option.id == "empty"
        ):
            return

        try:
            self._selected_date = date.fromisoformat(str(event.option.id))
        except ValueError:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-cancel":
            self.dismiss(None)
        elif event.button.id == "btn-prev":
            self._offset_months -= 1
            self._refresh_iteration_list()
        elif event.button.id == "btn-next-month":
            self._offset_months += 1
            self._refresh_iteration_list()
        elif event.button.id == "btn-link":
            if self._selected_date:
                self.dismiss(self._selected_date)
            else:
                self.notify("Veuillez sélectionner une itération", severity="warning")

    def action_cancel(self) -> None:
        """Cancel selection."""
        self.dismiss(None)
