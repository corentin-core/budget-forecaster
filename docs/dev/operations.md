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
