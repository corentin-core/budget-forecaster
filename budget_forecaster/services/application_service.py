"""Central application service orchestrating data flow between services.

This module contains the ApplicationService class that serves as the single
entry point for the TUI, coordinating imports, categorization, and forecast
management while maintaining cached matchers for efficient link creation.
"""

import logging
from datetime import date, datetime
from pathlib import Path

from dateutil.relativedelta import relativedelta

from budget_forecaster.account.account_analysis_report import AccountAnalysisReport
from budget_forecaster.account.persistent_account import PersistentAccount
from budget_forecaster.amount import Amount
from budget_forecaster.forecast.forecast import Forecast
from budget_forecaster.operation_range.budget import Budget
from budget_forecaster.operation_range.historic_operation import HistoricOperation
from budget_forecaster.operation_range.operation_link import OperationLink
from budget_forecaster.operation_range.operation_matcher import OperationMatcher
from budget_forecaster.operation_range.planned_operation import PlannedOperation
from budget_forecaster.services.forecast_service import (
    ForecastService,
    MonthlySummary,
)
from budget_forecaster.services.import_service import (
    ImportResult,
    ImportService,
    ImportSummary,
)
from budget_forecaster.services.operation_link_service import OperationLinkService
from budget_forecaster.services.operation_service import (
    OperationCategoryUpdate,
    OperationFilter,
    OperationService,
)
from budget_forecaster.time_range import PeriodicTimeRange
from budget_forecaster.types import (
    BudgetId,
    Category,
    ImportProgressCallback,
    LinkType,
    MatcherKey,
    PlannedOperationId,
)

logger = logging.getLogger(__name__)


