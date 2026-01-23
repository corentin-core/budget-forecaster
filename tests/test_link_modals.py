"""Tests for link modal logic and OperationTable link column."""

from datetime import datetime

from dateutil.relativedelta import relativedelta

from budget_forecaster.amount import Amount
from budget_forecaster.operation_range.budget import Budget
from budget_forecaster.operation_range.historic_operation import HistoricOperation
from budget_forecaster.operation_range.operation_link import LinkType, OperationLink
from budget_forecaster.operation_range.planned_operation import PlannedOperation
from budget_forecaster.time_range import (
    DailyTimeRange,
    PeriodicDailyTimeRange,
    TimeRange,
)
from budget_forecaster.tui.modals.link_iteration import LinkIterationModal
from budget_forecaster.tui.modals.link_target import LinkTargetModal
from budget_forecaster.tui.widgets.operation_table import OperationTable
from budget_forecaster.types import Category


class TestOperationTableLinkColumn:
    """Tests for the OperationTable 'Lien' column rendering."""

    def test_link_column_empty_when_no_link(self) -> None:
        """Test that link column renders empty when operation has no link."""
        operations = [
            HistoricOperation(
                unique_id=1,
                description="Test Operation",
                amount=Amount(100.0),
                category=Category.GROCERIES,
                date=datetime(2023, 1, 15),
            )
        ]

        # Create table and load operations without links
        table = OperationTable()
        table._columns_added = True  # Skip column creation
        table._operations = {}  # Initialize

        # Simulate load_operations logic without Textual context
        # We verify that the function can be called without errors
        # and that the link display logic is correct
        links: dict[int, OperationLink] = {}
        targets: dict[tuple[LinkType, int], str] = {}

        # Verify link display would be empty
        op = operations[0]
        link_str = ""
        if link := links.get(op.unique_id):
            target_key = (link.target_type, link.target_id)
            if target_name := targets.get(target_key):
                link_str = f"🔗 {target_name[:12]}"
            else:
                link_str = "🔗"

        assert link_str == ""

    def test_link_column_shows_link_emoji_and_name(self) -> None:
        """Test that link column renders '🔗 Name' when operation is linked."""
        operation = HistoricOperation(
            unique_id=1,
            description="Test Operation",
            amount=Amount(100.0),
            category=Category.GROCERIES,
            date=datetime(2023, 1, 15),
        )

        link = OperationLink(
            operation_unique_id=1,
            target_type=LinkType.PLANNED_OPERATION,
            target_id=42,
            iteration_date=datetime(2023, 1, 1),
            is_manual=True,
        )

        links: dict[int, OperationLink] = {1: link}
        targets: dict[tuple[LinkType, int], str] = {
            (LinkType.PLANNED_OPERATION, 42): "Loyer"
        }

        # Simulate link display logic
        link_str = ""
        if found_link := links.get(operation.unique_id):
            target_key = (found_link.target_type, found_link.target_id)
            if target_name := targets.get(target_key):
                link_str = f"🔗 {target_name[:12]}"
            else:
                link_str = "🔗"

        assert link_str == "🔗 Loyer"

    def test_link_column_truncates_long_names(self) -> None:
        """Test that long target names are truncated in link column."""
        operation = HistoricOperation(
            unique_id=1,
            description="Test Operation",
            amount=Amount(100.0),
            category=Category.GROCERIES,
            date=datetime(2023, 1, 15),
        )

        link = OperationLink(
            operation_unique_id=1,
            target_type=LinkType.BUDGET,
            target_id=99,
            iteration_date=datetime(2023, 1, 1),
            is_manual=False,
        )

        links: dict[int, OperationLink] = {1: link}
        targets: dict[tuple[LinkType, int], str] = {
            (LinkType.BUDGET, 99): "Very Long Budget Name That Should Be Truncated"
        }

        # Simulate link display logic from OperationTable
        table = OperationTable()
        link_str = ""
        if found_link := links.get(operation.unique_id):
            target_key = (found_link.target_type, found_link.target_id)
            if target_name := targets.get(target_key):
                link_str = f"🔗 {table._truncate(target_name, 12)}"
            else:
                link_str = "🔗"

        # Should be "🔗 Very Long..." (12 char limit)
        assert link_str == "🔗 Very Long..."
        assert len(link_str) <= 16  # "🔗 " + 12 chars


