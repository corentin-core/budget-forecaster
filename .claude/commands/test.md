Run tests on the specified module or directory.

Usage: /test [path]

Examples:

- /test (runs all tests)
- /test tests/test_budget.py
- /test tests/ -v

Run `pytest $ARGUMENTS` (defaults to `pytest tests/` if no arguments).

Report any failures with a summary and fix them.

$ARGUMENTS
