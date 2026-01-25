# Forecast Calculation - Developer Documentation

This document describes the architecture and data flow of the forecast calculation
system.

## Overview

The forecast system predicts future account balance by combining:

- **Historic operations**: Real bank transactions (imported)
- **Planned operations**: Expected future transactions (recurring or one-time)
- **Budgets**: Spending limits per category
- **Operation links**: Connections between historic and planned operations

## Architecture

```mermaid
graph TB
    subgraph "Entry Point"
        FS[ForecastService]
    end

    subgraph "Analysis Layer"
        AA[AccountAnalyzer]
    end

    subgraph "Core Components"
        FA[ForecastActualizer]
        AF[AccountForecaster]
    end

    subgraph "Data"
        F[Forecast]
        A[Account]
        OL[OperationLinks]
    end

    FS --> AA
    AA --> FA
    AA --> AF

    FA --> F
    FA --> OL
    AF --> A
    AF --> F
```

## Key Components

### Forecast

Container for planned operations and budgets.

```python
class Forecast(NamedTuple):
    operations: tuple[PlannedOperation, ...]
    budgets: tuple[Budget, ...]
```

### ForecastActualizer

Transforms a forecast based on what has already happened. Uses operation links to
determine which planned iterations are actualized.

**Responsibilities:**

- Actualize planned operations by advancing past linked iterations
- Compute remaining budget amounts from linked operations
- Flag iterations that should have occurred but have no link (late)

### AccountForecaster

Computes the account state at any given date by combining historic operations with
forecast projections.

**Responsibilities:**

- Compute account state at any target date
- Use historic operations for past dates
- Use forecast projections for future dates

### AccountAnalyzer

Orchestrates the analysis and produces the final report.

**Responsibilities:**

- Generate the full AccountAnalysisReport
- Compute daily balance projections
- Compute budget consumption forecasts
- Compute category spending statistics

## Data Flow

### Report Generation

```mermaid
sequenceDiagram
    participant FS as ForecastService
    participant OLS as OperationLinkService
    participant AA as AccountAnalyzer
    participant FA as ForecastActualizer
    participant AF as AccountForecaster

    FS->>OLS: get_all_links()
    OLS-->>FS: operation_links

    FS->>AA: new(account, forecast, links)
    FS->>AA: compute_report(start, end)

    AA->>FA: new(account, links)
    AA->>FA: __call__(forecast)
    Note over FA: Actualize using links
    FA-->>AA: actualized_forecast

    AA->>AF: new(account, actualized_forecast)
    AA->>AF: __call__(start_date)
    AF-->>AA: initial_state
    AA->>AF: __call__(end_date)
    AF-->>AA: final_state

    AA->>AA: compute balance evolution
    AA->>AA: compute budget stats
    AA-->>FS: AccountAnalysisReport
```

### Actualization Process

```mermaid
flowchart TD
    subgraph "Input"
        F[Forecast]
        L[OperationLinks]
    end

    subgraph "ForecastActualizer"
        BI[Build indexes from links]
        AP[Actualize PlannedOperations]
        AB[Actualize Budgets]
    end

    subgraph "PlannedOperation Logic"
        CHK{Has linked operations?}
        ADV[Advance start_date past linked iterations]
        LATE[Flag late iterations]
        KEEP[Keep future iterations]
    end

    subgraph "Budget Logic"
        CONS[Compute consumed amount from links]
        REM[Remaining = amount - consumed]
    end

    F --> BI
    L --> BI
    BI --> AP
    BI --> AB

    AP --> CHK
    CHK -->|Yes| ADV
    CHK -->|No| KEEP
    ADV --> LATE
    LATE --> KEEP

    AB --> CONS
    CONS --> REM
```

## Role of Operation Links

Operation links are critical for accurate forecast calculation:

### For Planned Operations

1. **Iteration actualization**: A linked iteration is considered "done"
2. **Start date advancement**: Periodic operations advance past linked iterations
3. **Late detection**: Iterations in the past without links are flagged as late

```mermaid
timeline
    title Planned Operation: Monthly Rent (1st of month)
    section January
        Jan 1 : Iteration expected
        Jan 3 : Bank operation received
        Jan 3 : Link created → Iteration actualized
    section February
        Feb 1 : Iteration expected
        Feb 5 : No operation yet
        Feb 5 : Flagged as LATE
    section March
        Mar 1 : Future iteration
        Mar 1 : Shown in forecast
```

### For Budgets

1. **Consumption tracking**: Linked operations consume budget amount
2. **Remaining calculation**: Budget shows remaining = total - sum(linked operations)

```mermaid
timeline
    title Budget: Groceries (500€/month)
    section Week 1
        Mon : Supermarket -80€ → linked
        Wed : Market -25€ → linked
    section Week 2
        Sat : Supermarket -95€ → linked
        : Remaining: 500 - 200 = 300€
    section Week 3
        : Forecast shows 300€ remaining
```

## Link Impact Summary

| Scenario          | Without Links            | With Links                  |
| ----------------- | ------------------------ | --------------------------- |
| Past planned op   | Removed from forecast    | Actualized with real amount |
| Missing iteration | Not detected             | Flagged as LATE             |
| Budget spending   | Not tracked              | Decrements remaining        |
| Forecast accuracy | Based on planned amounts | Based on actual amounts     |

## Key Algorithms

### Late Iteration Detection

An iteration is late if:

1. Its date is in the past (before today)
2. No operation is linked to it
3. It's within the "late window" (configurable)

### Budget Consumption

```python
consumed = sum(
    operation.amount
    for link in links_for_budget
    if link.iteration_date in current_period
)
remaining = budget.amount - consumed
```

### Periodic Operation Advancement

When a periodic operation has linked iterations:

1. Find the latest linked iteration date
2. Advance `start_date` to the next period after that date
3. Future iterations continue from the new start date
