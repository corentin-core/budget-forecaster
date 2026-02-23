# TUI Layout Rules (Textual)

## Composite widgets must use Vertical, not Container

**Why**: `Container` does not lay out children vertically by default — it renders them
overlapping. This causes blank screens when widgets are placed inside `TabPane`.

**Rule**: ALWAYS use `Vertical` as the base class for composite screen widgets.

```python
# BAD - Container does not stack children vertically
class OperationsScreen(Container):
    ...

# GOOD - Vertical stacks children top-to-bottom
class OperationsScreen(Vertical):
    ...
```

## Use height: 1fr for tab content widgets

**Why**: Widgets inside `TabPane` need `height: 1fr` to fill available space. Using
`height: 100%` or omitting height causes rendering issues.

**Rule**: Follow the established pattern used by all existing tab widgets.

```python
class MyWidget(Vertical):
    DEFAULT_CSS = """
    MyWidget {
        height: 1fr;
    }
    """
```

**Reference pattern** (used by `BudgetsWidget`, `PlannedOperationsWidget`,
`ForecastWidget`):

```python
class BudgetsWidget(Vertical):
    DEFAULT_CSS = """
    BudgetsWidget {
        height: 1fr;
    }
    """
```

## Checklist before creating a new TUI widget

- [ ] Base class is `Vertical` (not `Container`, not `Horizontal`)
- [ ] `DEFAULT_CSS` sets `height: 1fr` on the widget itself
- [ ] Inner data tables use `height: 1fr`
- [ ] Status bars use `dock: bottom; height: 1;`
