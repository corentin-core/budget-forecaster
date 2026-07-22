-- v8 -> v9: source-scoped external account id (IBAN for banks, Swile id).
-- NULL for accounts imported from a file that carries no external id.
ALTER TABLE accounts ADD COLUMN external_id TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS idx_accounts_external_id
    ON accounts (external_id) WHERE external_id IS NOT NULL;
