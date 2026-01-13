"""Tests for the ImportService."""

# pylint: disable=redefined-outer-name,protected-access,too-few-public-methods

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from budget_forecaster.services.import_service import (
    ImportResult,
    ImportService,
    ImportSummary,
)


@pytest.fixture
def mock_persistent_account() -> MagicMock:
    """Create a mock persistent account."""
    mock = MagicMock()
    mock.account.operations = ()
    return mock


@pytest.fixture
def temp_inbox(tmp_path: Path) -> Path:
    """Create a temporary inbox directory."""
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    return inbox


@pytest.fixture
def service(mock_persistent_account: MagicMock, temp_inbox: Path) -> ImportService:
    """Create an ImportService with mock data."""
    return ImportService(
        persistent_account=mock_persistent_account,
        inbox_path=temp_inbox,
        exclude_patterns=["*.tmp", "ignore_*"],
    )


class TestImportServiceInit:
    """Tests for ImportService initialization."""

    def test_inbox_path_property(
        self, service: ImportService, temp_inbox: Path
    ) -> None:
        """inbox_path returns the correct path."""
        assert service.inbox_path == temp_inbox

    def test_has_pending_imports_empty(self, service: ImportService) -> None:
        """has_pending_imports returns False for empty inbox."""
        assert service.has_pending_imports is False

    def test_pending_import_count_empty(self, service: ImportService) -> None:
        """pending_import_count returns 0 for empty inbox."""
        assert service.pending_import_count == 0


class TestIsSupportedExport:
    """Tests for is_supported_export method."""

    def test_unsupported_format(self, service: ImportService, temp_inbox: Path) -> None:
        """is_supported_export returns False for unsupported formats."""
        unsupported_file = temp_inbox / "file.txt"
        unsupported_file.write_text("test")
        assert service.is_supported_export(unsupported_file) is False

    def test_nonexistent_file(self, service: ImportService, temp_inbox: Path) -> None:
        """is_supported_export returns False for nonexistent files."""
        nonexistent = temp_inbox / "nonexistent.xlsx"
        assert service.is_supported_export(nonexistent) is False

    @patch("budget_forecaster.services.import_service.BankAdapterFactory")
    def test_supported_format(
        self,
        mock_factory_class: MagicMock,
        service: ImportService,
        temp_inbox: Path,
    ) -> None:
        """is_supported_export returns True when adapter is found."""
        # Create a file
        supported_file = temp_inbox / "bank_export.xlsx"
        supported_file.write_bytes(b"fake xlsx content")

        # Mock the factory to not raise
        mock_factory = MagicMock()
        mock_factory_class.return_value = mock_factory

        # Re-create service with mocked factory
        new_service = ImportService(
            persistent_account=MagicMock(),
            inbox_path=temp_inbox,
        )
        new_service._bank_adapter_factory = mock_factory

        assert new_service.is_supported_export(supported_file) is True


class TestExcludePatterns:
    """Tests for file exclusion patterns."""

    def test_is_excluded_matches_pattern(self, service: ImportService) -> None:
        """Files matching exclude patterns are excluded."""
        assert service._is_excluded(Path("test.tmp")) is True
        assert service._is_excluded(Path("ignore_this.xlsx")) is True

    def test_is_excluded_no_match(self, service: ImportService) -> None:
        """Files not matching exclude patterns are not excluded."""
        assert service._is_excluded(Path("valid.xlsx")) is False
        assert service._is_excluded(Path("data.csv")) is False


class TestGetSupportedExportsInInbox:
    """Tests for get_supported_exports_in_inbox method."""

    def test_empty_inbox(self, service: ImportService) -> None:
        """Returns empty list for empty inbox."""
        exports = service.get_supported_exports_in_inbox()
        assert not exports

    def test_excludes_processed_folder(
        self, service: ImportService, temp_inbox: Path
    ) -> None:
        """Excludes the 'processed' folder."""
        processed = temp_inbox / "processed"
        processed.mkdir()
        (processed / "old_file.xlsx").write_bytes(b"data")

        exports = service.get_supported_exports_in_inbox()
        assert not any(p.parent.name == "processed" for p in exports)

    def test_excludes_pattern_matches(
        self, service: ImportService, temp_inbox: Path
    ) -> None:
        """Excludes files matching exclude patterns."""
        (temp_inbox / "valid.xlsx").write_bytes(b"data")
        (temp_inbox / "temp.tmp").write_bytes(b"data")
        (temp_inbox / "ignore_me.xlsx").write_bytes(b"data")

        # Mock is_supported_export to return True for all .xlsx
        with patch.object(service, "is_supported_export", return_value=True):
            exports = service.get_supported_exports_in_inbox()

        names = [p.name for p in exports]
        assert "valid.xlsx" in names
        assert "temp.tmp" not in names
        assert "ignore_me.xlsx" not in names

    def test_nonexistent_inbox(
        self, mock_persistent_account: MagicMock, tmp_path: Path
    ) -> None:
        """Returns empty list when inbox doesn't exist."""
        nonexistent = tmp_path / "nonexistent_inbox"
        service = ImportService(mock_persistent_account, nonexistent)
        exports = service.get_supported_exports_in_inbox()
        assert not exports


