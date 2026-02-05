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
  (`target_type, target_id, matcher`).

- **Avoid redundant computations** - If you compute something in a loop, store it in the
  result structure rather than recomputing it later.

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

- **NEVER commit directly to main** - always create a feature branch and submit a PR
- **Never use `git add -A` or `git add .`** - always stage files explicitly

See `.claude/rules/git-conventions.md` for branch naming, commit message format, and
detailed workflow.

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

- **End-to-end tests are required** for every feature
- **Use fixtures** for expected outputs (`tests/fixtures/`)
- **Validate actual output**, not just existence

See `.claude/rules/testing.md` for detailed patterns and examples.

## Workflow Automation

- **Use commands proactively** - Do not wait for the user to explicitly call them.
  Invoke them automatically when relevant to the current task (e.g., `/lint`, `/test`,
  `/review`, `/create-pr`)

## Working Principles

### Code Navigation with MCP Serena

**Prefer MCP Serena tools** for code navigation and exploration. Performance is
significantly better than grep/glob for symbol-based searches.

- `jet_brains_find_symbol` - Find symbol definitions by name
- `jet_brains_find_referencing_symbols` - Find all usages of a symbol
- `jet_brains_get_symbols_overview` - Get file structure overview
- `jet_brains_type_hierarchy` - Explore class hierarchies

Use Grep/Glob only for pattern searches in non-code files or when searching for strings
that aren't symbols.

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

This section teaches Claude how to learn from mistakes and write effective rules.

### When You Make a Mistake

If the user says **"Reflect on this mistake"**, follow this process:

1. **Reflect** - Analyze what went wrong using available context
2. **Abstract** - Extract the general pattern from the specific instance
3. **Generalize** - Create a reusable rule that prevents this class of errors
4. **Document** - Write the rule to `.claude/rules/` or update CLAUDE.md

### How to Write Effective Rules

| Principle                   | Description                                                      |
| --------------------------- | ---------------------------------------------------------------- |
| **Absolute directives**     | Start with "NEVER" or "ALWAYS" when the rule has no exceptions   |
| **Lead with why**           | Explain the problem (1-3 bullets) before the solution            |
| **Be concrete**             | Include actual code examples from the budget-forecaster codebase |
| **One point per example**   | Don't combine multiple lessons in one code block                 |
| **Bullets over paragraphs** | Keep explanations concise and scannable                          |

### Rule Format Template

````markdown
## Rule Name

**Why**: [1-3 bullet points explaining the problem this rule prevents]

**Rule**: ALWAYS/NEVER [specific instruction]

```python
# BAD - [brief explanation]
[code example]

# GOOD - [brief explanation]
[code example]
```
````

### Anti-Bloat Rules

- NEVER add warning sections to obvious rules
- NEVER show bad examples for trivial mistakes
- NEVER use paragraphs when bullets suffice
- NEVER add generic examples - use real project code

### When NOT to Create a Rule

- One-off mistakes that won't recur
- Mistakes already covered by existing rules (reinforce, don't duplicate)
- Style preferences without clear justification
