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

## Pre-commit Hooks

The project uses pre-commit hooks that run automatically on every commit:

| Hook        | Purpose                             |
| ----------- | ----------------------------------- |
| autoflake   | Remove unused imports and variables |
| ruff        | Fast linter (import sorting, style) |
| pyupgrade   | Modernize Python syntax             |
| black       | Code formatting                     |
| mypy        | Static type checking                |
| pylint      | Code quality analysis               |
| prettier    | Markdown/YAML formatting            |
| trailing-ws | Remove trailing whitespace          |
| end-of-file | Ensure files end with a newline     |

**Important**: Always activate the virtual environment in the same command as
`git commit`, since pre-commit hooks need access to project dependencies:

```bash
source budget-forecaster-venv/bin/activate && git commit -m "message"
```

## Code Conventions

### Type Hints

All functions must have complete type annotations:

```python
def compute_balance(
    operations: tuple[HistoricOperation, ...], initial: Amount
) -> Amount:
    ...
```

### Immutability

- Return `tuple[T, ...]` instead of `list[T]` from functions
- Use `NamedTuple` for simple data records
- Use `@dataclass(frozen=True)` for domain objects with custom methods

### Encapsulation

- Attributes are private by default (`self._repository`, not `self.repository`)
- Expose through properties when needed

### Domain Objects Over Primitives

Use domain types instead of `dict`, `str`, or raw `int`:

```python
# Prefer
def get_links(self) -> tuple[OperationLink, ...]: ...

# Over
def get_links(self) -> dict[int, date]: ...
```

## Testing Conventions

- **pytest** is the test framework
- Tests mirror the source structure under `tests/`
- End-to-end tests are required for every feature
- Use fixtures for expected outputs (`tests/fixtures/`)
- Validate actual output content, not just existence

```python
# Validate actual behavior
def test_export():
    exporter.export(data, "output.csv")
    expected = Path("tests/fixtures/expected.csv").read_text()
    assert Path("output.csv").read_text() == expected
```

## Git Workflow

1. **Never commit directly to main** - always create a feature branch
2. **Branch naming**: `issue/<number>-<kebab-case-description>`
3. **Commit messages**: Conventional Commits format (`feat:`, `fix:`, `refactor:`, etc.)
4. **Stage files explicitly** - never use `git add -A` or `git add .`
5. **Run tests before committing**

```bash
# Create a feature branch from main
git checkout main && git pull origin main
git checkout -b issue/42-add-multi-currency

# After implementing and testing
source budget-forecaster-venv/bin/activate && git add <files> && git commit -m "feat: add multi-currency support"

# Push and create PR
git push -u origin issue/42-add-multi-currency
gh pr create --title "feat: add multi-currency support" --body "Closes #42"
```

## Architecture Overview

The codebase follows a layered architecture. See [Architecture](architecture.md) for the
full diagram and layer descriptions.

| Layer              | Purpose                                                                 |
| ------------------ | ----------------------------------------------------------------------- |
| **Core**           | Foundational types (`Amount`, `DateRange`, `Category`) with no deps     |
| **Domain**         | Business entities (accounts, operations, forecasts) - pure data + rules |
| **Services**       | Orchestration between domain objects, use case implementation           |
| **Infrastructure** | Persistence (SQLite), file parsing (bank adapters), configuration       |
| **Presentation**   | CLI and TUI (Textual framework)                                         |

Dependencies flow downward: Presentation -> Services -> Domain -> Core. Infrastructure
implements interfaces defined by the upper layers.

## Adding a New Feature

1. Check for an existing issue or create one
2. Read related issues and existing documentation
3. Implement data models first, then core logic, then entry points
4. Write tests that validate behavior (not just existence)
5. Run `pytest tests/` to verify
6. Commit and create a PR
