"""Central application service orchestrating data flow between services.

This module contains the ApplicationService class that serves as a thin
facade for the TUI, delegating orchestration logic to focused use cases
while providing direct access to read-only service methods.
"""

import logging
from datetime import date, timedelta
from pathlib import Path
from typing import NamedTuple

from dateutil.relativedelta import relativedelta

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.date_range import RecurringDay
from budget_forecaster.core.types import (
    BudgetId,
    Category,
    ImportProgressCallback,
    IterationDate,
    LinkType,
    OperationId,
    PlannedOperationId,
    TargetId,
)
from budget_forecaster.domain.forecast.forecast import Forecast
from budget_forecaster.domain.operation.budget import Budget
from budget_forecaster.domain.operation.historic_operation import HistoricOperation
from budget_forecaster.domain.operation.operation_link import OperationLink
from budget_forecaster.domain.operation.planned_operation import PlannedOperation
from budget_forecaster.infrastructure.persistence.persistent_account import (
    PersistentAccount,
)
from budget_forecaster.services.account.account_analysis_report import (
    AccountAnalysisReport,
)
from budget_forecaster.services.forecast.forecast_service import (
    ForecastService,
    MonthlySummary,
)
from budget_forecaster.services.import_service import (
    ImportResult,
    ImportService,
    ImportSummary,
)
from budget_forecaster.services.operation.operation_link_service import (
    OperationLinkService,
)
from budget_forecaster.services.operation.operation_service import (
    OperationCategoryUpdate,
    OperationFilter,
    OperationService,
)
from budget_forecaster.services.use_cases import (
    CategorizeUseCase,
    ComputeForecastUseCase,
    ImportUseCase,
    ManageLinksUseCase,
    ManageTargetsUseCase,
    MatcherCache,
)

logger = logging.getLogger(__name__)


class UpcomingIteration(NamedTuple):
    """A single upcoming iteration of a planned operation."""

    iteration_date: date
    description: str
    amount: float
    currency: str
    period: relativedelta | None


def get_upcoming_iterations(
    planned_operations: tuple[PlannedOperation, ...],
    reference_date: date,
    horizon_days: int = 30,
) -> tuple[UpcomingIteration, ...]:
    """Get upcoming iterations from planned operations within a time horizon.

    Args:
        planned_operations: All planned operations.
        reference_date: The date to compute from (typically today).
        horizon_days: Number of days ahead to look.

    Returns:
        Upcoming iterations sorted by date ascending.
    """
    cutoff = reference_date + timedelta(days=horizon_days)
    iterations: list[UpcomingIteration] = []

    for op in planned_operations:
        period = (
            op.date_range.period if isinstance(op.date_range, RecurringDay) else None
        )
        for date_range in op.date_range.iterate_over_date_ranges(
            from_date=reference_date
        ):
            if date_range.start_date > cutoff:
                break
            if date_range.start_date >= reference_date:
                iterations.append(
                    UpcomingIteration(
                        iteration_date=date_range.start_date,
                        description=op.description,
                        amount=op.amount,
                        currency=op.currency,
                        period=period,
                    )
                )

    return tuple(sorted(iterations, key=lambda it: it.iteration_date))


