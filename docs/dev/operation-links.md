# Operation Links - Developer Documentation

This document describes the architecture and implementation of the operation links
feature, which connects historic bank operations to planned operations or budgets.

## Architecture Overview

```mermaid
graph TB
    subgraph "Presentation Layer"
        TUI[TUI App]
        LinkTargetModal[LinkTargetModal]
        LinkIterationModal[LinkIterationModal]
        OperationTable[OperationTable]
    end

    subgraph "Service Layer"
        AS[ApplicationService]
        OLS[OperationLinkService]
        FS[ForecastService]
        IS[ImportService]
        OS[OperationService]
    end

    subgraph "Domain Layer"
        OM[OperationMatcher]
        OL[OperationLink]
        PO[PlannedOperation]
        B[Budget]
        HO[HistoricOperation]
    end

    subgraph "Persistence Layer"
        Repo[SqliteRepository]
        DB[(SQLite DB)]
    end

    TUI --> AS
    TUI --> LinkTargetModal
    TUI --> LinkIterationModal
    TUI --> OperationTable

    LinkTargetModal --> AS
    LinkIterationModal --> AS

    AS --> IS
    AS --> FS
    AS --> OLS
    AS --> OS
    AS --> OM

    OLS --> Repo
    FS --> Repo
    IS --> Repo

    OM --> OL
    OM --> PO
    OM --> B
    OM --> HO

    Repo --> DB
```

**ApplicationService** is the central orchestrator that:

- Coordinates imports and creates heuristic links afterward
- Manages CRUD for planned operations and budgets with automatic link recalculation
- Caches matchers for efficient link creation
- Handles categorization with potential link creation

## Data Model

### Class Diagram

```mermaid
classDiagram
    class LinkType {
        <<StrEnum>>
        PLANNED_OPERATION = "planned_operation"
        BUDGET = "budget"
    }

    class OperationLink {
        <<NamedTuple>>
        +int id
        +int operation_unique_id
        +LinkType target_type
        +int target_id
        +datetime iteration_date
        +bool is_manual
    }

    class OperationMatcher {
        -OperationRange operation_range
        -tuple~OperationLink~ operation_links
        -timedelta approximation_date_range
        -float approximation_amount_ratio
        -set~str~ description_hints
        +match(operation) bool
        +match_heuristic(operation) bool
        +is_linked(operation) bool
    }

    class OperationLinkService {
        -OperationLinkRepositoryInterface repository
        +get_all_links() tuple~OperationLink~
        +get_link_for_operation(operation_id) OperationLink?
        +upsert_link(link) void
        +delete_link(operation_unique_id) void
        +load_links_for_target(target) tuple~OperationLink~
        +create_heuristic_links(operations, matchers) tuple~OperationLink~
        +delete_automatic_links_for_target(type, id) void
        +delete_links_for_target(type, id) void
    }

    class ApplicationService {
        -PersistentAccount persistent_account
        -ImportService import_service
        -OperationService operation_service
        -ForecastService forecast_service
        -OperationLinkService operation_link_service
        -dict matchers_cache
        +import_file(path) ImportResult
        +import_from_inbox(callback) ImportSummary
        +categorize_operation(id, category) OperationCategoryUpdate?
        +bulk_categorize(ids, category) tuple~OperationCategoryUpdate~
        +add_planned_operation(op) PlannedOperation
        +update_planned_operation(op) PlannedOperation
        +delete_planned_operation(id) void
        +add_budget(budget) Budget
        +update_budget(budget) Budget
        +delete_budget(id) void
        +get_all_links() tuple~OperationLink~
        +get_link_for_operation(id) OperationLink?
        +delete_link(operation_id) void
        +create_manual_link(link) void
        +compute_report(start, end) AccountAnalysisReport
    }

    class OperationLinkRepositoryInterface {
        <<interface>>
        +get_link_for_operation(unique_id) OperationLink?
        +get_all_links() tuple~OperationLink~
        +get_links_for_planned_operation(id) tuple~OperationLink~
        +get_links_for_budget(id) tuple~OperationLink~
        +upsert_link(link) void
        +delete_link(unique_id) void
        +delete_automatic_links_for_target(type, id) void
        +delete_links_for_target(type, id) void
    }

    OperationLink --> LinkType
    OperationMatcher --> OperationLink
    OperationLinkService --> OperationLinkRepositoryInterface
    OperationLinkService --> OperationMatcher
```

