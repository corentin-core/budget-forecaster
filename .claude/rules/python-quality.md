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

---

For complete guidelines, see `CLAUDE.md`.
