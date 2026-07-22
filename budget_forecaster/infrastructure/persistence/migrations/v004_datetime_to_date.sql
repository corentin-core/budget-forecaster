-- v3 -> v4: convert datetime strings to date strings
UPDATE accounts SET balance_date = SUBSTR(balance_date, 1, 10)
    WHERE LENGTH(balance_date) > 10;
UPDATE operations SET date = SUBSTR(date, 1, 10)
    WHERE LENGTH(date) > 10;
UPDATE planned_operations SET start_date = SUBSTR(start_date, 1, 10)
    WHERE LENGTH(start_date) > 10;
UPDATE planned_operations SET end_date = SUBSTR(end_date, 1, 10)
    WHERE end_date IS NOT NULL AND LENGTH(end_date) > 10;
UPDATE budgets SET start_date = SUBSTR(start_date, 1, 10)
    WHERE LENGTH(start_date) > 10;
UPDATE budgets SET end_date = SUBSTR(end_date, 1, 10)
    WHERE end_date IS NOT NULL AND LENGTH(end_date) > 10;
UPDATE operation_links SET iteration_date = SUBSTR(iteration_date, 1, 10)
    WHERE LENGTH(iteration_date) > 10;
