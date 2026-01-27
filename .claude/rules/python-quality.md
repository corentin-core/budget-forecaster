---
paths:
  - "**/*.py"
---

# Python Code Quality

These patterns prevent common review comments. Follow them strictly.

## Type hints - Required everywhere

All functions must have complete type annotations:

```python
# BAD
def calculate_balance(operations, initial):
    return initial + sum(op.amount for op in operations)

# GOOD
def calculate_balance(operations: tuple[Operation, ...], initial: Decimal) -> Decimal:
    return initial + sum(op.amount for op in operations)
```

## Return tuples, not lists

**Why**: Tuples are immutable and signal that the caller shouldn't modify the result.

Use `tuple[T, ...]` for return types:

```python
# BAD
def get_operations(self) -> list[Operation]:
    return list(self._operations)

# GOOD
def get_operations(self) -> tuple[Operation, ...]:
    return tuple(self._operations)
```

**Rule**: ALWAYS use `tuple[T, ...]` instead of `list[T]` for function return values.

## NamedTuple vs dataclass

**Why**: NamedTuple is immutable and lighter. Use dataclass only when you need
mutability or methods.

| Use case                          | Choice     |
| --------------------------------- | ---------- |
| Immutable data, no methods        | NamedTuple |
| Needs methods (e.g., `matches()`) | dataclass  |
| Needs default mutable values      | dataclass  |

```python
# BAD - dataclass for simple immutable data
@dataclass
class UpdateResult:
    operation: HistoricOperation
    category_changed: bool

# GOOD - NamedTuple for immutable data without methods
class UpdateResult(NamedTuple):
    operation: HistoricOperation
    category_changed: bool
```

## Domain objects over primitives

Use domain objects instead of primitive types:

```python
# BAD
def get_linked_operations(self) -> dict[str, date]:
    ...

# GOOD
def get_linked_operations(self) -> tuple[OperationLink, ...]:
    ...
```

## Single source of truth

Don't maintain two representations of the same data:

```python
# BAD - redundant index
self._links: tuple[OperationLink, ...] = links
self._links_by_id: dict[OperationId, OperationLink] = {l.id: l for l in links}

# GOOD - derive when needed
self._links: tuple[OperationLink, ...] = links

def get_link_by_id(self, id: OperationId) -> OperationLink | None:
    return next((l for l in self._links if l.id == id), None)
```

## Encapsulation - Private by default

Attributes should be private unless there's a reason to expose them:

```python
# BAD
self.repository = SqliteRepository()

# GOOD
self._repository = SqliteRepository()
```

## No over-engineering

Keep it simple - don't add abstractions for one-time operations:

```python
# BAD - unnecessary factory
def create_operation_factory() -> Callable[..., Operation]:
    def factory(**kwargs) -> Operation:
        return Operation(**kwargs)
    return factory

# GOOD - direct instantiation
operation = Operation(date=date, amount=amount, label=label)
```

## Logging instead of print

Never use `print()` for user feedback in library code:

```python
# BAD
print(f"Imported {len(operations)} operations")

# GOOD
logger.info("Imported %d operations", len(operations))
```

## Circular imports - Never work around silently

**Why**: Using `TYPE_CHECKING` to avoid circular imports hides architectural problems.
Circular imports indicate poor module organization that should be fixed properly.

**Rule**: NEVER use `if TYPE_CHECKING:` to work around circular imports. Instead:

1. **Stop and report** the circular import to the user
2. **Analyze** which module depends on which
3. **Propose** a refactoring solution (extract common types, reorganize modules)

```python
# BAD - hiding the problem
if TYPE_CHECKING:
    from budget_forecaster.services.forecast_service import ForecastService

# GOOD - fix the architecture
# Extract common types to a shared module, or reorganize dependencies
```

**Acceptable uses of TYPE_CHECKING**:

- Forward references within the same module (self-referential types)
- Avoiding heavy imports that are only needed for type hints (e.g., pandas, numpy)

---

For complete guidelines, see `CLAUDE.md`.
