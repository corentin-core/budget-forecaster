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
- **Prefer tuples over lists for return types** - Use `tuple[T, ...]` instead of
  `list[T]` for function return values (tuples are immutable and signal that the caller
  shouldn't modify the result)

## Design principles

- **Check the design before implementing** - Read linked issues (`Related to #X`) to
  understand the full feature design. Don't add methods not specified in the design.

- **Prefer domain objects over primitives** - Use `tuple[OperationLink, ...]` instead of
  `dict[OperationId, IterationDate]`. Domain objects are more expressive and avoid
  transformations.

- **Single source of truth** - Don't maintain two representations of the same data
  (e.g., a tuple AND an index dict). Pick one and derive the other if needed.

- **Immutability by default** - Prefer immutable objects when the design allows. If an
  object receives data at construction and doesn't need mutation methods, don't add
  them.

- **Simplify method signatures** - Accept domain objects directly
  (`target: PlannedOperation | Budget`) rather than their decomposed parts
  (`linked_type, linked_id, matcher`).

- **Avoid redundant computations** - If you compute something in a loop, store it in the
  result structure rather than recomputing it later.

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

## Git workflow

- **NEVER commit directly to main** - always create a feature branch and submit a PR
- When working on an issue:
  1. Create a branch from up-to-date main:
     `git checkout main && git pull && git checkout -b issue/<number>-<short-description>`
  2. Make commits on the feature branch
  3. Push the branch and create a PR with `gh pr create`
- **Never use `git add -A` or `git add .`** - always stage files explicitly to avoid
  committing untracked files (venv, data files, etc.)
- Use `git add <file1> <file2>` to stage only the files you intend to commit

## PR review workflow

When addressing PR review comments:

- **Always reply inline** to each comment using
  `gh api repos/{owner}/{repo}/pulls/{pr}/comments/{id}/replies -X POST -f body="..."`
- **Never post global comments** summarizing changes - each comment deserves its own
  inline response
- **Prefix replies with `🤖 Claude:`** to distinguish AI-generated responses from user
  comments (since both appear under the same GitHub account)
- Reference commit hashes and issue numbers in replies (e.g., "🤖 Claude: ✅ Fixed in
  commit abc123" or "🤖 Claude: 📝 Issue created: #42")

## Creating GitHub issues

All issues must be created in **English** with the following structure:

### Required elements

1. **Labels** (add with `gh issue edit {id} --add-label "label"`):

   - Priority: `P0-critical`, `P1-high`, `P2-medium`, `P3-low`
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

gh issue edit $ISSUE_NUM --add-label "enhancement" --add-label "P2-medium"
```

## Testing Principles

**Test the feature, not just the code.** Unit tests alone are not sufficient.

When implementing or reviewing tests:

1. **End-to-end tests are required** - Every feature needs at least one test that
   exercises the complete flow, not just individual components with mocks

2. **Use fixtures for expected outputs** - For features that generate files (CSV, Excel,
   JSON), include reference files in `tests/fixtures/` and compare against them

3. **Validate actual output** - A test that only checks "no exception thrown" or "file
   exists" is insufficient. Verify the content matches expectations

Example of insufficient vs. sufficient testing:

```python
# Insufficient - only checks file exists
def test_export():
    exporter.export(data, "output.csv")
    assert Path("output.csv").exists()

# Sufficient - validates actual content
def test_export():
    exporter.export(data, "output.csv")
    expected = Path("tests/fixtures/expected.csv").read_text()
    assert Path("output.csv").read_text() == expected
```

## Workflow Automation

- **Use commands proactively** - Do not wait for the user to explicitly call them.
  Invoke them automatically when relevant to the current task (e.g., `/lint`, `/test`,
  `/review`, `/create-pr`)
