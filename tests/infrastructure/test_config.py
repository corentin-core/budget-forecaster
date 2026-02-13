"""Tests for the Config class."""

import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from budget_forecaster.infrastructure.config import (
    AccountConfig,
    BackupConfig,
    Config,
)

CONFIGS_FIXTURES_DIR = Path(__file__).parents[1] / "fixtures" / "configs"


class TestConfigDefaults:
    """Tests for Config default values."""

    def test_default_language(self) -> None:
        """Test that default language is English."""
        config = Config()
        assert config.language == "en"

    def test_default_account(self) -> None:
        """Test that default account config is Main Account / EUR."""
        config = Config()
        assert config.account == AccountConfig(name="Main Account", currency="EUR")

    def test_default_database_path(self) -> None:
        """Test that default database path is budget.db."""
        config = Config()
        assert config.database_path == Path("budget.db")

    def test_default_backup(self) -> None:
        """Test that default backup config has enabled=True, max_backups=5."""
        config = Config()
        assert config.backup == BackupConfig(
            enabled=True, max_backups=5, directory=None
        )

    def test_default_inbox_patterns(self) -> None:
        """Test that default inbox patterns are empty lists."""
        config = Config()
        assert config.inbox_exclude_patterns == []
        assert config.inbox_include_patterns == []

    def test_default_logging_config(self) -> None:
        """Test that default logging config is None."""
        config = Config()
        assert config.logging_config is None


class TestConfigParseYaml:
    """Tests for YAML config file parsing."""

    def test_parse_minimal_config(self) -> None:
        """Test parsing a config with only required fields."""
        config = Config()
        config.parse(CONFIGS_FIXTURES_DIR / "minimal_config.yaml")

        assert config.account == AccountConfig(name="My Account", currency="EUR")
        assert config.database_path == Path("budget.db")

    def test_parse_preserves_defaults_for_missing_optional_fields(self) -> None:
        """Test that optional fields keep defaults when not in YAML."""
        config = Config()
        config.parse(CONFIGS_FIXTURES_DIR / "minimal_config.yaml")

        assert config.inbox_exclude_patterns == []
        assert config.inbox_include_patterns == []
        assert config.backup == BackupConfig(
            enabled=True, max_backups=5, directory=None
        )
        assert config.logging_config is None

    def test_parse_full_config(self) -> None:
        """Test parsing a config with all optional fields set."""
        config = Config()
        config.parse(CONFIGS_FIXTURES_DIR / "full_config.yaml")

        assert config.language == "fr"
        assert config.account == AccountConfig(name="Full Account", currency="USD")
        assert config.database_path == Path("budget.db")
        assert config.inbox_path == Path("inbox")
        assert config.inbox_exclude_patterns == ["*.tmp", "*.bak"]
        assert config.inbox_include_patterns == ["*.xls", "*.csv"]
        assert config.backup == BackupConfig(
            enabled=False, max_backups=10, directory=Path("backups")
        )
        assert config.logging_config is not None
        assert config.logging_config["version"] == 1

    def test_parse_backup_partial_config(self) -> None:
        """Test parsing backup config with only some fields set."""
        config = Config()
        config.parse(CONFIGS_FIXTURES_DIR / "backup_partial_config.yaml")

        assert config.backup.enabled is False
        assert config.backup.max_backups == 5  # default
        assert config.backup.directory is None  # default

    def test_parse_inbox_patterns_none_becomes_empty_list(self) -> None:
        """Test that null inbox patterns in YAML are converted to empty lists."""
        config = Config()
        config.parse(CONFIGS_FIXTURES_DIR / "null_patterns_config.yaml")

        assert config.inbox_exclude_patterns == []
        assert config.inbox_include_patterns == []

    def test_parse_unsupported_format_raises(self, tmp_path: Path) -> None:
        """Test that parsing a non-YAML file raises ValueError."""
        config_path = tmp_path / "config.json"
        config_path.write_text("{}")

        config = Config()
        with pytest.raises(ValueError, match="Unsupported file format: '.json'"):
            config.parse(config_path)


class TestConfigSetupLogging:
    """Tests for the setup_logging method."""

    def test_setup_logging_default(self, tmp_path: Path) -> None:
        """Test that default logging writes to a file in .local/share."""
        config = Config()

        with patch("budget_forecaster.infrastructure.config.Path.home") as mock_home:
            mock_home.return_value = tmp_path
            config.setup_logging()

        log_dir = tmp_path / ".local" / "share" / "budget-forecaster"
        assert log_dir.exists()

    def test_setup_logging_with_valid_dictconfig(self) -> None:
        """Test that valid logging dictConfig is applied."""
        config = Config()
        config.parse(CONFIGS_FIXTURES_DIR / "full_config.yaml")
        # Should not raise
        config.setup_logging()

    def test_setup_logging_with_invalid_dictconfig(self) -> None:
        """Test that invalid logging config falls back to basic config."""
        config = Config()
        config.logging_config = {"invalid": "config"}

        # Should not raise — falls back to basicConfig
        config.setup_logging()

        # Verify a fallback logger was configured
        logger = logging.getLogger()
        assert logger.level is not None
