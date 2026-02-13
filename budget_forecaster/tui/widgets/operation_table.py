"""Widget for displaying operations in a table."""

from collections.abc import Iterable
from typing import Any

from textual.binding import Binding
from textual.events import Click
from textual.message import Message
from textual.widgets import DataTable
from textual.widgets.data_table import ColumnKey, RowKey

from budget_forecaster.core.types import MatcherKey, OperationId, TargetName
from budget_forecaster.domain.operation.historic_operation import HistoricOperation
from budget_forecaster.domain.operation.operation_link import OperationLink
from budget_forecaster.i18n import _


def get_row_key_at_cursor(table: DataTable) -> RowKey | None:  # type: ignore[type-arg]
    """Get the RowKey at the current cursor position.

    This helper encapsulates access to Textual's private _row_locations API.
    If Textual changes its internal API, only this function needs updating.

    Args:
        table: The DataTable widget.

    Returns:
        The RowKey at cursor position, or None if not found.
    """
    if table.cursor_row is None or table.row_count == 0:
        return None
    try:
        # pylint: disable=protected-access
        return table._row_locations.get_key(table.cursor_row)
    except (KeyError, IndexError, AttributeError):
        return None


class OperationTable(DataTable[str]):  # pylint: disable=too-many-instance-attributes
    """A table widget for displaying operations with multi-selection support."""

    BINDINGS = [
        Binding("space", "toggle_selection", _("Select"), show=True),
        Binding("shift+up", "extend_selection_up", _("Extend up"), show=False),
        Binding("shift+down", "extend_selection_down", _("Extend down"), show=False),
        Binding("ctrl+a", "select_all", _("Select all"), show=False),
        Binding("escape", "clear_selection", _("Deselect"), show=False),
    ]

    class OperationSelected(Message):
        """Message sent when an operation is selected (Enter pressed)."""

        def __init__(self, operation: HistoricOperation) -> None:
            self.operation = operation
            super().__init__()

    class OperationHighlighted(Message):
        """Message sent when an operation is highlighted."""

        def __init__(self, operation: HistoricOperation) -> None:
            self.operation = operation
            super().__init__()

    class SelectionChanged(Message):
        """Message sent when the selection changes."""

        def __init__(self, selected_count: int) -> None:
            self.selected_count = selected_count
            super().__init__()

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the operation table."""
        super().__init__(**kwargs)
        self._operations: dict[str, HistoricOperation] = {}
        self._selected_ids: set[OperationId] = set()
        self._columns_added = False
        self._date_column_key: ColumnKey | None = None
        self._links: dict[OperationId, OperationLink] = {}
        self._targets: dict[MatcherKey, TargetName] = {}
        self._anchor_row: int | None = None
        self.cursor_type = "row"
        self.zebra_stripes = True

    def on_mount(self) -> None:
        """Set up the table columns when mounted."""
        self._ensure_columns()

    def _ensure_columns(self) -> None:
        """Ensure table columns exist (only once)."""
        if not self._columns_added:
            column_keys = self.add_columns(
                _("Date"), _("Description"), _("Amount"), _("Category"), _("Link")
            )
            self._date_column_key = column_keys[0]
            self._columns_added = True

    def load_operations(
        self,
        operations: Iterable[HistoricOperation],
        links: dict[OperationId, OperationLink] | None = None,
        targets: dict[MatcherKey, TargetName] | None = None,
    ) -> None:
        """Load operations into the table.

        Args:
            operations: Operations to display.
            links: Mapping of operation_unique_id to OperationLink (optional).
            targets: Mapping of (type, id) to target name for display (optional).
        """
        self._ensure_columns()
        self.clear()
        self._operations.clear()
        self._selected_ids.clear()

        self._links = links or {}
        self._targets = targets or {}

        for op in operations:
            row_key = str(op.unique_id)
            self._operations[row_key] = op
            self._add_operation_row(op, row_key)

    def _add_operation_row(self, op: HistoricOperation, row_key: str) -> None:
        """Add a single operation row to the table."""
        # Format date with selection marker
        date_str = op.operation_date.strftime("%d/%m/%Y")
        if op.unique_id in self._selected_ids:
            date_str = f"► {date_str}"

        # Format amount
        amount_str = f"{op.amount:+.2f} €"

        # Build link column value
        link_str = ""
        if link := self._links.get(op.unique_id):
            target_key = MatcherKey(link.target_type, link.target_id)
            if target_name := self._targets.get(target_key):
                link_str = f"🔗 {self._truncate(target_name, 12)}"
            else:
                link_str = "🔗"

        self.add_row(
            date_str,
            self._truncate(op.description, 50),
            amount_str,
            op.category.display_name,
            link_str,
            key=row_key,
        )

    def _truncate(self, text: str, max_length: int) -> str:
        """Truncate text to max length with ellipsis."""
        if len(text) <= max_length:
            return text
        return text[: max_length - 3] + "..."

    def _update_row_style(self, op_id: OperationId) -> None:
        """Update the visual style for a selected/deselected row."""
        if (row_key := str(op_id)) not in self._operations:
            return
        if self._date_column_key is None:
            return

        op = self._operations[row_key]
        date_str = op.operation_date.strftime("%d/%m/%Y")
        if op_id in self._selected_ids:
            date_str = f"► {date_str}"

        self.update_cell(row_key, self._date_column_key, date_str)

    def get_highlighted_operation(self) -> HistoricOperation | None:
        """Get the currently highlighted operation."""
        if (row_key := get_row_key_at_cursor(self)) is None:
            return None
        return self._operations.get(str(row_key.value))

    def get_selected_operation(self) -> HistoricOperation | None:
        """Get the currently highlighted operation (for backward compatibility)."""
        return self.get_highlighted_operation()

    def get_selected_operations(self) -> tuple[HistoricOperation, ...]:
        """Get all selected operations.

        Returns:
            Tuple of selected operations, or tuple with just the highlighted
            operation if no explicit selection.
        """
        if self._selected_ids:
            return tuple(
                op
                for op in self._operations.values()
                if op.unique_id in self._selected_ids
            )
        # If no selection, return the highlighted operation
        if highlighted := self.get_highlighted_operation():
            return (highlighted,)
        return ()

    def clear_selection(self) -> None:
        """Clear all selections."""
        old_selected = self._selected_ids.copy()
        self._selected_ids.clear()
        for op_id in old_selected:
            self._update_row_style(op_id)
        self.post_message(self.SelectionChanged(0))

    def action_clear_selection(self) -> None:
        """Action to clear selection (bound to Escape)."""
        self.clear_selection()

    @property
    def selected_count(self) -> int:
        """Get the number of selected operations."""
        return len(self._selected_ids)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection (Enter pressed)."""
        if event.row_key is not None:
            if operation := self._operations.get(str(event.row_key.value)):
                self.post_message(self.OperationSelected(operation))

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Handle row highlight."""
        if event.row_key is not None:
            if operation := self._operations.get(str(event.row_key.value)):
                self.post_message(self.OperationHighlighted(operation))

    def on_click(self, event: Click) -> None:
        """Handle clicks - clear selection on regular click, toggle on Ctrl+click."""
        # Get the row from the click position
        style_meta = getattr(event.style, "meta", None)
        if not isinstance(style_meta, dict):
            return

        row_index = style_meta.get("row")
        if row_index is None or row_index < 0 or row_index >= self.row_count:
            return

        if event.ctrl:
            # Ctrl+click: toggle individual selection
            if (operation := self.get_operation_by_row(row_index)) is None:
                return
            self._toggle_selection(operation.unique_id, row_index)
            self.post_message(self.SelectionChanged(len(self._selected_ids)))
            event.stop()
            event.prevent_default()
        elif not event.shift and not event.meta and self._selected_ids:
            # Regular click with existing selection: clear selection
            self.clear_selection()
            # Update anchor to clicked row
            self._anchor_row = row_index

    def action_toggle_selection(self) -> None:
        """Toggle selection of the current row (Space key)."""
        if self.cursor_row is None:
            return
        if (operation := self.get_highlighted_operation()) is None:
            return

        self._toggle_selection(operation.unique_id, self.cursor_row)
        self.post_message(self.SelectionChanged(len(self._selected_ids)))

    def action_extend_selection_up(self) -> None:
        """Extend selection upward (Shift+Up)."""
        if self.cursor_row is None or self.cursor_row <= 0:
            return

        # Set anchor if not set, and also select the anchor row
        if self._anchor_row is None:
            self._anchor_row = self.cursor_row
            if anchor_op := self.get_operation_by_row(self._anchor_row):
                self._selected_ids.add(anchor_op.unique_id)
                self._update_row_style(anchor_op.unique_id)

        # Move cursor up
        new_row = self.cursor_row - 1
        self.move_cursor(row=new_row)

        # Select the new row
        if operation := self.get_operation_by_row(new_row):
            if operation.unique_id not in self._selected_ids:
                self._selected_ids.add(operation.unique_id)
                self._update_row_style(operation.unique_id)
        self.post_message(self.SelectionChanged(len(self._selected_ids)))

    def action_extend_selection_down(self) -> None:
        """Extend selection downward (Shift+Down)."""
        if self.cursor_row is None or self.cursor_row >= self.row_count - 1:
            return

        # Set anchor if not set, and also select the anchor row
        if self._anchor_row is None:
            self._anchor_row = self.cursor_row
            if anchor_op := self.get_operation_by_row(self._anchor_row):
                self._selected_ids.add(anchor_op.unique_id)
                self._update_row_style(anchor_op.unique_id)

        # Move cursor down
        new_row = self.cursor_row + 1
        self.move_cursor(row=new_row)

        # Select the new row
        if operation := self.get_operation_by_row(new_row):
            if operation.unique_id not in self._selected_ids:
                self._selected_ids.add(operation.unique_id)
                self._update_row_style(operation.unique_id)
        self.post_message(self.SelectionChanged(len(self._selected_ids)))

    def action_select_all(self) -> None:
        """Select all operations (Ctrl+A)."""
        for op in self._operations.values():
            if op.unique_id not in self._selected_ids:
                self._selected_ids.add(op.unique_id)
                self._update_row_style(op.unique_id)
        self.post_message(self.SelectionChanged(len(self._selected_ids)))

    def _toggle_selection(self, op_id: OperationId, row_index: int) -> None:
        """Toggle selection for a single operation."""
        if op_id in self._selected_ids:
            self._selected_ids.remove(op_id)
        else:
            self._selected_ids.add(op_id)
        self._anchor_row = row_index
        self._update_row_style(op_id)

    @property
    def operation_count(self) -> int:
        """Get the number of operations in the table."""
        return len(self._operations)

    def get_operation_by_row(self, row_index: int) -> HistoricOperation | None:
        """Get operation at a specific row index."""
        if row_index < 0 or row_index >= self.row_count:
            return None
        try:
            # pylint: disable=protected-access
            if (row_key := self._row_locations.get_key(row_index)) is None:
                return None
            return self._operations.get(str(row_key.value))
        except (KeyError, IndexError, AttributeError):
            return None
