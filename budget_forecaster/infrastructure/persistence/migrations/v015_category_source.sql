-- v14 -> v15: record how each operation's category was set.
-- Every category stored so far was the user's (or the bank's, read as the user's).
ALTER TABLE operations ADD COLUMN category_source TEXT;
UPDATE operations SET category_source = 'manual' WHERE category != 'uncategorized';
