"""Main TUI application for budget forecaster."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    OptionList,
    Static,
    TabbedContent,
    TabPane,
)
from textual.widgets.option_list import Option

from budget_forecaster.account.persistent_account import PersistentAccount
from budget_forecaster.config import Config
from budget_forecaster.operation_range.historic_operation import HistoricOperation
from budget_forecaster.services import (
    ForecastService,
    ImportService,
    OperationFilter,
    OperationService,
)
from budget_forecaster.tui.screens.forecast import ForecastWidget
from budget_forecaster.tui.screens.imports import ImportWidget
from budget_forecaster.tui.widgets.operation_table import OperationTable
from budget_forecaster.types import Category

# Logger instance (configured via Config.setup_logging)
logger = logging.getLogger("budget_forecaster")


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
        if table.cursor_row is None or table.row_count == 0:
            # Select current directory
            self.dismiss(self._current_path)
            return

        try:
            # pylint: disable=protected-access
            if row_key := table._row_locations.get_key(table.cursor_row):
                selected_path = Path(str(row_key.value))
                # Select the highlighted item (file or directory)
                self.dismiss(selected_path)
        except (KeyError, IndexError):
            self.dismiss(self._current_path)


class CategoryModal(ModalScreen[Category | None]):
    """Modal for selecting a category."""

    DEFAULT_CSS = """
    CategoryModal {
        align: center middle;
    }

    CategoryModal #modal-container {
        width: 80;
        height: 30;
        border: solid $primary;
        background: $surface;
        padding: 1;
    }

    CategoryModal #op-info {
        height: auto;
        margin-bottom: 1;
        padding: 1;
        border: solid $accent;
    }

    CategoryModal #op-description {
        height: auto;
        max-height: 4;
    }

    CategoryModal #op-details {
        color: $text-muted;
    }

    CategoryModal .amount-positive {
        color: $success;
    }

    CategoryModal .amount-negative {
        color: $error;
    }

    CategoryModal OptionList {
        height: 1fr;
    }
    """

    BINDINGS = [("escape", "cancel", "Annuler")]

    def __init__(self, operation: HistoricOperation, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._operation = operation

    def compose(self) -> ComposeResult:
        """Create the modal layout."""
        op = self._operation
        amount_class = "amount-negative" if op.amount < 0 else "amount-positive"

        with Vertical(id="modal-container"):
            with Vertical(id="op-info"):
                yield Static(op.description, id="op-description")
                yield Static(
                    f"{op.date.strftime('%d/%m/%Y')} | {op.amount:+.2f} €",
                    id="op-details",
                    classes=amount_class,
                )
            categories = sorted(Category, key=lambda c: c.value)
            options = [Option(cat.value, id=cat.name) for cat in categories]
            yield OptionList(*options, id="category-list")

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle category selection."""
        if event.option.id:
            self.dismiss(Category[event.option.id])

    def action_cancel(self) -> None:
        """Cancel selection."""
        self.dismiss(None)


