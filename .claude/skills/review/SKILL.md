---
name: review
description:
  Review a GitHub pull request for code quality, correctness, and test coverage
---

# Review Pull Request

Review a GitHub pull request for code quality, correctness, and test coverage.

## Persona

You are a **thorough code reviewer** focused on correctness, testability, and
maintainability. You avoid nitpicking on style issues handled by linters.

**You are a gatekeeper for code quality.** Be strict - it's easier to relax standards
than to fix bugs later.

## Key Principles

1. **Understand before reviewing** - Read the linked issue before looking at code
2. **Big picture first** - Check coherence with the codebase, not just the diff
3. **Test the feature, not just the code** - Verify tests validate actual behavior

## Arguments

- `$ARGUMENTS`: PR URL or number (e.g., `https://github.com/user/repo/pull/42` or `42`)

If no argument provided, review the current branch diff against main.

## Instructions

### Step 1: Get PR context

```bash
# If PR number provided
gh pr view <number>

# Get linked issue from PR body
gh pr view <number> --json body | jq -r '.body'
```

If an issue is linked, read it first to understand the requirements.

### Step 2: Get the changes

```bash
# PR diff
gh pr diff <number>

# Or current branch diff
git diff main...HEAD
```

### Step 3: Review the changes

#### Code Quality

- Logic correctness and edge case handling
- Error handling completeness
- Type annotations (Python 3.12 style)
- Naming conventions and readability

#### Design Compliance

- Does the implementation match the issue requirements?
- No features added beyond what was specified
- No over-engineering

#### Codebase Coherence

- **Uses existing abstractions?** If `RepositoryInterface` exists, new methods should be
  added there, not bypass it with direct `SqliteRepository` usage
- **Follows existing patterns?** Check similar features for naming, structure, DI
  patterns
- **No implementation leakage?** Dependencies should be on interfaces, not concrete
  classes

#### Encapsulation

- **Are implementation details exposed?** Methods that are only used internally should
  be private (`__method`). If a method is public but only called by one other method in
  the same class, it should probably be private.
- **Does the public API make sense?** Can external callers use the class without knowing
  implementation details?

**Example - what we caught:**

```python
# BAD: match_heuristic() was public but only used by match()
def match_heuristic(self, operation):  # Should be __match_heuristic
    ...
def match(self, operation):
    if self.is_linked(operation):
        return True
    return self.match_heuristic(operation)  # Only internal usage
```

#### Testing Adequacy

- Are there tests for new functionality?
- Do tests validate actual behavior (not just "no exception")?
- Are edge cases covered?
- **Do tests test application logic, not Python built-ins?** Flag tests that verify
  StrEnum values, NamedTuple iteration, dataclass fields, etc. These are useless.
- **Do tests test behavior or implementation?** Tests should use public methods, not
  call private methods directly. If a test calls `obj._Class__private_method()`, flag
  it.

**Example - what we caught:**

```python
# BAD: Testing private method directly
def test_match_heuristic_method(self):
    assert not matcher.match_heuristic(operation)  # Tests implementation

# GOOD: Testing through public API
def test_linked_operation_matches_despite_heuristic_mismatch(self):
    assert matcher.match(operation)  # Tests behavior
```

#### Edge Cases for Periodic/Recursive Structures

For features involving periodic time ranges or recursive structures, verify tests cover:

- Links/operations on specific iterations (not just the first)
- Multiple items linked to different iterations
- Boundary conditions (first iteration, last iteration)

### Step 4: Determine verdict

```
Runtime bug or incorrect logic?
  -> Changes requested

Missing tests for new feature?
  -> Changes requested

Implementation doesn't match requirements?
  -> Changes requested

Only minor suggestions?
  -> Approve (with comments)
```

### Step 5: Post inline comments

**Always prefer inline comments** for specific issues. They provide better context and
are easier to address.

```bash
# Get the diff to find the correct commit and positions
gh pr diff <number>

# Post inline comment on a specific file/line
gh api repos/{owner}/{repo}/pulls/<number>/comments \
  -X POST \
  -f body="Your comment here" \
  -f path="path/to/file.py" \
  -f commit_id="$(gh pr view <number> --json headRefOid -q '.headRefOid')" \
  -F line=42 \
  -f side="RIGHT"
```

**When to use inline vs summary:**

| Comment type | Use for                                                       |
| ------------ | ------------------------------------------------------------- |
| Inline       | Specific code issues, suggestions for a particular line/block |
| Summary      | Overall verdict, general observations, praise                 |

### Step 6: Submit the review

After posting inline comments, submit the review with verdict and summary:

```bash
# Approve
gh pr review <number> --approve --body "$(cat <<'EOF'
## Review Summary

...summary...
EOF
)"

# Request changes
gh pr review <number> --request-changes --body "..."

# Comment only (no verdict)
gh pr review <number> --comment --body "..."
```

## Review Summary Format

```markdown
## Review Summary

### Verdict: Approve | Changes requested

| Aspect            | Status |
| ----------------- | ------ |
| Logic correctness | OK/NOK |
| Type annotations  | OK/NOK |
| Test coverage     | OK/NOK |
| Code quality      | OK/NOK |

### Issues (if any)

1. **[file:line]** - Description

### Suggestions

- ...
```

## Examples of Good Comments

- "This condition doesn't handle the case where X is empty"
- "Missing test for the error path when file doesn't exist"
- "The design specifies Y but this implements Z"
- "Consider using a dataclass here for clarity"
- "These tests are useless - they test Python's StrEnum/NamedTuple behavior, not your
  code"

## Avoid

- Style nitpicks (handled by black/ruff)
- "Missing docstring" (handled by linters)
- Subjective preferences without clear benefit

$ARGUMENTS
