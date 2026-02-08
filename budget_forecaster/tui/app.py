"""Main TUI application for budget forecaster."""

import logging
from datetime import date
from pathlib import Path
from typing import Any

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.css.query import NoMatches
from textual.widgets import Footer, Header, Static, TabbedContent, TabPane

from budget_forecaster.core.types import (
    Category,
    LinkType,
    MatcherKey,
    OperationId,
    TargetName,
)
from budget_forecaster.domain.operation.budget import Budget
from budget_forecaster.domain.operation.historic_operation import HistoricOperation
from budget_forecaster.domain.operation.operation_link import OperationLink
from budget_forecaster.domain.operation.planned_operation import PlannedOperation
from budget_forecaster.exceptions import AccountNotLoadedError, BudgetForecasterError
from budget_forecaster.infrastructure.backup import BackupService
from budget_forecaster.infrastructure.config import Config
from budget_forecaster.infrastructure.persistence.persistent_account import (
    PersistentAccount,
)
from budget_forecaster.infrastructure.persistence.sqlite_repository import (
    SqliteRepository,
)
from budget_forecaster.services.application_service import ApplicationService
from budget_forecaster.services.forecast.forecast_service import ForecastService
from budget_forecaster.services.import_service import ImportService
from budget_forecaster.services.operation.operation_link_service import (
    OperationLinkService,
)
from budget_forecaster.services.operation.operation_service import (
    OperationFilter,
    OperationService,
)
from budget_forecaster.tui.messages import DataRefreshRequested, SaveRequested
from budget_forecaster.tui.modals import (
    BudgetEditModal,
    CategoryModal,
    FileBrowserModal,
    LinkIterationModal,
    LinkTargetModal,
    PlannedOperationEditModal,
    SplitOperationModal,
    SplitResult,
)
from budget_forecaster.tui.screens.budgets import BudgetsWidget
from budget_forecaster.tui.screens.forecast import ForecastWidget
from budget_forecaster.tui.screens.imports import ImportWidget
from budget_forecaster.tui.screens.planned_operations import PlannedOperationsWidget
from budget_forecaster.tui.widgets import OperationTable

# Logger instance (configured via Config.setup_logging)
logger = logging.getLogger("budget_forecaster")


