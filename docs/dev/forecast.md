# Forecast

This document describes the forecast system, which manages planned operations and
budgets, and actualizes them based on real transactions.

## Components

| Component              | Responsibilities                                                                             |
| ---------------------- | -------------------------------------------------------------------------------------------- |
| **Forecast**           | Container for planned operations and budgets.                                                |
| **ForecastActualizer** | Updates forecast based on links. Handles late iterations, postponements, budget consumption. |

## Forecast Structure

A Forecast holds:

- **Planned operations**: Expected recurring or one-time transactions
- **Budgets**: Allocated amounts for categories over time periods

Both are loaded from CSV files and stored in the repository.

## Actualization Algorithm

The ForecastActualizer adjusts planned operations based on actual data:

1. **Identify actualized iterations** - iterations with links to past operations
2. **Detect late iterations** - past iterations without links (within tolerance window)
3. **Postpone late iterations** - create one-time operations for tomorrow
4. **Advance periodic operations** - move start date past last actualized iteration
5. **Consume budgets** - reduce remaining amount based on linked operations

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

The computation flow:

1. Load raw forecast (planned operations + budgets)
2. Actualize based on existing links
3. Generate balance projections using the actualized forecast
4. Produce the analysis report with statistics
