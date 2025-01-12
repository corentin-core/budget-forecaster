"""Module for the PersistentAccount class."""
import json
import pathlib
from datetime import datetime

from budget_forecaster.account.account import Account
from budget_forecaster.account.aggregated_account import AggregatedAccount
from budget_forecaster.amount import Amount
from budget_forecaster.operation_range.historic_operation import HistoricOperation
from budget_forecaster.types import Category


class AggregatedAccountConverter:
    """A class to serialize and deserialize an aggregated accounts to a json file."""

    @staticmethod
    def to_json(aggregated_account: AggregatedAccount) -> str:
        """Convert an account to a json string."""
        json_aggregated_account_account = {
            "name": aggregated_account.account.name,
            "accounts": {
                account.name: {
                    "balance": account.balance,
                    "currency": account.currency,
                    "balance_date": account.balance_date.isoformat(),
                    "operations": [
                        {
                            "unique_id": operation.unique_id,
                            "description": operation.description,
                            "category": operation.category.value,
                            "date": operation.date.isoformat(),
                            "amount": operation.amount,
                            "currency": operation.currency,
                        }
                        for operation in account.operations
                    ],
                }
                for account in aggregated_account.accounts
            },
        }
        return json.dumps(json_aggregated_account_account)

    @staticmethod
    def from_json(json_aggregated_account_account: str) -> AggregatedAccount:
        """Convert a json string to an account."""
        aggregated_account_data = json.loads(json_aggregated_account_account)
        aggregated_name = aggregated_account_data["name"]
        accounts = []
        for account_name, account_data in aggregated_account_data["accounts"].items():
            balance = account_data["balance"]
            currency = account_data["currency"]
            balance_date = datetime.fromisoformat(account_data["balance_date"])
            operations = [
                HistoricOperation(
                    unique_id=operation["unique_id"],
                    description=operation["description"],
                    category=Category(operation["category"]),
                    date=datetime.fromisoformat(operation["date"]),
                    amount=Amount(operation["amount"], operation["currency"]),
                )
                for operation in account_data["operations"]
            ]
            accounts.append(
                Account(
                    account_name, balance, currency, balance_date, tuple(operations)
                )
            )
        return AggregatedAccount(aggregated_name, accounts)


class PersistentAccount:
    """Saved multiple accounts in a file and aggregate them as one."""

    def __init__(self, backup_path: pathlib.Path) -> None:
        self.__backup_path = backup_path
        self.__aggregated_account: AggregatedAccount | None = None

    def save(self) -> None:
        """Save the account to a file."""
        # make a backup of previous account
        if self.__backup_path.exists():
            self.__backup_path.rename(self.__backup_path.with_suffix(".back"))
        self.__backup_path.write_text(
            AggregatedAccountConverter.to_json(self.aggregated_account),
            encoding="utf-8",
        )

    def load(self) -> None:
        """Load the account from a file."""
        if self.__backup_path.exists():
            self.__aggregated_account = AggregatedAccountConverter.from_json(
                self.__backup_path.read_text(encoding="utf-8")
            )
            return
        raise FileNotFoundError("No account found")

    @property
    def aggregated_account(self) -> AggregatedAccount:
        """Return the aggregated account"""
        if self.__aggregated_account is None:
            raise FileNotFoundError("No account found")
        return self.__aggregated_account
