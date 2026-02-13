# Budget Forecaster

Personal budget forecasting CLI application in Python. Imports bank statements (BNP,
Swile), categorizes operations, and generates forecasts.

## Architecture

```
budget_forecaster/
  core/                  # Primitives (Amount, DateRange, types)
  domain/                # Business entities
    account/             # Account, AggregatedAccount
    operation/           # HistoricOperation, PlannedOperation, Budget, OperationLink
    forecast/            # Forecast
  services/              # Business logic
    account/             # AccountForecaster, AccountAnalyzer, reports
    operation/           # OperationService, OperationMatcher, Categorizer
    forecast/            # ForecastService, ForecastActualizer
    application_service.py
    import_service.py
  infrastructure/        # External interfaces
    persistence/         # SQLite repository
    bank_adapters/       # BNP, Swile adapters
    config.py, backup.py
  tui/                   # Terminal UI (Textual)
  main.py                # CLI entry point
tests/                   # Mirrors source structure
```

## Common commands

```bash
# Activate virtual environment
source budget-forecaster-venv/bin/activate

# Run tests
pytest tests/

# Run a specific test
pytest tests/domain/operation/test_budget.py -v

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

See `.claude/rules/python-quality.md` for detailed patterns and examples.

## Design principles

- **Check the design before implementing** - Read linked issues (`Related to #X`) to
  understand the full feature design. Don't add methods not specified in the design.

See `.claude/rules/python-quality.md` for detailed patterns (domain objects over
primitives, single source of truth, immutability, etc.).

## Data files (not versioned)

- `*.xlsx` - BNP bank statements
- `*.db` - SQLite account database
- `config.yaml` - Local configuration
- `planned_operations.csv` - Planned operations
- `budgets.csv` - Budgets by category

## Important notes

- Categories are defined in `budget_forecaster/core/types.py`
- Persistence uses SQLite (`infrastructure/persistence/sqlite_repository.py`)
- Amounts are in EUR by default
- Always ask for review before committing

## Git workflow

See `.claude/rules/git-conventions.md` for branch naming, commit messages, worktrees,
and merge workflow.

## PR review workflow

See `.claude/commands/handle-pr-comments.md` for the full PR comment handling workflow
(inline replies, `🤖 Claude:` prefix, commit references).

## Creating GitHub issues

All issues must be created in **English** with the following structure:

### Required elements

1. **Labels** (add with `gh issue edit {id} --add-label "label"`):

   - Priority: `priority:high`, `priority:medium`, `priority:low`
   - Theme: `enhancement`, `bug`, `refactor`, `documentation`, `testing`

2. **Issue body structure**:

   ```markdown
   ## Context

   Brief explanation of why this is needed.

   ## Proposed solution

   High-level design/approach (2-5 bullet points).

   ## Acceptance criteria

   - [ ] Criterion 1
   - [ ] Criterion 2

   ## Related issues

   - Depends on #X
   - Blocks #Y
   - Related to #Z
   ```

3. **Link related issues** using keywords: `depends on`, `blocks`, `related to`

### Example

```bash
# Create issue and capture its number
ISSUE_NUM=$(gh issue create --title "feat: add multi-currency support" --body "## Context
Currently all amounts are hardcoded in EUR.

## Proposed solution
- Add currency field to Account model
- Update bank adapters to detect currency from exports
- Add conversion service for reporting

## Acceptance criteria
- [ ] Account stores currency
- [ ] BNP/Swile adapters detect currency
- [ ] Reports show amounts in original currency

## Related issues
- Related to #36 (import filtering)
" | grep -oE '[0-9]+$')

gh issue edit $ISSUE_NUM --add-label "enhancement" --add-label "priority:medium"
```

## Testing Principles

See `.claude/rules/testing.md` for the full testing strategy (two-tier testing,
fixtures, validate actual output).

## Workflow Automation

- **Use commands proactively** - Do not wait for the user to explicitly call them.
  Invoke them automatically when relevant to the current task (e.g., `/lint`, `/test`,
  `/review`, `/create-pr`)

## Working Principles

### Code Navigation with MCP Serena

**Prefer MCP Serena tools** for code navigation and exploration. Performance is
significantly better than grep/glob for symbol-based searches.

- `find_symbol` - Find symbol definitions by name
- `find_referencing_symbols` - Find all usages of a symbol
- `get_symbols_overview` - Get file structure overview
- `search_for_pattern` - Flexible regex search across files

Use Grep/Glob only for pattern searches in non-code files or when searching for strings
that aren't symbols.

**Worktree limitation**: Serena operates on the **activated project** (main repo), not
on git worktrees.

- **Read/search tools** (find_symbol, get_symbols_overview, search_for_pattern): Safe to
  use — the base code is shared
- **Edit tools** (replace_symbol_body, insert_after_symbol): **Write to the main repo**,
  not the worktree. Use Edit/Write with absolute worktree paths instead.

### Coherence with Existing Codebase

When using internal modules, check how they're used in related code.

### Apply Changes Globally

When a fix or pattern is requested (via review comments or direct feedback), don't just
apply it where explicitly mentioned. Search for the same pattern elsewhere in the code
and fix all occurrences for consistency.

```bash
# Example: if asked to change list to tuple returns, search for similar patterns
grep -r "-> list\[" --include="*.py"
```

## META - Self-Improvement System

See `.claude/rules/auto-introspection.md` for the self-improvement workflow (triggered
when the user points out mistakes, proposes config updates).
