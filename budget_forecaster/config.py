"""Module for the Config class."""
import logging
import logging.config
import subprocess
from pathlib import Path
from typing import Any, NamedTuple

import yaml


def _get_user_download_dir() -> Path:
    """Get the user's download directory using xdg-user-dir or fallback."""
    try:
        result = subprocess.run(
            ["xdg-user-dir", "DOWNLOAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Fallback to ~/Downloads
        return Path.home() / "Downloads"


class AccountConfig(NamedTuple):
    """A class to store the account configuration."""

    name: str
    currency: str


class BackupConfig(NamedTuple):
    """Configuration for automatic database backups."""

    enabled: bool = True
    max_backups: int = 5
    directory: Path | None = None  # None = same directory as database


class Config:  # pylint: disable=too-few-public-methods
    """A class to store the configuration."""

    def __init__(self) -> None:
        # Account config
        self.account = AccountConfig(name="Main Account", currency="EUR")
        self.database_path = Path("budget.db")
        # Backup config
        self.backup = BackupConfig()
        # Import config (default to user's download directory)
        self.inbox_path = _get_user_download_dir()
        self.inbox_exclude_patterns: list[str] = []
        # Logging config (native Python logging dictConfig format)
        self.logging_config: dict[str, Any] | None = None

    def __parse_yaml(self, yaml_path: Path) -> None:
        """Parse a YAML configuration file."""
        with open(yaml_path, encoding="utf-8") as file:
            config = yaml.safe_load(file)
            self.database_path = Path(config["database_path"]).expanduser()
            self.account = AccountConfig(
                name=config["account_name"],
                currency=config["account_currency"],
            )
            if "inbox_path" in config:
                self.inbox_path = Path(config["inbox_path"]).expanduser()
            if "inbox_exclude_patterns" in config:
                self.inbox_exclude_patterns = config["inbox_exclude_patterns"] or []
            # Parse backup config
            if "backup" in config:
                backup_cfg = config["backup"]
                self.backup = BackupConfig(
                    enabled=backup_cfg.get("enabled", True),
                    max_backups=backup_cfg.get("max_backups", 5),
                    directory=(
                        Path(backup_cfg["directory"]).expanduser()
                        if backup_cfg.get("directory")
                        else None
                    ),
                )
            # Parse logging config (native dictConfig format)
            if "logging" in config:
                self.logging_config = config["logging"]

    def setup_logging(self) -> None:
        """Initialize Python's logging system using the configuration."""
        if not self.logging_config:
            # Default basic configuration
            logging.basicConfig(
                level=logging.INFO,
                format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            )
        else:
            try:
                logging.config.dictConfig(self.logging_config)
            except (ValueError, TypeError, AttributeError, ImportError) as e:
                # Fallback to basic config on error
                logging.basicConfig(level=logging.DEBUG)
                logging.error("Invalid logging configuration: %s", e)

        logging.debug("Logging initialized")

    def parse(self, config_path: Path) -> None:
        """Parse a configuration file."""
        if config_path.suffix == ".yaml":
            self.__parse_yaml(config_path)
        else:
            raise ValueError(f"Unsupported file format: '{config_path.suffix}'")