class ApplicationService:  # pylint: disable=too-many-instance-attributes,too-many-public-methods
    """Thin facade delegating orchestration to focused use cases.

    This service coordinates data flow between specialized use cases:
    - ImportUseCase: Import operations from bank exports
    - CategorizeUseCase: Categorize operations with heuristic link management
    - ManageTargetsUseCase: CRUD for planned operations/budgets + split
    - ManageLinksUseCase: Manual link creation
    - ComputeForecastUseCase: Forecast report computation

    Read-only methods are delegated directly to the underlying services.
    """

    def __init__(
        self,
        persistent_account: PersistentAccount,
        import_service: ImportService,
        operation_service: OperationService,
        forecast_service: ForecastService,
        operation_link_service: OperationLinkService,
    ) -> None:
        """Initialize the application service.

        Args:
            persistent_account: The persistent account for accessing operations.
            import_service: Service for importing bank exports.
            operation_service: Service for operation CRUD.
            forecast_service: Service for forecast and target CRUD.
            operation_link_service: Service for link management.
        """
        # Shared dependency
        matcher_cache = MatcherCache(forecast_service)

        self._import_uc = ImportUseCase(
            import_service, persistent_account, operation_link_service, matcher_cache
        )
        self._categorize_uc = CategorizeUseCase(
            operation_service, operation_link_service, matcher_cache
        )
        self._targets_uc = ManageTargetsUseCase(
            forecast_service,
            persistent_account,
            operation_link_service,
            matcher_cache,
        )
        self._links_uc = ManageLinksUseCase(operation_link_service)
        self._forecast_uc = ComputeForecastUseCase(
            forecast_service, operation_link_service
        )

        # Direct service references for pure delegations
        self._operation_service = operation_service
        self._forecast_service = forecast_service
        self._import_service = import_service
        self._operation_link_service = operation_link_service

    # -------------------------------------------------------------------------
    # Import operations (delegated to ImportUseCase)
    # -------------------------------------------------------------------------

    def import_file(self, path: Path, move_to_processed: bool = False) -> ImportResult:
        """Import a bank export file and create heuristic links."""
        return self._import_uc.import_file(path, move_to_processed)

    def import_from_inbox(
        self,
        on_progress: ImportProgressCallback | None = None,
    ) -> ImportSummary:
        """Import all bank exports from the inbox folder."""
        return self._import_uc.import_from_inbox(on_progress)

    # -------------------------------------------------------------------------
    # Categorization (delegated to CategorizeUseCase)
    # -------------------------------------------------------------------------

    def categorize_operations(
        self, operation_ids: tuple[OperationId, ...], category: Category
    ) -> tuple[OperationCategoryUpdate, ...]:
        """Categorize operations and create heuristic links."""
        return self._categorize_uc.categorize_operations(operation_ids, category)

    # -------------------------------------------------------------------------
    # Planned operation CRUD (delegated to ManageTargetsUseCase)
    # -------------------------------------------------------------------------

    def add_planned_operation(self, op: PlannedOperation) -> PlannedOperation:
        """Add a new planned operation and create heuristic links."""
        return self._targets_uc.add_planned_operation(op)

    def update_planned_operation(self, op: PlannedOperation) -> PlannedOperation:
        """Update a planned operation and recalculate its links."""
        return self._targets_uc.update_planned_operation(op)

    def delete_planned_operation(self, op_id: PlannedOperationId) -> None:
        """Delete a planned operation and its links."""
        self._targets_uc.delete_planned_operation(op_id)

    # -------------------------------------------------------------------------
    # Budget CRUD (delegated to ManageTargetsUseCase)
    # -------------------------------------------------------------------------

    def add_budget(self, budget: Budget) -> Budget:
        """Add a new budget and create heuristic links."""
        return self._targets_uc.add_budget(budget)

    def update_budget(self, budget: Budget) -> Budget:
        """Update a budget and recalculate its links."""
        return self._targets_uc.update_budget(budget)

    def delete_budget(self, budget_id: BudgetId) -> None:
        """Delete a budget and its links."""
        self._targets_uc.delete_budget(budget_id)

    # -------------------------------------------------------------------------
    # Operation read methods (delegated to OperationService)
    # -------------------------------------------------------------------------

    @property
    def balance(self) -> float:
        """Get the current account balance."""
        return self._operation_service.balance

    @property
    def currency(self) -> str:
        """Get the account currency."""
        return self._operation_service.currency

    def get_operations(
        self, filter_: OperationFilter | None = None
    ) -> tuple[HistoricOperation, ...]:
        """Get operations, optionally filtered."""
        return tuple(self._operation_service.get_operations(filter_))

    def get_uncategorized_operations(self) -> tuple[HistoricOperation, ...]:
        """Get all uncategorized operations."""
        return tuple(self._operation_service.get_uncategorized_operations())

    def get_operation_by_id(self, operation_id: int) -> HistoricOperation:
        """Get a single operation by its ID."""
        return self._operation_service.get_operation_by_id(operation_id)

    def suggest_category(self, operation: HistoricOperation) -> Category | None:
        """Suggest a category based on similar operations."""
        return self._operation_service.suggest_category(operation)

    @property
    def operations(self) -> tuple[HistoricOperation, ...]:
        """Get all operations from the account."""
        return self._operation_service.operations

    def find_similar_operations(
        self, operation: HistoricOperation, limit: int = 5
    ) -> list[HistoricOperation]:
        """Find operations with similar descriptions."""
        return self._operation_service.find_similar_operations(operation, limit)

    def get_category_totals(
        self, filter_criteria: OperationFilter | None = None
    ) -> dict[Category, float]:
        """Get total amounts per category."""
        return self._operation_service.get_category_totals(filter_criteria)

    # -------------------------------------------------------------------------
    # Link methods (delegated to ManageLinksUseCase / OperationLinkService)
    # -------------------------------------------------------------------------

    def get_all_links(self) -> tuple[OperationLink, ...]:
        """Get all operation links."""
        return self._operation_link_service.get_all_links()

    def get_link_for_operation(self, operation_id: int) -> OperationLink | None:
        """Get the link for a specific operation."""
        return self._operation_link_service.get_link_for_operation(operation_id)

    def delete_link(self, operation_id: int) -> None:
        """Delete a link for an operation."""
        self._operation_link_service.delete_link(operation_id)

    def create_manual_link(
        self,
        operation: HistoricOperation,
        target: PlannedOperation | Budget,
        iteration_date: date,
    ) -> OperationLink:
        """Create a manual link between an operation and a target."""
        return self._links_uc.create_manual_link(operation, target, iteration_date)

    # -------------------------------------------------------------------------
    # Forecast read methods (delegated to ForecastService / ComputeForecastUseCase)
    # -------------------------------------------------------------------------

    def get_all_planned_operations(self) -> tuple[PlannedOperation, ...]:
        """Get all planned operations sorted alphabetically by description."""
        operations = self._forecast_service.get_all_planned_operations()
        return tuple(sorted(operations, key=lambda op: op.description.lower()))

    def get_upcoming_planned_iterations(
        self, horizon_days: int = 30
    ) -> tuple[UpcomingIteration, ...]:
        """Get upcoming iterations of planned operations within a time horizon.

        Args:
            horizon_days: Number of days ahead to look.

        Returns:
            Upcoming iterations sorted by date ascending.
        """
        planned_ops = self.get_all_planned_operations()
        return get_upcoming_iterations(planned_ops, date.today(), horizon_days)

    def get_all_budgets(self) -> tuple[Budget, ...]:
        """Get all budgets sorted alphabetically by description."""
        budgets = self._forecast_service.get_all_budgets()
        return tuple(sorted(budgets, key=lambda b: b.description.lower()))

    def get_budget_by_id(self, budget_id: BudgetId) -> Budget:
        """Get a budget by ID."""
        return self._forecast_service.get_budget_by_id(budget_id)

    def get_planned_operation_by_id(
        self, op_id: PlannedOperationId
    ) -> PlannedOperation:
        """Get a planned operation by ID."""
        return self._forecast_service.get_planned_operation_by_id(op_id)

    def load_forecast(self) -> Forecast:
        """Load the forecast from the database."""
        return self._forecast_service.load_forecast()

    def compute_report(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> AccountAnalysisReport:
        """Compute the forecast report."""
        return self._forecast_uc.compute_report(start_date, end_date)

    def get_balance_evolution_summary(
        self,
    ) -> list[tuple[date, float]]:
        """Get balance evolution from the last computed report."""
        return self._forecast_service.get_balance_evolution_summary()

    def get_monthly_summary(self) -> list[MonthlySummary]:
        """Get monthly summary from the last computed report."""
        return self._forecast_service.get_monthly_summary()

    def get_category_statistics(self) -> list[tuple[str, float, float]]:
        """Get category statistics from the report."""
        return self._forecast_service.get_category_statistics()

    # -------------------------------------------------------------------------
    # Import read methods (delegated to ImportService)
    # -------------------------------------------------------------------------

    @property
    def inbox_path(self) -> Path:
        """Get the inbox path for imports."""
        return self._import_service.inbox_path

    def has_pending_imports(self) -> bool:
        """Check if there are pending imports in the inbox."""
        return self._import_service.has_pending_imports

    def get_pending_import_count(self) -> int:
        """Get the count of pending imports."""
        return self._import_service.pending_import_count

    def get_supported_exports_in_inbox(self) -> list[Path]:
        """Get list of supported export files in the inbox."""
        return self._import_service.get_supported_exports_in_inbox()

    def is_supported_export(self, path: Path) -> bool:
        """Check if a path is a supported bank export."""
        return self._import_service.is_supported_export(path)

    # -------------------------------------------------------------------------
    # Report access
    # -------------------------------------------------------------------------

    @property
    def report(self) -> AccountAnalysisReport | None:
        """Get the last computed report, if any."""
        return self._forecast_service.report

    # -------------------------------------------------------------------------
    # Split operations (delegated to ManageTargetsUseCase)
    # -------------------------------------------------------------------------

    def get_next_non_actualized_iteration(
        self,
        target_type: LinkType,
        target_id: TargetId,
    ) -> IterationDate | None:
        """Find the next iteration that has no linked operation."""
        return self._targets_uc.get_next_non_actualized_iteration(
            target_type, target_id
        )

    def split_planned_operation_at_date(
        self,
        operation_id: OperationId,
        split_date: date,
        new_amount: Amount | None = None,
        new_period: relativedelta | None = None,
    ) -> PlannedOperation:
        """Split a planned operation at the given date."""
        return self._targets_uc.split_planned_operation_at_date(
            operation_id, split_date, new_amount, new_period
        )

    def split_budget_at_date(
        self,
        budget_id: BudgetId,
        split_date: date,
        new_amount: Amount | None = None,
        new_period: relativedelta | None = None,
        new_duration: relativedelta | None = None,
    ) -> Budget:
        """Split a budget at the given date."""
        return self._targets_uc.split_budget_at_date(
            budget_id, split_date, new_amount, new_period, new_duration
        )
