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
