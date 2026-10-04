PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
INSERT OR IGNORE INTO metadata VALUES ('schema_version', '1');
INSERT OR IGNORE INTO metadata VALUES ('mode', 'shadow');
INSERT OR IGNORE INTO metadata VALUES ('revision', '0');
CREATE TABLE IF NOT EXISTS snapshot (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    raw BLOB NOT NULL,
    raw_sha256 TEXT NOT NULL,
    declared_revision TEXT,
    computed_revision TEXT NOT NULL,
    header_json TEXT NOT NULL CHECK (json_valid(header_json)),
    imported_at TEXT NOT NULL
);
-- Immutable import archive; never an independently writable operational Tower.
CREATE TABLE IF NOT EXISTS legacy_documents (
    path TEXT PRIMARY KEY,
    entry_json TEXT NOT NULL CHECK (json_valid(entry_json)),
    sha256 TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS immutable_snapshot_update BEFORE UPDATE ON snapshot
BEGIN SELECT RAISE(ABORT, 'immutable_snapshot'); END;
CREATE TRIGGER IF NOT EXISTS immutable_snapshot_delete BEFORE DELETE ON snapshot
BEGIN SELECT RAISE(ABORT, 'immutable_snapshot'); END;
CREATE TRIGGER IF NOT EXISTS immutable_legacy_update BEFORE UPDATE ON legacy_documents
BEGIN SELECT RAISE(ABORT, 'immutable_import_archive'); END;
CREATE TRIGGER IF NOT EXISTS immutable_legacy_delete BEFORE DELETE ON legacy_documents
BEGIN SELECT RAISE(ABORT, 'immutable_import_archive'); END;
-- Full payload retains every legacy field. The typed columns cannot drift from it.
CREATE TABLE IF NOT EXISTS objects (
    object_key TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    entity_id TEXT,
    source_path TEXT NOT NULL REFERENCES legacy_documents(path),
    pointer_json TEXT NOT NULL CHECK (json_valid(pointer_json)),
    payload_json TEXT NOT NULL CHECK (json_valid(payload_json)),
    version INTEGER NOT NULL CHECK (version > 0),
    scientific_state TEXT GENERATED ALWAYS AS (json_extract(payload_json, '$.state')) VIRTUAL,
    legacy_status TEXT GENERATED ALWAYS AS (json_extract(payload_json, '$.status')) VIRTUAL,
    attempt_state TEXT GENERATED ALWAYS AS (json_extract(payload_json, '$.execution_phase')) VIRTUAL,
    review_state TEXT GENERATED ALWAYS AS (json_extract(payload_json, '$.review_state')) VIRTUAL,
    UNIQUE (source_path, pointer_json)
);
CREATE INDEX IF NOT EXISTS objects_identity ON objects(kind, entity_id);
CREATE INDEX IF NOT EXISTS objects_scientific_state ON objects(kind, scientific_state);
CREATE TABLE IF NOT EXISTS relations (
    source_key TEXT NOT NULL REFERENCES objects(object_key),
    field TEXT NOT NULL,
    ordinal INTEGER NOT NULL,
    target_kind TEXT,
    target_id TEXT,
    raw_json TEXT NOT NULL CHECK (json_valid(raw_json)),
    PRIMARY KEY (source_key, field, ordinal)
);
CREATE TABLE IF NOT EXISTS migration_findings (
    finding_id INTEGER PRIMARY KEY,
    code TEXT NOT NULL,
    source_key TEXT,
    detail_json TEXT NOT NULL CHECK (json_valid(detail_json))
);
CREATE VIEW IF NOT EXISTS hypotheses AS SELECT * FROM objects WHERE kind = 'hypothesis';
CREATE VIEW IF NOT EXISTS scientific_contracts AS SELECT * FROM objects WHERE kind = 'contract';
CREATE VIEW IF NOT EXISTS tests AS SELECT * FROM objects WHERE kind = 'test';
CREATE VIEW IF NOT EXISTS works AS SELECT * FROM objects WHERE kind = 'work';
CREATE VIEW IF NOT EXISTS attempt_observations AS SELECT * FROM objects WHERE kind = 'attempt_observation';
CREATE VIEW IF NOT EXISTS results AS SELECT * FROM objects WHERE kind = 'result';
CREATE VIEW IF NOT EXISTS artifacts AS SELECT * FROM objects WHERE kind = 'artifact';
CREATE VIEW IF NOT EXISTS board_posts AS SELECT * FROM objects WHERE kind = 'board_post';
CREATE VIEW IF NOT EXISTS incidents AS SELECT * FROM objects WHERE kind = 'incident';
CREATE VIEW IF NOT EXISTS contests AS SELECT * FROM tests WHERE json_extract(payload_json, '$.contests_test_id') IS NOT NULL;
CREATE VIEW IF NOT EXISTS reviews AS SELECT * FROM objects WHERE kind = 'review_observation';
CREATE VIEW IF NOT EXISTS legacy_events AS SELECT * FROM objects WHERE kind = 'event';
CREATE VIEW IF NOT EXISTS legacy_receipts AS SELECT * FROM objects WHERE kind = 'legacy_receipt';