### Database Schema

```mermaid
erDiagram
    operations {
        int unique_id PK
        int account_id FK
        text description
        text category
        timestamp date
        real amount
        text currency
    }

    planned_operations {
        int id PK
        text description
        real amount
        text currency
        text category
        timestamp start_date
        int period_value
        text period_unit
        timestamp end_date
        text description_hints
        int approximation_date_days
        real approximation_amount_ratio
    }

    budgets {
        int id PK
        text description
        real amount
        text currency
        text category
        timestamp start_date
        int period_value
        text period_unit
        timestamp end_date
    }

    operation_links {
        int id PK
        int operation_unique_id FK,UK
        text target_type
        int target_id
        timestamp iteration_date
        bool is_manual
        timestamp created_at
    }

    operations ||--o| operation_links : "has (0..1)"
    planned_operations ||--o{ operation_links : "targeted by"
    budgets ||--o{ operation_links : "targeted by"
```

**Key constraints:**

- `UNIQUE(operation_unique_id)`: An operation can only have ONE link
- `target_type`: Either `"planned_operation"` or `"budget"`
- `is_manual`: Protects manual links from automatic recalculation

## Key Components

### OperationLink

Immutable NamedTuple representing a link between an operation and a target iteration.

```python
class OperationLink(NamedTuple):
    operation_unique_id: int
    target_type: LinkType
    target_id: int
    iteration_date: datetime
    is_manual: bool = False
    id: int | None = None
```

### OperationMatcher

Handles both link-based and heuristic matching. Links always take priority.

```python
def match(self, operation: HistoricOperation) -> bool:
    # 1. Check operation link first (always wins)
    if self.is_linked(operation):
        return True
    # 2. Fall back to heuristic matching
    return self.match_heuristic(operation)
```

### OperationLinkService

Manages link persistence and heuristic link creation.

**Responsibilities:**

- Fetch all links for display
- Create, update, or delete links
- Load links for a specific target
- Create automatic links for unlinked operations (heuristic matching)
- Delete automatic or all links for a target

### ApplicationService

Central orchestrator that coordinates data flow between services.

**Responsibilities:**

- Coordinate imports and create heuristic links afterward
- Manage CRUD for planned operations and budgets
- Recalculate links when targets are updated (delete automatic + create new)
- Delete ALL links when targets are deleted (including manual links)
- Cache matchers for efficient link creation
- Handle categorization with potential link creation

### Match Score

The `compute_match_score()` function calculates match quality (0-100):

```python
def compute_match_score(
    operation: HistoricOperation,
    operation_range: OperationRange,
    iteration_date: datetime,
) -> float:
    score = 0.0

    # Amount: 40% (only for PlannedOperation, not Budget)
    if not isinstance(operation_range, Budget):
        # ... amount scoring logic

    # Date: 30%
    # ... date proximity scoring

    # Category: 20%
    if operation.category == operation_range.category:
        score += 20.0

    # Description: 10%
    # ... description hints scoring

    return score
```

**Note:** Budgets skip amount scoring because budget amounts represent totals, not
individual operation amounts.

## Data Flows

### 1. Import Operations

