"""Modal for selecting a link target (planned operation or budget)."""

from datetime import timedelta
from typing import Any, Literal

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, OptionList, Static
from textual.widgets.option_list import Option

from budget_forecaster.operation_range.budget import Budget
from budget_forecaster.operation_range.historic_operation import HistoricOperation
from budget_forecaster.operation_range.operation_link import OperationLink
from budget_forecaster.operation_range.planned_operation import PlannedOperation
from budget_forecaster.services.operation_link_service import compute_match_score


class LinkTargetModal(
    ModalScreen[PlannedOperation | Budget | Literal["unlink"] | None]
):
    """Modal for selecting a link target (planned operation or budget)."""

    DEFAULT_CSS = """
    LinkTargetModal {
        align: center middle;
    }

    LinkTargetModal #modal-container {
        width: 90;
        height: 40;
        border: solid $primary;
        background: $surface;
        padding: 1 2;
    }

    LinkTargetModal #modal-title {
        text-style: bold;
        margin-bottom: 1;
        height: 2;
    }

    LinkTargetModal #op-info {
        height: auto;
        margin-bottom: 1;
        padding: 1;
        border: solid $accent;
    }

    LinkTargetModal #op-description {
        height: auto;
        max-height: 3;
    }

    LinkTargetModal #op-details {
        color: $text-muted;
    }

    LinkTargetModal .amount-positive {
        color: $success;
    }

    LinkTargetModal .amount-negative {
        color: $error;
    }

    LinkTargetModal #current-link-info {
        height: auto;
        margin-bottom: 1;
        padding: 1;
        border: solid $warning;
        background: $surface-darken-1;
    }

    LinkTargetModal #current-link-info.hidden {
        display: none;
    }

    LinkTargetModal #lists-container {
        height: 1fr;
    }

    LinkTargetModal .list-section {
        width: 1fr;
        height: 100%;
        margin: 0 1;
    }

    LinkTargetModal .section-title {
        text-style: bold;
        height: 2;
    }

    LinkTargetModal OptionList {
        height: 1fr;
    }

    LinkTargetModal #buttons-row {
        height: 3;
        margin-top: 1;
        dock: bottom;
    }

    LinkTargetModal Button {
        margin-left: 1;
    }

    LinkTargetModal #btn-unlink {
        background: $error;
    }
    """

    BINDINGS = [("escape", "cancel", "Annuler")]

    def __init__(
        self,
        operation: HistoricOperation,
        current_link: OperationLink | None,
        planned_operations: list[PlannedOperation],
        budgets: list[Budget],
        **kwargs: Any,
    ) -> None:
        """Initialize the modal.

        Args:
            operation: The operation to link.
            current_link: The current link if any.
            planned_operations: List of available planned operations.
            budgets: List of available budgets.
        """
        super().__init__(**kwargs)
        self._operation = operation
        self._current_link = current_link
        self._planned_operations = planned_operations
        self._budgets = budgets
        self._selected_target: PlannedOperation | Budget | None = None

        # Pre-compute scores for all targets
        self._planned_op_scores: dict[int, float] = {}
        self._budget_scores: dict[int, float] = {}
        self._compute_all_scores()

    def _compute_all_scores(self) -> None:
        """Compute best match scores for all targets."""
        for planned_op in self._planned_operations:
            if planned_op.id is not None:
                score = self._compute_best_score(planned_op)
                self._planned_op_scores[planned_op.id] = score

        for budget in self._budgets:
            if budget.id is not None:
                score = self._compute_best_score(budget)
                self._budget_scores[budget.id] = score

    def _compute_best_score(self, target: PlannedOperation | Budget) -> float:
        """Compute the best score across all iterations of a target.

        Args:
            target: The planned operation or budget.

        Returns:
            The best match score (0-100).
        """
        best_score = 0.0

        # Get iterations within a reasonable window around the operation date
        from_date = self._operation.date - timedelta(days=60)
        for iteration in target.time_range.iterate_over_time_ranges(from_date):
            # Stop if iteration is too far in the future
            if iteration.initial_date > self._operation.date + timedelta(days=60):
                break

            score = compute_match_score(
                self._operation,
                target,
                iteration.initial_date,
            )
            best_score = max(best_score, score)

        return best_score

    def compose(self) -> ComposeResult:
        """Create the modal layout."""
        op = self._operation
        amount_class = "amount-negative" if op.amount < 0 else "amount-positive"

        with Vertical(id="modal-container"):
            yield Static("Lier l'opération", id="modal-title")

            # Operation info
            with Vertical(id="op-info"):
                yield Static(op.description, id="op-description")
                yield Static(
                    f"{op.date.strftime('%d/%m/%Y')} | {op.amount:+.2f} €",
                    id="op-details",
                    classes=amount_class,
                )

            # Current link info (hidden if not linked)
            current_link_class = "" if self._current_link else "hidden"
            with Vertical(id="current-link-info", classes=current_link_class):
                link_text = "Liaison actuelle: "
                if self._current_link:
                    target_type = self._current_link.target_type.value
                    link_text += f"{target_type} #{self._current_link.target_id}"
                yield Static(link_text, id="current-link-text")
                yield Button("Délier", id="btn-unlink", variant="error")

            # Lists container
            with Horizontal(id="lists-container"):
                # Planned operations section
                with Vertical(classes="list-section"):
                    yield Static("Opérations planifiées:", classes="section-title")
                    planned_options = self._build_planned_options()
                    yield OptionList(*planned_options, id="planned-list")

                # Budgets section
                with Vertical(classes="list-section"):
                    yield Static("Budgets:", classes="section-title")
                    budget_options = self._build_budget_options()
                    yield OptionList(*budget_options, id="budget-list")

            # Buttons
            with Horizontal(id="buttons-row"):
                yield Button("Annuler", id="btn-cancel", variant="default")
                yield Button("Suivant", id="btn-next", variant="primary")

    def _build_planned_options(self) -> list[Option]:
        """Build options for planned operations list."""
        options = []

        # Sort by score descending
        sorted_ops = sorted(
            self._planned_operations,
            key=lambda op: self._planned_op_scores.get(op.id or 0, 0),
            reverse=True,
        )

        for planned_op in sorted_ops:
            if planned_op.id is None:
                continue
            score = self._planned_op_scores.get(planned_op.id, 0)
            score_str = f"{score:.0f}%" if score > 0 else "-"
            label = f"[{score_str:>4}] {planned_op.description[:40]}"
            options.append(Option(label, id=f"planned_{planned_op.id}"))

        return options

    def _build_budget_options(self) -> list[Option]:
        """Build options for budgets list."""
        options = []

        # Sort by score descending
        sorted_budgets = sorted(
            self._budgets,
            key=lambda b: self._budget_scores.get(b.id or 0, 0),
            reverse=True,
        )

        for budget in sorted_budgets:
            if budget.id is None:
                continue
            score = self._budget_scores.get(budget.id, 0)
            score_str = f"{score:.0f}%" if score > 0 else "-"
            label = f"[{score_str:>4}] {budget.description[:40]}"
            options.append(Option(label, id=f"budget_{budget.id}"))

        return options

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle option selection in either list."""
        if event.option.id is None:
            return

        option_id = str(event.option.id)
        if option_id.startswith("planned_"):
            target_id = int(option_id.replace("planned_", ""))
            self._selected_target = next(
                (op for op in self._planned_operations if op.id == target_id),
                None,
            )
            # Deselect other list
            budget_list = self.query_one("#budget-list", OptionList)
            budget_list.highlighted = None
        elif option_id.startswith("budget_"):
            target_id = int(option_id.replace("budget_", ""))
            self._selected_target = next(
                (b for b in self._budgets if b.id == target_id),
                None,
            )
            # Deselect other list
            planned_list = self.query_one("#planned-list", OptionList)
            planned_list.highlighted = None

    def on_option_list_option_highlighted(
        self, event: OptionList.OptionHighlighted
    ) -> None:
        """Handle option highlight in either list."""
        if event.option is None or event.option.id is None:
            return

        option_id = str(event.option.id)
        if option_id.startswith("planned_"):
            target_id = int(option_id.replace("planned_", ""))
            self._selected_target = next(
                (op for op in self._planned_operations if op.id == target_id),
                None,
            )
        elif option_id.startswith("budget_"):
            target_id = int(option_id.replace("budget_", ""))
            self._selected_target = next(
                (b for b in self._budgets if b.id == target_id),
                None,
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-cancel":
            self.dismiss(None)
        elif event.button.id == "btn-unlink":
            self.dismiss("unlink")
        elif event.button.id == "btn-next":
            if self._selected_target:
                self.dismiss(self._selected_target)
            else:
                self.notify("Veuillez sélectionner une cible", severity="warning")

    def action_cancel(self) -> None:
        """Cancel selection."""
        self.dismiss(None)
