-- v7 -> v8: add the source_ref dedup key (API entry_reference; NULL for file imports)
ALTER TABLE operations ADD COLUMN source_ref TEXT;
