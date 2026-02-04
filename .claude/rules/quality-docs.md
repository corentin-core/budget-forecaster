# Quality Documentation

## User-Observable Behaviors Only

**Why**: Quality docs describe what users experience, not implementation details.
Low-level behaviors (exceptions, method names, internal states) are test concerns, not
documentation concerns.

**Rule**: ALWAYS write scenarios from the user's perspective.

```markdown
# BAD - implementation details

> **Given** a non-existent planned operation ID **When** >
> `split_planned_operation_at_date()` is called **Then** a ValueError is raised with
> "not found"

# GOOD - user perspective

> **Given** a one-time planned operation (non-recurring) **When** the user tries to
> split it **Then** the split action is not available
```

## Generic Scenarios with Concrete Examples

**Why**: Scenarios should describe general behaviors, but concrete dates/values help
understanding. Use specific examples (January 15th) to illustrate generic rules.

**Rule**: Describe the general case, use dates with day precision as examples.

```markdown
# BAD - too abstract, loses precision

> **Given** a monthly operation with past linked iterations **When** the user splits it

# BAD - dates without day precision

> **Given** a monthly operation where January and February are linked **When** the user
> opens the split modal **Then** the default date is March

# GOOD - generic scenario with precise example

> **Given** a monthly planned operation where January 1st and February 1st are already
> linked **When** the user opens the split modal **Then** the default split date is
> March 1st (first iteration without a linked operation)
```

## Focus on Emergent Behaviors

**Why**: Quality docs capture behaviors that emerge from the system, not obvious CRUD
operations. Document what might surprise a user or what requires multiple components
working together.

Good candidates:

- Default values and pre-filling
- Cascading effects (links migrating after split)
- Validation rules that affect UX
- History preservation

Bad candidates:

- Basic CRUD (create/read/update/delete)
- Internal error handling
- API response formats
