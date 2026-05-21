use crate::config::settings::Settings;
use crate::scanner::entry::FileEntry;
use anyhow::Result;
use indicatif::ProgressBar;
use rayon::prelude::*;
use std::fs::File;
use std::io::Read;
use tracing::{debug, trace, warn};

pub fn hash_entries_parallel(
    entries: &[FileEntry],
    progress: &ProgressBar,
    settings: &Settings,
) -> Result<Vec<FileEntry>> {
    let max_size = settings.hash.max_file_size;
    let buffer_size = settings.hash.buffer_size;
    let thread_count = settings.effective_hash_threads();

    debug!(
        entries = entries.len(),
        threads = thread_count,
        max_size_bytes = max_size,
        buffer_size = buffer_size,
        "Starting parallel hashing"
    );


    let pool = rayon::ThreadPoolBuilder::new()
        .num_threads(thread_count)
        .build()?;

    let results: Vec<FileEntry> = pool.install(|| {
        entries
            .par_iter()
            .map(|entry| {
                let mut hashed_entry = entry.clone();

                if entry.size > max_size {

                    trace!(
                        path = %entry.relative_path.display(),
                        size = entry.size,
                        "Skipping hash for oversized file"
                    );
                    hashed_entry.content_hash = None;
                } else if entry.size == 0 {

                    hashed_entry.content_hash =
                        Some(blake3::hash(b"").to_hex().to_string());
                } else {
                    match hash_file(&entry.absolute_path, buffer_size) {
                        Ok(hash) => {
                            hashed_entry.content_hash = Some(hash);
                        }
                        Err(e) => {
                            warn!(
                                path = %entry.absolute_path.display(),
                                error = %e,
                                "Failed to hash file"
                            );
                            hashed_entry.content_hash = None;
                        }
                    }
                }

                progress.inc(1);
                hashed_entry
            })
            .collect()
    });

    Ok(results)
}


fn hash_file(path: &std::path::Path, buffer_size: usize) -> Result<String> {
    let mut file = File::open(path)?;
    let mut hasher = blake3::Hasher::new();
    let mut buffer = vec![0u8; buffer_size];

    loop {
        let bytes_read = file.read(&mut buffer)?;
        if bytes_read == 0 {
            break;
        }
        hasher.update(&buffer[..bytes_read]);
    }

    let hash = hasher.finalize();
    Ok(hash.to_hex().to_string())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;
    use tempfile::NamedTempFile;

    #[test]
    fn test_hash_empty_file() {
        let file = NamedTempFile::new().unwrap();
        let result = hash_file(file.path(), 4096).unwrap();

        let expected = blake3::hash(b"").to_hex().to_string();
        assert_eq!(result, expected);
    }

    #[test]
    fn test_hash_known_content() {
        let mut file = NamedTempFile::new().unwrap();
        file.write_all(b"hello world").unwrap();
        file.flush().unwrap();

        let result = hash_file(file.path(), 4096).unwrap();
        let expected = blake3::hash(b"hello world").to_hex().to_string();
        assert_eq!(result, expected);
    }

    #[test]
    fn test_hash_deterministic() {
        let mut file = NamedTempFile::new().unwrap();
        let data = vec![42u8; 1024 * 1024]; 
        file.write_all(&data).unwrap();
        file.flush().unwrap();

        let hash1 = hash_file(file.path(), 4096).unwrap();
        let hash2 = hash_file(file.path(), 8192).unwrap(); 
        assert_eq!(hash1, hash2, "Hash must be deterministic regardless of buffer size");
    }
}