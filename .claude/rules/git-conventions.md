# Git Conventions

## Pre-commit Validation

**BEFORE committing changes**, you MUST:

1. **Run linters** to ensure code quality
2. **Run tests** to verify your changes don't break existing functionality

```bash
# Run linters first
source budget-forecaster-venv/bin/activate && pre-commit run --all-files

# Then run tests
pytest tests/

# Then commit (pre-commit hooks will run automatically)
git add <files> && git commit -m "message"
```

Never commit without running linters and tests first, even for "simple" changes.

## Virtual Environment Activation

**ALWAYS activate the venv in the same command as git commit.**

Pre-commit hooks need access to project dependencies (pylint, etc.). The venv activation
doesn't persist between bash commands, so combine them:

```bash
# GOOD - activation persists for git commit
source budget-forecaster-venv/bin/activate && git add <files> && git commit -m "message"

# BAD - venv not available when pre-commit runs
source budget-forecaster-venv/bin/activate
git commit -m "message"  # pylint not found!
```

## Branch Creation

**ALWAYS use git worktrees** to isolate work from the main working directory.

```bash
# GOOD - create a worktree from main
git worktree add ../budget-forecaster-42 -b issue/42-new-feature origin/main

# BAD - checkout in the main worktree (blocks other work)
git checkout -b issue/42-new-feature
```

Worktree path convention: `../budget-forecaster-<issue-number>`.

To activate the venv from a worktree:

```bash
source ../budget-forecaster/budget-forecaster-venv/bin/activate
```

Cleanup after merge:

```bash
git worktree remove ../budget-forecaster-42
```

## Worktree + Editable Install

**The package is installed in editable mode (`pip install -e`).** The editable finder
maps `budget_forecaster` to the **main repo** directory, NOT the worktree.

When running `python3 budget_forecaster/main.py` from a worktree, Python sets
`sys.path[0]` to the script's directory (`budget_forecaster/`), can't find the package
there, and falls through to the editable install — which loads code from the **main
repo**.

**Rule**: ALWAYS use `PYTHONPATH=.` when running the app from a worktree:

```bash
# BAD - loads code from the main repo, not the worktree!
python3 budget_forecaster/main.py

# GOOD - forces Python to find the package in the current directory first
PYTHONPATH=. python3 -m budget_forecaster.main
```

**When testing worktree changes**, always verify the correct code is loaded before
debugging layout or behavior issues.

## Branch Naming

Format: `issue/<number>-<kebab-case-description>` or `feature/<number>-<description>`

Example: `issue/42-add-multi-currency-support`

## Commit Messages

Conventional Commits format:

```
type: Description using sentence case without terminal dot
```

**Types:**

| Type     | Purpose                                               |
| -------- | ----------------------------------------------------- |
| feat     | New feature                                           |
| fix      | Bug fix                                               |
| refactor | Code changes that neither fix a bug nor add a feature |
| test     | Adding or updating tests                              |
| docs     | Documentation updates                                 |
| chore    | Maintenance tasks                                     |

**Examples:**

```bash
# Good
feat: add multi-currency support for accounts
fix: correct balance calculation with pending operations
refactor: simplify forecast generation logic

# Bad
fix: bug fix                    # Too vague
update styles                   # No type specified
Added new feature.              # Wrong casing, unnecessary period
```

## Pull Request Merging

**NEVER merge a PR without explicit user approval.**

After creating a PR:

1. Share the PR URL with the user
2. Wait for the user to review the code and CI checks
3. Only merge when the user explicitly says to merge

**Before merging**, wait for CI checks (codecov) to pass:

```bash
# Check CI status
gh pr checks 123 --watch

# Then merge
gh pr merge 123 --squash
```

```
# BAD - merging without waiting for CI
gh pr merge 123 --squash

# GOOD - ask first, wait for CI + approval
"PR #123 created. Let me know when you want me to merge it."
```

## Important

- **NEVER commit directly to main** - always create a feature branch
- **NEVER use `git add -A` or `git add .`** - stage files explicitly
- **NEVER merge PRs without explicit user approval**
- **NEVER add `Co-Authored-By: Claude` to commit messages**
- Use imperative mood: "add feature" not "added feature"
- Keep first line under 50 characters
- Reference issue numbers in the body if relevant

---

For PR workflow and issue creation, see `CLAUDE.md`.