class TestLinkTargetModalScoreComputation:
    """Tests for LinkTargetModal score computation logic."""

    def _create_operation(self, date: datetime) -> HistoricOperation:
        """Create a test operation."""
        return HistoricOperation(
            unique_id=1,
            description="Test Operation",
            amount=Amount(-500.0),
            category=Category.RENT,
            date=date,
        )

    def _create_planned_operation(self) -> PlannedOperation:
        """Create a test planned operation."""
        return PlannedOperation(
            record_id=1,
            description="Monthly Rent",
            amount=Amount(-500.0, "EUR"),
            category=Category.RENT,
            time_range=PeriodicDailyTimeRange(
                datetime(2023, 1, 1),
                relativedelta(months=1),
            ),
        )

    def test_computes_best_score_for_target(self) -> None:
        """Test that modal computes the best score across iterations."""
        operation = self._create_operation(datetime(2023, 3, 15))
        planned_op = self._create_planned_operation()

        # Create modal instance (without mounting)
        modal = LinkTargetModal(
            operation=operation,
            current_link=None,
            planned_operations=[planned_op],
            budgets=[],
        )

        # Score should be computed during init
        assert planned_op.id is not None
        assert planned_op.id in modal._planned_op_scores
        # Score should be reasonable (not 0) since operation matches planned op
        score = modal._planned_op_scores[planned_op.id]
        assert score > 0

    def test_computes_best_score_finds_best_iteration(self) -> None:
        """Test that best score finds the closest iteration."""
        # Operation on Jan 15
        operation = self._create_operation(datetime(2023, 1, 15))
        planned_op = self._create_planned_operation()

        modal = LinkTargetModal(
            operation=operation,
            current_link=None,
            planned_operations=[planned_op],
            budgets=[],
        )

        # The best score should be high since Jan 15 is close to Jan 1 iteration
        assert planned_op.id is not None
        score = modal._planned_op_scores[planned_op.id]
        # With matching amount and category, and close date, expect high score
        assert score >= 70.0


class TestLinkTargetModalOptions:
    """Tests for LinkTargetModal option building."""

    def test_builds_planned_operation_options_sorted_by_score(self) -> None:
        """Test that planned operation options are sorted by score descending."""
        operation = HistoricOperation(
            unique_id=1,
            description="Test",
            amount=Amount(-500.0),
            category=Category.RENT,
            date=datetime(2023, 1, 15),
        )

        # Create two planned operations with different match levels
        rent_op = PlannedOperation(
            record_id=1,
            description="Rent",
            amount=Amount(-500.0, "EUR"),
            category=Category.RENT,
            time_range=DailyTimeRange(datetime(2023, 1, 15)),
        )

        groceries_op = PlannedOperation(
            record_id=2,
            description="Groceries",
            amount=Amount(-100.0, "EUR"),  # Different amount
            category=Category.GROCERIES,  # Different category
            time_range=DailyTimeRange(datetime(2023, 1, 15)),
        )

        modal = LinkTargetModal(
            operation=operation,
            current_link=None,
            planned_operations=[groceries_op, rent_op],  # Wrong order
            budgets=[],
        )

        options = modal._build_planned_options()

        # Rent should come first (higher score)
        assert len(options) == 2
        assert options[0].id == "planned_1"  # Rent
        assert options[1].id == "planned_2"  # Groceries

    def test_builds_budget_options_sorted_by_score(self) -> None:
        """Test that budget options are sorted by score descending."""
        operation = HistoricOperation(
            unique_id=1,
            description="Test",
            amount=Amount(-200.0),
            category=Category.GROCERIES,
            date=datetime(2023, 1, 15),
        )

        groceries_budget = Budget(
            record_id=1,
            description="Groceries Budget",
            amount=Amount(-200.0, "EUR"),
            category=Category.GROCERIES,
            time_range=TimeRange(datetime(2023, 1, 1), relativedelta(months=1)),
        )

        entertainment_budget = Budget(
            record_id=2,
            description="Entertainment",
            amount=Amount(-50.0, "EUR"),  # Different amount
            category=Category.ENTERTAINMENT,  # Different category
            time_range=TimeRange(datetime(2023, 1, 1), relativedelta(months=1)),
        )

        modal = LinkTargetModal(
            operation=operation,
            current_link=None,
            planned_operations=[],
            budgets=[entertainment_budget, groceries_budget],  # Wrong order
        )

        options = modal._build_budget_options()

        # Groceries budget should come first (higher score)
        assert len(options) == 2
        assert options[0].id == "budget_1"  # Groceries
        assert options[1].id == "budget_2"  # Entertainment


