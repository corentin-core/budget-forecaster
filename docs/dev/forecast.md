# Forecast

This document describes the forecast system, which manages planned operations and
budgets, and actualizes them based on real transactions.

## Components

```mermaid
classDiagram
    class Forecast {
        +operations: tuple~PlannedOperation~
        +budgets: tuple~Budget~
    }

    class ForecastActualizer {
        -account: Account
        -links: tuple~OperationLink~
        +__call__(forecast) Forecast
    }

    class PlannedOperation {
        +id
        +date_range
        +matcher
    }

    class Budget {
        +id
        +date_range
        +matcher
    }

    Forecast "1" *-- "*" PlannedOperation
    Forecast "1" *-- "*" Budget
    ForecastActualizer --> Forecast : transforms
    ForecastActualizer --> OperationLink : uses
```

ForecastActualizer transforms a raw forecast into an actualized one by examining
operation links. It advances periodic operations past linked iterations, flags late
iterations that should have occurred but weren't linked, and computes remaining budget
amounts from linked operations.

## Actualization Algorithm

```mermaid
stateDiagram-v2
    [*] --> Pending: iteration scheduled
    Pending --> Actualized: operation linked
    Pending --> Late: past due date
    Late --> Postponed: tolerance exceeded
    Postponed --> Actualized: operation linked
```

## Computation Flow

```mermaid
sequenceDiagram
    participant TUI
    participant AppService
    participant ForecastService
    participant ForecastActualizer
    participant AccountAnalyzer
    participant AccountForecaster

    TUI->>AppService: compute_report(date_range)
    AppService->>ForecastService: load_forecast()
    AppService->>ForecastActualizer: actualize(forecast, links)
    ForecastActualizer-->>AppService: actualized forecast
    AppService->>AccountAnalyzer: compute_report()
    AccountAnalyzer->>AccountForecaster: project balance
    AccountAnalyzer-->>TUI: AccountAnalysisReport
```

## Examples

### Planned Operation Actualization

```mermaid
timeline
    title Monthly Rent (1st of month)
    section January
        Jan 1 : Iteration expected
        Jan 3 : Bank operation received
        Jan 3 : Link created → Iteration actualized
        Jan 25 : February rent paid early
        Jan 25 : Link to Feb iteration → Also actualized
    section February
        Feb 1 : Iteration already actualized
        Feb 1 : Skipped in forecast
    section March
        Mar 1 : Future iteration
        Mar 1 : Shown in forecast
```

### Budget Consumption

```mermaid
timeline
    title Groceries Budget (500€/month)
    section Week 1
        Mon : Supermarket -80€ → linked
        Wed : Market -25€ → linked
    section Week 2
        Sat : Supermarket -95€ → linked
        : Remaining: 500 - 200 = 300€
    section Week 3
        : Forecast shows 300€ remaining
```

### Budget Sign Matching

A linked operation only consumes a budget when both share the same sign. This preserves
the invariant: **a link can only reduce the remaining budget amount (in absolute value),
never increase it**.

Without this rule, a +30€ refund linked to a -500€ grocery budget would push the
remaining amount to -530€, inflating the forecast beyond the original budget.

| Budget sign | Operation sign | Result                                   |
| ----------- | -------------- | ---------------------------------------- |
| Negative    | Negative       | Consumed (reduces remaining amount)      |
| Positive    | Positive       | Consumed (reduces remaining amount)      |
| Negative    | Positive       | Skipped (would inflate remaining amount) |
| Positive    | Negative       | Skipped (would inflate remaining amount) |

```mermaid
timeline
    title Groceries Budget (-500€/month)
    section Normal consumption
        Mon : Supermarket -80€ → consumed
        : Remaining: -420€
    section Refund (sign mismatch)
        Wed : Refund +30€ → skipped
        : Remaining stays -420€
    section Next purchase
        Fri : Market -50€ → consumed
        : Remaining: -370€
```
