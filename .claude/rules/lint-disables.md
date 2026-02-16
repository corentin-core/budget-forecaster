# Lint Disables

## Never Disable Lint Silently

**Why**: Disabling warnings hides problems. Each disable is a conscious tradeoff that
the user must validate.

**Rule**: ALWAYS ask the user before adding any `# pylint: disable=`, `# type: ignore`,
or `# noqa:` comment.

When you encounter a lint warning:

1. **Understand** why it triggers
2. **Fix** the underlying issue if possible
3. **If a fix is not possible**, STOP and ask the user:
   - Explain the warning and why it triggers
   - Explain the tradeoff of suppressing it
   - **Wait for explicit approval before adding any disable comment**
4. **Scope narrowly** - prefer inline disables over file-wide

**NEVER add a lint suppression without stopping to ask.** This is a hard checkpoint.

```python
# BAD - silently suppressing
# pylint: disable=protected-access
class TestFoo:
    def test_bar(self):
        obj._internal  # hidden from review

# GOOD - fix the code or ask first
# "This test needs access to _internal because X. Should I disable protected-access
# on this line, or refactor to test via the public interface?"
```
