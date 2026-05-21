
pub const CREATE_SCHEMA: &str = r#"
    -- Enable WAL mode for better concurrent performance
    PRAGMA journal_mode = WAL;

    -- Increase page size for better I/O on modern storage
    PRAGMA page_size = 4096;

    -- Allow the OS to handle fsync (faster, slightly less safe)
    PRAGMA synchronous = NORMAL;

    -- Main file index table
    CREATE TABLE IF NOT EXISTS files (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        relative_path   TEXT NOT NULL UNIQUE,
        absolute_path   TEXT NOT NULL,
        size            INTEGER NOT NULL,
        mtime           TEXT NOT NULL,
        extension       TEXT,
        is_symlink      INTEGER NOT NULL DEFAULT 0,
        content_hash    TEXT,
        permissions     INTEGER NOT NULL,
        inode           INTEGER NOT NULL,
        device          INTEGER NOT NULL,
        first_seen      TEXT NOT NULL DEFAULT (datetime('now')),
        last_updated    TEXT NOT NULL DEFAULT (datetime('now'))
    );

    -- Index for finding files by extension (e.g., all .bam files)
    CREATE INDEX IF NOT EXISTS idx_files_extension ON files(extension);

    -- Index for finding duplicate files by content hash
    CREATE INDEX IF NOT EXISTS idx_files_hash ON files(content_hash)
        WHERE content_hash IS NOT NULL;

    -- Index for size-based queries
    CREATE INDEX IF NOT EXISTS idx_files_size ON files(size);

    -- Scan history table for temporal tracking
    CREATE TABLE IF NOT EXISTS scan_events (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        scan_root       TEXT NOT NULL,
        started_at      TEXT NOT NULL DEFAULT (datetime('now')),
        files_total     INTEGER NOT NULL,
        files_hashed    INTEGER NOT NULL,
        duration_ms     INTEGER NOT NULL
    );

    -- Metadata table for key-value project settings
    CREATE TABLE IF NOT EXISTS metadata (
        key             TEXT PRIMARY KEY,
        value           TEXT NOT NULL,
        updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
    );
"#;