"""Tests for the OperationService."""

from datetime import date
from unittest.mock import MagicMock

import pytest

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.types import Category, CategorySource
from budget_forecaster.domain.account.account import Account
from budget_forecaster.domain.operation.historic_operation import HistoricOperation
from budget_forecaster.exceptions import OperationNotFoundError
from budget_forecaster.services.operation.operation_service import (
    OperationFilter,
    OperationService,
)


@pytest.fixture
def sample_operations() -> tuple[HistoricOperation, ...]:
    """Create sample operations for testing."""
    return (
        HistoricOperation(
            unique_id=1,
            description="CARTE CARREFOUR",
            amount=Amount(-50.0),
            category=Category.GROCERIES,
            operation_date=date(2025, 1, 15),
        ),
        HistoricOperation(
            unique_id=2,
            description="VIREMENT SALAIRE",
            amount=Amount(2500.0),
            category=Category.SALARY,
            operation_date=date(2025, 1, 10),
        ),
        HistoricOperation(
            unique_id=3,
            description="CARTE AMAZON",
            amount=Amount(-99.99),
            category=Category.UNCATEGORIZED,
            operation_date=date(2025, 1, 20),
        ),
        HistoricOperation(
            unique_id=4,
            description="CARTE CARREFOUR MARKET",
            amount=Amount(-35.50),
            category=Category.GROCERIES,
            operation_date=date(2025, 1, 18),
        ),
        HistoricOperation(
            unique_id=5,
            description="PRLV EDF",
            amount=Amount(-80.0),
            category=Category.ELECTRICITY,
            operation_date=date(2025, 1, 5),
        ),
    )


@pytest.fixture
def mock_account_manager(
    sample_operations: tuple[HistoricOperation, ...],
) -> MagicMock:
    """Create a mock account manager."""
    mock = MagicMock()
    mock.account = Account(
        name="Test Account",
        balance=1000.0,
        currency="EUR",
        balance_date=date(2025, 1, 20),
        operations=sample_operations,
    )
    return mock


@pytest.fixture
def service(mock_account_manager: MagicMock) -> OperationService:
    """Create an OperationService with mock data."""
    return OperationService(mock_account_manager)


class TestOperationFilter:
    """Tests for OperationFilter."""

    def test_matches_all_when_empty(
        self, sample_operations: tuple[HistoricOperation, ...]
    ) -> None:
        """Empty filter matches all operations."""
        filter_ = OperationFilter()
        assert all(filter_.matches(op) for op in sample_operations)

    def test_matches_search_text(
        self, sample_operations: tuple[HistoricOperation, ...]
    ) -> None:
        """Filter by search text."""
        filter_ = OperationFilter(search_text="carrefour")
        matches = [op for op in sample_operations if filter_.matches(op)]
        assert len(matches) == 2
        assert all("CARREFOUR" in op.description for op in matches)

    def test_matches_to_review(self) -> None:
        """The review filter keeps guessed categories only."""
        operations = {
            source: HistoricOperation(
                unique_id=index,
                description="CB RELAY",
                amount=Amount(-5.0),
                category=Category.LEISURE,
                operation_date=date(2025, 1, 15),
                category_source=source,
            )
            for index, source in enumerate((None, *CategorySource))
        }
        filter_ = OperationFilter(to_review_only=True)

        assert {s for s, op in operations.items() if filter_.matches(op)} == {
            CategorySource.PLANNED,
            CategorySource.HISTORY,
            CategorySource.RULE,
        }

    def test_matches_category(
        self, sample_operations: tuple[HistoricOperation, ...]
    ) -> None:
        """Filter by category."""
        filter_ = OperationFilter(category=Category.GROCERIES)
        matches = [op for op in sample_operations if filter_.matches(op)]
        assert len(matches) == 2
        assert all(op.category == Category.GROCERIES for op in matches)

    def test_matches_date_range(
        self, sample_operations: tuple[HistoricOperation, ...]
    ) -> None:
        """Filter by date range."""
        filter_ = OperationFilter(
            date_from=date(2025, 1, 10),
            date_to=date(2025, 1, 18),
        )
        matches = [op for op in sample_operations if filter_.matches(op)]
        assert len(matches) == 3  # ops on 10, 15, 18

    def test_matches_amount_range(
        self, sample_operations: tuple[HistoricOperation, ...]
    ) -> None:
        """Filter by amount range."""
        filter_ = OperationFilter(min_amount=-60.0, max_amount=-30.0)
        matches = [op for op in sample_operations if filter_.matches(op)]
        assert len(matches) == 2  # -50 and -35.50

    def test_matches_uncategorized_only(
        self, sample_operations: tuple[HistoricOperation, ...]
    ) -> None:
        """Filter uncategorized operations only."""
        filter_ = OperationFilter(uncategorized_only=True)
        matches = [op for op in sample_operations if filter_.matches(op)]
        assert len(matches) == 1
        assert matches[0].category == Category.UNCATEGORIZED


