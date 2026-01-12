# Budget Forecaster

Personal budget forecasting CLI application in Python. Imports bank statements (BNP,
Swile), categorizes operations, and generates forecasts.

## Architecture

```
budget_forecaster/
  account/           # Account management and SQLite persistence
  bank_adapter/      # Bank import adapters (BNP, Swile)
  forecast/          # Forecasting logic and actualization
  operation_range/   # Operations, budgets, categorization
  main.py            # CLI entry point
tests/               # pytest unit tests
```

## Common commands

```bash
# Activate virtual environment
source budget-forecaster-venv/bin/activate

# Run tests
pytest tests/

# Run a specific test
pytest tests/test_budget.py -v

# Load a bank statement
python -m budget_forecaster.main -c config.yaml load BNP-2025-01-29.xlsx

# Generate a forecast
python -m budget_forecaster.main -c config.yaml forecast

# Categorize operations
python -m budget_forecaster.main -c config.yaml categorize
```

## Code conventions

- Python 3.12+
- Type hints required
- Docstrings for public functions
- pytest tests for any new feature
- No dependencies not listed in setup.py
- Always run tests (`pytest tests/`) before committing changes

## Data files (not versioned)

- `*.xlsx` - BNP bank statements
- `*.db` - SQLite account database
- `config.yaml` - Local configuration
- `planned_operations.csv` - Planned operations
- `budgets.csv` - Budgets by category

## Important notes

- Categories are defined in `budget_forecaster/types.py`
- Persistence uses SQLite (`account/sqlite_repository.py`)
- Amounts are in EUR by default
- Always ask for review before committing