class BudgetApp(App[None]):
    """Main TUI application for budget management."""

    TITLE = "Budget Forecaster"
    CSS = """
    #stats-row {
        height: 3;
        margin-bottom: 1;
    }

    #stats-row Static {
        width: 1fr;
        border: solid $primary;
        padding: 0 1;
        margin: 0 1;
    }

    .stat-positive {
        color: $success;
    }

    .stat-negative {
        color: $error;
    }

    #categorize-help {
        height: 1;
        margin-bottom: 1;
    }

    OperationTable {
        height: 1fr;
        max-height: 100%;
    }

    #import-header {
        height: 3;
        margin-bottom: 1;
    }

    #inbox-info {
        width: 1fr;
        padding: 0 1;
    }

    #pending-title {
        text-style: bold;
        margin-bottom: 1;
    }

    #pending-table {
        height: 1fr;
        max-height: 100%;
    }

    #manual-title {
        text-style: bold;
        margin-top: 1;
        margin-bottom: 1;
    }

    #file-input-row {
        height: 3;
    }

    #file-path-input {
        width: 1fr;
    }

    #btn-import-file {
        margin-left: 1;
    }
    """

    BINDINGS = [
        Binding("r", "refresh_data", "Rafraîchir", show=True),
        Binding("c", "categorize", "Catégoriser", show=True),
        Binding("q", "quit", "Quitter", show=True),
    ]

    def __init__(
        self,
        config_path: Path,
        **kwargs: Any,
    ) -> None:
        """Initialize the application.

        Args:
            config_path: Path to the configuration file.
            **kwargs: Additional arguments passed to App.
        """
        super().__init__(**kwargs)
        self._config_path = config_path
        self._config: Config | None = None
        self._persistent_account: PersistentAccount | None = None
        self._operation_service: OperationService | None = None
        self._import_service: ImportService | None = None
        self._forecast_service: ForecastService | None = None
        self._categorizing_operation_id: int | None = None

    def _load_config(self) -> None:
        """Load configuration and account."""
        self._config = Config()
        self._config.parse(self._config_path)

        # Setup logging from config
        self._config.setup_logging()
        logger.info("Starting Budget Forecaster TUI")

        self._persistent_account = PersistentAccount(
            database_path=self._config.database_path
        )
        self._persistent_account.load()

        self._operation_service = OperationService(self._persistent_account)
        self._import_service = ImportService(
            self._persistent_account,
            self._config.inbox_path,
            self._config.inbox_exclude_patterns,
        )
        self._forecast_service = ForecastService(
            self._persistent_account.account,
            self._config.planned_operations_path,
            self._config.budgets_path,
        )

    @property
    def operation_service(self) -> OperationService:
        """Get the operation service."""
        if self._operation_service is None:
            raise RuntimeError("Application not initialized")
        return self._operation_service

    @property
    def persistent_account(self) -> PersistentAccount:
        """Get the persistent account."""
        if self._persistent_account is None:
            raise RuntimeError("Application not initialized")
        return self._persistent_account

    @property
    def import_service(self) -> ImportService:
        """Get the import service."""
        if self._import_service is None:
            raise RuntimeError("Application not initialized")
        return self._import_service

    @property
    def forecast_service(self) -> ForecastService:
        """Get the forecast service."""
        if self._forecast_service is None:
            raise RuntimeError("Application not initialized")
        return self._forecast_service

    def compose(self) -> ComposeResult:
        """Create the UI layout."""
        yield Header()
        with TabbedContent(initial="dashboard"):
            with TabPane("Dashboard", id="dashboard"):
                # Simple stats display
                with Horizontal(id="stats-row"):
                    yield Static("Solde: -", id="stat-balance")
                    yield Static("Opérations ce mois: -", id="stat-month-ops")
                    yield Static("Non catégorisées: -", id="stat-uncategorized")
                yield OperationTable(id="dashboard-table")
            with TabPane("Opérations", id="operations"):
                yield OperationTable(id="operations-table")
            with TabPane("Catégorisation", id="categorize"):
                yield Static(
                    "Sélectionnez une opération et appuyez sur [c] pour catégoriser",
                    id="categorize-help",
                )
                yield OperationTable(id="categorize-table")
            with TabPane("Import", id="import"):
                yield ImportWidget(id="import-widget")
            with TabPane("Prévisions", id="forecast"):
                yield ForecastWidget(id="forecast-widget")
        yield Footer()

    def on_mount(self) -> None:
        """Initialize the application on mount."""
        try:
            self._load_config()
            # Use call_after_refresh to ensure screens are mounted
            self.call_after_refresh(self._refresh_screens)
        except FileNotFoundError as e:
            self.notify(f"Erreur: {e}", severity="error")
            self.exit()

    def _refresh_screens(self) -> None:  # pylint: disable=too-many-locals
        """Refresh all screens with current data."""
        service = self.operation_service

        # Update dashboard stats
        balance = service.balance
        stat_balance = self.query_one("#stat-balance", Static)
        stat_balance.update(f"Solde: {balance:,.2f} {service.currency}")
        stat_balance.remove_class("stat-positive", "stat-negative")
        stat_balance.add_class("stat-negative" if balance < 0 else "stat-positive")

        # Last 3 months operations
        now = datetime.now()
        month, year = now.month - 3, now.year
        if month <= 0:
            month, year = month + 12, year - 1
        recent_filter = OperationFilter(date_from=datetime(year, month, 1))
        recent_ops = service.get_operations(recent_filter)
        self.query_one("#stat-month-ops", Static).update(
            f"3 derniers mois: {len(recent_ops)} opérations"
        )

        # Uncategorized count
        uncategorized = service.get_uncategorized_operations()
        stat_uncat = self.query_one("#stat-uncategorized", Static)
        stat_uncat.update(f"Non catégorisées: {len(uncategorized)}")
        stat_uncat.remove_class("stat-positive", "stat-negative")
        stat_uncat.add_class("stat-negative" if uncategorized else "stat-positive")

        # Refresh tables
        self.query_one("#dashboard-table", OperationTable).load_operations(recent_ops)
        self.query_one("#operations-table", OperationTable).load_operations(
            service.get_operations()
        )
        self.query_one("#categorize-table", OperationTable).load_operations(
            uncategorized
        )

        # Refresh import widget
        import_widget = self.query_one("#import-widget", ImportWidget)
        import_widget.set_service(self.import_service)

        # Refresh forecast widget
        forecast_widget = self.query_one("#forecast-widget", ForecastWidget)
        forecast_widget.set_service(self.forecast_service)

    def action_refresh_data(self) -> None:
        """Refresh data from the database."""
        if self._persistent_account is not None:
            self._persistent_account.load()
            self._refresh_screens()

    def save_changes(self) -> None:
        """Save changes to the database."""
        if self._persistent_account:
            self._persistent_account.save()
            self.notify("Modifications enregistrées")

    def on_import_widget_browse_requested(
        self, event: ImportWidget.BrowseRequested
    ) -> None:
        """Handle browse request from import widget."""
        event.stop()
        # Start in inbox directory if it exists, otherwise home
        start_path = self.import_service.inbox_path
        if not start_path.exists():
            start_path = Path.home()
        self.push_screen(FileBrowserModal(start_path), self._on_file_selected)

    def on_import_widget_import_completed(
        self, event: ImportWidget.ImportCompleted
    ) -> None:
        """Handle import completion from import widget."""
        event.stop()
        if event.success:
            # Reload data from database and refresh all screens
            if self._persistent_account:
                self._persistent_account.load()
            self._refresh_screens()

    def _on_file_selected(self, path: Path | None) -> None:
        """Handle file selection from browser."""
        if path is None:
            return
        import_widget = self.query_one("#import-widget", ImportWidget)
        import_widget.set_file_path(path)

    def action_categorize(self) -> None:
        """Open category selection for the currently selected operation."""
        # Get the active tab and prioritize its table
        tabbed = self.query_one(TabbedContent)
        active_tab = tabbed.active

        # Map tab IDs to table IDs
        tab_to_table = {
            "dashboard": "#dashboard-table",
            "operations": "#operations-table",
            "categorize": "#categorize-table",
        }

        # Try active tab's table first, then others
        table_order = [tab_to_table.get(active_tab, "#categorize-table")]
        for table_id in ("#categorize-table", "#operations-table", "#dashboard-table"):
            if table_id not in table_order:
                table_order.append(table_id)

        for table_id in table_order:
            table = self.query_one(table_id, OperationTable)
            if operation := table.get_selected_operation():
                self._categorizing_operation_id = operation.unique_id
                self.push_screen(CategoryModal(operation), self._on_category_selected)
                return

        self.notify("Aucune opération sélectionnée", severity="warning")

    def _on_category_selected(self, category: Category | None) -> None:
        """Handle category selection from modal."""
        if category is None or self._categorizing_operation_id is None:
            return

        self.operation_service.categorize_operation(
            self._categorizing_operation_id, category
        )
        self.save_changes()
        # Reload data from database and refresh all screens
        if self._persistent_account:
            self._persistent_account.load()
        self._refresh_screens()
        self.notify(f"Catégorie '{category.value}' assignée")


def run_app(config_path: Path) -> None:
    """Run the TUI application.

    Args:
        config_path: Path to the configuration file.
    """
    app = BudgetApp(config_path=config_path)
    app.run()
