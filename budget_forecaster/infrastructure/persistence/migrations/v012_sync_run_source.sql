-- v11 -> v12: tag each sync run with the integration that produced it
ALTER TABLE sync_runs ADD COLUMN source TEXT NOT NULL DEFAULT 'enable_banking';
