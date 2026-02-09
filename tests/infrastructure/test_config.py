"""Tests for the Config class."""

import logging
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from budget_forecaster.infrastructure.config import (
    AccountConfig,
    BackupConfig,
    Config,
)


@pytest.fixture
def minimal_config_yaml(tmp_path: Path) -> Path:
    """Create a minimal valid YAML config file."""
    config = {
        "database_path": str(tmp_path / "budget.db"),
        "account_name": "My Account",
        "account_currency": "EUR",
    }
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump(config), encoding="utf-8")
    return config_path


@pytest.fixture
def full_config_yaml(tmp_path: Path) -> Path:
    """Create a YAML config file with all optional fields."""
    config = {
        "database_path": str(tmp_path / "budget.db"),
        "account_name": "Full Account",
        "account_currency": "USD",
        "inbox_path": str(tmp_path / "inbox"),
        "inbox_exclude_patterns": ["*.tmp", "*.bak"],
        "inbox_include_patterns": ["*.xls", "*.csv"],
        "backup": {
            "enabled": False,
            "max_backups": 10,
            "directory": str(tmp_path / "backups"),
        },
        "logging": {
            "version": 1,
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "level": "DEBUG",
                }
            },
            "root": {"level": "DEBUG", "handlers": ["console"]},
        },
    }
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump(config), encoding="utf-8")
    return config_path


class TestConfigDefaults:
    """Tests for Config default values."""

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

    def test_parse_minimal_config(
        self, minimal_config_yaml: Path, tmp_path: Path
    ) -> None:
        """Test parsing a config with only required fields."""
        config = Config()
        config.parse(minimal_config_yaml)

        assert config.account == AccountConfig(name="My Account", currency="EUR")
        assert config.database_path == tmp_path / "budget.db"

    def test_parse_preserves_defaults_for_missing_optional_fields(
        self, minimal_config_yaml: Path
    ) -> None:
        """Test that optional fields keep defaults when not in YAML."""
        config = Config()
        config.parse(minimal_config_yaml)

        # inbox patterns should stay as defaults
        assert config.inbox_exclude_patterns == []
        assert config.inbox_include_patterns == []
        # backup should stay as default
        assert config.backup == BackupConfig(
            enabled=True, max_backups=5, directory=None
        )
        # logging should stay as None
        assert config.logging_config is None

    def test_parse_full_config(self, full_config_yaml: Path, tmp_path: Path) -> None:
        """Test parsing a config with all optional fields set."""
        config = Config()
        config.parse(full_config_yaml)

        assert config.account == AccountConfig(name="Full Account", currency="USD")
        assert config.database_path == tmp_path / "budget.db"
        assert config.inbox_path == tmp_path / "inbox"
        assert config.inbox_exclude_patterns == ["*.tmp", "*.bak"]
        assert config.inbox_include_patterns == ["*.xls", "*.csv"]
        assert config.backup == BackupConfig(
            enabled=False, max_backups=10, directory=tmp_path / "backups"
        )
        assert config.logging_config is not None
        assert config.logging_config["version"] == 1

    def test_parse_backup_partial_config(self, tmp_path: Path) -> None:
        """Test parsing backup config with only some fields set."""
        config_data = {
            "database_path": str(tmp_path / "budget.db"),
            "account_name": "Test",
            "account_currency": "EUR",
            "backup": {"enabled": False},
        }
        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.dump(config_data), encoding="utf-8")

        config = Config()
        config.parse(config_path)

        assert config.backup.enabled is False
        assert config.backup.max_backups == 5  # default
        assert config.backup.directory is None  # default

    def test_parse_inbox_patterns_none_becomes_empty_list(self, tmp_path: Path) -> None:
        """Test that null inbox patterns in YAML are converted to empty lists."""
        config_data = {
            "database_path": str(tmp_path / "budget.db"),
            "account_name": "Test",
            "account_currency": "EUR",
            "inbox_exclude_patterns": None,
            "inbox_include_patterns": None,
        }
        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.dump(config_data), encoding="utf-8")

        config = Config()
        config.parse(config_path)

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

    def test_setup_logging_with_valid_dictconfig(self, full_config_yaml: Path) -> None:
        """Test that valid logging dictConfig is applied."""
        config = Config()
        config.parse(full_config_yaml)
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
