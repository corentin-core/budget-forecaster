"""Main TUI application for budget forecaster."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Footer, Header, Static, TabbedContent, TabPane

from budget_forecaster.account.persistent_account import PersistentAccount
from budget_forecaster.account.sqlite_repository import SqliteRepository
from budget_forecaster.backup import BackupService
from budget_forecaster.config import Config
from budget_forecaster.operation_range.budget import Budget
from budget_forecaster.operation_range.historic_operation import HistoricOperation
from budget_forecaster.operation_range.operation_link import LinkType, OperationLink
from budget_forecaster.operation_range.planned_operation import PlannedOperation
from budget_forecaster.services import (
    ForecastService,
    ImportService,
    OperationFilter,
    OperationLinkService,
    OperationService,
)
from budget_forecaster.tui.modals import (
    BudgetEditModal,
    CategoryModal,
    FileBrowserModal,
    LinkIterationModal,
    LinkTargetModal,
    PlannedOperationEditModal,
)
from budget_forecaster.tui.screens.budgets import BudgetsWidget
from budget_forecaster.tui.screens.forecast import ForecastWidget
from budget_forecaster.tui.screens.imports import ImportWidget
from budget_forecaster.tui.screens.planned_operations import PlannedOperationsWidget
from budget_forecaster.tui.widgets import OperationTable
from budget_forecaster.types import Category

# Logger instance (configured via Config.setup_logging)
logger = logging.getLogger("budget_forecaster")


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
        Binding("l", "link_operation", "Lier", show=True),
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
        self._operation_link_service: OperationLinkService | None = None
        self._categorizing_operation_id: int | None = None
        self._linking_operation: HistoricOperation | None = None

    def _load_config(self) -> None:
        """Load configuration and account."""
        self._config = Config()
        self._config.parse(self._config_path)

        # Setup logging from config
        self._config.setup_logging()
        logger.info("Starting Budget Forecaster TUI")

        # Create backup before any database access
        if self._config.backup.enabled:
            backup_service = BackupService(
                database_path=self._config.database_path,
                backup_directory=self._config.backup.directory,
                max_backups=self._config.backup.max_backups,
            )
            if backup_path := backup_service.create_backup():
                logger.info("Database backup created: %s", backup_path)
            backup_service.rotate_backups()

        repository = SqliteRepository(self._config.database_path)
        self._persistent_account = PersistentAccount(repository)
        self._persistent_account.load()

        self._operation_service = OperationService(self._persistent_account)
        self._operation_link_service = OperationLinkService(
            self._persistent_account.repository
        )
        self._import_service = ImportService(
            self._persistent_account,
            self._config.inbox_path,
            self._operation_link_service,
            self._config.inbox_exclude_patterns,
        )
        self._forecast_service = ForecastService(
            self._persistent_account.account,
            self._persistent_account.repository,
            self._operation_link_service,
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

    @property
    def operation_link_service(self) -> OperationLinkService:
        """Get the operation link service."""
        if self._operation_link_service is None:
            raise RuntimeError("Application not initialized")
        return self._operation_link_service

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
            with TabPane("Budgets", id="budgets"):
                yield BudgetsWidget(id="budgets-widget")
            with TabPane("Op. planifiées", id="planned-ops"):
                yield PlannedOperationsWidget(id="planned-ops-widget")
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

        # Build links and targets lookup dicts for operation tables
        links: dict[int, OperationLink] = {}
        targets: dict[tuple[LinkType, int], str] = {}

        for link in self.operation_link_service.get_all_links():
            links[link.operation_unique_id] = link

        for planned_op in self.forecast_service.get_all_planned_operations():
            if planned_op.id is not None:
                targets[
                    (LinkType.PLANNED_OPERATION, planned_op.id)
                ] = planned_op.description
        for budget in self.forecast_service.get_all_budgets():
            if budget.id is not None:
                targets[(LinkType.BUDGET, budget.id)] = budget.description

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

        # Refresh tables with link data
        self.query_one("#dashboard-table", OperationTable).load_operations(
            recent_ops, links, targets
        )
        self.query_one("#operations-table", OperationTable).load_operations(
            service.get_operations(), links, targets
        )
        self.query_one("#categorize-table", OperationTable).load_operations(
            uncategorized, links, targets
        )

        # Refresh import widget
        import_widget = self.query_one("#import-widget", ImportWidget)
        import_widget.set_service(self.import_service)

        # Refresh forecast widget
        forecast_widget = self.query_one("#forecast-widget", ForecastWidget)
        forecast_widget.set_service(self.forecast_service)

        # Refresh budgets widget
        budgets_widget = self.query_one("#budgets-widget", BudgetsWidget)
        budgets_widget.set_service(self.forecast_service)

        # Refresh planned operations widget
        planned_ops_widget = self.query_one(
            "#planned-ops-widget", PlannedOperationsWidget
        )
        planned_ops_widget.set_service(self.forecast_service)

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

    def action_link_operation(self) -> None:
        """Open link modal for the currently selected operation."""
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
        table_order = [tab_to_table.get(active_tab, "#operations-table")]
        for table_id in ("#operations-table", "#dashboard-table", "#categorize-table"):
            if table_id not in table_order:
                table_order.append(table_id)

        for table_id in table_order:
            table = self.query_one(table_id, OperationTable)
            if operation := table.get_selected_operation():
                self._linking_operation = operation

                # Get current link if any
                current_link = None
                for link in self.operation_link_service.get_all_links():
                    if link.operation_unique_id == operation.unique_id:
                        current_link = link
                        break

                # Get all targets
                planned_operations = list(
                    self.forecast_service.get_all_planned_operations()
                )
                budgets = list(self.forecast_service.get_all_budgets())

                self.push_screen(
                    LinkTargetModal(
                        operation,
                        current_link,
                        planned_operations,
                        budgets,
                    ),
                    self._on_target_selected,
                )
                return

        self.notify("Aucune opération sélectionnée", severity="warning")

    def _on_target_selected(
        self, result: PlannedOperation | Budget | str | None
    ) -> None:
        """Handle target selection from link modal."""
        if result is None or self._linking_operation is None:
            return

        # Handle unlink
        if result == "unlink":
            self.persistent_account.repository.delete_link(
                self._linking_operation.unique_id
            )
            self.notify("Liaison supprimée")
            self._refresh_screens()
            self._linking_operation = None
            return

        # Target selected - show iteration modal
        if isinstance(result, (PlannedOperation, Budget)):
            self.push_screen(
                LinkIterationModal(self._linking_operation, result),
                lambda date: self._on_iteration_selected(date, result),
            )

    def _on_iteration_selected(
        self,
        iteration_date: datetime | None,
        target: PlannedOperation | Budget,
    ) -> None:
        """Handle iteration selection from link modal."""
        if iteration_date is None or self._linking_operation is None:
            return

        # Determine target type and id
        if isinstance(target, PlannedOperation):
            target_type = LinkType.PLANNED_OPERATION
        else:
            target_type = LinkType.BUDGET

        if target.id is None:
            self.notify("Cible invalide", severity="error")
            return

        # Create the link
        link = OperationLink(
            operation_unique_id=self._linking_operation.unique_id,
            target_type=target_type,
            target_id=target.id,
            iteration_date=iteration_date,
            is_manual=True,
        )

        # Upsert (replace any existing link for this operation)
        self.persistent_account.repository.upsert_link(link)

        self.notify(f"Opération liée à '{target.description}'")
        self._refresh_screens()
        self._linking_operation = None

    # Budget event handlers

    def on_budgets_widget_budget_edit_requested(
        self, event: BudgetsWidget.BudgetEditRequested
    ) -> None:
        """Handle budget edit request."""
        event.stop()
        self.push_screen(BudgetEditModal(event.budget), self._on_budget_edited)

    def on_budgets_widget_budget_delete_requested(
        self, event: BudgetsWidget.BudgetDeleteRequested
    ) -> None:
        """Handle budget delete request."""
        event.stop()
        if event.budget.id is None:
            self.notify("Cannot delete unsaved budget", severity="error")
            return
        try:
            self.forecast_service.delete_budget(event.budget.id)
            self.notify(f"Budget '{event.budget.description}' supprimé")
            self._refresh_budgets()
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.exception("Error deleting budget")
            self.notify(f"Erreur: {e}", severity="error")

    def _on_budget_edited(self, budget: Budget | None) -> None:
        """Handle budget edit completion."""
        if budget is None:
            return

        try:
            if budget.id is None:
                # New budget
                self.forecast_service.add_budget(budget)
                self.notify(f"Budget '{budget.description}' créé")
            else:
                # Update existing
                self.forecast_service.update_budget(budget)
                self.notify(f"Budget '{budget.description}' modifié")
            self._refresh_budgets()
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.exception("Error saving budget")
            self.notify(f"Erreur: {e}", severity="error")

    def _refresh_budgets(self) -> None:
        """Refresh budgets and forecast widgets."""
        budgets_widget = self.query_one("#budgets-widget", BudgetsWidget)
        budgets_widget.refresh_data()
        forecast_widget = self.query_one("#forecast-widget", ForecastWidget)
        forecast_widget.refresh_data()

    # Planned operation event handlers

    def on_planned_operations_widget_operation_edit_requested(
        self, event: PlannedOperationsWidget.OperationEditRequested
    ) -> None:
        """Handle planned operation edit request."""
        event.stop()
        self.push_screen(
            PlannedOperationEditModal(event.operation),
            self._on_planned_operation_edited,
        )

    def on_planned_operations_widget_operation_delete_requested(
        self, event: PlannedOperationsWidget.OperationDeleteRequested
    ) -> None:
        """Handle planned operation delete request."""
        event.stop()
        if event.operation.id is None:
            self.notify("Cannot delete unsaved operation", severity="error")
            return
        try:
            self.forecast_service.delete_planned_operation(event.operation.id)
            self.notify(f"Opération '{event.operation.description}' supprimée")
            self._refresh_planned_operations()
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.exception("Error deleting planned operation")
            self.notify(f"Erreur: {e}", severity="error")

    def _on_planned_operation_edited(self, operation: PlannedOperation | None) -> None:
        """Handle planned operation edit completion."""
        if operation is None:
            return

        try:
            if operation.id is None:
                # New operation
                self.forecast_service.add_planned_operation(operation)
                self.notify(f"Opération '{operation.description}' créée")
            else:
                # Update existing
                self.forecast_service.update_planned_operation(operation)
                self.notify(f"Opération '{operation.description}' modifiée")
            self._refresh_planned_operations()
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.exception("Error saving planned operation")
            self.notify(f"Erreur: {e}", severity="error")

    def _refresh_planned_operations(self) -> None:
        """Refresh planned operations and forecast widgets."""
        planned_ops_widget = self.query_one(
            "#planned-ops-widget", PlannedOperationsWidget
        )
        planned_ops_widget.refresh_data()
        forecast_widget = self.query_one("#forecast-widget", ForecastWidget)
        forecast_widget.refresh_data()


def run_app(config_path: Path) -> None:
    """Run the TUI application.

    Args:
        config_path: Path to the configuration file.
    """
    app = BudgetApp(config_path=config_path)
    app.run()
