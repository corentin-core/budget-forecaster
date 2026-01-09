"""Main TUI application for budget forecaster."""

from datetime import datetime
from pathlib import Path
from typing import Any

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, OptionList, Static, TabbedContent, TabPane
from textual.widgets.option_list import Option

from budget_forecaster.account.persistent_account import PersistentAccount
from budget_forecaster.config import Config
from budget_forecaster.operation_range.historic_operation import HistoricOperation
from budget_forecaster.services import OperationFilter, OperationService
from budget_forecaster.tui.widgets.operation_table import OperationTable
from budget_forecaster.types import Category


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
        from textual.containers import Vertical

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
        self._categorizing_operation_id: int | None = None

    def _load_config(self) -> None:
        """Load configuration and account."""
        self._config = Config()
        self._config.parse(self._config_path)

        self._persistent_account = PersistentAccount(
            database_path=self._config.database_path
        )
        self._persistent_account.load()

        self._operation_service = OperationService(self._persistent_account)

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

    def _refresh_screens(self) -> None:
        """Refresh all screens with current data."""
        service = self.operation_service

        # Update dashboard stats
        balance = service.balance
        balance_class = "stat-negative" if balance < 0 else "stat-positive"
        stat_balance = self.query_one("#stat-balance", Static)
        stat_balance.update(f"Solde: {balance:,.2f} {service.currency}")
        stat_balance.remove_class("stat-positive", "stat-negative")
        stat_balance.add_class(balance_class)

        # Last 3 months operations
        now = datetime.now()
        # Calculate 3 months ago (handle year boundary)
        month = now.month - 3
        year = now.year
        if month <= 0:
            month += 12
            year -= 1
        three_months_ago = datetime(year, month, 1)
        recent_filter = OperationFilter(date_from=three_months_ago)
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

        # Refresh dashboard table with recent operations (last 3 months)
        dashboard_table = self.query_one("#dashboard-table", OperationTable)
        dashboard_table.load_operations(recent_ops)

        # Refresh operations table with all operations
        operations_table = self.query_one("#operations-table", OperationTable)
        operations_table.load_operations(service.get_operations())

        # Refresh categorize table with uncategorized operations
        categorize_table = self.query_one("#categorize-table", OperationTable)
        categorize_table.load_operations(uncategorized)

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
        for table_id in ["#categorize-table", "#operations-table", "#dashboard-table"]:
            if table_id not in table_order:
                table_order.append(table_id)

        for table_id in table_order:
            table = self.query_one(table_id, OperationTable)
            operation = table.get_selected_operation()
            if operation:
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
