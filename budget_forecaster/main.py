"""Main module for the Budget Forecaster application."""
import argparse
import sys
from datetime import date, datetime, time
from pathlib import Path

from dateutil.relativedelta import relativedelta

from budget_forecaster.account.account import Account, AccountParameters
from budget_forecaster.account.account_analysis_renderer import (
    AccountAnalysisRendererExcel,
)
from budget_forecaster.account.account_analyzer import AccountAnalyzer
from budget_forecaster.account.persistent_account import PersistentAccount
from budget_forecaster.bank_adapter.bank_adapter_factory import BankAdapterFactory
from budget_forecaster.config import Config
from budget_forecaster.forecast.forecast import Forecast
from budget_forecaster.forecast.forecast_reader import ForecastReader
from budget_forecaster.operation_range.historic_operation import HistoricOperation
from budget_forecaster.operation_range.historic_operation_factory import (
    HistoricOperationFactory,
)
from budget_forecaster.types import Category


def get_last_operation_id(account: Account) -> int:
    """Get the last operation id."""
    if not account.operations:
        return 0

    return max(operation.unique_id for operation in account.operations)


def load_bank_export(
    export_path: Path, operation_factory: HistoricOperationFactory
) -> AccountParameters:
    """
    Load a bank export and update the account.
    """
    bank_adapter_factory = BankAdapterFactory()
    bank_adapter = bank_adapter_factory.create_bank_adapter(export_path)
    bank_adapter.load_bank_export(export_path, operation_factory)

    print(f"Loaded {len(bank_adapter.operations)} operations from {export_path}")

    return AccountParameters(
        name=bank_adapter.name,
        balance=bank_adapter.balance,
        currency="EUR",
        balance_date=bank_adapter.export_date or datetime.now(),
        operations=bank_adapter.operations,
    )


def create_parser() -> argparse.ArgumentParser:
    """
    Create the argument parser for the CLI.
    """
    parser = argparse.ArgumentParser(description="Budget Forecaster")
    parser.add_argument(
        "-c",
        "--config",
        help="Config of the accounts",
        type=Path,
        required=True,
    )
    sub_parser = parser.add_subparsers(dest="command")

    load_parser = sub_parser.add_parser("load", help="Load a bank export")
    load_parser.add_argument(
        "bank_export",
        help="Path to the bank export",
        type=Path,
    )

    forecast_parser = sub_parser.add_parser("forecast", help="Forecast the budget")
    forecast_parser.add_argument(
        "start_date",
        help="Start date for the forecast",
        type=date.fromisoformat,
        nargs="?",
        default=date.today() - relativedelta(months=4),
    )
    forecast_parser.add_argument(
        "end_date",
        help="End date for the forecast",
        type=date.fromisoformat,
        nargs="?",
        default=date.today() + relativedelta(months=12),
    )

    sub_parser.add_parser("add", help="Add an operation")
    categorize_parser = sub_parser.add_parser(
        "categorize", help="Categorize operations"
    )
    categorize_parser.add_argument(
        "-o",
        "--operation",
        help="ID of the operation to categorize",
        type=int,
        nargs="?",
    )
    return parser


def load_persistent_account(
    config: Config,
) -> PersistentAccount:
    """
    Load the persistent account from the backup file.
    If the file does not exist, create a new account.
    """
    persistent_account = PersistentAccount(backup_path=config.backup_path)
    try:
        persistent_account.load()
        account = persistent_account.aggregated_account.account
        print("Loaded account:")
        print("Name:", account.name)
        print("Balance:", account.balance)
        print("Currency:", account.currency)
        print("Balance date:", account.balance_date)
        print("Operations:", len(account.operations))
    except FileNotFoundError:
        print("No account found. Creating a new one.")
        print(
            f"Creating account {config.account.name} with currency {config.account.currency}"
        )
        # Save the account
        persistent_account.aggregated_account.upsert_account(
            AccountParameters(
                name=config.account.name,
                balance=0.0,
                currency=config.account.currency,
                balance_date=datetime.min,
                operations=(),
            )
        )
        persistent_account.save()

    return persistent_account


