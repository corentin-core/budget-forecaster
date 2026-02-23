# Planned Operations & Budgets

This document describes the management of planned operations and budgets, including
modification operations like splitting.

## Overview

PlannedOperation and Budget extend ForecastOperationRange and represent expected future
activity. Both include an OperationMatcher for automatic linking to historic operations.

For the operation hierarchy and linking system basics, see
[Operations & Linking](operations.md).

## Splitting Operations and Budgets

Split functionality allows users to modify recurring planned operations or budgets from
a specific date while preserving historical data.

### Split Process

```mermaid
sequenceDiagram
    participant User
    participant TUI
    participant AppService
    participant ManageTargetsUC
    participant Repositories

    User->>TUI: Click "Scinder"
    TUI->>AppService: get_next_non_actualized_iteration()
    AppService->>ManageTargetsUC: get_next_non_actualized_iteration()
    ManageTargetsUC-->>TUI: Default split date

    User->>TUI: Configure split (date, amount, period)
    TUI->>AppService: split_planned_operation_at_date() or split_budget_at_date()
    AppService->>ManageTargetsUC: split_planned_operation_at_date() or split_budget_at_date()

    ManageTargetsUC->>Repositories: Load original target
    ManageTargetsUC->>Repositories: Terminate original (set expiration_date)
    ManageTargetsUC->>Repositories: Create new target with new values
    ManageTargetsUC->>Repositories: Migrate links for iterations >= split_date
    ManageTargetsUC-->>TUI: New target created
```

### Split Data Flow

```mermaid
flowchart LR
    subgraph Before Split
        A[Original PlannedOp/Budget]
        A -->|links| L1[Link Jan]
        A -->|links| L2[Link Feb]
        A -->|links| L3[Link Mar]
        A -->|links| L4[Link Apr]
    end

    subgraph After Split at Mar
        B[Original - terminated Feb 28]
        B -->|links| L1x[Link Jan]
        B -->|links| L2x[Link Feb]

        C[New - starts Mar 1]
        C -->|links| L3x[Link Mar]
        C -->|links| L4x[Link Apr]
    end
```

### Key Behaviors

- **Termination**: Original element's `expiration_date` is set to `split_date - 1 day`
- **Creation**: New element inherits the original's description and category
- **Link Migration**: All links with `iteration_date >= split_date` are moved to the new
  target. The `target_id` is updated; `target_type` and `iteration_date` remain
  unchanged.
- **Manual links preserved**: Both manual and automatic links are migrated

### Validation Rules

- Split date must be strictly after the original's `start_date`
- Target must have a periodic date range (`RecurringDateRange` or `RecurringDay`)
- Non-periodic elements cannot be split

### ManageTargetsUseCase Methods

- `get_next_non_actualized_iteration(target_type, target_id)`: Finds the first iteration
  without a linked operation (used as default split date)
- `split_planned_operation_at_date(operation_id, split_date, new_amount, new_period)`:
  Splits a PlannedOperation
- `split_budget_at_date(budget_id, split_date, new_amount, new_period, new_duration)`:
  Splits a Budget (includes duration parameter)

ApplicationService delegates these calls to ManageTargetsUseCase.

## Archiving

Planned operations and budgets can be archived to hide them from the default view while
preserving them for historical reference (e.g., comparing actual vs planned in reports).

### Domain Model

Both `PlannedOperation` and `Budget` include an `is_archived: bool` field (defaults to
`False`). Archiving is a simple toggle using `replace(is_archived=True/False)` followed
by an update through `ApplicationService`.

### Status Lifecycle

```mermaid
stateDiagram-v2
    [*] --> Active
    Active --> Expired: end date passes
    Active --> Archived: user archives
    Expired --> Archived: user archives
    Archived --> Active: user unarchives (if not expired)
    Archived --> Expired: user unarchives (if expired)
```

### TUI Integration

The `FilterBar` provides a status dropdown with four values: Active, Expired, Archived,
All. The status filter determines which items are displayed in the table. A bulk
"Archive all expired" action is available when viewing expired items.
