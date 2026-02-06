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

### Step 2.5: Fetch existing comments (if re-reviewing)

If the PR already has review comments:

```bash
gh api repos/{owner}/{repo}/pulls/<number>/comments \
  --jq '.[] | {user: .user.login, path: .path, line: .line, body: .body}'
```

- Avoid duplicating existing feedback
- Build on unresolved discussions
- Note resolved vs. unresolved issues

### Step 3: Check CI status and coverage

**Do NOT run tests locally** - use CI results instead.

```bash
# Check CI status
gh pr checks <number>

# Get coverage comment from PR (posted by python-coverage-comment-action)
gh api repos/{owner}/{repo}/issues/<number>/comments \
  --jq '.[] | select(.body | contains("Coverage report")) | .body'
```

#### CI Checks

- All checks must pass (tests, linting, type checking)
- If CI is still running, wait for results

#### Coverage Analysis (CRITICAL)

**Don't just look at percentages** - analyze the "Lines missing" column in the coverage
report.

For each file modified by the PR, check:

1. **New statements coverage** - What percentage of NEW code is covered?
2. **Lines missing** - Which specific lines are NOT tested?
3. **Are missing lines acceptable?** Examples:
   - Error handlers that are hard to trigger → often acceptable
   - Core business logic → NOT acceptable, request tests
   - TUI event handlers → depends on existing patterns

**Red flags to catch:**

- New feature code with 0% coverage
- Critical paths (data mutation, external calls) without tests
- Complex conditionals where only one branch is tested

**Example analysis:**

```
app.py: 15% (7/44 new statements covered)
  Lines missing: 639-640, 646-656, 665-684...
  → These are the split event handlers - NO tests for the TUI integration!
  → Flag this: "The split button handlers in app.py have no test coverage"
```

### Step 4: Review the changes

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

### Step 5: Determine verdict

```
Runtime bug or incorrect logic?
  -> Changes requested

Missing tests for new feature code?
  -> Changes requested (check "Lines missing" in coverage report!)

New code paths with 0% coverage?
  -> Changes requested (unless justified pattern like existing TUI code)

Implementation doesn't match requirements?
  -> Changes requested

Only minor suggestions?
  -> Approve (with comments)
```

**Coverage verdict rules:**

- Domain/business logic not covered → **Changes requested**
- Service layer not covered → **Changes requested**
- TUI glue code not covered → Check existing pattern. If similar code is already
  untested, note it but don't block. If it's a regression, request changes.

### Step 6: Post inline comments

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

**Comment placement strategy:**

| Comment type              | Place on                       |
| ------------------------- | ------------------------------ |
| Missing tests for a class | The `class` definition line    |
| Bug in specific code      | The exact line with the issue  |
| Missing method            | The `class` definition line    |
| Suggestion to add code    | The closest relevant line      |
| Function implementation   | The `def` line of the function |

### Step 7: Submit the review

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

### Step 8: Introspection

After the review is submitted, reflect:

1. **Were any comments incorrect or poorly calibrated?**
   - If yes, note what to check differently next time
2. **Did the user edit or reject any comments?**
   - If yes, understand why and adjust future reviews
3. **Were there issues you missed that the user caught?**
   - If yes, consider updating `.claude/rules/` with the new pattern

This feeds into the auto-introspection system (`.claude/rules/auto-introspection.md`).

## Review Summary Format

```markdown
## Review Summary

### Verdict: Approve | Changes requested

| Aspect            | Status            |
| ----------------- | ----------------- |
| CI checks         | OK/NOK            |
| Coverage          | OK/NOK (X% -> Y%) |
| Logic correctness | OK/NOK            |
| Type annotations  | OK/NOK            |
| Test coverage     | OK/NOK            |
| Code quality      | OK/NOK            |

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
- "Lines 639-684 in app.py (split event handlers) have 0% test coverage. Please add
  integration tests for the button→modal→service flow."
- "application_service.py:647 - this error path is not covered. Add a test for the 'not
  found' case."

## Avoid

- Style nitpicks (handled by black/ruff)
- "Missing docstring" (handled by linters)
- Subjective preferences without clear benefit

$ARGUMENTS
