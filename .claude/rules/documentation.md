# Documentation Guidelines

## Structure

Separate user documentation from developer documentation:

```
docs/
├── user/    # End-user guides (how to use features)
└── dev/     # Developer docs (architecture, data flows, APIs)
```

## No File Paths

**Why**: File paths create maintenance burden when refactoring.

**Rule**: NEVER include file paths in documentation unless absolutely necessary.

```markdown
# BAD - paths become stale on refactor

### OperationLink (`operation_range/operation_link.py`)

| File                           | Coverage            |
| ------------------------------ | ------------------- |
| `tests/test_operation_link.py` | OperationLink tests |

# GOOD - describe components, not locations

### OperationLink

| Component     | Coverage            |
| ------------- | ------------------- |
| OperationLink | Dataclass, LinkType |
```

## Developer Documentation Content

Focus on concepts that help understand the system:

- Architecture and component interactions
- Data models and relationships
- Event flows and state transitions
- Service APIs and responsibilities
- Testing strategies

Use Mermaid diagrams for:

- Architecture overviews (graph TB)
- Class relationships (classDiagram)
- Database schemas (erDiagram)
- Sequence flows (sequenceDiagram)
- State machines (stateDiagram-v2)

## User Documentation Content

Focus on practical usage:

- Feature overview and use cases
- Step-by-step guides
- Configuration options
- Troubleshooting sections
