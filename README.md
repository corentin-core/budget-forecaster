# Budget Forecaster

[![CI](https://github.com/corentin-core/budget-forecaster/actions/workflows/ci.yml/badge.svg)](https://github.com/corentin-core/budget-forecaster/actions/workflows/ci.yml)
[![Docs](https://github.com/corentin-core/budget-forecaster/actions/workflows/docs.yml/badge.svg)](https://corentin-core.github.io/budget-forecaster/)
[![codecov](https://codecov.io/gh/corentin-core/budget-forecaster/graph/badge.svg)](https://codecov.io/gh/corentin-core/budget-forecaster)
[![CodSpeed](https://img.shields.io/endpoint?url=https://codspeed.io/badge.json)](https://codspeed.io/corentin-core/budget-forecaster)
![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)
![mypy strict](https://img.shields.io/badge/mypy-strict-blue)

Personal budget forecasting CLI application. Import bank statements, categorize
transactions, and generate balance forecasts through a terminal UI.

## Why

I used to track my budget in a spreadsheet. The recurring question was always: **"Can I
afford this expense, and when?"**

The spreadsheet worked, but it was painful to maintain and nearly impossible to adjust
mid-month. I looked at existing tools — they had nice dashboards and direct bank
connections, but none could forecast my balance the way I needed, and their budget
management was too limited.

So I built my own.
[Read the full story on my blog.](https://corentin-core.github.io/posts/budget-forecaster/)

## Features

- **Bank import** — Load statements from BNP Paribas (Excel) and Swile (JSON)
- **Categorization** — Automatic and manual categorization of transactions
- **Planned operations & budgets** — Define recurring expenses, one-time payments, and
  monthly budgets by category
- **Forecasting** — Project future balances based on planned operations, budgets, and
  history
- **Operation linking** — Match actual transactions to their planned counterparts for
  accurate forecast updates
- **Monthly review** — Per-category planned vs actual with consumption bars
- **Available margin** — Track remaining disposable income with alert threshold
- **Category drill-down** — Inspect planned sources and matched operations per category
- **Terminal UI** — Interactive interface built with
  [Textual](https://textual.textualize.io/)
- **Internationalization** — Available in English and French

## Screenshots

**Monthly Review** — Per-category budget tracking with consumption bars and available
margin:

![Review screen](docs/images/review.png)

**Balance** — Balance projection chart with past actuals and future forecast:

![Balance screen](docs/images/balance.png)

**Operations** — Imported transactions with categories and links to planned operations:

![Operations screen](docs/images/operations.png)

## Quick Start

Demo data is included so you can try the application without your own bank statements.

```bash
# Clone and install
git clone https://github.com/corentin-core/budget-forecaster.git
cd budget-forecaster
python3.12 -m venv venv && source venv/bin/activate
pip install -e .

# Optionally regenerate demo data with fresh dates
python examples/generate_demo.py

# Launch with the demo data
cd examples/
python -m budget_forecaster.main -c config.yaml
```

The demo database contains categorized operations with planned counterparts and budgets.
See [examples/README.md](examples/README.md) for details.

## Architecture

The application follows a layered architecture with clear separation of concerns:

```mermaid
graph TD
    Presentation["Presentation — CLI, Terminal UI (Textual)"]
    Services["Services — Use cases, forecasting, categorization, import"]
    Domain["Domain — Account, Operation, PlannedOperation, Budget, Forecast"]
    Core["Core — Amount, DateRange, Category"]
    Infrastructure["Infrastructure — SQLite persistence, bank adapters, config"]

    Presentation --> Services
    Services --> Domain
    Domain --> Core
    Services --> Infrastructure
```

See [docs/dev/architecture.md](docs/dev/architecture.md) for the full layer diagram.

## Tech Stack

| Area          | Tools                                                |
| ------------- | ---------------------------------------------------- |
| Language      | Python 3.12                                          |
| UI            | [Textual](https://textual.textualize.io/)            |
| Persistence   | SQLite                                               |
| Testing       | pytest                                               |
| Type checking | mypy (strict mode)                                   |
| Linting       | pylint, ruff, autoflake, pyupgrade                   |
| Formatting    | black, prettier                                      |
| CI            | GitHub Actions (pre-commit, mypy, pylint, tests+cov) |
| Pre-commit    | All of the above, run locally before each commit     |

## Documentation

Browse the full documentation at
[corentin-core.github.io/budget-forecaster](https://corentin-core.github.io/budget-forecaster/):

- **User guides** — Configuration, forecast, operations, TUI usage
- **Developer docs** — Architecture, data models, persistence, contributing
- **Quality scenarios** — Given-When-Then specifications for core features

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pip install pre-commit && pre-commit install

# Run tests
pytest tests/

# Run tests with coverage
pytest tests/ --cov=budget_forecaster --cov-report=html
```

See [docs/dev/contributing.md](docs/dev/contributing.md) for the full setup guide.
