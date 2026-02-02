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

| Component                   | Responsibilities                                       |
| --------------------------- | ------------------------------------------------------ |
| **HistoricOperation**       | Immutable record of a completed bank transaction.      |
| **PlannedOperation**        | Expected recurring or one-time operation with matcher. |
| **Budget**                  | Allocated amount for a category over a time period.    |
| **OperationRangeInterface** | Common interface for amount calculations.              |

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

| Component                  | Responsibilities                                 |
| -------------------------- | ------------------------------------------------ |
| **TimeRange**              | Single time period with start date and duration. |
| **DailyTimeRange**         | Single-day time range.                           |
| **PeriodicTimeRange**      | Repeating time range with configurable period.   |
| **PeriodicDailyTimeRange** | Daily iteration over a periodic range.           |

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

| Component            | Responsibilities                                                  |
| -------------------- | ----------------------------------------------------------------- |
| **OperationLink**    | Associates a historic operation to a target iteration.            |
| **OperationMatcher** | Scoring rules for matching (category, amount, date, description). |

### Key Constraint

An operation can be linked to **at most one** planned operation or budget iteration.
This is enforced at the repository level.

## Heuristic Link Matching

When an operation is imported or categorized, the system attempts to link it to a
planned operation or budget:

1. **Filter candidates** by category match
2. **Score each candidate** based on:
   - Amount proximity (within tolerance ratio)
   - Date proximity (within tolerance days)
   - Description hint matches (substring matching)
3. **Select best match** if score exceeds threshold
4. **Determine iteration date** from the planned operation's time range

Manual links (user-created) are never overwritten by heuristic matching.

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

When a user categorizes an operation:

1. The operation's category is updated
2. Any existing heuristic links are removed (category may have changed)
3. New heuristic links are computed based on the new category
