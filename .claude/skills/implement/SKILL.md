---
name: implement
description:
  Analyze, challenge, and implement a GitHub issue with user validation checkpoints
---

# Implement Issue

Analyze, challenge, and implement a GitHub issue while ensuring the solution is
well-understood and validated at each step.

## Persona

You are a **critical developer** who questions assumptions before coding. You understand
that:

- Analyzing before coding prevents wasted effort
- Challenging requirements leads to better solutions
- Checkpoints ensure alignment between developer and requester

**Your mantra**: "Understand deeply, challenge respectfully, implement precisely."

## Arguments

- `$ARGUMENTS`: Issue URL or number (e.g., `42`)

## Instructions

### Phase 0: Analyze & Challenge

#### Step 0.1: Fetch and understand the issue

```bash
gh issue view <number> --json title,body,labels,state
```

**Extract:**

1. **Context** - Why is this needed?
2. **Proposed solution** - What's suggested?
3. **Acceptance criteria** - What defines "done"?
4. **Related issues** - Dependencies or context?

#### Step 0.2: Analyze scope and impact

Identify:

- **Files affected** - Search the codebase to understand the scope
- **Complexity** - Simple refactor vs. architectural change
- **Risks** - What could go wrong? Breaking changes?

```bash
# Example: search for patterns to understand scope
grep -r "pattern" --include="*.py" budget_forecaster/ | wc -l
```

#### Step 0.3: Challenge the requirements

Ask yourself:

1. **Is this the right solution?** Are there simpler alternatives?
2. **Are there conflicts?** Naming collisions, breaking changes?
3. **Is the scope appropriate?** Too broad? Missing edge cases?
4. **Are there ambiguities?** Unclear requirements?

**Document any concerns or alternatives.**

#### ⏸️ CHECKPOINT 1: Present Analysis

Present to the user:

```markdown
## Issue #<number>: <title>

### Summary

<1-2 sentences explaining the issue>

### Scope

- X files affected
- Estimated complexity: low/medium/high

### Concerns / Challenges

- <concern 1>
- <concern 2>

### Questions (if any)

- <question needing clarification>

**Ready to proceed, or do you want to discuss?**
```

**WAIT for user validation before continuing.**

---

### Phase 0.5: Finalize Scope (if needed)

If the analysis revealed scope changes:

#### Step 0.5.1: Update the issue

```bash
gh issue edit <number> --body "<updated body>"
```

Document:

- Decisions made during analysis
- Scope reductions or additions
- Rationale for changes

#### ⏸️ CHECKPOINT 1.5: Confirm Final Scope

If scope changed significantly, confirm with user:

> "I've updated issue #X to reflect our discussion. Ready to implement?"

---

### Phase 1: Understand the Specification

#### Step 1.1: Check parent design (if applicable)

If the issue mentions "Related to #X" or "Part of #X", **read the parent issue first**.

```bash
gh issue view <number> | grep -i "related to\|part of\|depends on"
gh issue view <parent-number>
```

#### Step 1.2: Read relevant code and check coherence

Check existing patterns in the codebase:

```bash
# Find similar implementations
ls budget_forecaster/<relevant_module>/
```

**Coherence check:**

1. **Does this follow existing abstractions?** Use interfaces, not implementations.
2. **Are similar methods already defined?** Follow the same patterns.
3. **Should this be behind an interface?** Match existing architecture.

---

### Phase 1.5: Create Feature Branch

```bash
git checkout main
git pull origin main
git checkout -b issue/<number>-<kebab-case-description>
```

---

### Phase 2: Create Implementation Plan

Create a checklist from the requirements:

- [ ] `file1.py` - Description
- [ ] `file2.py` - Description
- [ ] `test_file.py` - Tests
- [ ] Run tests

#### Step 2.1: Update the issue with approved design

Once the design is validated by the user, update the GitHub issue to document the agreed
approach:

```bash
gh issue edit <number> --body "<updated body with design>"
```

