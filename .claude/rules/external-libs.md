# External Libraries

## Consult Documentation First

**Why**: Trial and error wastes time and produces unreliable code. Library behaviors can
be subtle (e.g., terminal mouse event handling, framework-specific patterns).

**Rule**: ALWAYS consult official documentation before using external library features.

When using a library you're unfamiliar with:

1. **Search online** for official documentation using WebSearch
2. **Read the relevant section** before writing code
3. **Check GitHub issues** if behavior seems unexpected

```
# BAD - guessing at Textual mouse event handling
def on_click(self, event: Click) -> None:
    if event.shift:  # Does this work? Maybe not...
        self._select_range()

# GOOD - verify in Textual docs first
# After checking docs: Shift+click is intercepted by terminals for text selection
# Use keyboard alternatives instead: Shift+Up/Down
```

**Common external libraries in this project:**

- **Textual** - TUI framework (widgets, events, CSS)
- **Rich** - Terminal formatting
- **openpyxl** - Excel file handling
- **pytest** - Testing framework

## GitHub Issues as Documentation

When official docs are insufficient, search the library's GitHub issues:

```bash
# Example: searching for mouse event issues in Textual
gh search issues --repo Textualize/textual "shift click"
```
