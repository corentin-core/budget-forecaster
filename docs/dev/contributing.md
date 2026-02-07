# Contributing

## Development Environment Setup

### Prerequisites

- Python 3.12+
- Git

### Installation

```bash
# Clone the repository
git clone git@github.com:corentin-core/budget-forecaster.git
cd budget-forecaster

# Create and activate virtual environment
python3.12 -m venv budget-forecaster-venv
source budget-forecaster-venv/bin/activate

# Install the package with dev dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pip install pre-commit
pre-commit install
```

### Running the Application

```bash
# Launch the TUI (creates default config on first run)
python -m budget_forecaster.main

# With a specific config file
python -m budget_forecaster.main -c config.yaml
```

### Running Tests

```bash
# Run all tests
pytest tests/

# Run a specific test file
pytest tests/domain/operation/test_budget.py -v

# Run with coverage
pytest tests/ --cov=budget_forecaster --cov-report=html
```

## Commit Messages

The project uses [Conventional Commits](https://www.conventionalcommits.org/):

```
type: description in imperative mood
```

| Type       | Purpose                                               |
| ---------- | ----------------------------------------------------- |
| `feat`     | New feature                                           |
| `fix`      | Bug fix                                               |
| `refactor` | Code changes that neither fix a bug nor add a feature |
| `test`     | Adding or updating tests                              |
| `docs`     | Documentation updates                                 |
| `chore`    | Maintenance tasks                                     |

Examples:

```
feat: add multi-currency support for accounts
fix: correct balance calculation with pending operations
refactor: simplify forecast generation logic
```
