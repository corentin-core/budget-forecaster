"""Import screen for loading bank exports."""

import logging
from pathlib import Path
from typing import Any

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Input, ProgressBar, Static

from budget_forecaster.i18n import _
from budget_forecaster.services.application_service import ApplicationService

logger = logging.getLogger(__name__)


class ImportProgressModal(ModalScreen[bool]):
    """Modal showing import progress."""

    DEFAULT_CSS = """
    ImportProgressModal {
        align: center middle;
    }

    ImportProgressModal > Container {
        width: 60;
        height: auto;
        max-height: 20;
        border: solid $primary;
        background: $surface;
        padding: 1;
    }

    ImportProgressModal .modal-title {
        text-style: bold;
        margin-bottom: 1;
    }

    ImportProgressModal #progress-text {
        margin-bottom: 1;
    }

    ImportProgressModal ProgressBar {
        margin-bottom: 1;
    }

    ImportProgressModal #result-text {
        margin-top: 1;
    }

    ImportProgressModal #btn-close {
        margin-top: 1;
    }
    """

    BINDINGS = [("escape", "close", _("Close"))]

    def __init__(self, app_service: ApplicationService, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._app_service = app_service
        self._import_done = False

    def compose(self) -> ComposeResult:
        with Container():
            yield Static(_("Importing..."), classes="modal-title", id="modal-title")
            yield Static(_("Preparing..."), id="progress-text")
            yield ProgressBar(total=100, id="progress-bar")
            yield Static("", id="result-text")
            yield Button(_("Close"), id="btn-close", variant="primary", disabled=True)

    def on_mount(self) -> None:
        """Start the import process."""
        self.run_import()

    def run_import(self) -> None:
        """Run the import process."""
        pending = self._app_service.get_supported_exports_in_inbox()

        if (total := len(pending)) == 0:
            self._show_result(_("No files to import"), success=True)
            return

        progress_bar = self.query_one("#progress-bar", ProgressBar)
        progress_text = self.query_one("#progress-text", Static)
        progress_bar.update(total=total, progress=0)

        def on_progress(current: int, _total_count: int, filename: str) -> None:
            progress_text.update(_("Importing {}...").format(filename))
            progress_bar.update(progress=current)
            self.refresh()

        logger.info("Starting inbox import...")
        summary = self._app_service.import_from_inbox(on_progress=on_progress)

        # Log results
        for result in summary.results:
            if result.success and result.stats:
                logger.info(
                    "Imported %s: %d new, %d duplicates skipped",
                    result.path,
                    result.stats.new_operations,
                    result.stats.duplicates_skipped,
                )
            else:
                logger.error(
                    "Failed to import %s: %s", result.path, result.error_message
                )

        # Show results
        if summary.failed_imports == 0:
            result_msg = _("{} file(s) imported\n{} new operation(s)").format(
                summary.successful_imports, summary.total_new_operations
            )
            if summary.total_duplicates_skipped > 0:
                result_msg += "\n" + _("{} duplicate(s) skipped").format(
                    summary.total_duplicates_skipped
                )
            self._show_result(result_msg, success=True)
        else:
            result_msg = _("{} imported, {} error(s) - see logs").format(
                summary.successful_imports, summary.failed_imports
            )
            self._show_result(result_msg, success=False)

    def _show_result(self, message: str, success: bool) -> None:
        """Show the import result."""
        self._import_done = True
        title = self.query_one("#modal-title", Static)
        title.update(
            _("Import completed") if success else _("Import completed with errors")
        )

        result_text = self.query_one("#result-text", Static)
        result_text.update(message)

        self.query_one("#btn-close", Button).disabled = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "btn-close":
            self.dismiss(self._import_done)

    def action_close(self) -> None:
        """Close the modal."""
        self.dismiss(self._import_done)


class ImportWidget(Vertical):
    """Widget for importing bank exports."""

    class ImportCompleted(Message):
        """Message sent when an import is completed."""

        def __init__(self, success: bool) -> None:
            self.success = success
            super().__init__()

    class BrowseRequested(Message):
        """Message sent when the user wants to browse for a file."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._app_service: ApplicationService | None = None

    def compose(self) -> ComposeResult:
        with Horizontal(id="import-header"):
            yield Static(_("Inbox folder: -"), id="inbox-info")
            yield Button(
                _("Import from inbox"), id="btn-import-inbox", variant="primary"
            )
        yield Static(_("Files pending import"), id="pending-title")
        yield DataTable(id="pending-table")
        yield Static(_("Manual import"), id="manual-title")
        with Horizontal(id="file-input-row"):
            yield Input(
                placeholder=_("Path to file or folder..."),
                id="file-path-input",
            )
            yield Button(_("Browse"), id="btn-browse", variant="default")
            yield Button(_("Import"), id="btn-import-file", variant="primary")

    def on_mount(self) -> None:
        """Initialize the table."""
        table = self.query_one("#pending-table", DataTable)
        table.add_columns(_("File"), _("Type"))
        table.cursor_type = "row"

    def set_app_service(self, service: ApplicationService) -> None:
        """Set the application service."""
        self._app_service = service
        self.refresh_view()

    def refresh_view(self) -> None:
        """Refresh the view with current data."""
        if not self._app_service:
            return

        # Update inbox info
        inbox_info = self.query_one("#inbox-info", Static)
        inbox_path = self._app_service.inbox_path
        inbox_info.update(_("Inbox folder: {}").format(inbox_path))

        # Update pending files table
        table = self.query_one("#pending-table", DataTable)
        table.clear()

        pending = self._app_service.get_supported_exports_in_inbox()
        for path in pending:
            file_type = _("Folder") if path.is_dir() else path.suffix.upper()
            table.add_row(path.name, file_type, key=str(path))

        # Update import button state
        btn = self.query_one("#btn-import-inbox", Button)
        if pending:
            btn.label = _("Import from inbox ({})").format(len(pending))
            btn.disabled = False
        else:
            btn.label = _("Inbox empty")
            btn.disabled = True

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-import-inbox":
            self._start_inbox_import()
        elif event.button.id == "btn-import-file":
            self._start_file_import()
        elif event.button.id == "btn-browse":
            self.post_message(self.BrowseRequested())

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key in file path input."""
        if event.input.id == "file-path-input":
            self._start_file_import()

    def set_file_path(self, path: Path) -> None:
        """Set the file path input value."""
        path_input = self.query_one("#file-path-input", Input)
        path_input.value = str(path)

    def _start_inbox_import(self) -> None:
        """Start importing from inbox."""
        if not self._app_service:
            return

        self.app.push_screen(
            ImportProgressModal(self._app_service),
            self._on_import_complete,
        )

    def _start_file_import(self) -> None:
        """Start importing from a specific file."""
        if not self._app_service:
            return

        path_input = self.query_one("#file-path-input", Input)

        if not (path_str := path_input.value.strip()):
            self.app.notify(_("Please enter a path"), severity="warning")
            return

        path = Path(path_str).expanduser().resolve()

        if not path.exists():
            logger.warning("File not found: %s", path)
            self.app.notify(_("File not found: {}").format(path), severity="error")
            return

        if not self._app_service.is_supported_export(path):
            logger.warning("Unsupported format: %s", path)
            self.app.notify(_("Unsupported or unrecognized format"), severity="error")
            return

        logger.info("Importing file: %s", path)

        # Import the file
        result = self._app_service.import_file(path, move_to_processed=False)

        if result.success and result.stats:
            logger.info(
                "Successfully imported %s: %d new, %d duplicates skipped",
                path,
                result.stats.new_operations,
                result.stats.duplicates_skipped,
            )
            msg = _("Imported: {} new").format(result.stats.new_operations)
            if result.stats.duplicates_skipped > 0:
                msg += ", " + _("{} duplicate(s) skipped").format(
                    result.stats.duplicates_skipped
                )
            self.app.notify(msg)
            path_input.value = ""
            self._on_import_complete(True)
        else:
            logger.error("Failed to import %s: %s", path, result.error_message)
            self.app.notify(
                _("Error: {}").format(result.error_message), severity="error"
            )

    def _on_import_complete(self, success: bool | None) -> None:
        """Handle import completion."""
        if success:
            self.refresh_view()
            self.post_message(self.ImportCompleted(success=True))
