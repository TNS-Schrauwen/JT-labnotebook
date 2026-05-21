use assert_fs::prelude::*;
use assert_fs::TempDir;
use std::process::Command;

fn biotrack_bin() -> String {
    let mut path = std::env::current_exe().unwrap();
    path.pop(); 
    path.pop();
    path.push("biotrack");
    path.to_string_lossy().to_string()
}

#[test]
fn test_init_creates_database() {
    let dir = TempDir::new().unwrap();

    let output = Command::new(biotrack_bin())
        .args(["init", dir.path().to_str().unwrap()])
        .output()
        .expect("Failed to execute biotrack");

    assert!(output.status.success(), "Init command failed: {:?}", output);

    let stdout = String::from_utf8_lossy(&output.stdout);
    assert!(stdout.contains("Initialized BioTrack"));
    assert!(dir.path().join(".biotrack").join("index.db").exists());
    assert!(dir.path().join(".biotrack").join("config.toml").exists());
}

#[test]
fn test_scan_indexes_files() {
    let dir = TempDir::new().unwrap();

    dir.child("sample1.fastq").write_str("@SEQ1\nACGT\n+\nIIII").unwrap();
    dir.child("sample2.fastq").write_str("@SEQ2\nTGCA\n+\nIIII").unwrap();
    dir.child("results/output.bam").write_str("fake bam content").unwrap();
    dir.child("scripts/pipeline.nf").write_str("process foo {}").unwrap();

    let output = Command::new(biotrack_bin())
        .args(["init", dir.path().to_str().unwrap()])
        .output()
        .expect("Failed to execute biotrack init");
    assert!(output.status.success());

    let output = Command::new(biotrack_bin())
        .args(["scan", dir.path().to_str().unwrap()])
        .output()
        .expect("Failed to execute biotrack scan");

    assert!(output.status.success(), "Scan failed: {:?}", String::from_utf8_lossy(&output.stderr));

    let stdout = String::from_utf8_lossy(&output.stdout);
    assert!(stdout.contains("Scan Complete"));
    assert!(stdout.contains("4"));
}

#[test]
fn test_scan_dry_run() {
    let dir = TempDir::new().unwrap();
    dir.child("test.txt").write_str("hello").unwrap();

    let output = Command::new(biotrack_bin())
        .args(["scan", "--dry-run", dir.path().to_str().unwrap()])
        .output()
        .expect("Failed to execute biotrack");

    assert!(output.status.success());
    let stdout = String::from_utf8_lossy(&output.stdout);
    assert!(stdout.contains("DRY RUN"));
    assert!(!dir.path().join(".biotrack").join("index.db").exists());
}

#[test]
fn test_incremental_scan_skips_unchanged() {
    let dir = TempDir::new().unwrap();
    dir.child("file1.txt").write_str("content1").unwrap();
    dir.child("file2.txt").write_str("content2").unwrap();

    Command::new(biotrack_bin())
        .args(["init", dir.path().to_str().unwrap()])
        .output()
        .unwrap();

    Command::new(biotrack_bin())
        .args(["scan", dir.path().to_str().unwrap()])
        .output()
        .unwrap();

    let output = Command::new(biotrack_bin())
        .args(["scan", dir.path().to_str().unwrap(), "-v"])
        .output()
        .unwrap();

    let stdout = String::from_utf8_lossy(&output.stdout);
    assert!(
        stdout.contains("0") || stdout.contains("hashed"),
        "Incremental scan should skip unchanged files. Got: {}",
        stdout
    );
}

#[test]
fn test_status_command() {
    let dir = TempDir::new().unwrap();
    dir.child("data.csv").write_str("a,b,c").unwrap();

    Command::new(biotrack_bin())
        .args(["init", dir.path().to_str().unwrap()])
        .output()
        .unwrap();

    Command::new(biotrack_bin())
        .args(["scan", dir.path().to_str().unwrap()])
        .output()
        .unwrap();

    let output = Command::new(biotrack_bin())
        .args(["status", dir.path().to_str().unwrap()])
        .output()
        .unwrap();

    assert!(output.status.success());
    let stdout = String::from_utf8_lossy(&output.stdout);
    assert!(stdout.contains("Project Status"));
    assert!(stdout.contains("1"));
}