class TestImportFile:
    """Tests for import_file method."""

    def test_import_unsupported_file(
        self, service: ImportService, temp_inbox: Path
    ) -> None:
        """import_file returns failure for unsupported files."""
        unsupported = temp_inbox / "file.txt"
        unsupported.write_text("not a bank export")

        result = service.import_file(unsupported)

        assert result.success is False
        assert result.operations_count == 0
        assert result.error_message is not None

    @patch("budget_forecaster.services.import_service.BankAdapterFactory")
    def test_import_success(
        self,
        mock_factory_class: MagicMock,
        mock_persistent_account: MagicMock,
        temp_inbox: Path,
    ) -> None:
        """import_file returns success for valid files."""
        # Setup mock
        mock_adapter = MagicMock()
        mock_adapter.name = "Test Bank"
        mock_adapter.balance = 1000.0
        mock_adapter.export_date = None
        mock_adapter.operations = [MagicMock(), MagicMock()]  # 2 operations

        mock_factory = MagicMock()
        mock_factory.create_bank_adapter.return_value = mock_adapter
        mock_factory_class.return_value = mock_factory

        # Create service and file
        service = ImportService(mock_persistent_account, temp_inbox)
        test_file = temp_inbox / "bank.xlsx"
        test_file.write_bytes(b"fake xlsx")

        result = service.import_file(test_file)

        assert result.success is True
        assert result.operations_count == 2
        assert result.error_message is None
        mock_persistent_account.upsert_account.assert_called_once()
        mock_persistent_account.save.assert_called_once()

    @patch("budget_forecaster.services.import_service.BankAdapterFactory")
    def test_import_moves_to_processed(
        self,
        mock_factory_class: MagicMock,
        mock_persistent_account: MagicMock,
        temp_inbox: Path,
    ) -> None:
        """import_file moves file to processed folder when requested."""
        # Setup mock
        mock_adapter = MagicMock()
        mock_adapter.name = "Test"
        mock_adapter.balance = 0
        mock_adapter.export_date = None
        mock_adapter.operations = []

        mock_factory = MagicMock()
        mock_factory.create_bank_adapter.return_value = mock_adapter
        mock_factory_class.return_value = mock_factory

        service = ImportService(mock_persistent_account, temp_inbox)
        test_file = temp_inbox / "to_process.xlsx"
        test_file.write_bytes(b"fake")

        result = service.import_file(test_file, move_to_processed=True)

        assert result.success is True
        assert not test_file.exists()
        assert (temp_inbox / "processed" / "to_process.xlsx").exists()


class TestImportFromInbox:
    """Tests for import_from_inbox method."""

    def test_empty_inbox_returns_empty_summary(self, service: ImportService) -> None:
        """import_from_inbox returns empty summary for empty inbox."""
        summary = service.import_from_inbox()

        assert summary.total_files == 0
        assert summary.successful_imports == 0
        assert summary.failed_imports == 0
        assert summary.total_operations == 0
        assert summary.results == []

    def test_creates_inbox_if_missing(
        self, mock_persistent_account: MagicMock, tmp_path: Path
    ) -> None:
        """import_from_inbox creates inbox directory if it doesn't exist."""
        nonexistent = tmp_path / "new_inbox"
        service = ImportService(mock_persistent_account, nonexistent)

        service.import_from_inbox()

        assert nonexistent.exists()

    @patch("budget_forecaster.services.import_service.BankAdapterFactory")
    def test_calls_progress_callback(
        self,
        mock_factory_class: MagicMock,
        mock_persistent_account: MagicMock,
        temp_inbox: Path,
    ) -> None:
        """import_from_inbox calls progress callback for each file."""
        # Setup mock adapter
        mock_adapter = MagicMock()
        mock_adapter.name = "Test"
        mock_adapter.balance = 0
        mock_adapter.export_date = None
        mock_adapter.operations = []

        mock_factory = MagicMock()
        mock_factory.create_bank_adapter.return_value = mock_adapter
        mock_factory_class.return_value = mock_factory

        # Create files
        (temp_inbox / "file1.xlsx").write_bytes(b"data")
        (temp_inbox / "file2.xlsx").write_bytes(b"data")

        service = ImportService(mock_persistent_account, temp_inbox)
        progress_calls: list[tuple[int, int, str]] = []

        def on_progress(current: int, total: int, name: str) -> None:
            progress_calls.append((current, total, name))

        service.import_from_inbox(on_progress=on_progress)

        assert len(progress_calls) == 2
        assert progress_calls[0][0] == 1
        assert progress_calls[0][1] == 2
        assert progress_calls[1][0] == 2
        assert progress_calls[1][1] == 2


class TestImportResult:
    """Tests for ImportResult dataclass."""

    def test_success_result(self, tmp_path: Path) -> None:
        """ImportResult correctly represents success."""
        result = ImportResult(
            path=tmp_path / "file.xlsx",
            success=True,
            operations_count=10,
        )
        assert result.success is True
        assert result.operations_count == 10
        assert result.error_message is None

    def test_failure_result(self, tmp_path: Path) -> None:
        """ImportResult correctly represents failure."""
        result = ImportResult(
            path=tmp_path / "file.xlsx",
            success=False,
            operations_count=0,
            error_message="File corrupted",
        )
        assert result.success is False
        assert result.operations_count == 0
        assert result.error_message == "File corrupted"


class TestImportSummary:
    """Tests for ImportSummary dataclass."""

    def test_summary_calculation(self, tmp_path: Path) -> None:
        """ImportSummary correctly aggregates results."""
        results = [
            ImportResult(tmp_path / "f1.xlsx", True, 10),
            ImportResult(tmp_path / "f2.xlsx", True, 5),
            ImportResult(tmp_path / "f3.xlsx", False, 0, "Error"),
        ]
        summary = ImportSummary(
            total_files=3,
            successful_imports=2,
            failed_imports=1,
            total_operations=15,
            results=results,
        )
        assert summary.total_files == 3
        assert summary.successful_imports == 2
        assert summary.failed_imports == 1
        assert summary.total_operations == 15
