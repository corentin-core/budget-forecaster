---
name: create-pr
description: Create a well-documented GitHub pull request with proper linking to issues
---

# Create Pull Request

Create a well-documented GitHub pull request with proper linking to issues.

## Arguments

- `$ARGUMENTS`: Optional issue number to link (e.g., `#42` or `42`)

## Instructions

### 1. Gather context

```bash
# Current branch
git branch --show-current

# Commits on this branch
git log origin/main..HEAD --oneline

# Changes summary
git diff origin/main...HEAD --stat
```

If an issue number is provided, fetch issue details:

```bash
gh issue view <number>
```

### 2. Review the changes

```bash
git diff origin/main...HEAD
```

Identify:

- Main changes and their purpose
- Files that might need explanation for reviewers
- Any trade-offs or design decisions made

### 3. Ensure branch is pushed

```bash
# Push with upstream tracking if needed
git push -u origin $(git branch --show-current)
```

### 4. Create the PR

Use `gh pr create` with a structured body:

```bash
gh pr create --title "<type>: <description>" --body "$(cat <<'EOF'
## Summary

<Brief description of what this PR does>

## Related Issue

Closes #<issue_number>
<!-- or "Related to #<issue_number>" if it doesn't fully close -->

## Changes

- <List of main changes>
- <Grouped by component if needed>

## Notes for Reviewers

<Any context that helps reviewers understand the changes>
EOF
)"
```

### 5. Title format

Use conventional commits style:

- `feat: add budget import from CSV`
- `fix: correct date parsing in BNP adapter`
- `refactor: extract common logic to base class`
- `test: add tests for forecast module`
- `docs: update README with usage examples`

## Tips

- Keep the summary concise but informative
- Link the issue properly (`Closes #X` for auto-close on merge)
- Mention any areas where you'd like specific feedback
- If the PR is large, consider suggesting it be split

$ARGUMENTS
