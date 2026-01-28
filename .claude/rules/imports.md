# Import Conventions

## No Import-Outside-Toplevel

**Why**: Import statements inside functions or methods hide dependencies and indicate
architectural problems (often circular imports).

**Rule**: NEVER use `import-outside-toplevel` pattern. Always ask the user before
considering such a workaround.

```python
# BAD - hiding imports inside methods
def on_show(self) -> None:
    # pylint: disable=import-outside-toplevel
    from budget_forecaster.tui.app import BudgetApp
    if isinstance(self.app, BudgetApp):
        self.set_app_service(self.app.app_service)

# GOOD - dependency injection
class CategorizeScreen(Vertical):
    def set_app_service(self, service: ApplicationService) -> None:
        """Set the application service and refresh."""
        self._app_service = service
        self._refresh()
```

**When you encounter a circular import:**

1. **Stop and report** the issue to the user
2. **Analyze** the dependency graph
3. **Propose** a proper solution:
   - Extract common types to a shared module
   - Use dependency injection (pass dependencies at runtime)
   - Reorganize module boundaries

**Acceptable exceptions (require user approval):**

- Development-only imports (debugging, profiling)
- Optional dependencies that may not be installed
