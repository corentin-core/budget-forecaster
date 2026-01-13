"""File browser modal for selecting files and directories."""

from pathlib import Path
from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Static

from budget_forecaster.tui.widgets import get_row_key_at_cursor


class FileBrowserModal(ModalScreen[Path | None]):
    """Modal for browsing and selecting files."""

    DEFAULT_CSS = """
    FileBrowserModal {
        align: center middle;
    }

    FileBrowserModal #browser-container {
        width: 90;
        height: 35;
        border: solid $primary;
        background: $surface;
        padding: 1;
    }

    FileBrowserModal #current-path {
        height: 1;
        margin-bottom: 1;
        color: $text-muted;
    }

    FileBrowserModal #file-list {
        height: 1fr;
    }

    FileBrowserModal #button-row {
        height: 3;
        margin-top: 1;
    }

    FileBrowserModal .dir-entry {
        color: $primary;
    }

    FileBrowserModal .file-entry {
        color: $text;
    }
    """

    BINDINGS = [
        ("escape", "cancel", "Annuler"),
        ("backspace", "go_up", "Dossier parent"),
    ]

    def __init__(self, start_path: Path | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._current_path = (start_path or Path.home()).resolve()
        if not self._current_path.is_dir():
            self._current_path = self._current_path.parent

    def compose(self) -> ComposeResult:
        """Create the modal layout."""
        with Vertical(id="browser-container"):
            yield Static(str(self._current_path), id="current-path")
            yield DataTable(id="file-list")
            with Horizontal(id="button-row"):
                yield Button("← Parent", id="btn-parent", variant="default")
                yield Button("Sélectionner", id="btn-select", variant="primary")
                yield Button("Annuler", id="btn-cancel", variant="default")

    def on_mount(self) -> None:
        """Initialize the file list."""
        table = self.query_one("#file-list", DataTable)
        table.add_columns("Type", "Nom")
        table.cursor_type = "row"
        self._refresh_file_list()

    def _refresh_file_list(self) -> None:
        """Refresh the file list with current directory contents."""
        table = self.query_one("#file-list", DataTable)
        table.clear()

        self.query_one("#current-path", Static).update(str(self._current_path))

        try:
            entries = sorted(
                self._current_path.iterdir(),
                key=lambda p: (not p.is_dir(), p.name.lower()),
            )
        except PermissionError:
            self.app.notify("Permission refusée", severity="error")
            return

        for entry in entries:
            if entry.name.startswith("."):
                continue  # Skip hidden files
            if entry.is_dir():
                table.add_row("📁", entry.name, key=str(entry))
            else:
                table.add_row("📄", entry.name, key=str(entry))

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle double-click or Enter on a row."""
        if event.row_key is None:
            return
        selected_path = Path(str(event.row_key.value))
        if selected_path.is_dir():
            self._current_path = selected_path
            self._refresh_file_list()
        else:
            self.dismiss(selected_path)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-parent":
            self.action_go_up()
        elif event.button.id == "btn-select":
            self._select_current()
        elif event.button.id == "btn-cancel":
            self.dismiss(None)

    def action_cancel(self) -> None:
        """Cancel selection."""
        self.dismiss(None)

    def action_go_up(self) -> None:
        """Go to parent directory."""
        if (parent := self._current_path.parent) != self._current_path:
            self._current_path = parent
            self._refresh_file_list()

    def _select_current(self) -> None:
        """Select the currently highlighted item (file or directory)."""
        table = self.query_one("#file-list", DataTable)
        if (row_key := get_row_key_at_cursor(table)) is None:
            # No selection, use current directory
            self.dismiss(self._current_path)
            return

        selected_path = Path(str(row_key.value))
        # Select the highlighted item (file or directory)
        self.dismiss(selected_path)
