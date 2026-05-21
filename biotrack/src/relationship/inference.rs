use crate::classifier::extension_map::FileCategory;
use crate::classifier::pipeline_stage::PipelineStage;
use crate::relationship::types::{FileRelationship, RelationshipType};
use crate::tree::arena::{DirectoryTree, FileMetadata, NodeKind, TreeNode};
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use tracing::debug;


pub fn infer_relationships(tree: &DirectoryTree) -> Vec<FileRelationship> {
    let mut relationships = Vec::new();

    debug!("Starting relationship inference");


    relationships.extend(detect_index_pairs(tree));

    relationships.extend(detect_paired_reads(tree));

    relationships.extend(detect_sample_lineage(tree));

    relationships.extend(detect_duplicates(tree));

    relationships.sort_by(|a, b| b.confidence.partial_cmp(&a.confidence).unwrap());

    debug!(
        count = relationships.len(),
        "Relationship inference complete"
    );

    relationships
}


fn detect_index_pairs(tree: &DirectoryTree) -> Vec<FileRelationship> {
    let mut results = Vec::new();

    let index_mappings: &[(&str, &[&str])] = &[
        ("bai", &["bam"]),
        ("csi", &["bam", "vcf"]),
        ("tbi", &["vcf", "bed"]),
        ("fai", &["fa", "fasta", "fna"]),
        ("idx", &["bam", "fa"]),
    ];

    let mut dir_files: HashMap<PathBuf, Vec<&TreeNode>> = HashMap::new();
    for node in tree.iter_files() {
        let dir = node.relative_path.parent().unwrap_or(Path::new("")).to_path_buf();
        dir_files.entry(dir).or_default().push(node);
    }

    for (_dir, files) in &dir_files {
        for file in files {
            if let NodeKind::File(meta) = &file.kind {
                if meta.classification.category != FileCategory::Index {
                    continue;
                }

                let ext = meta.extension.as_deref().unwrap_or("");

                for (idx_ext, data_exts) in index_mappings {
                    if ext != *idx_ext {
                        continue;
                    }

                    let stem = file.relative_path.file_stem()
                        .and_then(|s| s.to_str())
                        .unwrap_or("");

                    for sibling in files {
                        if std::ptr::eq(*sibling, *file) {
                            continue;
                        }
                        if let NodeKind::File(sib_meta) = &sibling.kind {
                            let sib_ext = sib_meta.extension.as_deref().unwrap_or("");
                            let sib_stem = sibling.relative_path.file_stem()
                                .and_then(|s| s.to_str())
                                .unwrap_or("");

                            if data_exts.contains(&sib_ext) && (sib_stem == stem || sibling.name.starts_with(stem)) {
                                results.push(FileRelationship {
                                    source: file.relative_path.clone(),
                                    target: sibling.relative_path.clone(),
                                    relationship_type: RelationshipType::IndexOf,
                                    confidence: 0.95,
                                    reason: format!(".{} indexes .{}", idx_ext, sib_ext),
                                });
                            }
                        }
                    }
                }
            }
        }
    }

    results
}

fn detect_paired_reads(tree: &DirectoryTree) -> Vec<FileRelationship> {
    let mut results = Vec::new();

    let raw_files: Vec<&TreeNode> = tree
        .iter_files()
        .filter(|n| {
            if let NodeKind::File(meta) = &n.kind {
                meta.classification.category == FileCategory::RawSequencing
            } else {
                false
            }
        })
        .collect();

    let mut dir_groups: HashMap<PathBuf, Vec<&TreeNode>> = HashMap::new();
    for file in &raw_files {
        let dir = file.relative_path.parent().unwrap_or(Path::new("")).to_path_buf();
        dir_groups.entry(dir).or_default().push(file);
    }

    for (_dir, files) in &dir_groups {
        let mut seen_pairs: std::collections::HashSet<String> = std::collections::HashSet::new();

        for file in files {
            let name = &file.name;

            let pair_name = if name.contains("_R1") {
                Some(name.replace("_R1", "_R2"))
            } else if name.contains("_R2") {
                Some(name.replace("_R2", "_R1"))
            } else if name.contains("_1.") {
                Some(name.replacen("_1.", "_2.", 1))
            } else if name.contains("_2.") {
                Some(name.replacen("_2.", "_1.", 1))
            } else {
                None
            };

            if let Some(pair) = pair_name {

                let pair_key = if file.name < pair {
                    format!("{}:{}", file.name, pair)
                } else {
                    format!("{}:{}", pair, file.name)
                };

                if seen_pairs.contains(&pair_key) {
                    continue;
                }

                for other in files {
                    if other.name == pair {
                        results.push(FileRelationship {
                            source: file.relative_path.clone(),
                            target: other.relative_path.clone(),
                            relationship_type: RelationshipType::PairedWith,
                            confidence: 0.98,
                            reason: "Paired-end reads (R1/R2)".to_string(),
                        });
                        seen_pairs.insert(pair_key);
                        break;
                    }
                }
            }
        }
    }

    results
}

