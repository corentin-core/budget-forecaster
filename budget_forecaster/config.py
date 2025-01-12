"""Module for the Config class."""
from pathlib import Path
from typing import NamedTuple

import yaml


class AccountConfig(NamedTuple):
    """A class to store the account configuration."""

    name: str
    currency: str


class Config:  # pylint: disable=too-few-public-methods
    """A class to store the configuration."""

    def __init__(self) -> None:
        # Account config
        self.account = AccountConfig(name="Main Account", currency="EUR")
        self.backup_path = Path("account.json")
        # Forecast config
        self.budgets_path = Path("budgets.json")
        self.planned_operations_path = Path("planned_operations.json")

    def __parse_yaml(self, yaml_path: Path) -> None:
        """Parse a YAML configuration file."""
        with open(yaml_path, encoding="utf-8") as file:
            config = yaml.safe_load(file)
            self.backup_path = Path(config["backup_path"])
            self.budgets_path = Path(config["budgets_path"])
            self.planned_operations_path = Path(config["planned_operations_path"])
            self.account = AccountConfig(
                name=config["account_name"],
                currency=config["account_currency"],
            )

    def parse(self, config_path: Path) -> None:
        """Parse a configuration file."""
        if config_path.suffix == ".yaml":
            self.__parse_yaml(config_path)
        else:
            raise ValueError(f"Unsupported file format: '{config_path.suffix}'")
