pub mod cli;
pub mod classifier;
pub mod config;
pub mod hasher;
pub mod logging;
pub mod relationship;
pub mod scanner;
pub mod store;
pub mod tree;

use anyhow::Result;
use cli::commands::{Cli, Commands};
use classifier::extension_map::FileClassification;
use config::settings::Settings;
use indicatif::{ProgressBar, ProgressStyle};
use scanner::parallel_walker::ParallelScanner;
use std::path::PathBuf;
use std::time::Instant;
use store::sqlite::SqliteStore;
use tree::builder::TreeBuilder;
use tracing::{info, warn};

/// Main application entry point
pub fn run(cli: Cli) -> Result<()> {
    logging::init(cli.verbose)?;

    match cli.command {
        Commands::Scan {
            path,
            config,
            full,
            dry_run,
        } => {
            let settings = load_settings(config)?;
            execute_scan(path, settings, full, dry_run)?;
        }
        Commands::Status { path, config } => {
            let settings = load_settings(config)?;
            execute_status(path, settings)?;
        }
        Commands::Init { path } => {
            execute_init(path)?;
        }
        Commands::Tree {
            path,
            config,
            max_depth,
            classify,
        } => {
            let settings = load_settings(config)?;
            execute_tree(path, settings, max_depth, classify)?;
        }
    }

    Ok(())
}

fn load_settings(config_path: Option<PathBuf>) -> Result<Settings> {
    match config_path {
        Some(path) => Settings::from_file(&path),
        None => Settings::default_with_discovery(),
    }
}

fn execute_scan(
    path: PathBuf,
    settings: Settings,
    full_rescan: bool,
    dry_run: bool,
) -> Result<()> {
    let start = Instant::now();
    let canonical_path = path.canonicalize().map_err(|e| {
        anyhow::anyhow!(
            "Cannot resolve path '{}': {}. Does the directory exist?",
            path.display(),
            e
        )
    })?;

    info!(
        path = %canonical_path.display(),
        full_rescan = full_rescan,
        "Starting filesystem scan"
    );

    let db_path = canonical_path.join(".biotrack").join("index.db");
    if let Some(parent) = db_path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    let mut store = SqliteStore::open(&db_path)?;

    let scanner = ParallelScanner::new(&settings);

    let progress = ProgressBar::new_spinner();
    progress.set_style(
        ProgressStyle::with_template(
            "{spinner:.green} [{elapsed_precise}] {msg} ({pos} files scanned)",
        )
        .unwrap(),
    );
    progress.set_message("Scanning...");

    let entries = scanner.scan(&canonical_path, &progress)?;
    progress.finish_with_message("Scan complete");

    let scan_duration = start.elapsed();
    info!(
        files_found = entries.len(),
        duration_ms = scan_duration.as_millis(),
        "Directory traversal complete"
    );

    if dry_run {
        println!("\n[DRY RUN] Would index {} files", entries.len());
        println!("Duration: {:.2?}", scan_duration);
        return Ok(());
    }

    let hash_start = Instant::now();
    let entries_to_hash = if full_rescan {
        info!("Full rescan requested - hashing all files");
        entries.clone()
    } else {
        store.filter_changed_entries(&entries)?
    };

    info!(
        total_files = entries.len(),
        files_to_hash = entries_to_hash.len(),
        "Incremental diff computed"
    );

    let progress = ProgressBar::new(entries_to_hash.len() as u64);
    progress.set_style(
        ProgressStyle::with_template(
            "{spinner:.cyan} [{elapsed_precise}] [{bar:40.cyan/blue}] {pos}/{len} hashing ({eta})",
        )
        .unwrap()
        .progress_chars("█▓░"),
    );

    let hashed_entries =
        hasher::blake3::hash_entries_parallel(&entries_to_hash, &progress, &settings)?;
    progress.finish_with_message("Hashing complete");

    let hash_duration = hash_start.elapsed();
    info!(
        hashed_count = hashed_entries.len(),
        duration_ms = hash_duration.as_millis(),
        "Hashing complete"
    );

    let persist_start = Instant::now();
    store.upsert_entries(&hashed_entries)?;
    store.record_scan_event(
        &canonical_path,
        entries.len(),
        hashed_entries.len(),
        scan_duration + hash_duration,
    )?;
    let persist_duration = persist_start.elapsed();

    let total_size: u64 = entries.iter().map(|e| e.size).sum();
    println!("\n╔══════════════════════════════════════════╗");
    println!("║       BioTrack Scan Complete             ║");
    println!("╠══════════════════════════════════════════╣");
    println!("║ Files indexed:    {:>20} ║", entries.len());
    println!("║ Files hashed:     {:>20} ║", hashed_entries.len());
    println!(
        "║ Total size:       {:>20} ║",
        humansize::format_size(total_size, humansize::BINARY)
    );
    println!("║ Scan time:        {:>20.2?} ║", scan_duration);
    println!("║ Hash time:        {:>20.2?} ║", hash_duration);
    println!("║ Persist time:     {:>20.2?} ║", persist_duration);
    println!("║ Total time:       {:>20.2?} ║", start.elapsed());
    println!("╚══════════════════════════════════════════╝");

    Ok(())
}