def handle_load_command(
    bank_export_path: Path,
    persistent_account: PersistentAccount,
    operation_factory: HistoricOperationFactory,
) -> None:
    """Handle the load command."""
    persistent_account.aggregated_account.upsert_account(
        load_bank_export(bank_export_path, operation_factory)
    )
    persistent_account.save()
    account = persistent_account.aggregated_account.account
    print("New account state:")
    print("Name:", account.name)
    print("Balance:", account.balance)
    print("Currency:", account.currency)
    print("Balance date:", account.balance_date)
    print("Operations:", len(account.operations))
    sys.exit(0)


def handle_forecast_command(
    start_date: date,
    end_date: date,
    account: Account,
    config: Config,
) -> None:
    """Handle the forecast command."""
    forecast_reader = ForecastReader()
    planned_operations = forecast_reader.read_planned_operations(
        config.planned_operations_path
    )
    budgets = forecast_reader.read_budgets(config.budgets_path)
    forecast = Forecast(planned_operations, budgets)

    account_analyzer = AccountAnalyzer(account, forecast)
    report = account_analyzer.compute_report(
        datetime.combine(start_date, time()),
        datetime.combine(end_date, time()),
    )

    renderer = AccountAnalysisRendererExcel(
        Path(f"BNP-{account.balance_date.date()}.xlsx")
    )
    renderer.render_report(report)
    sys.exit(0)


def handle_categorize_command(
    account: Account,
    persistent_account: PersistentAccount,
    operation_id: int | None,
) -> None:
    """Handle the categorize command."""
    category_mapping = dict(enumerate(sorted(Category, key=lambda cat: cat.value)))

    def categorize_operation(operation: HistoricOperation) -> HistoricOperation:
        nonlocal account
        print("Un-categorized operation:")
        print(operation)
        while True:
            try:
                print("Please enter one of the following categories:")
                for index, category in category_mapping.items():
                    print(f"{index}: {category}")
                category_index = input("Category: ")
                category = category_mapping[int(category_index)]
                break
            except (ValueError, KeyError):
                print("Invalid category")
        return operation.replace(category=category)

    if operation_id is not None:
        operation = next(
            (op for op in account.operations if op.unique_id == operation_id),
            None,
        )
        if operation is None:
            print(f"No operation found with ID {operation_id}")
            sys.exit(1)
        new_operation = categorize_operation(operation)
        persistent_account.aggregated_account.replace_operation(new_operation)
        persistent_account.save()
        sys.exit(0)

    for operation in sorted(account.operations, key=lambda op: op.date, reverse=True):
        if operation.category == Category.OTHER:
            new_operation = categorize_operation(operation)
            persistent_account.aggregated_account.replace_operation(new_operation)
            persistent_account.save()
    sys.exit(0)


def main() -> None:
    """
    Command Line Interface for the Budget Forecaster application.
    Several commands are available:
    - load: Load a bank export
    - forecast: Forecast the budget
    - add: Add an operation
    - categorize: Categorize operations
    """
    parser = create_parser()
    args = parser.parse_args()

    config = Config()
    config.parse(Path(args.config))

    persistent_account = load_persistent_account(config)
    account = persistent_account.aggregated_account.account

    # Create an operation factory
    operation_factory = HistoricOperationFactory(
        get_last_operation_id(account) if account else 0
    )

    match args.command:
        case "load":
            if args.bank_export is None:
                raise ValueError("The bank export path is required for the load action")
            handle_load_command(
                args.bank_export,
                persistent_account,
                operation_factory,
            )

        case "forecast":
            handle_forecast_command(
                args.start_date,
                args.end_date,
                account,
                config,
            )

        case "add":
            raise NotImplementedError("The add action is not implemented yet")

        case "categorize":
            handle_categorize_command(
                account,
                persistent_account,
                args.operation,
            )

        case _:
            parser.print_help()
            sys.exit(1)


if __name__ == "__main__":
    main()
