"""Widget for displaying operations in a table."""

from typing import Any

from textual.message import Message
from textual.widgets import DataTable
from textual.widgets.data_table import RowKey

from budget_forecaster.operation_range.historic_operation import HistoricOperation
from budget_forecaster.operation_range.operation_link import LinkType, OperationLink


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


class OperationTable(DataTable[str]):
    """A table widget for displaying operations."""

    class OperationSelected(Message):
        """Message sent when an operation is selected."""

        def __init__(self, operation: HistoricOperation) -> None:
            self.operation = operation
            super().__init__()

    class OperationHighlighted(Message):
        """Message sent when an operation is highlighted."""

        def __init__(self, operation: HistoricOperation) -> None:
            self.operation = operation
            super().__init__()

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the operation table."""
        super().__init__(**kwargs)
        self._operations: dict[str, HistoricOperation] = {}
        self._columns_added = False
        self.cursor_type = "row"
        self.zebra_stripes = True

    def on_mount(self) -> None:
        """Set up the table columns when mounted."""
        self._ensure_columns()

    def _ensure_columns(self) -> None:
        """Ensure table columns exist (only once)."""
        if not self._columns_added:
            self.add_columns("Date", "Description", "Montant", "Catégorie", "Lien")
            self._columns_added = True

    def load_operations(
        self,
        operations: list[HistoricOperation],
        links: dict[int, OperationLink] | None = None,
        targets: dict[tuple[LinkType, int], str] | None = None,
    ) -> None:
        """Load operations into the table.

        Args:
            operations: List of operations to display.
            links: Mapping of operation_unique_id to OperationLink (optional).
            targets: Mapping of (type, id) to target name for display (optional).
        """
        self._ensure_columns()
        self.clear()
        self._operations.clear()

        links = links or {}
        targets = targets or {}

        for op in operations:
            row_key = str(op.unique_id)
            self._operations[row_key] = op

            # Format amount with color hint
            amount_str = f"{op.amount:+.2f} €"

            # Build link column value
            link_str = ""
            if link := links.get(op.unique_id):
                target_key = (link.target_type, link.target_id)
                if target_name := targets.get(target_key):
                    link_str = f"🔗 {self._truncate(target_name, 12)}"
                else:
                    link_str = "🔗"

            self.add_row(
                op.date.strftime("%d/%m/%Y"),
                self._truncate(op.description, 50),
                amount_str,
                op.category.value,
                link_str,
                key=row_key,
            )

    def _truncate(self, text: str, max_length: int) -> str:
        """Truncate text to max length with ellipsis."""
        if len(text) <= max_length:
            return text
        return text[: max_length - 3] + "..."

    def get_selected_operation(self) -> HistoricOperation | None:
        """Get the currently selected operation."""
        if (row_key := get_row_key_at_cursor(self)) is None:
            return None
        return self._operations.get(str(row_key.value))

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection."""
        if event.row_key is not None:
            if operation := self._operations.get(str(event.row_key.value)):
                self.post_message(self.OperationSelected(operation))

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Handle row highlight."""
        if event.row_key is not None:
            if operation := self._operations.get(str(event.row_key.value)):
                self.post_message(self.OperationHighlighted(operation))

    @property
    def operation_count(self) -> int:
        """Get the number of operations in the table."""
        return len(self._operations)

    def get_operation_by_row(self, row_index: int) -> HistoricOperation | None:
        """Get operation at a specific row index."""
        try:
            if (row_key := self.get_row_at(row_index)) is not None:
                return self._operations.get(str(row_key))
        except IndexError:
            pass
        return None