fn execute_status(path: PathBuf, _settings: Settings) -> Result<()> {
    let canonical_path = path.canonicalize()?;
    let db_path = canonical_path.join(".biotrack").join("index.db");

    if !db_path.exists() {
        println!("No BioTrack index found at {}", canonical_path.display());
        println!("Run `biotrack init {}` first.", canonical_path.display());
        return Ok(());
    }

    let store = SqliteStore::open(&db_path)?;
    let stats = store.get_statistics()?;

    println!("\n╔══════════════════════════════════════════╗");
    println!("║       BioTrack Project Status            ║");
    println!("╠══════════════════════════════════════════╣");
    println!("║ Project root:     {}", canonical_path.display());
    println!("║ Total files:      {:>20} ║", stats.total_files);
    println!(
        "║ Total size:       {:>20} ║",
        humansize::format_size(stats.total_size, humansize::BINARY)
    );
    println!("║ Last scan:        {:>20} ║", stats.last_scan);
    println!("║ Scan count:       {:>20} ║", stats.scan_count);
    println!("╚══════════════════════════════════════════╝");

    Ok(())
}

fn execute_init(path: PathBuf) -> Result<()> {
    let canonical_path = path.canonicalize().unwrap_or_else(|_| {
        std::fs::create_dir_all(&path).ok();
        path.canonicalize().unwrap_or(path.clone())
    });

    let biotrack_dir = canonical_path.join(".biotrack");
    std::fs::create_dir_all(&biotrack_dir)?;

    let db_path = biotrack_dir.join("index.db");
    let _store = SqliteStore::open(&db_path)?;

    let config_path = biotrack_dir.join("config.toml");
    if !config_path.exists() {
        let default_config = Settings::default();
        let toml_str = toml::to_string_pretty(&default_config)?;
        std::fs::write(&config_path, toml_str)?;
    }

    println!(
        "✓ Initialized BioTrack project at {}",
        canonical_path.display()
    );
    println!("  Database: {}", db_path.display());
    println!("  Config:   {}", config_path.display());
    println!(
        "\nRun `biotrack scan {}` to index files.",
        canonical_path.display()
    );

    Ok(())
}

/// Execute the tree command — build and display the directory tree
fn execute_tree(
    path: PathBuf,
    settings: Settings,
    max_depth: Option<usize>,
    classify: bool,
) -> Result<()> {
    let start = Instant::now();
    let canonical_path = path.canonicalize().map_err(|e| {
        anyhow::anyhow!(
            "Cannot resolve path '{}': {}. Does the directory exist?",
            path.display(),
            e
        )
    })?;

    info!(path = %canonical_path.display(), "Building directory tree");

    // Scan filesystem
    let scanner = ParallelScanner::new(&settings);
    let progress = ProgressBar::hidden();
    let entries = scanner.scan(&canonical_path, &progress)?;

    // Build tree
    let tree = TreeBuilder::build_from_entries(&canonical_path, &entries);

    let tree_duration = start.elapsed();

    // Display tree
    println!(
        "\n🌲 Project Tree: {}",
        canonical_path.display()
    );
    println!("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");

    let display_depth = max_depth.unwrap_or(usize::MAX);
    tree.print_tree(display_depth, classify);

    // Statistics
    let stats = tree.statistics();
    println!("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
    println!("  Directories: {}", stats.total_directories);
    println!("  Files:       {}", stats.total_files);
    println!(
        "  Total size:  {}",
        humansize::format_size(stats.total_size, humansize::BINARY)
    );
    println!("  Max depth:   {}", stats.max_depth);
    println!("  Build time:  {:.2?}", tree_duration);

    if classify {
        println!("\n  📊 File Classification:");
        for (category, count) in &stats.classification_counts {
            println!("    {:20} {:>6}", format!("{:?}", category), count);
        }
    }

    // Relationship inference
    let relationships = relationship::inference::infer_relationships(&tree);
    if !relationships.is_empty() {
        println!("\n  🔗 Inferred Relationships: {}", relationships.len());
        for rel in relationships.iter().take(10) {
            println!("    {}", rel);
        }
        if relationships.len() > 10 {
            println!("    ... and {} more", relationships.len() - 10);
        }
    }

    Ok(())
}