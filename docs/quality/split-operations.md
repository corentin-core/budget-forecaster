# Split Operations - Test Scenarios

## Split PlannedOperation

### Not Found Error

> **Given** a non-existent planned operation ID
>
> **When** `split_planned_operation_at_date()` is called
>
> **Then** a ValueError is raised with "not found"

### Non-Periodic Error

> **Given** a planned operation with a non-periodic time range (e.g., DailyTimeRange)
>
> **When** `split_planned_operation_at_date()` is called
>
> **Then** a ValueError is raised with "non-periodic"

### Split Date Before Start Error

> **Given** a planned operation starting on 2025-01-01
>
> **When** `split_planned_operation_at_date()` is called with split_date = 2025-01-01
>
> **Then** a ValueError is raised (split date must be strictly after initial date)

### Successful Split

> **Given** a periodic planned operation (ID=1) starting 2025-01-01
>
> **When** `split_planned_operation_at_date()` is called with split_date = 2025-03-01
> and new_amount = -850
>
> **Then**:
>
> - Original operation is terminated on 2025-02-28
> - New operation is created starting 2025-03-01 with the new amount
> - New operation inherits description and category

### Link Migration

> **Given** a planned operation with links on 2025-01-01, 2025-03-01, and 2025-04-01
>
> **When** `split_planned_operation_at_date()` is called with split_date = 2025-03-01
>
> **Then**:
>
> - Link on 2025-01-01 stays with original operation
> - Links on 2025-03-01 and 2025-04-01 are migrated to new operation

## Split Budget

### Not Found Error

> **Given** a non-existent budget ID
>
> **When** `split_budget_at_date()` is called
>
> **Then** a ValueError is raised with "not found"

### Non-Periodic Error

> **Given** a budget with a non-periodic time range
>
> **When** `split_budget_at_date()` is called
>
> **Then** a ValueError is raised with "non-periodic"

### Successful Split

> **Given** a periodic budget (ID=1) starting 2025-01-01
>
> **When** `split_budget_at_date()` is called with split_date = 2025-03-01 and
> new_amount = -400
>
> **Then**:
>
> - Original budget is terminated
> - New budget is created starting 2025-03-01 with the new amount
> - New budget inherits description and category

### Link Migration

> **Given** a budget with links on 2025-01-01, 2025-03-01, and 2025-04-01
>
> **When** `split_budget_at_date()` is called with split_date = 2025-03-01
>
> **Then**:
>
> - Link on 2025-01-01 stays with original budget
> - Links on 2025-03-01 and 2025-04-01 are migrated to new budget

## Get Next Non-Actualized Iteration

### Target Not Found

> **Given** a non-existent target ID
>
> **When** `get_next_non_actualized_iteration()` is called
>
> **Then** None is returned

### Non-Periodic Target

> **Given** a target with a non-periodic time range
>
> **When** `get_next_non_actualized_iteration()` is called
>
> **Then** None is returned

### Skips Actualized Iterations

> **Given** a periodic operation with links on 2025-01-01 and 2025-02-01
>
> **When** `get_next_non_actualized_iteration()` is called
>
> **Then** returns 2025-03-01 (first iteration without a link)
