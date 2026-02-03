# Operations & Linking

This document describes the operation domain model, time ranges, and the linking system
that connects historic operations to planned operations and budgets.

## Operation Hierarchy

All operations share a common interface for amount calculations over time periods.

```mermaid
classDiagram
    class OperationRangeInterface {
        <<interface>>
        +description
        +amount
        +category
        +time_range
        +amount_on_period()
    }

    class OperationRange {
        #description
        #amount
        #category
        #time_range
    }

    class ForecastOperationRange {
        +id
        +matcher
    }

    class PlannedOperation
    class Budget

    class HistoricOperation {
        +unique_id
        +date
        +description
        +amount
        +category
    }

    OperationRangeInterface <|.. OperationRange
    OperationRange <|-- ForecastOperationRange
    ForecastOperationRange <|-- PlannedOperation
    ForecastOperationRange <|-- Budget
    OperationRangeInterface <|.. HistoricOperation
```

HistoricOperation represents actual bank transactions (imported). PlannedOperation and
Budget represent expected future activity and include an OperationMatcher for automatic
linking. All share amount_on_period() which computes the amount over any time slice.

## TimeRange Hierarchy

Time ranges define when operations occur and how they repeat.

```mermaid
classDiagram
    class TimeRangeInterface {
        <<interface>>
        +initial_date
        +last_date
        +duration
        +total_duration
        +is_expired()
        +is_future()
        +is_within()
        +iterate_over_time_ranges()
        +current_time_range()
        +replace()
    }

    class TimeRange {
        -initial_date
        -duration
    }

    class DailyTimeRange {
        +iterate_over_time_ranges()
    }

    class PeriodicTimeRange {
        -period
        -end_date
        +iterate_over_time_ranges()
        +current_time_range()
        +next_time_range()
        +last_time_range()
    }

    class PeriodicDailyTimeRange {
        +iterate_over_time_ranges()
    }

    TimeRangeInterface <|.. TimeRange
    TimeRange <|-- DailyTimeRange
    TimeRange <|-- PeriodicTimeRange
    PeriodicTimeRange <|-- PeriodicDailyTimeRange
```

PeriodicTimeRange enables recurring operations (monthly rent, weekly groceries) by
generating iterations via iterate_over_time_ranges(). DailyTimeRange is used for
one-time operations on a specific date.

## Linking System

Links connect historic operations to their planned counterparts or budgets.

```mermaid
classDiagram
    class HistoricOperation {
        +unique_id: OperationId
    }

    class OperationLink {
        +operation_id: OperationId
        +target_type: LinkType
        +target_id: TargetId
        +iteration_date: IterationDate
        +is_manual: bool
    }

    class PlannedOperation {
        +id: PlannedOperationId
        +matcher: OperationMatcher
    }

    class Budget {
        +id: BudgetId
        +matcher: OperationMatcher
    }

    class OperationMatcher {
        +category
        +amount_tolerance
        +date_tolerance
        +description_hints
        +matches()
    }

    HistoricOperation "1" -- "0..1" OperationLink : linked by
    OperationLink "*" -- "1" PlannedOperation : targets
    OperationLink "*" -- "1" Budget : targets
    PlannedOperation "1" *-- "1" OperationMatcher
    Budget "1" *-- "1" OperationMatcher
```

OperationMatcher uses configurable tolerances (amount ratio, date window) and
description hints to score potential matches. The is_manual flag on OperationLink
distinguishes user-created links (protected) from heuristic ones (recalculated on target
changes).

### Key Constraint

An operation can be linked to **at most one** planned operation or budget iteration.
This is enforced at the repository level.

## Heuristic Link Matching

```mermaid
flowchart TD
    START[Operation imported/categorized] --> CHECK{Already manually linked?}
    CHECK -->|Yes| SKIP[Skip - preserve manual link]
    CHECK -->|No| FILTER[Filter candidates by category]
    FILTER --> SCORE[Score each candidate]

    subgraph Scoring
        SCORE --> S1[Amount proximity]
        SCORE --> S2[Date proximity]
        SCORE --> S3[Description hints]
    end

    S1 & S2 & S3 --> BEST{Best score > threshold?}
    BEST -->|No| UNLINKED[No link created]
    BEST -->|Yes| LINK[Create link with iteration date]
```

## Categorization Flow

```mermaid
sequenceDiagram
    participant User
    participant TUI
    participant AppService
    participant OperationService
    participant LinkService

    User->>TUI: Assign category
    TUI->>AppService: categorize_operations()
    AppService->>OperationService: update category
    AppService->>LinkService: delete old heuristic links
    AppService->>LinkService: create new heuristic links
```

## Link Lifecycle

```mermaid
stateDiagram-v2
    [*] --> Unlinked: Operation imported

    Unlinked --> AutoLinked: Heuristic match found
    Unlinked --> ManualLinked: User creates link

    AutoLinked --> Unlinked: Target edited (no match)
    AutoLinked --> AutoLinked: Target edited (still matches)
    AutoLinked --> ManualLinked: User creates manual link
    AutoLinked --> Unlinked: User deletes link

    ManualLinked --> Unlinked: User deletes link
    ManualLinked --> ManualLinked: Target edited (preserved)

    note right of AutoLinked: is_manual = false
    note right of ManualLinked: is_manual = true
```

## Splitting Operations and Budgets

Split functionality allows users to modify recurring planned operations or budgets from
a specific date while preserving historical data.

### Split Process

```mermaid
sequenceDiagram
    participant User
    participant TUI
    participant AppService
    participant Repositories

    User->>TUI: Click "Scinder"
    TUI->>AppService: get_next_non_actualized_iteration()
    AppService-->>TUI: Default split date

    User->>TUI: Configure split (date, amount, period)
    TUI->>AppService: split_planned_operation_at_date() or split_budget_at_date()

    AppService->>Repositories: Load original target
    AppService->>Repositories: Terminate original (set expiration_date)
    AppService->>Repositories: Create new target with new values
    AppService->>Repositories: Migrate links for iterations >= split_date
    AppService-->>TUI: New target created
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

- Split date must be strictly after the original's `initial_date`
- Target must have a periodic time range (`PeriodicTimeRange` or
  `PeriodicDailyTimeRange`)
- Non-periodic elements cannot be split

### ApplicationService Methods

- `get_next_non_actualized_iteration(target_type, target_id)`: Finds the first iteration
  without a linked operation (used as default split date)
- `split_planned_operation_at_date(operation_id, split_date, new_amount, new_period)`:
  Splits a PlannedOperation
- `split_budget_at_date(budget_id, split_date, new_amount, new_period, new_duration)`:
  Splits a Budget (includes duration parameter)
