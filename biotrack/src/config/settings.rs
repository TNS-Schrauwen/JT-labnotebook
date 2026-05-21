use anyhow::Result;
use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};
use tracing::info;


#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Settings {
    pub scan: ScanSettings,
    pub hash: HashSettings,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ScanSettings {

    pub ignore_patterns: Vec<String>,

    pub max_depth: usize,

    pub follow_symlinks: bool,

    pub include_hidden: bool,

    pub threads: usize,

    pub max_entries_per_dir: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HashSettings {

    pub max_file_size: u64,

    pub threads: usize,

    pub buffer_size: usize,
}

impl Default for Settings {
    fn default() -> Self {
        Self {
            scan: ScanSettings {
                ignore_patterns: vec![

                    ".git".to_string(),
                    ".biotrack".to_string(),
                    ".snakemake".to_string(),
                    ".nextflow".to_string(),
                    "work/".to_string(),       
                    ".nextflow.log*".to_string(),
                    "node_modules".to_string(),
                    "__pycache__".to_string(),
                    "*.pyc".to_string(),
                    ".conda".to_string(),
                ],
                max_depth: 0, 
                follow_symlinks: false,
                include_hidden: false,
                threads: 0, 
                max_entries_per_dir: 0,
            },
            hash: HashSettings {
                max_file_size: 2 * 1024 * 1024 * 1024, 
                threads: 0,                             
                buffer_size: 1024 * 1024,           
            },
        }
    }
}

impl Settings {

    pub fn from_file(path: &Path) -> Result<Self> {
        let content = std::fs::read_to_string(path)?;
        let settings: Settings = toml::from_str(&content)?;
        info!(path = %path.display(), "Loaded configuration");
        Ok(settings)
    }

    pub fn default_with_discovery() -> Result<Self> {
        let cwd = std::env::current_dir()?;
        let mut search_dir = Some(cwd.as_path());

        while let Some(dir) = search_dir {
            let config_path = dir.join(".biotrack").join("config.toml");
            if config_path.exists() {
                return Self::from_file(&config_path);
            }
            search_dir = dir.parent();
        }


        Ok(Self::default())
    }


    pub fn effective_scan_threads(&self) -> usize {
        if self.scan.threads == 0 {

            std::thread::available_parallelism()
                .map(|n| n.get().max(2))
                .unwrap_or(4)
        } else {
            self.scan.threads
        }
    }

    pub fn effective_hash_threads(&self) -> usize {
        if self.hash.threads == 0 {
            std::thread::available_parallelism()
                .map(|n| n.get())
                .unwrap_or(4)
        } else {
            self.hash.threads
        }
    }
}