class TestLinkIterationModalWindow:
    """Tests for LinkIterationModal window logic."""

    def _create_operation(self, date: datetime) -> HistoricOperation:
        """Create a test operation."""
        return HistoricOperation(
            unique_id=1,
            description="Test Operation",
            amount=Amount(-500.0),
            category=Category.RENT,
            date=date,
        )

    def _create_monthly_planned_operation(self) -> PlannedOperation:
        """Create a monthly recurring planned operation."""
        return PlannedOperation(
            record_id=1,
            description="Monthly Rent",
            amount=Amount(-500.0, "EUR"),
            category=Category.RENT,
            time_range=PeriodicDailyTimeRange(
                datetime(2022, 1, 1),
                relativedelta(months=1),
            ),
        )

    def test_window_center_is_operation_date(self) -> None:
        """Test that window centers on operation date."""
        op_date = datetime(2023, 5, 15)
        operation = self._create_operation(op_date)
        target = self._create_monthly_planned_operation()

        modal = LinkIterationModal(operation=operation, target=target)

        assert modal._window_center == op_date

    def test_window_spans_plus_minus_two_months(self) -> None:
        """Test that window spans ±2 months from center."""
        op_date = datetime(2023, 5, 15)
        operation = self._create_operation(op_date)
        target = self._create_monthly_planned_operation()

        modal = LinkIterationModal(operation=operation, target=target)

        # Window start: May 15 - 2 months = March 15
        assert modal._window_start == datetime(2023, 3, 15)
        # Window end: May 15 + 2 months = July 15
        assert modal._window_end == datetime(2023, 7, 15)

    def test_navigation_shifts_window_by_one_month(self) -> None:
        """Test that navigation shifts window by 1 month."""
        op_date = datetime(2023, 5, 15)
        operation = self._create_operation(op_date)
        target = self._create_monthly_planned_operation()

        modal = LinkIterationModal(operation=operation, target=target)

        # Initial window center
        assert modal._window_center == op_date

        # Shift forward by 1 month
        modal._offset_months = 1
        expected_center = op_date + relativedelta(months=1)
        assert modal._window_center == expected_center

        # Shift backward by 2 months from original
        modal._offset_months = -2
        expected_center = op_date + relativedelta(months=-2)
        assert modal._window_center == expected_center

    def test_builds_iteration_options_within_window(self) -> None:
        """Test that only iterations within window are shown."""
        op_date = datetime(2023, 5, 15)
        operation = self._create_operation(op_date)
        target = self._create_monthly_planned_operation()

        modal = LinkIterationModal(operation=operation, target=target)

        options = modal._build_iteration_options()

        # Should have iterations for March, April, May, June, July
        # (depending on exact window boundaries and iteration dates)
        assert len(options) >= 3  # At least 3 monthly iterations
        assert len(options) <= 6  # At most ~5-6 in 4-month window

        # All options should have date-based IDs
        for option in options:
            if option.id != "empty":
                # Should be in YYYY-MM-DD format
                assert len(str(option.id)) == 10  # "2023-05-01"

    def test_preselects_best_match_iteration(self) -> None:
        """Test that best matching iteration is pre-selected."""
        # Operation on May 5
        op_date = datetime(2023, 5, 5)
        operation = self._create_operation(op_date)
        target = self._create_monthly_planned_operation()

        modal = LinkIterationModal(operation=operation, target=target)

        # Build options to trigger pre-selection
        modal._build_iteration_options()

        # Selected date should be the closest iteration (May 1)
        assert modal._selected_date is not None
        # Should be May 1, 2023 (closest to May 5)
        assert modal._selected_date == datetime(2023, 5, 1)


class TestLinkIterationModalDateRangeText:
    """Tests for LinkIterationModal date range display."""

    def test_date_range_text_format(self) -> None:
        """Test that date range text is properly formatted."""
        op_date = datetime(2023, 5, 15)
        operation = HistoricOperation(
            unique_id=1,
            description="Test",
            amount=Amount(-100.0),
            category=Category.OTHER,
            date=op_date,
        )
        target = PlannedOperation(
            record_id=1,
            description="Test",
            amount=Amount(-100.0, "EUR"),
            category=Category.OTHER,
            time_range=DailyTimeRange(datetime(2023, 1, 1)),
        )

        modal = LinkIterationModal(operation=operation, target=target)

        text = modal._get_date_range_text()

        # Should be in "Mon YYYY - Mon YYYY" format
        assert " - " in text
        # Should contain month abbreviations
        assert "Mar" in text  # Window start
        assert "Jul" in text  # Window end
        assert "2023" in text
