"""Tests for the ImportService."""

# pylint: disable=redefined-outer-name,protected-access,too-few-public-methods

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from budget_forecaster.core.types import ImportStats
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
def service(
    mock_persistent_account: MagicMock,
    temp_inbox: Path,
) -> ImportService:
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


class TestIncludePatterns:
    """Tests for file inclusion patterns."""

    def test_should_include_no_patterns(
        self, mock_persistent_account: MagicMock, temp_inbox: Path
    ) -> None:
        """Without include patterns, all non-excluded files are included."""
        service = ImportService(mock_persistent_account, temp_inbox)
        assert service._should_include(Path("any_file.xlsx")) is True
        assert service._should_include(Path("another.csv")) is True

    def test_should_include_with_include_patterns(
        self, mock_persistent_account: MagicMock, temp_inbox: Path
    ) -> None:
        """With include patterns, only matching files are included."""
        service = ImportService(
            mock_persistent_account,
            temp_inbox,
            include_patterns=["BNP-*.xlsx", "Swile-*.xlsx"],
        )
        assert service._should_include(Path("BNP-2025-01-01.xlsx")) is True
        assert service._should_include(Path("Swile-export.xlsx")) is True
        assert service._should_include(Path("other-bank.xlsx")) is False
        assert service._should_include(Path("random.csv")) is False

    def test_should_include_exclude_takes_precedence(
        self, mock_persistent_account: MagicMock, temp_inbox: Path
    ) -> None:
        """Exclude patterns take precedence over include patterns."""
        service = ImportService(
            mock_persistent_account,
            temp_inbox,
            exclude_patterns=["*-backup.xlsx"],
            include_patterns=["BNP-*.xlsx"],
        )
        # Matches include but also matches exclude -> excluded
        assert service._should_include(Path("BNP-backup.xlsx")) is False
        # Matches include and doesn't match exclude -> included
        assert service._should_include(Path("BNP-2025-01-01.xlsx")) is True

    def test_get_supported_exports_with_include_patterns(
        self, mock_persistent_account: MagicMock, temp_inbox: Path
    ) -> None:
        """get_supported_exports_in_inbox respects include patterns."""
        # Create files
        (temp_inbox / "BNP-2025-01.xlsx").write_bytes(b"data")
        (temp_inbox / "Swile-export.xlsx").write_bytes(b"data")
        (temp_inbox / "other-bank.xlsx").write_bytes(b"data")

        service = ImportService(
            mock_persistent_account,
            temp_inbox,
            include_patterns=["BNP-*.xlsx"],
        )

        with patch.object(service, "is_supported_export", return_value=True):
            exports = service.get_supported_exports_in_inbox()

        names = [p.name for p in exports]
        assert "BNP-2025-01.xlsx" in names
        assert "Swile-export.xlsx" not in names
        assert "other-bank.xlsx" not in names


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
        self,
        mock_persistent_account: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Returns empty list when inbox doesn't exist."""
        nonexistent = tmp_path / "nonexistent_inbox"
        service = ImportService(
            mock_persistent_account,
            nonexistent,
        )
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
        assert result.stats is None
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

        # Mock upsert_account to return stats
        mock_stats = ImportStats(
            total_in_file=2, new_operations=2, duplicates_skipped=0
        )
        mock_persistent_account.upsert_account.return_value = mock_stats

        # Create service and file
        service = ImportService(
            mock_persistent_account,
            temp_inbox,
        )
        test_file = temp_inbox / "bank.xlsx"
        test_file.write_bytes(b"fake xlsx")

        result = service.import_file(test_file)

        assert result.success is True
        assert result.stats is not None
        assert result.stats.new_operations == 2
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

        # Mock upsert_account to return stats
        mock_stats = ImportStats(
            total_in_file=0, new_operations=0, duplicates_skipped=0
        )
        mock_persistent_account.upsert_account.return_value = mock_stats

        service = ImportService(
            mock_persistent_account,
            temp_inbox,
        )
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
        assert summary.total_new_operations == 0
        assert summary.total_duplicates_skipped == 0
        assert summary.results == ()

    def test_creates_inbox_if_missing(
        self,
        mock_persistent_account: MagicMock,
        tmp_path: Path,
    ) -> None:
        """import_from_inbox creates inbox directory if it doesn't exist."""
        nonexistent = tmp_path / "new_inbox"
        service = ImportService(
            mock_persistent_account,
            nonexistent,
        )

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

        # Mock upsert_account to return stats
        mock_stats = ImportStats(
            total_in_file=0, new_operations=0, duplicates_skipped=0
        )
        mock_persistent_account.upsert_account.return_value = mock_stats

        # Create files
        (temp_inbox / "file1.xlsx").write_bytes(b"data")
        (temp_inbox / "file2.xlsx").write_bytes(b"data")

        service = ImportService(
            mock_persistent_account,
            temp_inbox,
        )
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
    """Tests for ImportResult NamedTuple."""

    def test_success_result(self, tmp_path: Path) -> None:
        """ImportResult correctly represents success."""
        stats = ImportStats(total_in_file=10, new_operations=8, duplicates_skipped=2)
        result = ImportResult(
            path=tmp_path / "file.xlsx",
            success=True,
            stats=stats,
        )
        assert result.success is True
        assert result.stats is not None
        assert result.stats.new_operations == 8
        assert result.stats.duplicates_skipped == 2
        assert result.error_message is None

    def test_failure_result(self, tmp_path: Path) -> None:
        """ImportResult correctly represents failure."""
        result = ImportResult(
            path=tmp_path / "file.xlsx",
            success=False,
            stats=None,
            error_message="File corrupted",
        )
        assert result.success is False
        assert result.stats is None
        assert result.error_message == "File corrupted"


class TestImportSummary:
    """Tests for ImportSummary NamedTuple."""

    def test_summary_calculation(self, tmp_path: Path) -> None:
        """ImportSummary correctly aggregates results."""
        results = (
            ImportResult(
                tmp_path / "f1.xlsx",
                True,
                ImportStats(total_in_file=10, new_operations=8, duplicates_skipped=2),
            ),
            ImportResult(
                tmp_path / "f2.xlsx",
                True,
                ImportStats(total_in_file=5, new_operations=5, duplicates_skipped=0),
            ),
            ImportResult(tmp_path / "f3.xlsx", False, None, "Error"),
        )
        summary = ImportSummary(
            total_files=3,
            successful_imports=2,
            failed_imports=1,
            total_new_operations=13,
            total_duplicates_skipped=2,
            results=results,
        )
        assert summary.total_files == 3
        assert summary.successful_imports == 2
        assert summary.failed_imports == 1
        assert summary.total_new_operations == 13
        assert summary.total_duplicates_skipped == 2