class TestOperationService:
    """Tests for OperationService."""

    def test_get_operations_returns_all(self, service: OperationService) -> None:
        """get_operations returns all operations by default."""
        operations = service.get_operations()
        assert len(operations) == 5

    def test_get_operations_sorted_by_date_desc(
        self, service: OperationService
    ) -> None:
        """Operations are sorted by date descending by default."""
        operations = service.get_operations()
        dates = [op.operation_date for op in operations]
        assert dates == sorted(dates, reverse=True)

    def test_get_operations_with_filter(self, service: OperationService) -> None:
        """get_operations applies filter correctly."""
        filter_ = OperationFilter(category=Category.GROCERIES)
        operations = service.get_operations(filter_criteria=filter_)
        assert len(operations) == 2
        assert all(op.category == Category.GROCERIES for op in operations)

    def test_get_operation_by_id_found(self, service: OperationService) -> None:
        """get_operation_by_id returns the correct operation."""
        operation = service.get_operation_by_id(3)
        assert operation.unique_id == 3
        assert operation.description == "CARTE AMAZON"

    def test_get_operation_by_id_not_found(self, service: OperationService) -> None:
        """get_operation_by_id raises OperationNotFoundError for unknown ID."""
        with pytest.raises(OperationNotFoundError):
            service.get_operation_by_id(999)

    def test_get_uncategorized_operations(self, service: OperationService) -> None:
        """get_uncategorized_operations returns only UNCATEGORIZED category."""
        operations = service.get_uncategorized_operations()
        assert len(operations) == 1
        assert operations[0].category == Category.UNCATEGORIZED

    def test_update_operation_category(
        self, service: OperationService, mock_account_manager: MagicMock
    ) -> None:
        """update_operation changes the category."""
        result = service.update_operation(3, category=Category.LEISURE)
        assert result.category == Category.LEISURE
        assert result.category_source == CategorySource.MANUAL
        mock_account_manager.replace_operation.assert_called_once()

    def test_update_operation_not_found(self, service: OperationService) -> None:
        """update_operation raises OperationNotFoundError for unknown ID."""
        with pytest.raises(OperationNotFoundError):
            service.update_operation(999, category=Category.LEISURE)

    def test_categorize_operation(
        self, service: OperationService, mock_account_manager: MagicMock
    ) -> None:
        """categorize_operation is a shortcut for update_operation."""
        result = service.categorize_operation(3, Category.ENTERTAINMENT)
        assert result.category == Category.ENTERTAINMENT
        mock_account_manager.replace_operation.assert_called_once()

    def test_get_category_totals(self, service: OperationService) -> None:
        """get_category_totals returns totals per category."""
        totals = service.get_category_totals()
        assert totals[Category.GROCERIES] == -85.50  # -50 + -35.50
        assert totals[Category.SALARY] == 2500.0
        assert totals[Category.ELECTRICITY] == -80.0

    def test_get_monthly_totals(self, service: OperationService) -> None:
        """get_monthly_totals returns totals per month."""
        totals = service.get_monthly_totals()
        # All operations are in January 2025
        assert "2025-01" in totals
        expected = -50.0 + 2500.0 - 99.99 - 35.50 - 80.0
        assert abs(totals["2025-01"] - expected) < 0.01

    def test_balance_property(self, service: OperationService) -> None:
        """balance property returns account balance."""
        assert service.balance == 1000.0

    def test_currency_property(self, service: OperationService) -> None:
        """currency property returns account currency."""
        assert service.currency == "EUR"

    def test_balance_date_property(self, service: OperationService) -> None:
        """balance_date property returns account balance_date."""
        assert service.balance_date == date(2025, 1, 20)


class TestOperationServiceGaps:
    """Additional edge-case tests for OperationService."""

    def test_update_operation_description_only(
        self, service: OperationService, mock_account_manager: MagicMock
    ) -> None:
        """update_operation changes only the description."""
        result = service.update_operation(3, description="CARTE AMAZON PRIME")
        assert result.description == "CARTE AMAZON PRIME"
        mock_account_manager.replace_operation.assert_called_once()

    def test_update_operation_no_changes(
        self, service: OperationService, mock_account_manager: MagicMock
    ) -> None:
        """update_operation returns unchanged operation when no kwargs given."""
        result = service.update_operation(3)
        assert result.unique_id == 3
        mock_account_manager.replace_operation.assert_not_called()
