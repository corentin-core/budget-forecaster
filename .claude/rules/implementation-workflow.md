# Implementation Workflow

## Mandatory steps before implementing any issue

**NEVER** start coding immediately. Follow this workflow:

**This applies to ALL issues, including quick wins.** No exceptions.

### 1. Present the issue

- Read and understand the issue
- Summarize it to the user
- Identify any ambiguities or missing details

### 2. Propose a design

**Before making any claims about project tooling**, verify the actual configuration:

- Check `mypy.ini`, `.mypy.ini`, `pyproject.toml [tool.mypy]` for type checking setup
- Check `.pre-commit-config.yaml` for CI/quality hooks
- Check `setup.py`, `setup.cfg`, `pyproject.toml` for dependencies and build config

NEVER assume a tool is missing without checking these files first.

Present a draft design including:

- **Approach**: High-level solution
- **Files to modify**: List affected files
- **UI mockups**: ASCII art for any UI changes
- **Edge cases**: Identified corner cases

### 3. Wait for validation

- User reviews the design
- Address feedback and iterate if needed
- **DO NOT proceed without explicit approval**

### 4. Update the issue

Once design is approved:

- Add the design to the GitHub issue body or as a comment
- This documents the agreed approach for future reference

### 5. Implement

Only after user gives explicit "go":

- Implement the feature
- Write tests
- Commit and create PR

## Example workflow

```
Claude: "Issue #42 proposes X. Here's my design:
         [design details]
         Does this approach work for you?"

User:   "Looks good, but change Y to Z"

Claude: "Updated design with Z. Shall I update the issue?"

User:   "Yes"

Claude: [Updates issue with design]
        "Issue updated. Ready to implement when you give the go."

User:   "Go"

Claude: [Implements, commits, creates PR]
```
