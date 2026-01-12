# Code Review

Review the current branch changes for code quality.

## Instructions

1. Get the current branch and diff against main:

```bash
git diff main...HEAD
```

2. Review the changes for:

   - Code quality and readability
   - Type hints completeness
   - Test coverage for new code
   - Potential bugs or edge cases
   - Adherence to project conventions (see CLAUDE.md)

3. For Claude configuration files (`.claude/`):

   - Check for duplicate permissions in `settings.json`
   - Verify consistency between PR description and actual changes
   - Check for missing permissions based on project context (e.g., `mypy` if used)
   - Ensure `$ARGUMENTS` is correctly placed in command templates

4. Provide a summary with:

   - What's good
   - What could be improved
   - Any blocking issues

5. If a GitHub PR URL or number is provided in $ARGUMENTS:
   - Extract the PR number from the URL (e.g., `/pull/35` → `35`)
   - Use `gh pr view <number>` to get PR details
   - After completing the review, post it using:
     ```bash
     gh pr review <number> --comment --body "review content here"
     ```
   - For approval: `gh pr review <number> --approve --body "..."`
   - For requesting changes: `gh pr review <number> --request-changes --body "..."`

$ARGUMENTS