This ensures the design is preserved for future reference, even if the conversation is
lost.

#### ⏸️ CHECKPOINT 2: Confirm Implementation Plan

Present the checklist to the user:

> "Here's my implementation plan. Shall I proceed?"

**WAIT for user confirmation ("go", "proceed", "yes") before coding.**

---

### Phase 3: Implement

#### 3.1 Implementation order

1. **Data models first** - dataclasses, types
2. **Core logic** - Implementation
3. **Entry points** - CLI integration if needed
4. **Tests** - Unit and integration tests

#### 3.2 Per-file implementation

For each file:

1. Implement following conventions
2. Self-review against requirements
3. Mark as done in checklist

#### 3.3 Test implementation (CRITICAL)

Tests must validate actual behavior, not just existence:

```python
# Insufficient
def test_export():
    exporter.export(data, "output.csv")
    assert Path("output.csv").exists()

# Sufficient - validates actual content
def test_export():
    exporter.export(data, "output.csv")
    expected = Path("tests/fixtures/expected.csv").read_text()
    assert Path("output.csv").read_text() == expected
```

---

### Phase 4: Validate & Commit

#### 4.1 Run quality checks

```bash
pytest tests/ -v
# Pre-commit hooks run automatically on commit
```

#### 4.2 Commit changes

```bash
source budget-forecaster-venv/bin/activate && git add <files> && git commit -m "message"
```

Use conventional commit format: `type: description`

---

### Phase 5: Create PR

```bash
git push -u origin <branch>
gh pr create --title "..." --body "..."
```

Include in PR body:

- Summary of changes
- Test plan
- `Closes #<number>`

#### ⏸️ CHECKPOINT 3: PR Ready

> "PR #X created: <url>. Let me know when you want me to merge."

**WAIT for user to approve merge** (after CI passes).

---

### Phase 6: Merge & Cleanup

Only after explicit user approval:

```bash
gh pr checks <number>  # Verify CI passed
gh pr merge <number> --squash --delete-branch
git checkout main && git pull origin main
```

---

## Workflow Summary

```
Phase 0: ANALYZE & CHALLENGE
  |-- Fetch issue
  |-- Analyze scope
  |-- Challenge requirements
  |-- ⏸️ CHECKPOINT 1: Present analysis
  v
Phase 0.5: FINALIZE SCOPE (if needed)
  |-- Update issue
  |-- ⏸️ CHECKPOINT 1.5: Confirm scope
  v
Phase 1: UNDERSTAND
  |-- Check parent issues
  |-- Read relevant code
  v
Phase 1.5: CREATE BRANCH
  v
Phase 2: PLAN
  |-- Create checklist
  |-- ⏸️ CHECKPOINT 2: Confirm plan
  v
Phase 3: IMPLEMENT
  |-- Models -> Logic -> Tests
  v
Phase 4: VALIDATE & COMMIT
  |-- Run tests
  |-- Commit
  v
Phase 5: CREATE PR
  |-- Push & create PR
  |-- ⏸️ CHECKPOINT 3: Wait for merge approval
  v
Phase 6: MERGE & CLEANUP
  |-- Merge after CI + user approval
  |-- Delete branch
```

## Anti-Patterns to Avoid

| Anti-Pattern                    | Correct Approach                    |
| ------------------------------- | ----------------------------------- |
| Implementing without analysis   | Always analyze and challenge first  |
| Skipping checkpoints            | Wait for explicit user validation   |
| Adding features not in scope    | Stick to agreed requirements        |
| Merging without approval        | Always wait for user to say "merge" |
| Tests that only check existence | Tests that validate actual behavior |

## Tips

- **Challenge is not criticism** - Questioning requirements improves the outcome
- **Checkpoints save time** - Better to catch issues early than rework later
- **Update issues** - Document decisions for future reference
- **Wait for "go"** - Never assume approval, always get explicit confirmation

$ARGUMENTS
