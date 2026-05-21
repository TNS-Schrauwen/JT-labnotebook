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
fn test_tree_command_basic() {
    let dir = TempDir::new().unwrap();

    dir.child("raw/sample1_R1.fastq.gz").write_str("@SEQ1\nACGT\n+\nIIII").unwrap();
    dir.child("raw/sample1_R2.fastq.gz").write_str("@SEQ1\nTGCA\n+\nIIII").unwrap();
    dir.child("aligned/sample1.bam").write_str("fake bam").unwrap();
    dir.child("aligned/sample1.bam.bai").write_str("fake bai").unwrap();
    dir.child("variants/sample1.vcf").write_str("##fileformat=VCFv4.2").unwrap();
    dir.child("scripts/pipeline.nf").write_str("process foo {}").unwrap();
    dir.child("README.md").write_str("# My Project").unwrap();

    let output = Command::new(biotrack_bin())
        .args(["tree", dir.path().to_str().unwrap(), "--classify"])
        .output()
        .expect("Failed to execute biotrack tree");

    assert!(output.status.success(), "Tree command failed: {:?}", String::from_utf8_lossy(&output.stderr));

    let stdout = String::from_utf8_lossy(&output.stdout);

    assert!(stdout.contains("Project Tree"), "Should show tree header");
    assert!(stdout.contains("raw"), "Should show raw directory");
    assert!(stdout.contains("aligned"), "Should show aligned directory");
    assert!(stdout.contains("variants"), "Should show variants directory");
    assert!(stdout.contains("Files:"), "Should show file count");
    assert!(stdout.contains("Directories:"), "Should show directory count");
}

#[test]
fn test_tree_with_depth_limit() {
    let dir = TempDir::new().unwrap();

    dir.child("a/b/c/deep_file.txt").write_str("deep").unwrap();
    dir.child("top_file.txt").write_str("top").unwrap();

    let output = Command::new(biotrack_bin())
        .args(["tree", dir.path().to_str().unwrap(), "-d", "1"])
        .output()
        .expect("Failed to execute biotrack tree");

    assert!(output.status.success());
    let stdout = String::from_utf8_lossy(&output.stdout);

    assert!(stdout.contains("top_file.txt"), "Should show top-level file");
}

#[test]
fn test_tree_classification_display() {
    let dir = TempDir::new().unwrap();

    dir.child("data/reads.fastq").write_str("@SEQ\nACGT\n+\nIIII").unwrap();
    dir.child("results/output.bam").write_str("fake bam").unwrap();
    dir.child("scripts/analyze.py").write_str("import os").unwrap();

    let output = Command::new(biotrack_bin())
        .args(["tree", dir.path().to_str().unwrap(), "--classify"])
        .output()
        .expect("Failed to execute biotrack tree");

    assert!(output.status.success());
    let stdout = String::from_utf8_lossy(&output.stdout);

    assert!(stdout.contains("File Classification"), "Should show classification summary");
}

#[test]
fn test_tree_relationship_inference() {
    let dir = TempDir::new().unwrap();

    dir.child("raw/sample1_R1.fastq").write_str("@SEQ1\nACGT\n+\nIIII").unwrap();
    dir.child("raw/sample1_R2.fastq").write_str("@SEQ2\nTGCA\n+\nIIII").unwrap();

    let output = Command::new(biotrack_bin())
        .args(["tree", dir.path().to_str().unwrap(), "--classify"])
        .output()
        .expect("Failed to execute biotrack tree");

    assert!(output.status.success());
    let stdout = String::from_utf8_lossy(&output.stdout);

    assert!(
        stdout.contains("Inferred Relationships") || stdout.contains("Paired"),
        "Should detect paired-end reads. Output: {}",
        stdout
    );
}