```mermaid
sequenceDiagram
    participant CLI as CLI/TUI
    participant AS as ApplicationService
    participant IS as ImportService
    participant OLS as OperationLinkService
    participant Repo as Repository
    participant OM as OperationMatcher

    CLI->>AS: import_file(path)
    AS->>IS: import_file(path)
    IS->>Repo: save operations
    IS-->>AS: ImportResult (success)

    AS->>AS: get_matchers() (cached)
    AS->>OLS: create_heuristic_links(operations, matchers)

    loop For each unlinked operation
        OLS->>Repo: get_link_for_operation(id)
        Repo-->>OLS: None

        loop For each matcher
            OLS->>OM: match_heuristic(operation)
            OM-->>OLS: True/False

            alt Match found
                OLS->>OLS: compute_match_score()
                Note over OLS: Track best match
            end
        end

        alt Best match exists
            OLS->>Repo: upsert_link(link)
        end
    end

    OLS-->>AS: created links
    AS-->>CLI: ImportResult
```

### 2. Manual Linking (TUI)

```mermaid
sequenceDiagram
    participant User
    participant TUI as BudgetApp
    participant AS as ApplicationService
    participant LTM as LinkTargetModal
    participant LIM as LinkIterationModal
    participant OLS as OperationLinkService
    participant Repo as Repository

    User->>TUI: Press L on operation
    TUI->>TUI: Get selected operation
    TUI->>AS: get_all_links()
    AS->>OLS: get_all_links()
    OLS-->>AS: all links
    AS-->>TUI: current_link or None
    TUI->>LTM: push_screen(operation, current_link, targets)

    alt User selects "Supprimer le lien"
        LTM-->>TUI: "unlink"
        TUI->>AS: delete_link(operation_id)
        AS->>OLS: delete_link(operation_id)
        OLS->>Repo: delete_link(operation_id)
    else User selects target
        LTM-->>TUI: selected_target
        TUI->>LIM: push_screen(operation, target)
        User->>LIM: Select iteration
        LIM-->>TUI: iteration_date
        TUI->>AS: create_manual_link(OperationLink)
        AS->>OLS: upsert_link(link)
        OLS->>Repo: upsert_link(link)
    else User cancels
        LTM-->>TUI: None
    end

    TUI->>TUI: refresh_screens()
```

### 3. Edit Planned Operation / Budget

```mermaid
sequenceDiagram
    participant User
    participant TUI as BudgetApp
    participant AS as ApplicationService
    participant FS as ForecastService
    participant OLS as OperationLinkService
    participant Repo as Repository

    User->>TUI: Edit planned operation
    TUI->>AS: update_planned_operation(op)
    AS->>FS: update_planned_operation(op)
    FS->>Repo: save planned operation
    FS-->>AS: updated operation

    AS->>AS: update matcher cache
    AS->>OLS: delete_automatic_links_for_target(type, id)
    OLS->>Repo: delete_automatic_links_for_target(type, id)
    Note over Repo: Manual links preserved

    AS->>OLS: create_heuristic_links(operations, {target: matcher})
    OLS->>Repo: upsert_link() for each new match

    OLS-->>AS: new links
    AS-->>TUI: updated operation
    TUI->>TUI: refresh_screens()
```

### 4. Forecast Calculation

```mermaid
sequenceDiagram
    participant CLI as CLI/TUI
    participant AS as ApplicationService
    participant OLS as OperationLinkService
    participant FS as ForecastService
    participant AA as AccountAnalyzer
    participant FA as ForecastActualizer

    CLI->>AS: compute_report(start, end)
    AS->>OLS: get_all_links()
    OLS-->>AS: all links
    AS->>FS: compute_report(start, end, links)

    FS->>AA: new AccountAnalyzer(account, forecast, links)
    FS->>AA: compute_report(start, end)

    AA->>FA: ForecastActualizer(account, links)(forecast)
    Note over FA: Actualizes planned ops and budgets using links
    FA-->>AA: actualized forecast

    AA->>AA: compute balance evolution
    AA-->>FS: AccountAnalysisReport

    FS-->>AS: report
    AS-->>CLI: report
```

**Note:** ApplicationService orchestrates report computation by fetching links and
passing them to ForecastService. This decouples the TUI from OperationLinkService.

## Link Lifecycle State Machine

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

**Key rules:**

- Manual links are never automatically deleted
- Automatic links are recalculated when their target is edited
- User can always override automatic links with manual ones
