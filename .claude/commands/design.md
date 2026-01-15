# Design Issue

Fetch a GitHub issue, analyze it in the project context, and iterate on the design in a
local draft before updating the issue.

## Arguments

- `$ARGUMENTS`: Issue URL or number (e.g., `https://github.com/user/repo/issues/42` or
  `42`)

## Instructions

### 1. Fetch the issue

```bash
gh issue view <number>
```

Note the current state: title, description, labels, any existing design.

### 2. Analyze project context

Read relevant documentation to understand constraints:

- `CLAUDE.md` - Project conventions
- Related code files mentioned in the issue
- Existing patterns in the codebase

### 3. Create a local draft

Create a draft file in the repository root:

```bash
# File: <issue_number>_draft.md
```

Copy the issue description into this file, or start fresh if the issue lacks detail.

### 4. Design the solution

Structure the design with:

```markdown
## Context

<Why this is needed, what problem it solves>

## Proposed Solution

<High-level approach, 3-5 bullet points>

## Implementation Details

### Files to create/modify

- `budget_forecaster/module/file.py` - Description
- `tests/test_file.py` - Tests for the feature

### Data Model (if applicable)

<Classes, fields, relationships>

### Key Logic

<Algorithm or flow description>

## Acceptance Criteria

- [ ] Criterion 1
- [ ] Criterion 2
```

### 5. Verify data source mapping (CRITICAL)

For each output or data flow, ensure the design specifies:

| Aspect     | Bad (vague)         | Good (explicit)                         |
| ---------- | ------------------- | --------------------------------------- |
| Source     | "from the database" | "from `sqlite_repository.get_all()`"    |
| Field name | "the amount"        | "the `amount` field (Decimal)"          |
| Transform  | "format the date"   | "format as `YYYY-MM-DD` using strftime" |

**If data sources are unclear, ask for clarification.**

### 6. Review cycle

After each batch of changes:

1. Summarize what was modified
2. Ask if the user wants to:
   - Continue with more changes
   - Review the full draft
   - Update the GitHub issue

### 7. Update the GitHub issue

Once approved:

```bash
gh issue edit <number> --body "$(cat <issue_number>_draft.md)"
```

Then clean up:

```bash
rm <issue_number>_draft.md
```

## Workflow Summary

```
Fetch Issue
    |
    v
Analyze Context
    |
    v
Create Draft
    |
    v
+-> Edit Design
|       |
|       v
|   User Review ---> More changes needed?
|       |                   |
|       | Approved          +---> (loop back)
|       v
Update GitHub Issue
    |
    v
Cleanup Draft
```

## Tips

- **Incremental changes**: Don't rewrite everything at once. Make focused changes.
- **Be explicit**: Vague designs lead to implementation bugs.
- **Keep code snippets minimal**: Show interfaces, not full implementations.
- **Use diagrams sparingly**: ASCII diagrams are fine for simple flows.

$ARGUMENTS
