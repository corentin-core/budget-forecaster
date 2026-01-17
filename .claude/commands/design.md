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

### 5. Break down large features (IMPORTANT)

For complex features, split the work into multiple smaller PRs that are easier to
review:

1. **Create sub-issues** - Each sub-issue handles one piece of the feature
2. **Link issues together** - Use "Part of #X" in sub-issues, "Blocked by #Y" in parent
3. **Create a feature branch** - e.g., `feature/32-manual-operation-linking`
4. **PRs target the feature branch** - Each sub-issue PR merges into the feature branch
5. **Final PR** - Merge the feature branch into main when all sub-PRs are done

```
main
  └── feature/32-manual-linking  (feature branch)
        ├── PR #63: issue/57-data-model  (merged)
        ├── PR #64: issue/58-heuristics  (merged)
        └── PR #65: issue/59-ui          (in progress)
```

**Benefits:**

- Smaller PRs are easier to review thoroughly
- Issues can be worked on in parallel
- Each piece can be tested independently
- Easier to revert if something goes wrong

**When to split:**

- Feature touches 3+ files with significant changes
- Multiple independent components (data model, logic, UI)
- Estimated review time > 15 minutes

### 6. Verify codebase coherence (CRITICAL)

Before finalizing the design, check that it integrates well with existing code:

**Abstractions:**

- If there's a `RepositoryInterface`, new persistence methods go there (not a new class)
- If similar services use dependency injection, yours should too
- Don't introduce direct dependencies on implementations (e.g., `SqliteRepository`)

**Patterns:**

- Check how similar features are structured (e.g., existing adapters, services)
- Follow the same naming conventions and file organization
- If existing code uses interfaces/protocols, yours should too

**Questions to answer in the design:**

- [ ] Which existing interfaces need to be extended?
- [ ] What dependencies will the new code have? (should be abstractions, not
      implementations)
- [ ] Does the design follow existing patterns in the codebase?

**Real example:** Commit `f5e64c8` was needed because the initial design didn't account
for the existing `RepositoryInterface` pattern - code was coupled to `SqliteRepository`
directly.

### 7. Verify data source mapping (CRITICAL)

For each output or data flow, ensure the design specifies:

| Aspect     | Bad (vague)         | Good (explicit)                         |
| ---------- | ------------------- | --------------------------------------- |
| Source     | "from the database" | "from `sqlite_repository.get_all()`"    |
| Field name | "the amount"        | "the `amount` field (Decimal)"          |
| Transform  | "format the date"   | "format as `YYYY-MM-DD` using strftime" |

**If data sources are unclear, ask for clarification.**

### 8. Review cycle

After each batch of changes:

1. Summarize what was modified
2. Ask if the user wants to:
   - Continue with more changes
   - Review the full draft
   - Update the GitHub issue

### 9. Update the GitHub issue

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
Split into sub-issues? ---> Yes: Create sub-issues + feature branch
    |                              |
    | No                           v
    v                        Update each sub-issue
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

## Testing Guidelines

When specifying tests in the design:

- **Test application logic, not Python built-ins** - Don't specify tests for StrEnum
  values, NamedTuple iteration, dataclass field access, etc. These test Python, not your
  code.
- **Focus on behavior** - Test CRUD operations, business rules, edge cases, error
  handling.

```markdown
# BAD - testing Python features

- [ ] Test that `LinkType.BUDGET == "budget"`
- [ ] Test that OperationLink is iterable

# GOOD - testing application logic

- [ ] Test that duplicate links raise IntegrityError
- [ ] Test that `delete_automatic_links` preserves manual links
```

$ARGUMENTS