fn detect_sample_lineage(tree: &DirectoryTree) -> Vec<FileRelationship> {
    let mut results = Vec::new();


    let mut sample_groups: HashMap<String, Vec<&TreeNode>> = HashMap::new();
    for node in tree.iter_files() {
        if let NodeKind::File(meta) = &node.kind {
            if let Some(sample) = &meta.sample_name {
                sample_groups
                    .entry(sample.clone())
                    .or_default()
                    .push(node);
            }
        }
    }


    for (sample, files) in &sample_groups {
        if files.len() < 2 {
            continue;
        }


        let mut staged_files: Vec<(&TreeNode, PipelineStage)> = files
            .iter()
            .filter_map(|f| {
                if let NodeKind::File(meta) = &f.kind {
                    meta.pipeline_stage.map(|stage| (*f, stage))
                } else {
                    None
                }
            })
            .collect();

        staged_files.sort_by_key(|(_, stage)| *stage);

        for window in staged_files.windows(2) {
            let (earlier_file, earlier_stage) = &window[0];
            let (later_file, later_stage) = &window[1];

            if earlier_stage < later_stage {
                results.push(FileRelationship {
                    source: later_file.relative_path.clone(),
                    target: earlier_file.relative_path.clone(),
                    relationship_type: RelationshipType::DerivedFrom,
                    confidence: 0.7,
                    reason: format!(
                        "Sample '{}': {} → {}",
                        sample, earlier_stage, later_stage
                    ),
                });
            }
        }

        for pair in files.windows(2) {
            results.push(FileRelationship {
                source: pair[0].relative_path.clone(),
                target: pair[1].relative_path.clone(),
                relationship_type: RelationshipType::SameSample,
                confidence: 0.6,
                reason: format!("Same sample: {}", sample),
            });
        }
    }

    results
}


fn detect_duplicates(tree: &DirectoryTree) -> Vec<FileRelationship> {
    let duplicates = tree.find_duplicates();
    let mut results = Vec::new();

    for group in duplicates {

        for i in 0..group.len() {
            for j in (i + 1)..group.len() {
                results.push(FileRelationship {
                    source: group[i].relative_path.clone(),
                    target: group[j].relative_path.clone(),
                    relationship_type: RelationshipType::DuplicateOf,
                    confidence: 1.0,
                    reason: "Identical content hash".to_string(),
                });
            }
        }
    }

    results
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::scanner::entry::FileEntry;
    use crate::tree::builder::TreeBuilder;
    use chrono::Utc;

    fn make_entry(path: &str, size: u64, hash: Option<&str>) -> FileEntry {
        FileEntry {
            relative_path: PathBuf::from(path),
            absolute_path: PathBuf::from(format!("/project/{}", path)),
            size,
            mtime: Utc::now(),
            extension: Path::new(path)
                .extension()
                .and_then(|e| e.to_str())
                .map(|s| s.to_lowercase()),
            is_symlink: false,
            content_hash: hash.map(|s| s.to_string()),
            permissions: 0o644,
            inode: 1,
            device: 1,
        }
    }

    #[test]
    fn test_detect_index_pairs() {
        let entries = vec![
            make_entry("aligned/sample1.bam", 5000, None),
            make_entry("aligned/sample1.bam.bai", 100, None),
        ];

        let tree = TreeBuilder::build_from_entries(Path::new("/project"), &entries);
        let rels = detect_index_pairs(&tree);

        assert!(
            rels.iter().any(|r| r.relationship_type == RelationshipType::IndexOf),
            "Should detect BAM/BAI pair"
        );
    }

    #[test]
    fn test_detect_paired_reads() {
        let entries = vec![
            make_entry("raw/sample1_R1.fastq", 1000, None),
            make_entry("raw/sample1_R2.fastq", 1000, None),
        ];

        let tree = TreeBuilder::build_from_entries(Path::new("/project"), &entries);
        let rels = detect_paired_reads(&tree);

        assert_eq!(rels.len(), 1);
        assert_eq!(rels[0].relationship_type, RelationshipType::PairedWith);
    }

    #[test]
    fn test_detect_duplicates() {
        let entries = vec![
            make_entry("data/copy1.txt", 100, Some("abc123")),
            make_entry("backup/copy2.txt", 100, Some("abc123")),
        ];

        let tree = TreeBuilder::build_from_entries(Path::new("/project"), &entries);
        let rels = detect_duplicates(&tree);

        assert_eq!(rels.len(), 1);
        assert_eq!(rels[0].relationship_type, RelationshipType::DuplicateOf);
        assert_eq!(rels[0].confidence, 1.0);
    }
}