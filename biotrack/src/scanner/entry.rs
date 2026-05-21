use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::path::PathBuf;


#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FileEntry {

    pub relative_path: PathBuf,

    pub absolute_path: PathBuf,

    pub size: u64,

    pub mtime: DateTime<Utc>,

    pub extension: Option<String>,

    pub is_symlink: bool,

    pub content_hash: Option<String>,

    pub permissions: u32,

    pub inode: u64,

    pub device: u64,
}

impl FileEntry {

    pub fn change_key(&self) -> String {
        format!(
            "{}:{}:{}",
            self.relative_path.display(),
            self.size,
            self.mtime.timestamp_nanos_opt().unwrap_or(0)
        )
    }
}

#[derive(Debug, Default)]
pub struct ScanStatistics {
    pub files_found: usize,
    pub dirs_traversed: usize,
    pub symlinks_found: usize,
    pub errors: usize,
    pub total_size: u64,
}