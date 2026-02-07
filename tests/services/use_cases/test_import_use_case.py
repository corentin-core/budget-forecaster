"""Tests for the ImportUseCase."""


from pathlib import Path
from unittest.mock import MagicMock

import pytest

from budget_forecaster.services.import_service import (
    ImportResult,
    ImportService,
    ImportSummary,
)
from budget_forecaster.services.operation.operation_link_service import (
    OperationLinkService,
)
from budget_forecaster.services.use_cases.import_use_case import ImportUseCase
from budget_forecaster.services.use_cases.matcher_cache import MatcherCache


@pytest.fixture(name="mock_import_service")
def mock_import_service_fixture() -> MagicMock:
    """Create a mock import service."""
    return MagicMock(spec=ImportService)


@pytest.fixture(name="mock_persistent_account")
def mock_persistent_account_fixture() -> MagicMock:
    """Create a mock persistent account."""
    mock = MagicMock()
    mock.account.operations = ()
    return mock


@pytest.fixture(name="mock_operation_link_service")
def mock_operation_link_service_fixture() -> MagicMock:
    """Create a mock operation link service."""
    return MagicMock(spec=OperationLinkService)


@pytest.fixture(name="mock_matcher_cache")
def mock_matcher_cache_fixture() -> MagicMock:
    """Create a mock matcher cache."""
    mock = MagicMock(spec=MatcherCache)
    mock.get_matchers.return_value = {}
    return mock


@pytest.fixture(name="use_case")
def use_case_fixture(
    mock_import_service: MagicMock,
    mock_persistent_account: MagicMock,
    mock_operation_link_service: MagicMock,
    mock_matcher_cache: MagicMock,
) -> ImportUseCase:
    """Create an ImportUseCase with mock dependencies."""
    return ImportUseCase(
        mock_import_service,
        mock_persistent_account,
        mock_operation_link_service,
        mock_matcher_cache,
    )


class TestImportFile:
    """Tests for import_file."""

    def test_delegates_to_import_service(
        self,
        use_case: ImportUseCase,
        mock_import_service: MagicMock,
    ) -> None:
        """Import delegates to the import service."""
        mock_import_service.import_file.return_value = ImportResult(
            path=Path("test.xlsx"), success=False, stats=None, error_message="error"
        )

        result = use_case.import_file(Path("test.xlsx"))

        mock_import_service.import_file.assert_called_once_with(
            Path("test.xlsx"), False
        )
        assert not result.success

    def test_creates_heuristic_links_on_success(
        self,
        use_case: ImportUseCase,
        mock_import_service: MagicMock,
        mock_matcher_cache: MagicMock,
        mock_operation_link_service: MagicMock,
    ) -> None:
        """Successful import triggers heuristic link creation."""
        mock_import_service.import_file.return_value = ImportResult(
            path=Path("test.xlsx"), success=True, stats=MagicMock()
        )
        mock_matcher_cache.get_matchers.return_value = {"key": MagicMock()}
        mock_operation_link_service.create_heuristic_links.return_value = []

        use_case.import_file(Path("test.xlsx"))

        mock_operation_link_service.create_heuristic_links.assert_called_once()

    def test_no_links_on_failure(
        self,
        use_case: ImportUseCase,
        mock_import_service: MagicMock,
        mock_operation_link_service: MagicMock,
    ) -> None:
        """Failed import does not create links."""
        mock_import_service.import_file.return_value = ImportResult(
            path=Path("test.xlsx"), success=False, stats=None, error_message="error"
        )

        use_case.import_file(Path("test.xlsx"))

        mock_operation_link_service.create_heuristic_links.assert_not_called()


class TestImportFromInbox:
    """Tests for import_from_inbox."""

    def test_creates_links_when_imports_succeed(
        self,
        use_case: ImportUseCase,
        mock_import_service: MagicMock,
        mock_matcher_cache: MagicMock,
        mock_operation_link_service: MagicMock,
    ) -> None:
        """Successful inbox import triggers heuristic link creation."""
        mock_import_service.import_from_inbox.return_value = ImportSummary(
            total_files=2,
            successful_imports=2,
            failed_imports=0,
            total_new_operations=10,
            total_duplicates_skipped=0,
            results=(),
        )
        mock_matcher_cache.get_matchers.return_value = {"key": MagicMock()}
        mock_operation_link_service.create_heuristic_links.return_value = []

        use_case.import_from_inbox()

        mock_operation_link_service.create_heuristic_links.assert_called_once()

    def test_no_links_when_no_successful_imports(
        self,
        use_case: ImportUseCase,
        mock_import_service: MagicMock,
        mock_operation_link_service: MagicMock,
    ) -> None:
        """No links created when all imports fail."""
        mock_import_service.import_from_inbox.return_value = ImportSummary(
            total_files=1,
            successful_imports=0,
            failed_imports=1,
            total_new_operations=0,
            total_duplicates_skipped=0,
            results=(),
        )

        use_case.import_from_inbox()

        mock_operation_link_service.create_heuristic_links.assert_not_called()