class ApplicationService:  # pylint: disable=too-many-public-methods
    """Central orchestrator for the budget forecaster application.

    This service coordinates data flow between specialized services:
    - ImportService: Import operations from bank exports
    - OperationService: CRUD operations on historic operations
    - ForecastService: CRUD operations on planned operations and budgets
    - OperationLinkService: Manage links between operations and targets

    The ApplicationService maintains a cache of matchers for efficient
    link creation during imports and categorization.
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
        self._persistent_account = persistent_account
        self._import_service = import_service
        self._operation_service = operation_service
        self._forecast_service = forecast_service
        self._operation_link_service = operation_link_service

        # Lazy-loaded matcher cache
        self._matchers: dict[MatcherKey, OperationMatcher] | None = None

    # -------------------------------------------------------------------------
    # Matcher cache management
    # -------------------------------------------------------------------------

    def _build_matchers(
        self,
    ) -> dict[MatcherKey, OperationMatcher]:
        """Build matchers for all planned operations and budgets.

        Returns:
            Dict mapping (target_type, target_id) to OperationMatcher.
        """
        matchers: dict[MatcherKey, OperationMatcher] = {}

        for planned_op in self._forecast_service.get_all_planned_operations():
            if planned_op.id is not None:
                key = MatcherKey(LinkType.PLANNED_OPERATION, planned_op.id)
                matchers[key] = planned_op.matcher

        for budget in self._forecast_service.get_all_budgets():
            if budget.id is not None:
                key = MatcherKey(LinkType.BUDGET, budget.id)
                matchers[key] = budget.matcher

        logger.debug(
            "Built %d matchers (%d planned operations, %d budgets)",
            len(matchers),
            sum(1 for k in matchers if k.link_type == LinkType.PLANNED_OPERATION),
            sum(1 for k in matchers if k.link_type == LinkType.BUDGET),
        )

        return matchers

    def _get_matchers(
        self,
    ) -> dict[MatcherKey, OperationMatcher]:
        """Get the matcher cache, building it if necessary."""
        if self._matchers is None:
            self._matchers = self._build_matchers()
        return self._matchers

    def _add_matcher(self, target: PlannedOperation | Budget) -> None:
        """Add or update a matcher for a target."""
        if target.id is None:
            return

        matchers = self._get_matchers()
        if isinstance(target, PlannedOperation):
            key = MatcherKey(LinkType.PLANNED_OPERATION, target.id)
        else:
            key = MatcherKey(LinkType.BUDGET, target.id)
        matchers[key] = target.matcher

    def _remove_matcher(self, key: MatcherKey) -> None:
        """Remove a matcher from the cache."""
        matchers = self._get_matchers()
        matchers.pop(key, None)

    # -------------------------------------------------------------------------
    # Import operations
    # -------------------------------------------------------------------------

    def import_file(self, path: Path, move_to_processed: bool = False) -> ImportResult:
        """Import a bank export file and create heuristic links.

        Args:
            path: Path to the export file.
            move_to_processed: If True, move file to processed/ after import.

        Returns:
            ImportResult with the outcome.
        """
        result = self._import_service.import_file(path, move_to_processed)

        if result.success:
            # Create heuristic links for newly imported operations
            operations = self._persistent_account.account.operations
            if matchers := self._get_matchers():
                created_links = self._operation_link_service.create_heuristic_links(
                    operations, matchers
                )
                logger.info(
                    "Created %d heuristic links after import", len(created_links)
                )

        return result

    def import_from_inbox(
        self,
        on_progress: ImportProgressCallback | None = None,
    ) -> ImportSummary:
        """Import all bank exports from the inbox folder.

        Args:
            on_progress: Optional callback for progress updates.

        Returns:
            ImportSummary with the results.
        """
        summary = self._import_service.import_from_inbox(on_progress)

        if summary.successful_imports > 0:
            # Create heuristic links for all newly imported operations
            operations = self._persistent_account.account.operations
            if matchers := self._get_matchers():
                created_links = self._operation_link_service.create_heuristic_links(
                    operations, matchers
                )
                logger.info(
                    "Created %d heuristic links after inbox import", len(created_links)
                )

        return summary

    # -------------------------------------------------------------------------
    # Categorization operations
    # -------------------------------------------------------------------------

    def categorize_operations(
        self, operation_ids: tuple[int, ...], category: Category
    ) -> tuple[OperationCategoryUpdate, ...]:
        """Categorize one or more operations and create heuristic links.

        When a category changes:
        1. Delete existing heuristic link (if any) - manual links are preserved
        2. Batch create new heuristic links for all changed operations

        Args:
            operation_ids: Tuple of operation IDs to categorize.
            category: The category to assign to all operations.

        Returns:
            Tuple of OperationCategoryUpdate for each successfully updated operation.
            Operations not found are silently skipped.
        """
        results: list[OperationCategoryUpdate] = []
        changed_operations: list[HistoricOperation] = []

        for op_id in operation_ids:
            if (op := self._operation_service.get_operation_by_id(op_id)) is None:
                continue

            old_category = op.category
            if (
                updated := self._operation_service.categorize_operation(op_id, category)
            ) is None:
                continue

            if category_changed := old_category != category:
                # Check and delete existing heuristic link
                existing = self._operation_link_service.get_link_for_operation(op_id)
                if existing is not None and not existing.is_manual:
                    self._operation_link_service.delete_link(op_id)
                    changed_operations.append(updated)
                elif existing is None:
                    changed_operations.append(updated)

            results.append(OperationCategoryUpdate(updated, category_changed, None))

        # Batch create heuristic links for all changed operations
        created_links: dict[int, OperationLink] = {}
        if changed_operations and (matchers := self._get_matchers()):
            for link in self._operation_link_service.create_heuristic_links(
                tuple(changed_operations), matchers
            ):
                created_links[link.operation_unique_id] = link

        # Enrich results with created links
        return tuple(
            OperationCategoryUpdate(
                r.operation,
                r.category_changed,
                created_links.get(r.operation.unique_id),
            )
            if r.operation.unique_id in created_links
            else r
            for r in results
        )

    # -------------------------------------------------------------------------
    # Planned operation CRUD
    # -------------------------------------------------------------------------

    def add_planned_operation(self, op: PlannedOperation) -> PlannedOperation:
        """Add a new planned operation and create heuristic links.

        Args:
            op: Planned operation to add (id should be None).

        Returns:
            The newly created planned operation with its assigned ID.
        """
        new_op = self._forecast_service.add_planned_operation(op)

        # Add matcher for new target
        self._add_matcher(new_op)

        # Create links for matching operations
        if new_op.id is not None:
            operations = self._persistent_account.account.operations
            created_links = self._operation_link_service.create_heuristic_links(
                operations,
                {MatcherKey(LinkType.PLANNED_OPERATION, new_op.id): new_op.matcher},
            )
            logger.debug(
                "Created %d links for new planned operation %d",
                len(created_links),
                new_op.id,
            )

        return new_op

    def update_planned_operation(self, op: PlannedOperation) -> PlannedOperation:
        """Update a planned operation and recalculate its links.

        Args:
            op: Planned operation with updated values (id must not be None).

        Returns:
            The updated planned operation.
        """
        if op.id is None:
            raise ValueError("Planned operation must have a valid ID for update")

        updated_op = self._forecast_service.update_planned_operation(op)

        # Update matcher
        self._add_matcher(updated_op)

        # Recalculate links: delete automatic links and recreate
        self._operation_link_service.delete_automatic_links_for_target(
            LinkType.PLANNED_OPERATION, op.id
        )
        operations = self._persistent_account.account.operations
        created_links = self._operation_link_service.create_heuristic_links(
            operations,
            {MatcherKey(LinkType.PLANNED_OPERATION, op.id): updated_op.matcher},
        )
        logger.debug(
            "Recalculated %d links for planned operation %d",
            len(created_links),
            op.id,
        )

        return updated_op

    def delete_planned_operation(self, op_id: PlannedOperationId) -> None:
        """Delete a planned operation and its links.

        Args:
            op_id: ID of the planned operation to delete.
        """
        # Delete ALL links for this target (see #76)
        self._operation_link_service.delete_links_for_target(
            LinkType.PLANNED_OPERATION, op_id
        )

        # Remove matcher
        self._remove_matcher(MatcherKey(LinkType.PLANNED_OPERATION, op_id))

        # Delete the planned operation
        self._forecast_service.delete_planned_operation(op_id)

    # -------------------------------------------------------------------------
    # Budget CRUD
    # -------------------------------------------------------------------------

    def add_budget(self, budget: Budget) -> Budget:
        """Add a new budget and create heuristic links.

        Args:
            budget: Budget to add (id should be None).

        Returns:
            The newly created budget with its assigned ID.
        """
        new_budget = self._forecast_service.add_budget(budget)

        # Add matcher for new target
        self._add_matcher(new_budget)

        # Create links for matching operations
        if new_budget.id is not None:
            operations = self._persistent_account.account.operations
            created_links = self._operation_link_service.create_heuristic_links(
                operations,
                {MatcherKey(LinkType.BUDGET, new_budget.id): new_budget.matcher},
            )
            logger.debug(
                "Created %d links for new budget %d",
                len(created_links),
                new_budget.id,
            )

        return new_budget

    def update_budget(self, budget: Budget) -> Budget:
        """Update a budget and recalculate its links.

        Args:
            budget: Budget with updated values (id must not be None).

        Returns:
            The updated budget.
        """
        if budget.id is None:
            raise ValueError("Budget must have a valid ID for update")

        updated_budget = self._forecast_service.update_budget(budget)

        # Update matcher
        self._add_matcher(updated_budget)

        # Recalculate links: delete automatic links and recreate
        self._operation_link_service.delete_automatic_links_for_target(
            LinkType.BUDGET, budget.id
        )
        operations = self._persistent_account.account.operations
        created_links = self._operation_link_service.create_heuristic_links(
            operations,
            {MatcherKey(LinkType.BUDGET, budget.id): updated_budget.matcher},
        )
        logger.debug(
            "Recalculated %d links for budget %d",
            len(created_links),
            budget.id,
        )

        return updated_budget

    def delete_budget(self, budget_id: BudgetId) -> None:
        """Delete a budget and its links.

        Args:
            budget_id: ID of the budget to delete.
        """
        # Delete ALL links for this target (see #76)
        self._operation_link_service.delete_links_for_target(LinkType.BUDGET, budget_id)

        # Remove matcher
        self._remove_matcher(MatcherKey(LinkType.BUDGET, budget_id))

        # Delete the budget
        self._forecast_service.delete_budget(budget_id)

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
        """Get operations, optionally filtered.

        Args:
            filter_: Optional filter to apply.

        Returns:
            Tuple of matching operations.
        """
        return tuple(self._operation_service.get_operations(filter_))

    def get_uncategorized_operations(self) -> tuple[HistoricOperation, ...]:
        """Get all uncategorized operations."""
        return tuple(self._operation_service.get_uncategorized_operations())

    def get_operation_by_id(self, operation_id: int) -> HistoricOperation | None:
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
    # Link read methods (delegated to OperationLinkService)
    # -------------------------------------------------------------------------

    def get_all_links(self) -> tuple[OperationLink, ...]:
        """Get all operation links."""
        return self._operation_link_service.get_all_links()

    def get_link_for_operation(self, operation_id: int) -> OperationLink | None:
        """Get the link for a specific operation.

        Args:
            operation_id: The operation's unique ID.

        Returns:
            The link if found, None otherwise.
        """
        return self._operation_link_service.get_link_for_operation(operation_id)

    def delete_link(self, operation_id: int) -> None:
        """Delete a link for an operation.

        Args:
            operation_id: The operation's unique ID.
        """
        self._operation_link_service.delete_link(operation_id)

    def create_manual_link(
        self,
        operation: HistoricOperation,
        target: PlannedOperation | Budget,
        iteration_date: datetime,
    ) -> OperationLink:
        """Create a manual link between an operation and a target.

        Args:
            operation: The historic operation to link.
            target: The planned operation or budget to link to.
            iteration_date: The iteration date for the link.

        Returns:
            The created link.

        Raises:
            ValueError: If target has no ID.
        """
        if target.id is None:
            raise ValueError("Target must have an ID")

        target_type = (
            LinkType.PLANNED_OPERATION
            if isinstance(target, PlannedOperation)
            else LinkType.BUDGET
        )

        link = OperationLink(
            operation_unique_id=operation.unique_id,
            target_type=target_type,
            target_id=target.id,
            iteration_date=iteration_date,
            is_manual=True,
        )
        self._operation_link_service.upsert_link(link)
        return link

    # -------------------------------------------------------------------------
    # Forecast read methods (delegated to ForecastService)
    # -------------------------------------------------------------------------

    def get_all_planned_operations(self) -> tuple[PlannedOperation, ...]:
        """Get all planned operations sorted alphabetically by description."""
        operations = self._forecast_service.get_all_planned_operations()
        return tuple(sorted(operations, key=lambda op: op.description.lower()))

    def get_all_budgets(self) -> tuple[Budget, ...]:
        """Get all budgets sorted alphabetically by description."""
        budgets = self._forecast_service.get_all_budgets()
        return tuple(sorted(budgets, key=lambda b: b.description.lower()))

    def get_budget_by_id(self, budget_id: BudgetId) -> Budget | None:
        """Get a budget by ID."""
        return self._forecast_service.get_budget_by_id(budget_id)

    def get_planned_operation_by_id(
        self, op_id: PlannedOperationId
    ) -> PlannedOperation | None:
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
        """Compute the forecast report.

        Args:
            start_date: Start date for the report (default: today).
            end_date: End date for the report (default: 1 year from start).

        Returns:
            The computed analysis report.
        """
        links = self._operation_link_service.get_all_links()
        return self._forecast_service.compute_report(start_date, end_date, links)

    def get_balance_evolution_summary(
        self,
    ) -> list[tuple[date, float]]:
        """Get balance evolution from the last computed report."""
        return self._forecast_service.get_balance_evolution_summary()

    def get_monthly_summary(self) -> list[MonthlySummary]:
        """Get monthly summary from the last computed report."""
        return self._forecast_service.get_monthly_summary()

    def get_category_statistics(self) -> list[tuple[str, float, float]]:
        """Get category statistics (category, total, monthly_average) from the report."""
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
    # Report access (for widgets that need direct report data)
    # -------------------------------------------------------------------------

    @property
    def report(self) -> AccountAnalysisReport | None:
        """Get the last computed report, if any."""
        return self._forecast_service.report

    # -------------------------------------------------------------------------
    # Split operations (for modifying recurring elements from a date)
    # -------------------------------------------------------------------------

    def get_next_non_actualized_iteration(
        self,
        target_type: LinkType,
        target_id: int,
    ) -> datetime | None:
        """Find the next iteration that has no linked operation.

        Args:
            target_type: Type of target (PLANNED_OPERATION or BUDGET).
            target_id: ID of the target.

        Returns:
            The date of the next non-actualized iteration, or None if not found.
        """
        # Get the target
        if target_type == LinkType.PLANNED_OPERATION:
            target: PlannedOperation | Budget | None = (
                self._forecast_service.get_planned_operation_by_id(target_id)
            )
        else:
            target = self._forecast_service.get_budget_by_id(target_id)

        if target is None or target.id is None:
            return None

        # Must be periodic
        if not isinstance(target.time_range, PeriodicTimeRange):
            return None

        # Get all links for this target
        links = self._operation_link_service.load_links_for_target(target)
        actualized_dates = {link.iteration_date for link in links}

        # Find the first future iteration that is not actualized
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        for time_range in target.time_range.iterate_over_time_ranges(today):
            if time_range.initial_date not in actualized_dates:
                return time_range.initial_date

        return None

    def split_planned_operation_at_date(
        self,
        operation_id: int,
        split_date: datetime,
        new_amount: Amount | None = None,
        new_period: relativedelta | None = None,
    ) -> PlannedOperation:
        """Split a planned operation at the given date.

        This terminates the original operation the day before split_date,
        creates a new operation starting at split_date with the updated values,
        and migrates links for iterations >= split_date to the new operation.

        Args:
            operation_id: ID of the planned operation to split.
            split_date: Date from which the new values apply.
            new_amount: New amount (if None, keeps the original).
            new_period: New period (if None, keeps the original).

        Returns:
            The newly created PlannedOperation.

        Raises:
            ValueError: If the operation doesn't exist or isn't periodic.
        """
        if (
            original := self._forecast_service.get_planned_operation_by_id(operation_id)
        ) is None:
            raise ValueError(f"Planned operation {operation_id} not found")

        terminated, continuation = original.split_at(split_date, new_amount, new_period)

        self._forecast_service.update_planned_operation(terminated)
        new_op = self._forecast_service.add_planned_operation(continuation)
        self._add_matcher(new_op)

        if new_op.id is not None:
            self._migrate_links_after_split(
                LinkType.PLANNED_OPERATION,
                operation_id,
                new_op.id,
                split_date,
            )

        logger.info(
            "Split planned operation %d at %s, created new operation %d",
            operation_id,
            split_date.date(),
            new_op.id,
        )

        return new_op

    def split_budget_at_date(
        self,
        budget_id: int,
        split_date: datetime,
        new_amount: Amount | None = None,
        new_period: relativedelta | None = None,
        new_duration: relativedelta | None = None,
    ) -> Budget:
        """Split a budget at the given date.

        This terminates the original budget the day before split_date,
        creates a new budget starting at split_date with the updated values,
        and migrates links for iterations >= split_date to the new budget.

        Args:
            budget_id: ID of the budget to split.
            split_date: Date from which the new values apply.
            new_amount: New amount (if None, keeps the original).
            new_period: New period (if None, keeps the original).
            new_duration: New duration (if None, keeps the original).

        Returns:
            The newly created Budget.

        Raises:
            ValueError: If the budget doesn't exist or isn't periodic.
        """
        if (original := self._forecast_service.get_budget_by_id(budget_id)) is None:
            raise ValueError(f"Budget {budget_id} not found")

        terminated, continuation = original.split_at(
            split_date, new_amount, new_period, new_duration
        )

        self._forecast_service.update_budget(terminated)
        new_budget = self._forecast_service.add_budget(continuation)
        self._add_matcher(new_budget)

        if new_budget.id is not None:
            self._migrate_links_after_split(
                LinkType.BUDGET,
                budget_id,
                new_budget.id,
                split_date,
            )

        logger.info(
            "Split budget %d at %s, created new budget %d",
            budget_id,
            split_date.date(),
            new_budget.id,
        )

        return new_budget

    def _migrate_links_after_split(
        self,
        target_type: LinkType,
        old_target_id: int,
        new_target_id: int,
        split_date: datetime,
    ) -> None:
        """Migrate links from old target to new target for iterations >= split_date.

        Args:
            target_type: Type of target (PLANNED_OPERATION or BUDGET).
            old_target_id: ID of the original target.
            new_target_id: ID of the new target.
            split_date: Date from which links should be migrated.
        """
        # Get links for the old target
        if target_type == LinkType.PLANNED_OPERATION:
            old_target: PlannedOperation | Budget | None = (
                self._forecast_service.get_planned_operation_by_id(old_target_id)
            )
        else:
            old_target = self._forecast_service.get_budget_by_id(old_target_id)

        if old_target is None:
            return

        links = self._operation_link_service.load_links_for_target(old_target)

        # Migrate links where iteration_date >= split_date
        for link in links:
            if link.iteration_date >= split_date:
                # Delete old link and create new one with updated target
                self._operation_link_service.delete_link(link.operation_unique_id)
                new_link = OperationLink(
                    operation_unique_id=link.operation_unique_id,
                    target_type=target_type,
                    target_id=new_target_id,
                    iteration_date=link.iteration_date,
                    is_manual=link.is_manual,
                    notes=link.notes,
                )
                self._operation_link_service.upsert_link(new_link)
                logger.debug(
                    "Migrated link for operation %s from target %d to %d",
                    link.operation_unique_id,
                    old_target_id,
                    new_target_id,
                )
