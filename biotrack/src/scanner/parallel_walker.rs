use crate::config::settings::Settings;
use crate::scanner::entry::FileEntry;
use anyhow::Result;
use chrono::{DateTime, Utc};
use ignore::WalkBuilder;
use indicatif::ProgressBar;
use std::os::unix::fs::MetadataExt;
use std::path::Path;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::{Arc, Mutex};
use std::time::SystemTime;
use tracing::{debug, trace, warn};


pub struct ParallelScanner {
    settings: Settings,
}

impl ParallelScanner {
    pub fn new(settings: &Settings) -> Self {
        Self {
            settings: settings.clone(),
        }
    }

    pub fn scan(&self, root: &Path, progress: &ProgressBar) -> Result<Vec<FileEntry>> {
        let entries: Arc<Mutex<Vec<FileEntry>>> = Arc::new(Mutex::new(Vec::new()));
        let error_count = Arc::new(AtomicUsize::new(0));
        let file_count = Arc::new(AtomicUsize::new(0));


        let mut builder = WalkBuilder::new(root);


        let threads = self.settings.effective_scan_threads();
        builder.threads(threads);


        if self.settings.scan.max_depth > 0 {
            builder.max_depth(Some(self.settings.scan.max_depth));
        }


        builder.hidden(!self.settings.scan.include_hidden);


        builder.follow_links(self.settings.scan.follow_symlinks);

        builder.git_ignore(true);
        builder.git_global(true);
        builder.git_exclude(true);


        let mut overrides = ignore::overrides::OverrideBuilder::new(root);
        for pattern in &self.settings.scan.ignore_patterns {

            let ignore_pattern = format!("!{}", pattern);
            overrides.add(&ignore_pattern)?;
        }
        let overrides = overrides.build()?;
        builder.overrides(overrides);

        debug!(
            threads = threads,
            root = %root.display(),
            "Starting parallel directory walk"
        );

        let entries_clone = Arc::clone(&entries);
        let error_count_clone = Arc::clone(&error_count);
        let file_count_clone = Arc::clone(&file_count);
        let root_owned = root.to_path_buf();

        builder.build_parallel().run(|| {
            let entries = Arc::clone(&entries_clone);
            let error_count = Arc::clone(&error_count_clone);
            let file_count = Arc::clone(&file_count_clone);
            let root = root_owned.clone();

            Box::new(move |result| {
                match result {
                    Ok(dir_entry) => {

                        if dir_entry.path() == root {
                            return ignore::WalkState::Continue;
                        }


                        let file_type = match dir_entry.file_type() {
                            Some(ft) => ft,
                            None => return ignore::WalkState::Continue,
                        };

                        if !file_type.is_file() {
                            return ignore::WalkState::Continue;
                        }

                        let metadata = match dir_entry.metadata() {
                            Ok(m) => m,
                            Err(e) => {
                                warn!(
                                    path = %dir_entry.path().display(),
                                    error = %e,
                                    "Failed to read metadata"
                                );
                                error_count.fetch_add(1, Ordering::Relaxed);
                                return ignore::WalkState::Continue;
                            }
                        };

                        let mtime = metadata
                            .modified()
                            .unwrap_or(SystemTime::UNIX_EPOCH);
                        let mtime: DateTime<Utc> = mtime.into();

                        let relative_path = dir_entry
                            .path()
                            .strip_prefix(&root)
                            .unwrap_or(dir_entry.path())
                            .to_path_buf();

                        let extension = dir_entry
                            .path()
                            .extension()
                            .and_then(|e| e.to_str())
                            .map(|e| e.to_lowercase());

                        let entry = FileEntry {
                            relative_path,
                            absolute_path: dir_entry.path().to_path_buf(),
                            size: metadata.len(),
                            mtime,
                            extension,
                            is_symlink: file_type.is_symlink(),
                            content_hash: None, 
                            permissions: metadata.mode(),
                            inode: metadata.ino(),
                            device: metadata.dev(),
                        };

                        trace!(
                            path = %entry.relative_path.display(),
                            size = entry.size,
                            "Discovered file"
                        );

                        let count = file_count.fetch_add(1, Ordering::Relaxed);
                        if count % 1000 == 0 {

                        }

                        entries.lock().unwrap().push(entry);
                    }
                    Err(e) => {
                        warn!(error = %e, "Walk error");
                        error_count.fetch_add(1, Ordering::Relaxed);
                    }
                }

                ignore::WalkState::Continue
            })
        });

        let final_entries = std::mem::take(&mut *entries.lock().unwrap());

        let errors = error_count.load(Ordering::Relaxed);
        if errors > 0 {
            warn!(errors = errors, "Scan completed with errors");
        }

        progress.set_position(final_entries.len() as u64);

        debug!(
            files = final_entries.len(),
            errors = errors,
            "Parallel walk complete"
        );

        Ok(final_entries)
    }
}