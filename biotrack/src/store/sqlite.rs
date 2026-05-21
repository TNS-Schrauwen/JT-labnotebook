use crate::scanner::entry::FileEntry;
use crate::store::schema::CREATE_SCHEMA;
use anyhow::Result;
use chrono::Utc;
use rusqlite::{params, Connection, Transaction};
use std::collections::HashSet;
use std::path::Path;
use std::time::Duration;
use tracing::{debug, info};

pub struct IndexStatistics {
    pub total_files: u64,
    pub total_size: u64,
    pub last_scan: String,
    pub scan_count: u64,
}


pub struct SqliteStore {
    conn: Connection,
}

impl SqliteStore {

    pub fn open(path: &Path) -> Result<Self> {
        let conn = Connection::open(path)?;

        conn.execute_batch(CREATE_SCHEMA)?;

        info!(path = %path.display(), "Database opened");

        Ok(Self { conn })
    }


    pub fn filter_changed_entries(&self, entries: &[FileEntry]) -> Result<Vec<FileEntry>> {
        let mut existing: HashSet<String> = HashSet::new();

        let mut stmt = self
            .conn
            .prepare("SELECT relative_path, size, mtime FROM files")?;

        let rows = stmt.query_map([], |row| {
            let path: String = row.get(0)?;
            let size: i64 = row.get(1)?;
            let mtime: String = row.get(2)?;
            Ok(format!("{}:{}:{}", path, size, mtime))
        })?;

        for row in rows {
            if let Ok(key) = row {
                existing.insert(key);
            }
        }

        debug!(
            existing_entries = existing.len(),
            "Loaded existing index for change detection"
        );

        let changed: Vec<FileEntry> = entries
            .iter()
            .filter(|entry| {
                let key = format!(
                    "{}:{}:{}",
                    entry.relative_path.display(),
                    entry.size,
                    entry.mtime.to_rfc3339()
                );
                !existing.contains(&key)
            })
            .cloned()
            .collect();

        debug!(
            total = entries.len(),
            changed = changed.len(),
            unchanged = entries.len() - changed.len(),
            "Change detection complete"
        );

        Ok(changed)
    }


    pub fn upsert_entries(&mut self, entries: &[FileEntry]) -> Result<()> {
        const BATCH_SIZE: usize = 1000;

        let total_batches = (entries.len() + BATCH_SIZE - 1) / BATCH_SIZE;
        debug!(
            entries = entries.len(),
            batches = total_batches,
            "Persisting entries to database"
        );

        for (batch_idx, chunk) in entries.chunks(BATCH_SIZE).enumerate() {
            let tx = self.conn.transaction()?;
            Self::insert_batch(&tx, chunk)?;
            tx.commit()?;

            if (batch_idx + 1) % 10 == 0 {
                debug!(
                    batch = batch_idx + 1,
                    total = total_batches,
                    "Batch committed"
                );
            }
        }


        info!(entries = entries.len(), "All entries persisted");
        Ok(())
    }

    fn insert_batch(tx: &Transaction, entries: &[FileEntry]) -> Result<()> {
        let mut stmt = tx.prepare_cached(
            "INSERT OR REPLACE INTO files
                (relative_path, absolute_path, size, mtime, extension,
                 is_symlink, content_hash, permissions, inode, device, last_updated)
             VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, datetime('now'))",
        )?;

        for entry in entries {
            stmt.execute(params![
                entry.relative_path.to_string_lossy().to_string(),
                entry.absolute_path.to_string_lossy().to_string(),
                entry.size as i64,
                entry.mtime.to_rfc3339(),
                entry.extension,
                entry.is_symlink as i32,
                entry.content_hash,
                entry.permissions as i64,
                entry.inode as i64,
                entry.device as i64,
            ])?;
        }

