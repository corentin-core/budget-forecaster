---
name: refactor-check
description:
  Analyze code for refactoring opportunities, encapsulation issues, and test quality
  problems
---

# Refactor Check

Analyze code for refactoring opportunities: encapsulation issues, missing validations,
and test quality problems.

## Persona

You are a **code quality analyst** focused on identifying structural improvements that
make code more maintainable and robust.

## Arguments

- `$ARGUMENTS`: File path, directory, or module name to analyze. If empty, analyze
  recently modified files.

## Instructions

### Step 1: Identify scope

```bash
# If argument is a file
cat $ARGUMENTS

# If argument is a directory
find $ARGUMENTS -name "*.py" -type f

# If no argument, check recent changes
git diff main --name-only | grep '\.py$'
```

### Step 2: Check encapsulation

For each class, identify methods that should be private:

**Signals a method should be private:**

- Only called by one other method in the same class
- Name suggests implementation detail (`_compute_*`, `_validate_*`, `_build_*`)
- Not part of the documented public API
- Only used in tests that are testing implementation, not behavior

**Report format:**

```markdown
### Encapsulation Issues

| Class              | Method            | Reason                   | Suggestion                    |
| ------------------ | ----------------- | ------------------------ | ----------------------------- |
| `OperationMatcher` | `match_heuristic` | Only called by `match()` | Rename to `__match_heuristic` |
```

### Step 3: Check constructor validation

For each class, identify parameters that should be validated:

**Parameters that need validation:**

- IDs or references to other objects (should exist/be valid)
- Dates that must satisfy constraints (within range, valid iteration)
- Collections where items must satisfy predicates
- Numeric values with domain constraints (positive, non-zero, percentage)

**Report format:**

```markdown
### Missing Validations

| Class              | Parameter         | Constraint                     | Current       | Suggested                                       |
| ------------------ | ----------------- | ------------------------------ | ------------- | ----------------------------------------------- |
| `OperationMatcher` | `operation_links` | dates must be valid iterations | No validation | Add `__validate_iteration_date()` in `__init__` |
```

### Step 4: Check test quality

For each test file, identify problematic tests:

**Tests to flag:**

1. **Tests implementation, not behavior**

   - Directly calls private methods (`obj._Class__method()`)
   - Tests internal state rather than observable behavior
   - Would break if implementation changes but behavior stays same

2. **Tests Python, not application**

   - Verifies StrEnum values equal strings
   - Tests NamedTuple unpacking
   - Checks dataclass field existence

3. **Missing edge cases**
   - No tests for periodic structures with specific iterations
   - No tests for boundary conditions
   - No tests for error paths

**Report format:**

```markdown
### Test Quality Issues

| Test File                   | Test Name                     | Issue                | Suggestion                   |
| --------------------------- | ----------------------------- | -------------------- | ---------------------------- |
| `test_operation_matcher.py` | `test_match_heuristic_method` | Tests private method | Remove or test via `match()` |
```

### Step 5: Generate summary

```markdown
## Refactor Check Summary

**Scope:** [files analyzed]

### Quick Wins (Low effort, high impact)

- ...

### Recommended Refactors

- ...

### Technical Debt to Track

- ...
```

## Example Output

```markdown
## Refactor Check Summary

**Scope:** `budget_forecaster/operation_range/operation_matcher.py`

### Quick Wins

- [ ] Rename `match_heuristic` -> `__match_heuristic` (only internal use)

### Recommended Refactors

- [ ] Add validation in `__init__` for `operation_links` iteration dates
- [ ] Update `replace()` to clear links when `operation_range` changes

### Technical Debt to Track

- [ ] `test_match_heuristic_method` tests implementation, should be removed

### Test Coverage Gaps

- [ ] No tests for periodic ranges with links on specific iterations
```

## When to Run

- Before submitting a PR (catch issues early)
- After implementing a feature (verify quality)
- During code review (systematic analysis)
- Periodically on modules with high churn

$ARGUMENTS
