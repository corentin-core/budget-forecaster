# Commit Changes

Create a well-formatted git commit.

## Prerequisites

**ALWAYS activate the virtual environment before committing** so pre-commit hooks can
find linters (pylint, mypy, etc.):

```bash
source budget-forecaster-venv/bin/activate
```

## Instructions

1. Check the current status and diff:

```bash
git status
git diff --staged
```

2. If nothing is staged, ask what should be committed

3. Write a commit message following conventional commits:

   - `feat:` new feature
   - `fix:` bug fix
   - `refactor:` code refactoring
   - `test:` adding tests
   - `docs:` documentation

4. Create the commit:

```bash
git commit -m "type: description"
```

**Note**: Do NOT add `Co-Authored-By` lines (per project conventions in
CLAUDE.local.md).

5. Show the result with `git log -1`

$ARGUMENTS
