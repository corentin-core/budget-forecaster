"""Tests for the ManageLinksUseCase."""


from datetime import date
from unittest.mock import MagicMock

import pytest

from budget_forecaster.core.types import LinkType
from budget_forecaster.domain.operation.budget import Budget
from budget_forecaster.domain.operation.historic_operation import HistoricOperation
from budget_forecaster.domain.operation.planned_operation import PlannedOperation
from budget_forecaster.services.operation.operation_link_service import (
    OperationLinkService,
)
from budget_forecaster.services.use_cases.manage_links_use_case import (
    ManageLinksUseCase,
)


@pytest.fixture(name="mock_operation_link_service")
def mock_operation_link_service_fixture() -> MagicMock:
    """Create a mock operation link service."""
    return MagicMock(spec=OperationLinkService)


@pytest.fixture(name="use_case")
def use_case_fixture(mock_operation_link_service: MagicMock) -> ManageLinksUseCase:
    """Create a ManageLinksUseCase with mock dependencies."""
    return ManageLinksUseCase(mock_operation_link_service)


class TestCreateManualLink:
    """Tests for create_manual_link."""

    def test_creates_link_for_planned_operation(
        self,
        use_case: ManageLinksUseCase,
        mock_operation_link_service: MagicMock,
    ) -> None:
        """Creates a manual link to a planned operation."""
        operation = MagicMock(spec=HistoricOperation)
        operation.unique_id = 100
        target = MagicMock(spec=PlannedOperation)
        target.id = 5

        link = use_case.create_manual_link(operation, target, date(2025, 3, 1))

        assert link.operation_unique_id == 100
        assert link.target_type == LinkType.PLANNED_OPERATION
        assert link.target_id == 5
        assert link.is_manual is True
        mock_operation_link_service.upsert_link.assert_called_once()

    def test_creates_link_for_budget(
        self,
        use_case: ManageLinksUseCase,
        mock_operation_link_service: MagicMock,
    ) -> None:
        """Creates a manual link to a budget."""
        operation = MagicMock(spec=HistoricOperation)
        operation.unique_id = 200
        target = MagicMock(spec=Budget)
        target.id = 8

        link = use_case.create_manual_link(operation, target, date(2025, 4, 1))

        assert link.target_type == LinkType.BUDGET
        assert link.target_id == 8

    def test_raises_on_target_without_id(
        self,
        use_case: ManageLinksUseCase,
    ) -> None:
        """Raises ValueError when target has no ID."""
        operation = MagicMock(spec=HistoricOperation)
        target = MagicMock(spec=PlannedOperation)
        target.id = None

        with pytest.raises(ValueError, match="must have an ID"):
            use_case.create_manual_link(operation, target, date(2025, 1, 1))
