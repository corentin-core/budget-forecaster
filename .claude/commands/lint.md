# Lint

Run linters on the codebase.

## Instructions

1. Run pre-commit on all files or staged files:

```bash
# All files
pre-commit run --all-files

# Or staged files only
pre-commit run
```

2. If there are failures, analyze and fix them
3. Re-run until all checks pass

## Arguments

Optional: specify files or directories to lint (e.g., `/lint budget_forecaster/`). If no
arguments provided, lint all files.

$ARGUMENTS
