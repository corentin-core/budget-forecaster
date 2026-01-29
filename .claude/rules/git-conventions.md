# Git Conventions

## Pre-commit Validation

**BEFORE committing changes**, you MUST:

1. **Run tests** to verify your changes don't break existing functionality
2. **Run linters** (pre-commit or project-specific) to ensure code quality

```bash
# Run tests first
pytest tests/

# Then commit (pre-commit hooks will run automatically)
git add <files> && git commit -m "message"
```

Never commit without running tests first, even for "simple" changes.

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

```
# BAD - merging without asking
gh pr merge 123 --squash

# GOOD - ask first, wait for approval
"PR #123 created. Let me know when you want me to merge it."
```

## Important

- **NEVER commit directly to main** - always create a feature branch
- **NEVER use `git add -A` or `git add .`** - stage files explicitly
- **NEVER merge PRs without explicit user approval**
- Use imperative mood: "add feature" not "added feature"
- Keep first line under 50 characters
- Reference issue numbers in the body if relevant

---

For PR workflow and issue creation, see `CLAUDE.md`.
