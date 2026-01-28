# PR Review Handling

## Never Create Issues Without Asking

**Rule**: ALWAYS ask the user before creating GitHub issues. Don't assume that a review
comment should become an issue.

## Fix Problems Introduced by the PR

**Rule**: NEVER create issues for problems introduced by the current PR. Fix them
directly.

If a review comment points out:

- Missing tests for new code → Write the tests now
- Code quality issues in new code → Fix them now
- Missing documentation for new features → Add it now

Issues are only appropriate for pre-existing problems or scope expansions that the user
explicitly agrees to defer.

```python
# BAD - deferring work introduced by this PR
# "📝 Issue created: #94 - Tests for multi-selection"

# GOOD - fix it now
# Write the tests, commit, reply "✅ Fixed in commit abc123"
```
