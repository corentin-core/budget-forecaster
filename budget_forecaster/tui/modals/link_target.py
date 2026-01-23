"""Modal for selecting a link target (planned operation or budget)."""

from datetime import timedelta
from typing import Any, Literal

from rich.text import Text  # type: ignore[import]
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, OptionList, Select, Static
from textual.widgets.option_list import Option

from budget_forecaster.operation_range.budget import Budget
from budget_forecaster.operation_range.historic_operation import HistoricOperation
from budget_forecaster.operation_range.operation_link import LinkType, OperationLink
from budget_forecaster.operation_range.planned_operation import PlannedOperation
from budget_forecaster.services.operation_link_service import compute_match_score

# Column widths for alignment
COL_SCORE = 6
COL_DESCRIPTION = 35
COL_AMOUNT = 12
COL_CATEGORY = 15


class LinkTargetModal(
    ModalScreen[PlannedOperation | Budget | Literal["unlink"] | None]
):  # pylint: disable=too-many-instance-attributes
    """Modal for selecting a link target (planned operation or budget)."""

    DEFAULT_CSS = """
    LinkTargetModal {
        align: center middle;
    }

    LinkTargetModal #modal-container {
        width: 90;
        height: 38;
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

    LinkTargetModal #current-link-row {
        height: 2;
        margin-bottom: 1;
    }

    LinkTargetModal #current-link-row.hidden {
        display: none;
    }

    LinkTargetModal #current-link-text {
        width: 1fr;
    }

    LinkTargetModal #type-select-row {
        height: 3;
        margin-bottom: 1;
    }

    LinkTargetModal #type-select {
        width: 100%;
    }

    LinkTargetModal #list-header {
        height: 1;
        background: $surface-darken-1;
        color: $text-muted;
        text-style: bold;
    }

    LinkTargetModal #target-list {
        height: 1fr;
    }

    LinkTargetModal #buttons-row {
        height: 3;
        margin-top: 1;
        dock: bottom;
    }

    LinkTargetModal #btn-unlink {
        background: $error;
    }

    LinkTargetModal #btn-unlink.hidden {
        display: none;
    }

    LinkTargetModal #buttons-spacer {
        width: 1fr;
    }

    LinkTargetModal Button {
        margin-left: 1;
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

        # Set initial type based on current link
        if current_link and current_link.target_type == LinkType.BUDGET:
            self._current_type = "budget"
        else:
            self._current_type = "planned"

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

    def _get_current_link_name(self) -> str:
        """Get the name of the currently linked target."""
        if not self._current_link:
            return ""

        target_id = self._current_link.target_id
        if self._current_link.target_type == LinkType.PLANNED_OPERATION:
            for op in self._planned_operations:
                if op.id == target_id:
                    return op.description
        else:
            for budget in self._budgets:
                if budget.id == target_id:
                    return budget.description

        # Fallback to ID if not found
        return f"#{target_id}"

    def _build_header_text(self) -> str:
        """Build the header row text."""
        score = "Score".ljust(COL_SCORE)
        desc = "Description".ljust(COL_DESCRIPTION)
        amount = "Montant".rjust(COL_AMOUNT)
        category = "Catégorie".ljust(COL_CATEGORY)
        return f"{score}{desc}{amount}  {category}"

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
            with Horizontal(id="current-link-row", classes=current_link_class):
                link_name = self._get_current_link_name()
                yield Static(f"🔗 Lié à: {link_name}", id="current-link-text")

            # Type selector
            with Horizontal(id="type-select-row"):
                yield Select(
                    [
                        ("Opérations planifiées", "planned"),
                        ("Budgets", "budget"),
                    ],
                    value=self._current_type,
                    id="type-select",
                    allow_blank=False,
                )

            # List header
            yield Static(self._build_header_text(), id="list-header")

            # Target list (single list, content changes based on type)
            initial_options = (
                self._build_budget_options()
                if self._current_type == "budget"
                else self._build_planned_options()
            )
            yield OptionList(*initial_options, id="target-list")

            # Buttons
            unlink_class = "" if self._current_link else "hidden"
            with Horizontal(id="buttons-row"):
                yield Button(
                    "Supprimer le lien",
                    id="btn-unlink",
                    variant="error",
                    classes=unlink_class,
                )
                yield Static("", id="buttons-spacer")
                yield Button("Annuler", id="btn-cancel", variant="default")
                yield Button("Suivant", id="btn-next", variant="primary")

    def on_mount(self) -> None:
        """Highlight the currently linked target if any."""
        if self._current_link:
            # Delay highlighting to ensure the list is fully rendered
            self.call_after_refresh(self._highlight_current_link)

    def _highlight_current_link(self) -> None:
        """Highlight the currently linked target in the list."""
        if not self._current_link:
            return

        target_id = self._current_link.target_id
        target_list = self.query_one("#target-list", OptionList)

        # Find the option that matches the current link
        if self._current_type == "planned":
            option_id = f"planned_{target_id}"
        else:
            option_id = f"budget_{target_id}"

        # Find index of the option and highlight it
        for idx in range(target_list.option_count):
            option = target_list.get_option_at_index(idx)
            if str(option.id) == option_id:
                target_list.highlighted = idx
                target_list.scroll_to_highlight()
                # Also set as selected target
                if self._current_type == "planned":
                    self._selected_target = next(
                        (op for op in self._planned_operations if op.id == target_id),
                        None,
                    )
                else:
                    self._selected_target = next(
                        (b for b in self._budgets if b.id == target_id),
                        None,
                    )
                break

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
            label = self._build_option_label(
                score=score,
                description=planned_op.description,
                amount=planned_op.amount,
                category=planned_op.category.value,
            )
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
            label = self._build_option_label(
                score=score,
                description=budget.description,
                amount=budget.amount,
                category=budget.category.value,
            )
            options.append(Option(label, id=f"budget_{budget.id}"))

        return options

    def _build_option_label(
        self,
        score: float,
        description: str,
        amount: float,
        category: str,
    ) -> Text:
        """Build a formatted option label with columns."""
        label = Text()

        # Score column
        if score > 0:
            label.append(f"{score:3.0f}%  ", style="bold")
        else:
            label.append("  -   ", style="dim")

        # Description column (truncated)
        desc_truncated = description[: COL_DESCRIPTION - 1].ljust(COL_DESCRIPTION)
        label.append(desc_truncated)

        # Amount column
        amount_str = f"{amount:+.0f} €".rjust(COL_AMOUNT)
        if amount < 0:
            label.append(amount_str, style="red")
        else:
            label.append(amount_str, style="green")

        # Category column
        label.append("  ")
        label.append(category[:COL_CATEGORY].ljust(COL_CATEGORY), style="dim")

        return label

    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle type selection change."""
        if event.value == Select.BLANK:
            return

        self._current_type = str(event.value)
        self._selected_target = None

        # Rebuild the list with new options
        target_list = self.query_one("#target-list", OptionList)
        target_list.clear_options()

        if self._current_type == "planned":
            for option in self._build_planned_options():
                target_list.add_option(option)
        else:
            for option in self._build_budget_options():
                target_list.add_option(option)

    def on_option_list_option_highlighted(
        self, event: OptionList.OptionHighlighted
    ) -> None:
        """Handle option highlight."""
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