        Ok(())
    }

    pub fn record_scan_event(
        &self,
        root: &Path,
        files_total: usize,
        files_hashed: usize,
        duration: Duration,
    ) -> Result<()> {
        self.conn.execute(
            "INSERT INTO scan_events (scan_root, files_total, files_hashed, duration_ms)
             VALUES (?1, ?2, ?3, ?4)",
            params![
                root.to_string_lossy().to_string(),
                files_total as i64,
                files_hashed as i64,
                duration.as_millis() as i64,
            ],
        )?;
        Ok(())
    }

    pub fn get_statistics(&self) -> Result<IndexStatistics> {
        let total_files: u64 = self
            .conn
            .query_row("SELECT COUNT(*) FROM files", [], |row| row.get(0))?;

        let total_size: u64 = self
            .conn
            .query_row("SELECT COALESCE(SUM(size), 0) FROM files", [], |row| {
                row.get(0)
            })?;

        let last_scan: String = self
            .conn
            .query_row(
                "SELECT COALESCE(MAX(started_at), 'never') FROM scan_events",
                [],
                |row| row.get(0),
            )?;

        let scan_count: u64 = self
            .conn
            .query_row("SELECT COUNT(*) FROM scan_events", [], |row| row.get(0))?;

        Ok(IndexStatistics {
            total_files,
            total_size,
            last_scan,
            scan_count,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::Utc;
    use std::path::PathBuf;
    use tempfile::TempDir;

    fn create_test_store() -> (SqliteStore, TempDir) {
        let dir = TempDir::new().unwrap();
        let db_path = dir.path().join("test.db");
        let store = SqliteStore::open(&db_path).unwrap();
        (store, dir)
    }

    fn make_entry(path: &str, size: u64, hash: Option<&str>) -> FileEntry {
        FileEntry {
            relative_path: PathBuf::from(path),
            absolute_path: PathBuf::from(format!("/tmp/project/{}", path)),
            size,
            mtime: Utc::now(),
            extension: Path::new(path)
                .extension()
                .and_then(|e| e.to_str())
                .map(|s| s.to_lowercase()),
            is_symlink: false,
            content_hash: hash.map(|s| s.to_string()),
            permissions: 0o644,
            inode: 12345,
            device: 1,
        }
    }

    #[test]
    fn test_open_creates_schema() {
        let (store, _dir) = create_test_store();
        let count: u64 = store
            .conn
            .query_row(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='files'",
                [],
                |row| row.get(0),
            )
            .unwrap();
        assert_eq!(count, 1);
    }

    #[test]
    fn test_upsert_and_query() {
        let (mut store, _dir) = create_test_store();

        let entries = vec![
            make_entry("data/sample1.fastq.gz", 1024000, Some("abc123")),
            make_entry("results/output.bam", 5000000, Some("def456")),
        ];

        store.upsert_entries(&entries).unwrap();

        let stats = store.get_statistics().unwrap();
        assert_eq!(stats.total_files, 2);
        assert_eq!(stats.total_size, 6024000);
    }

    #[test]
    fn test_incremental_change_detection() {
        let (mut store, _dir) = create_test_store();

        let entries = vec![
            make_entry("file1.txt", 100, Some("hash1")),
            make_entry("file2.txt", 200, Some("hash2")),
        ];

        store.upsert_entries(&entries).unwrap();

        let changed = store.filter_changed_entries(&entries).unwrap();
        assert_eq!(changed.len(), 0, "Unchanged files should not be re-hashed");

        let mut modified_entries = entries.clone();
        modified_entries[0].size = 150;
        let changed = store.filter_changed_entries(&modified_entries).unwrap();
        assert_eq!(changed.len(), 1, "Modified file should be detected");
    }

    #[test]
    fn test_scan_event_recording() {
        let (store, _dir) = create_test_store();

        store
            .record_scan_event(
                Path::new("/tmp/project"),
                1000,
                500,
                Duration::from_secs(5),
            )
            .unwrap();

        let stats = store.get_statistics().unwrap();
        assert_eq!(stats.scan_count, 1);
    }
}