class BudgetApp(App[None]):  # pylint: disable=too-many-instance-attributes
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
        self._app_service: ApplicationService | None = None
        self._categorizing_operation_ids: tuple[OperationId, ...] = ()
        self._linking_operations: tuple[HistoricOperation, ...] = ()

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
        repository.initialize()
        self._persistent_account = PersistentAccount(repository)

        # Create individual services
        operation_service = OperationService(self._persistent_account)
        operation_link_service = OperationLinkService(
            self._persistent_account.repository
        )
        import_service = ImportService(
            self._persistent_account,
            self._config.inbox_path,
            self._config.inbox_exclude_patterns,
            self._config.inbox_include_patterns,
        )
        forecast_service = ForecastService(
            self._persistent_account.account,
            self._persistent_account.repository,
        )

        # Create the application service as central orchestrator
        self._app_service = ApplicationService(
            persistent_account=self._persistent_account,
            import_service=import_service,
            operation_service=operation_service,
            forecast_service=forecast_service,
            operation_link_service=operation_link_service,
        )

    @property
    def app_service(self) -> ApplicationService:
        """Get the application service."""
        if self._app_service is None:
            raise RuntimeError("Application not initialized")
        return self._app_service

    @property
    def persistent_account(self) -> PersistentAccount:
        """Get the persistent account."""
        if self._persistent_account is None:
            raise RuntimeError("Application not initialized")
        return self._persistent_account

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
        except AccountNotLoadedError as e:
            self.notify(f"Erreur: {e}", severity="error")
            self.exit()

    def _refresh_screens(self) -> None:  # pylint: disable=too-many-locals
        """Refresh all screens with current data."""
        # Build links and targets lookup dicts for operation tables
        links: dict[OperationId, OperationLink] = {}
        targets: dict[MatcherKey, TargetName] = {}

        for link in self.app_service.get_all_links():
            links[link.operation_unique_id] = link

        for planned_op in self.app_service.get_all_planned_operations():
            if planned_op.id is not None:
                key = MatcherKey(LinkType.PLANNED_OPERATION, planned_op.id)
                targets[key] = planned_op.description
        for budget in self.app_service.get_all_budgets():
            if budget.id is not None:
                key = MatcherKey(LinkType.BUDGET, budget.id)
                targets[key] = budget.description

        # Update dashboard stats
        balance = self.app_service.balance
        stat_balance = self.query_one("#stat-balance", Static)
        stat_balance.update(f"Solde: {balance:,.2f} {self.app_service.currency}")
        stat_balance.remove_class("stat-positive", "stat-negative")
        stat_balance.add_class("stat-negative" if balance < 0 else "stat-positive")

        # Last 3 months operations
        now = date.today()
        month, year = now.month - 3, now.year
        if month <= 0:
            month, year = month + 12, year - 1
        recent_filter = OperationFilter(date_from=date(year, month, 1))
        recent_ops = self.app_service.get_operations(recent_filter)
        self.query_one("#stat-month-ops", Static).update(
            f"3 derniers mois: {len(recent_ops)} opérations"
        )

        # Uncategorized count
        uncategorized = self.app_service.get_uncategorized_operations()
        stat_uncat = self.query_one("#stat-uncategorized", Static)
        stat_uncat.update(f"Non catégorisées: {len(uncategorized)}")
        stat_uncat.remove_class("stat-positive", "stat-negative")
        stat_uncat.add_class("stat-negative" if uncategorized else "stat-positive")

        # Refresh tables with link data
        self.query_one("#dashboard-table", OperationTable).load_operations(
            recent_ops, links, targets
        )
        self.query_one("#operations-table", OperationTable).load_operations(
            self.app_service.get_operations(), links, targets
        )
        # Refresh import widget
        import_widget = self.query_one("#import-widget", ImportWidget)
        import_widget.set_app_service(self.app_service)

        # Refresh forecast widget
        forecast_widget = self.query_one("#forecast-widget", ForecastWidget)
        forecast_widget.set_app_service(self.app_service)

        # Refresh budgets widget
        budgets_widget = self.query_one("#budgets-widget", BudgetsWidget)
        budgets_widget.set_app_service(self.app_service)

        # Refresh planned operations widget
        planned_ops_widget = self.query_one(
            "#planned-ops-widget", PlannedOperationsWidget
        )
        planned_ops_widget.set_app_service(self.app_service)

    def action_refresh_data(self) -> None:
        """Refresh data from the database."""
        if self._persistent_account is not None:
            self._persistent_account.reload()
            self._refresh_screens()

    def save_changes(self) -> None:
        """Save changes to the database."""
        if self._persistent_account:
            self._persistent_account.save()
            self.notify("Modifications enregistrées")

    def on_data_refresh_requested(self, event: DataRefreshRequested) -> None:
        """Handle data refresh request from child components."""
        event.stop()
        self.action_refresh_data()

    def on_save_requested(self, event: SaveRequested) -> None:
        """Handle save request from child components."""
        event.stop()
        self.save_changes()

    def on_import_widget_browse_requested(
        self, event: ImportWidget.BrowseRequested
    ) -> None:
        """Handle browse request from import widget."""
        event.stop()
        # Start in inbox directory if it exists, otherwise home
        start_path = self.app_service.inbox_path
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
                self._persistent_account.reload()
            self._refresh_screens()

    def _on_file_selected(self, path: Path | None) -> None:
        """Handle file selection from browser."""
        if path is None:
            return
        import_widget = self.query_one("#import-widget", ImportWidget)
        import_widget.set_file_path(path)

    def action_categorize(self) -> None:
        """Open category selection for selected operations."""
        # Get the active tab and prioritize its table
        tabbed = self.query_one(TabbedContent)
        active_tab = tabbed.active

        # Map tab IDs to table IDs
        tab_to_table = {
            "dashboard": "#dashboard-table",
            "operations": "#operations-table",
        }

        # Try active tab's table first, then others
        table_order = [tab_to_table.get(active_tab, "#operations-table")]
        for table_id in ("#operations-table", "#dashboard-table"):
            if table_id not in table_order:
                table_order.append(table_id)

        for table_id in table_order:
            try:
                table = self.query_one(table_id, OperationTable)
            except NoMatches:
                continue
            if operations := table.get_selected_operations():
                self._categorizing_operation_ids = tuple(
                    op.unique_id for op in operations
                )
                # Get similar operations and suggestion based on first operation
                first_op = operations[0]
                similar = tuple(self.app_service.find_similar_operations(first_op))
                suggested = self.app_service.suggest_category(first_op)

                self.push_screen(
                    CategoryModal(
                        operations,
                        similar_operations=similar,
                        suggested_category=suggested,
                    ),
                    self._on_category_selected,
                )
                return

        self.notify("Aucune opération sélectionnée", severity="warning")

    def _on_category_selected(self, category: Category | None) -> None:
        """Handle category selection from modal."""
        if category is None or not self._categorizing_operation_ids:
            return

        results = self.app_service.categorize_operations(
            self._categorizing_operation_ids, category
        )

        if not results:
            self.notify("Aucune opération trouvée", severity="error")
            return

        self.save_changes()
        # Reload data from database and refresh all screens
        if self._persistent_account:
            self._persistent_account.reload()
        self._refresh_screens()

        # Clear selection in all tables
        for table_id in ("#dashboard-table", "#operations-table"):
            try:
                table = self.query_one(table_id, OperationTable)
                table.clear_selection()
            except NoMatches:
                pass

        # Build notification message
        links_created = sum(1 for r in results if r.new_link is not None)
        if len(results) == 1:
            message = f"Catégorie '{category.value}' assignée"
            if links_created:
                message += " (lien créé)"
        else:
            message = f"{len(results)} opérations catégorisées '{category.value}'"
            if links_created:
                message += f" ({links_created} lien(s) créé(s))"
        self.notify(message)

        # Reset state
        self._categorizing_operation_ids = ()

    def action_link_operation(self) -> None:
        """Open link modal for selected operations."""
        # Get the active tab and prioritize its table
        tabbed = self.query_one(TabbedContent)
        active_tab = tabbed.active

        # Map tab IDs to table IDs
        tab_to_table = {
            "dashboard": "#dashboard-table",
            "operations": "#operations-table",
        }

        # Try active tab's table first, then others
        table_order = [tab_to_table.get(active_tab, "#operations-table")]
        for table_id in ("#operations-table", "#dashboard-table"):
            if table_id not in table_order:
                table_order.append(table_id)

        for table_id in table_order:
            try:
                table = self.query_one(table_id, OperationTable)
            except NoMatches:
                continue
            if operations := table.get_selected_operations():
                self._linking_operations = operations

                # Get current link for first operation (for display)
                current_link = self.app_service.get_link_for_operation(
                    operations[0].unique_id
                )

                # Get all targets
                planned_operations = list(self.app_service.get_all_planned_operations())
                budgets = list(self.app_service.get_all_budgets())

                self.push_screen(
                    LinkTargetModal(
                        operations,
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
        if result is None or not self._linking_operations:
            return

        # Handle unlink - only unlink operations that have a link
        if result == "unlink":
            count = 0
            for op in self._linking_operations:
                if self.app_service.get_link_for_operation(op.unique_id):
                    self.app_service.delete_link(op.unique_id)
                    count += 1
            if count > 0:
                self.notify(f"{count} liaison(s) supprimée(s)")
            else:
                self.notify("Aucune liaison à supprimer", severity="warning")
            self._refresh_screens()
            self._linking_operations = ()
            return

        # Target selected - show iteration modal (use first operation for context)
        if isinstance(result, (PlannedOperation, Budget)):
            self.push_screen(
                LinkIterationModal(self._linking_operations[0], result),
                lambda date: self._on_iteration_selected(date, result),
            )

    def _on_iteration_selected(
        self,
        iteration_date: date | None,
        target: PlannedOperation | Budget,
    ) -> None:
        """Handle iteration selection from link modal."""
        if iteration_date is None or not self._linking_operations:
            return

        if target.id is None:
            self.notify("Cible invalide", severity="error")
            return

        # Create manual links for all selected operations
        count = 0
        for op in self._linking_operations:
            self.app_service.create_manual_link(op, target, iteration_date)
            count += 1

        if count == 1:
            self.notify(f"Opération liée à '{target.description}'")
        else:
            self.notify(f"{count} opérations liées à '{target.description}'")

        self._refresh_screens()
        self._linking_operations = ()

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
            self.app_service.delete_budget(event.budget.id)
            self.notify(f"Budget '{event.budget.description}' supprimé")
            self._refresh_budgets()
        except BudgetForecasterError as e:
            logger.error("Error deleting budget: %s", e)
            self.notify(f"Erreur: {e}", severity="error")
        except Exception:  # pylint: disable=broad-exception-caught
            logger.exception("Unexpected error deleting budget")
            self.notify("Une erreur inattendue est survenue", severity="error")

    def _on_budget_edited(self, budget: Budget | None) -> None:
        """Handle budget edit completion."""
        if budget is None:
            return

        try:
            if budget.id is None:
                # New budget
                self.app_service.add_budget(budget)
                self.notify(f"Budget '{budget.description}' créé")
            else:
                # Update existing
                self.app_service.update_budget(budget)
                self.notify(f"Budget '{budget.description}' modifié")
            self._refresh_budgets()
        except BudgetForecasterError as e:
            logger.error("Error saving budget: %s", e)
            self.notify(f"Erreur: {e}", severity="error")
        except Exception:  # pylint: disable=broad-exception-caught
            logger.exception("Unexpected error saving budget")
            self.notify("Une erreur inattendue est survenue", severity="error")

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
            self.app_service.delete_planned_operation(event.operation.id)
            self.notify(f"Opération '{event.operation.description}' supprimée")
            self._refresh_planned_operations()
        except BudgetForecasterError as e:
            logger.error("Error deleting planned operation: %s", e)
            self.notify(f"Erreur: {e}", severity="error")
        except Exception:  # pylint: disable=broad-exception-caught
            logger.exception("Unexpected error deleting planned operation")
            self.notify("Une erreur inattendue est survenue", severity="error")

    def on_planned_operations_widget_operation_split_requested(
        self, event: PlannedOperationsWidget.OperationSplitRequested
    ) -> None:
        """Handle planned operation split request."""
        event.stop()
        if event.operation.id is None:
            self.notify("Cannot split unsaved operation", severity="error")
            return

        # Get default date (next non-actualized iteration)
        default_date = self.app_service.get_next_non_actualized_iteration(
            LinkType.PLANNED_OPERATION, event.operation.id
        )

        self.push_screen(
            SplitOperationModal(event.operation, default_date),
            lambda result: self._on_planned_operation_split(event.operation, result),
        )

    def _on_planned_operation_split(
        self, operation: PlannedOperation, result: SplitResult | None
    ) -> None:
        """Handle planned operation split completion."""
        if result is None or operation.id is None:
            return

        try:
            new_op = self.app_service.split_planned_operation_at_date(
                operation_id=operation.id,
                split_date=result.split_date,
                new_amount=result.new_amount,
                new_period=result.new_period,
            )
            self.notify(
                f"Opération '{operation.description}' scindée "
                f"(nouvelle: #{new_op.id})"
            )
            self._refresh_planned_operations()
        except (ValueError, BudgetForecasterError) as e:
            logger.error("Error splitting planned operation: %s", e)
            self.notify(f"Erreur: {e}", severity="error")
        except Exception:  # pylint: disable=broad-exception-caught
            logger.exception("Unexpected error splitting planned operation")
            self.notify("Une erreur inattendue est survenue", severity="error")

    def on_budgets_widget_budget_split_requested(
        self, event: BudgetsWidget.BudgetSplitRequested
    ) -> None:
        """Handle budget split request."""
        event.stop()
        if event.budget.id is None:
            self.notify("Cannot split unsaved budget", severity="error")
            return

        # Get default date (next non-actualized iteration)
        default_date = self.app_service.get_next_non_actualized_iteration(
            LinkType.BUDGET, event.budget.id
        )

        self.push_screen(
            SplitOperationModal(event.budget, default_date),
            lambda result: self._on_budget_split(event.budget, result),
        )

    def _on_budget_split(self, budget: Budget, result: SplitResult | None) -> None:
        """Handle budget split completion."""
        if result is None or budget.id is None:
            return

        try:
            new_budget = self.app_service.split_budget_at_date(
                budget_id=budget.id,
                split_date=result.split_date,
                new_amount=result.new_amount,
                new_period=result.new_period,
                new_duration=result.new_duration,
            )
            self.notify(
                f"Budget '{budget.description}' scindé " f"(nouveau: #{new_budget.id})"
            )
            self._refresh_budgets()
        except (ValueError, BudgetForecasterError) as e:
            logger.error("Error splitting budget: %s", e)
            self.notify(f"Erreur: {e}", severity="error")
        except Exception:  # pylint: disable=broad-exception-caught
            logger.exception("Unexpected error splitting budget")
            self.notify("Une erreur inattendue est survenue", severity="error")

    def _on_planned_operation_edited(self, operation: PlannedOperation | None) -> None:
        """Handle planned operation edit completion."""
        if operation is None:
            return

        try:
            if operation.id is None:
                # New operation
                self.app_service.add_planned_operation(operation)
                self.notify(f"Opération '{operation.description}' créée")
            else:
                # Update existing
                self.app_service.update_planned_operation(operation)
                self.notify(f"Opération '{operation.description}' modifiée")
            self._refresh_planned_operations()
        except BudgetForecasterError as e:
            logger.error("Error saving planned operation: %s", e)
            self.notify(f"Erreur: {e}", severity="error")
        except Exception:  # pylint: disable=broad-exception-caught
            logger.exception("Unexpected error saving planned operation")
            self.notify("Une erreur inattendue est survenue", severity="error")

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
