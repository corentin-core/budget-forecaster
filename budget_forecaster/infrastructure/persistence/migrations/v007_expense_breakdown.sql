-- v6 -> v7: add expense_breakdown_threshold setting
INSERT OR IGNORE INTO settings (key, value) VALUES ('expense_breakdown_threshold', '2');
